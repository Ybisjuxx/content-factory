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


def test_word_by_word_single_word_pop_mode():
    generator = SubtitleGenerator()
    segments = [
        {
            "id": 0,
            "start": 1.0,
            "end": 2.5,
            "text": "Viral hook text",
            "words": [
                {"word": "Viral", "start": 1.0, "end": 1.4},
                {"word": "hook", "start": 1.4, "end": 1.8},
                {"word": "text", "start": 1.8, "end": 2.4},
            ]
        }
    ]

    ass_path = generator.generate_ass_from_segments(
        transcript_segments=segments,
        output_filename="test_word_by_word.ass",
        sync_mode="word_by_word",
        highlight_color="#FFFF00"
    )

    assert Path(ass_path).exists()
    with open(ass_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.startswith("Dialogue:")]

    assert len(lines) == 3
    # In word_by_word mode, each line contains ONLY that specific word
    assert "VIRAL" in lines[0] and "HOOK" not in lines[0] and "TEXT" not in lines[0]
    assert "HOOK" in lines[1] and "VIRAL" not in lines[1] and "TEXT" not in lines[1]
    assert "TEXT" in lines[2] and "VIRAL" not in lines[2] and "HOOK" not in lines[2]


def test_cumulative_progressive_reveal_mode():
    generator = SubtitleGenerator()
    segments = [
        {
            "id": 0,
            "start": 0.0,
            "end": 2.0,
            "text": "Aprende esto hoy",
            "words": [
                {"word": "Aprende", "start": 0.0, "end": 0.6},
                {"word": "esto", "start": 0.6, "end": 1.2},
                {"word": "hoy", "start": 1.2, "end": 1.8},
            ]
        }
    ]

    ass_path = generator.generate_ass_from_segments(
        transcript_segments=segments,
        output_filename="test_cumulative.ass",
        sync_mode="cumulative",
        highlight_color="#00FFFF",
        primary_color="#FFFFFF"
    )

    with open(ass_path, "r", encoding="utf-8") as f:
        dialogues = [line.strip() for line in f if line.startswith("Dialogue:")]

    assert len(dialogues) == 3
    # Line 1: Only "APRENDE"
    assert "APRENDE" in dialogues[0]
    assert "ESTO" not in dialogues[0]
    assert "HOY" not in dialogues[0]

    # Line 2: "APRENDE" (primary) + "ESTO" (highlighted)
    assert "APRENDE" in dialogues[1]
    assert "ESTO" in dialogues[1]
    assert "HOY" not in dialogues[1]

    # Line 3: All 3 words appear
    assert "APRENDE" in dialogues[2]
    assert "ESTO" in dialogues[2]
    assert "HOY" in dialogues[2]


def test_karaoke_full_phrase_mode():
    generator = SubtitleGenerator()
    segments = [
        {
            "id": 0,
            "start": 0.0,
            "end": 2.0,
            "text": "Uno dos tres",
            "words": [
                {"word": "Uno", "start": 0.0, "end": 0.5},
                {"word": "dos", "start": 0.5, "end": 1.0},
                {"word": "tres", "start": 1.0, "end": 1.5},
            ]
        }
    ]

    ass_path = generator.generate_ass_from_segments(
        transcript_segments=segments,
        output_filename="test_karaoke.ass",
        sync_mode="karaoke",
        max_words_per_group=3
    )

    with open(ass_path, "r", encoding="utf-8") as f:
        dialogues = [line.strip() for line in f if line.startswith("Dialogue:")]

    assert len(dialogues) == 3
    # In karaoke mode, all lines have all 3 words visible from the beginning
    for d in dialogues:
        assert "UNO" in d
        assert "DOS" in d
        assert "TRES" in d

