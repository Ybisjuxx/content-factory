import logging
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from app.models.job import EditSegment

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Generates kinetic ASS (Advanced SubStation Alpha) subtitles with word-level highlighting for 9:16 vertical videos."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.CACHE_DIR / "subtitles"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_kinetic_ass(
        self,
        transcript_segments: List[Dict[str, Any]],
        edl: List[EditSegment],
        output_filename: str = "subtitles.ass",
        max_words_per_group: int = 4
    ) -> str:
        """Converts Whisper word-level timestamps, maps them to the pruned video timeline, and generates a kinetic ASS subtitle file."""
        output_path = self.output_dir / output_filename

        # Step 1: Map words to concatenated timeline
        mapped_words = self._map_words_to_timeline(transcript_segments, edl)
        if not mapped_words:
            logger.warning("No words retained in kept segments for subtitles.")
            # Create an empty but valid ASS file
            self._write_ass_file(output_path, [])
            return str(output_path.resolve())

        # Step 2: Group words into punchy short phrases (2-4 words per screen)
        word_groups = self._group_words(mapped_words, max_words=max_words_per_group)

        # Step 3: Generate dialogue events with per-word karaoke highlighting
        dialogue_events = self._create_highlight_dialogues(word_groups)

        # Step 4: Write ASS file
        self._write_ass_file(output_path, dialogue_events)
        logger.info(f"Generated kinetic ASS subtitles with {len(dialogue_events)} events at: {output_path}")
        return str(output_path.resolve())

    def _map_words_to_timeline(
        self, transcript_segments: List[Dict[str, Any]], edl: List[EditSegment]
    ) -> List[Dict[str, Any]]:
        """Maps word timestamps from raw video time to spliced timeline according to the EDL."""
        kept_spans = [seg for seg in edl if seg.keep]
        if not kept_spans:
            return []

        # Build timeline offset mapping: for each kept span, where does it start in the output video?
        span_mappings = []
        accumulated_out_time = 0.0
        for seg in kept_spans:
            duration = seg.end - seg.start
            span_mappings.append({
                "orig_start": seg.start,
                "orig_end": seg.end,
                "out_start": accumulated_out_time,
                "out_end": accumulated_out_time + duration
            })
            accumulated_out_time += duration

        # Flatten all words from Whisper
        raw_words = []
        for s in transcript_segments:
            for w in s.get("words", []):
                raw_words.append(w)

        # Map each word to output timeline
        mapped_words = []
        for w in raw_words:
            w_start = w["start"]
            w_end = w["end"]
            w_text = w["word"].strip()
            if not w_text:
                continue

            for span in span_mappings:
                # Check if word falls inside this kept span
                if w_start >= span["orig_start"] - 0.05 and w_end <= span["orig_end"] + 0.05:
                    offset = span["out_start"] - span["orig_start"]
                    mapped_words.append({
                        "word": w_text.upper(),
                        "start": max(0.0, round(w_start + offset, 3)),
                        "end": max(0.0, round(w_end + offset, 3)),
                    })
                    break

        return mapped_words

    def _group_words(
        self, words: List[Dict[str, Any]], max_words: int = 4
    ) -> List[List[Dict[str, Any]]]:
        """Groups words into concise 2-4 word bursts for rapid, punchy vertical short display."""
        groups = []
        current_group = []

        for i, word in enumerate(words):
            current_group.append(word)

            is_punctuation_break = any(word["word"].endswith(p) for p in [".", "!", "?", ","])
            is_max_length = len(current_group) >= max_words
            is_pause_after = False

            if i < len(words) - 1:
                gap = words[i + 1]["start"] - word["end"]
                if gap > 0.4:
                    is_pause_after = True

            if is_max_length or is_punctuation_break or is_pause_after:
                groups.append(current_group)
                current_group = []

        if current_group:
            groups.append(current_group)

        return groups

    def _create_highlight_dialogues(
        self, word_groups: List[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """For each word in a group, generates an active highlight state where that word is highlighted in neon color."""
        events = []

        for group in word_groups:
            if not group:
                continue

            for active_idx, target_word in enumerate(group):
                start_time = target_word["start"]
                end_time = target_word["end"]

                # Ensure minimum visible duration for each word (e.g. 150ms)
                if end_time <= start_time:
                    end_time = start_time + 0.15

                # Build styled line: highlight target word in yellow/cyan, others white
                line_parts = []
                for idx, w in enumerate(group):
                    if idx == active_idx:
                        # Highlight active word with scale bump and vibrant yellow color
                        line_parts.append(f"{{\\c{settings.SUBTITLE_HIGHLIGHT_COLOR}\\fscx110\\fscy110}}{w['word']}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c{settings.SUBTITLE_PRIMARY_COLOR}}}{w['word']}{{\\r}}")

                formatted_text = " ".join(line_parts)
                events.append({
                    "start": self._format_ass_time(start_time),
                    "end": self._format_ass_time(end_time),
                    "text": formatted_text
                })

        return events

    def _format_ass_time(self, seconds: float) -> str:
        """Formats seconds into ASS timestamp: H:MM:SS.cs"""
        total_cs = int(round(seconds * 100))
        hours = total_cs // 360000
        rem = total_cs % 360000
        mins = rem // 6000
        rem = rem % 6000
        secs = rem // 100
        cs = rem % 100
        return f"{hours}:{mins:02d}:{secs:02d}.{cs:02d}"

    def _write_ass_file(self, filepath: Path, events: List[Dict[str, Any]]) -> None:
        """Writes the full ASS subtitle file with vertical 9:16 safe area styles."""
        ass_header = f"""[Script Info]
Title: Autonomous Video Factory Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: {settings.TARGET_WIDTH}
PlayResY: {settings.TARGET_HEIGHT}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{settings.SUBTITLE_FONT_NAME},{settings.SUBTITLE_FONT_SIZE},{settings.SUBTITLE_PRIMARY_COLOR},{settings.SUBTITLE_HIGHLIGHT_COLOR},{settings.SUBTITLE_OUTLINE_COLOR},{settings.SUBTITLE_BACK_COLOR},-1,0,0,0,100,100,2,0,1,6,3,2,40,40,{settings.SUBTITLE_BOTTOM_MARGIN},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(ass_header)
            for ev in events:
                f.write(f"Dialogue: 0,{ev['start']},{ev['end']},Default,,0,0,0,,{ev['text']}\n")
