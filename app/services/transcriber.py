import os
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Forward-compatibility patch for PyAV >= 14 where metadata_errors was deprecated/removed
try:
    import av
    _orig_av_open = av.open
    def _patched_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _patched_av_open
except Exception:
    pass

from app.config import settings

logger = logging.getLogger(__name__)


class LocalTranscriber:
    """100% Local speech-to-text engine using faster-whisper (CTranslate2).

    Features:
    - Runs on CPU or CUDA locally.
    - int8 quantization for high throughput and low memory footprint.
    - Silero VAD (Voice Activity Detection) filter enabled.
    - Extracts precise word-level timestamps for kinetic subtitle highlighting.
    """

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ):
        self.model_size = model_size or settings.WHISPER_MODEL_SIZE
        self.device = device or settings.WHISPER_DEVICE
        self.compute_type = compute_type or settings.WHISPER_COMPUTE_TYPE
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            logger.info(
                f"Loading faster-whisper model '{self.model_size}' on {self.device} ({self.compute_type})..."
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=str(settings.CACHE_DIR / "whisper_models"),
            )
        return self._model

    def extract_audio(self, video_path: str, output_audio_path: Optional[str] = None) -> str:
        """Extracts 16kHz mono PCM audio from video for optimal Whisper accuracy."""
        video_p = Path(video_path)
        if not video_p.exists():
            raise FileNotFoundError(f"Input video file not found: {video_path}")

        if not output_audio_path:
            output_audio_path = str(settings.CACHE_DIR / f"{video_p.stem}_extracted.wav")

        ffmpeg_bin = settings.resolve_ffmpeg_path()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(video_p),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_audio_path)
        ]
        logger.info(f"Extracting audio using FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg audio extraction error: {result.stderr}")
            raise RuntimeError(f"Audio extraction failed: {result.stderr}")

        return output_audio_path

    def transcribe(
        self,
        media_path: str,
        language: Optional[str] = None,
        word_timestamps: bool = True,
    ) -> Dict[str, Any]:
        """Transcribes media file and returns segments with word-level timestamps."""
        path = Path(media_path)
        if not path.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        # If it's a video file, extract audio first for maximum speed & stability
        if path.suffix.lower() in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
            audio_path = self.extract_audio(str(path))
        else:
            audio_path = str(path)

        model = self._get_model()

        vad_params = dict(
            min_silence_duration_ms=settings.WHISPER_MIN_SILENCE_DURATION_MS
        ) if settings.WHISPER_VAD_FILTER else None

        logger.info(f"Starting faster-whisper transcription for: {audio_path}")
        segments_gen, info = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=word_timestamps,
            vad_filter=settings.WHISPER_VAD_FILTER,
            vad_parameters=vad_params,
        )

        segments_data = []
        full_text_parts = []

        for segment in segments_gen:
            words_data = []
            if segment.words:
                for w in segment.words:
                    words_data.append({
                        "word": w.word.strip(),
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 3)
                    })

            seg_dict = {
                "id": segment.id,
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": segment.text.strip(),
                "words": words_data,
            }
            segments_data.append(seg_dict)
            full_text_parts.append(segment.text.strip())

        result = {
            "media_path": str(media_path),
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 3),
            "full_text": " ".join(full_text_parts),
            "segments": segments_data,
        }
        logger.info(
            f"Transcription complete: {len(segments_data)} segments, detected language: {info.language}"
        )
        return result
