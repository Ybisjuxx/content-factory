import pytest
from pathlib import Path
from app.services.subtitle_generator import SubtitleGenerator
from app.models.job import EditSegment


def test_kinetic_ass_subtitles_mapping():
    generator = SubtitleGenerator()

    # Raw segments with word-level timestamps
    transcript_segments = [
        {
            "id": 0,
            "start": 0.0,
            "end": 2.0,
            "text": "False start line",
            "words": [
                {"word": "False", "start": 0.0, "end": 0.5, "probability": 0.9},
                {"word": "start", "start": 0.5, "end": 1.0, "probability": 0.9},
                {"word": "line", "start": 1.0, "end": 1.8, "probability": 0.9},
            ]
        },
        {
            "id": 1,
            "start": 3.0,
            "end": 6.0,
            "text": "This is kept take",
            "words": [
                {"word": "This", "start": 3.0, "end": 3.6, "probability": 0.95},
                {"word": "is", "start": 3.6, "end": 4.0, "probability": 0.95},
                {"word": "kept", "start": 4.0, "end": 4.8, "probability": 0.95},
                {"word": "take", "start": 4.8, "end": 5.8, "probability": 0.95},
            ]
        }
    ]

    # EDL: prune segment 0, keep segment 1
    edl = [
        EditSegment(start=0.0, end=2.0, keep=False, text="False start line"),
        EditSegment(start=3.0, end=6.0, keep=True, text="This is kept take")
    ]

    ass_path = generator.generate_kinetic_ass(
        transcript_segments=transcript_segments,
        edl=edl,
        output_filename="test_subtitles.ass"
    )

    assert Path(ass_path).exists()
    with open(ass_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify ASS header and 9:16 vertical resolution
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "[Events]" in content

    # Word from segment 0 must NOT be in final subtitles
    assert "FALSE" not in content

    # Words from kept segment must appear with word-level highlight tags
    assert "THIS" in content
    assert "KEPT" in content
    assert "\\c" in content  # Styling tag
