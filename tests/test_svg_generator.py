import pytest
from pathlib import Path
from app.services.svg_generator import ProceduralSvgGenerator


def test_svg_card_generation(tmp_path):
    gen = ProceduralSvgGenerator(output_dir=tmp_path)

    # Test stat card
    stat_path = gen.generate_card(
        card_type="stat",
        title="+350% SPEED",
        content="Optimized CTranslate2 Inference",
        badge="BENCHMARK"
    )
    assert Path(stat_path).exists()
    content = Path(stat_path).read_text(encoding="utf-8")
    assert "viewBox=\"0 0 1080 1920\"" in content
    assert "+350% SPEED" in content

    # Test terminal card
    term_path = gen.generate_card(
        card_type="terminal",
        title="python -m app.cli run",
        content="Processing job...\nComplete in 4.2s"
    )
    assert Path(term_path).exists()
    t_content = Path(term_path).read_text(encoding="utf-8")
    assert "terminal ~ local-video-factory" in t_content
