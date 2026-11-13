import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.motion_graphics import MotionGraphicsService

client = TestClient(app)


def test_list_motion_graphics_presets():
    res = client.get("/api/v1/motion-graphics/presets")
    assert res.status_code == 200
    presets = res.json()
    assert len(presets) >= 4
    preset_ids = [p["id"] for p in presets]
    assert "lower_third_glass" in preset_ids
    assert "stat_callout_neon" in preset_ids
    assert "viral_hook" in preset_ids


def test_preview_motion_graphic_svg():
    payload = {
        "preset_id": "lower_third_glass",
        "params": {
            "title": "JUAN PEREZ",
            "subtitle": "Tech Lead",
            "accent_color": "#38BDF8"
        },
        "width": 1080,
        "height": 1920
    }
    res = client.post("/api/v1/motion-graphics/preview", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "svg" in data
    assert "JUAN PEREZ" in data["svg"]
    assert "#38BDF8" in data["svg"]


def test_generate_overlay_png_generation():
    service = MotionGraphicsService()
    png_path = service.generate_overlay_png(
        preset_id="stat_callout_neon",
        params={
            "metric": "+500%",
            "explanation": "Crecimiento de audiencia",
            "badge": "VIRAL",
            "accent_color": "#10B981"
        }
    )
    assert png_path.exists()
    assert png_path.stat().st_size > 1000
    png_path.unlink()


def test_composite_motion_graphic_ffmpeg(tmp_path):
    # Create a 2s dummy video
    from app.config import settings
    import subprocess
    ffmpeg_bin = settings.resolve_ffmpeg_path()
    dummy_video = tmp_path / "dummy.mp4"
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=2:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "2",
        "-c:v", "libx264", "-c:a", "aac",
        str(dummy_video)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    service = MotionGraphicsService(cache_dir=tmp_path / "cache")
    out_video = service.composite_motion_graphic(
        video_path=str(dummy_video),
        preset_id="lower_third_glass",
        params={
            "title": "TEST SPEAKER",
            "subtitle": "Test Role",
            "start_time": 0.2,
            "duration": 1.5
        },
        output_path=str(tmp_path / "out_mg.mp4")
    )
    assert Path(out_video).exists()
    assert Path(out_video).stat().st_size > 1000


def test_list_all_presets_and_flip_card_stack():
    res = client.get("/api/v1/motion-graphics/presets")
    assert res.status_code == 200
    presets = res.json()
    assert len(presets) >= 70
    ids = [p["id"] for p in presets]
    assert "flip_card_stack" in ids
    assert "retention_bar" in ids
    assert "split_chars_stagger" in ids
    assert "proximity_scale_grid" in ids
    assert "velocity_skew" in ids
    assert "scrubbed_bento_gallery" in ids
    assert "directional_marquee" in ids
    assert "cursor_tilt_3d" in ids
    assert "physics_confetti_burst" in ids

    # Verify dedicated Anime.js engine presets
    assert "anime_stagger_grid_ripple" in ids
    assert "anime_svg_path_draw" in ids
    assert "anime_kinetic_elastic_pop" in ids
    assert "anime_circle_pulse_radar" in ids
    assert "anime_number_counter_odometer" in ids
    assert "anime_morphing_blob" in ids

    # Test preview of anime_stagger_grid_ripple
    anime_res = client.post("/api/v1/motion-graphics/preview", json={
        "preset_id": "anime_stagger_grid_ripple",
        "params": {
            "headline": "ONDA ESCALONADA TEST",
            "accent_color": "#A855F7"
        }
    })
    assert anime_res.status_code == 200
    assert "anime_grid_dots" in anime_res.json()["svg"]
    assert "ONDA ESCALONADA TEST" in anime_res.json()["svg"]

    # Test preview of proximity_scale_grid
    prox_res = client.post("/api/v1/motion-graphics/preview", json={
        "preset_id": "proximity_scale_grid",
        "params": {
            "headline": "TEST PROXIMITY",
            "accent_color": "#38BDF8"
        }
    })
    assert prox_res.status_code == 200
    assert "TEST PROXIMITY" in prox_res.json()["svg"]

    # Test PNG generation of flip_card_stack
    service = MotionGraphicsService()
    png_p = service.generate_overlay_png("flip_card_stack", {
        "headline": "TEST CARD STACK",
        "subheadline": "Kinetic layout morphing",
        "accent_color": "#38BDF8"
    })
    assert png_p.exists()
    assert png_p.stat().st_size > 5000
    png_p.unlink()


def test_custom_preset_crud_lifecycle(tmp_path):
    # Test adding a custom preset via API
    new_preset = {
        "id": "test_custom_countdown",
        "name": "Custom Dynamic Countdown",
        "category": "Retención & Cues",
        "description": "Preset importado para pruebas",
        "default_params": {
            "headline": "CUENTA REGRESIVA",
            "accent_color": "#EC4899",
            "duration": 5.0,
            "codepen_url": "https://codepen.io/GreenSock/pen/Yzdzxem"
        }
    }
    create_res = client.post("/api/v1/motion-graphics/presets", json=new_preset)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["status"] == "success"
    assert created["preset"]["id"] == "test_custom_countdown"

    # Verify preset appears in list
    list_res = client.get("/api/v1/motion-graphics/presets")
    assert any(p["id"] == "test_custom_countdown" for p in list_res.json())

    # Delete custom preset
    del_res = client.delete("/api/v1/motion-graphics/presets/test_custom_countdown")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"


def test_retention_bar_dynamic_composite_ffmpeg(tmp_path):
    from app.config import settings
    import subprocess
    ffmpeg_bin = settings.resolve_ffmpeg_path()
    dummy_video = tmp_path / "dummy_bar.mp4"
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=2:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "2",
        "-c:v", "libx264", "-c:a", "aac",
        str(dummy_video)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    service = MotionGraphicsService(cache_dir=tmp_path / "cache")
    out_video = service.composite_motion_graphic(
        video_path=str(dummy_video),
        preset_id="retention_bar",
        params={
            "bar_color": "#38BDF8",
            "height_px": 16,
            "start_time": 0.0,
            "duration": 2.0
        },
        output_path=str(tmp_path / "out_retention_bar.mp4")
    )
    assert Path(out_video).exists()
    assert Path(out_video).stat().st_size > 1000


def test_granular_preset_svg_structure():
    service = MotionGraphicsService()
    # 1. Split Chars Stagger has individual character tspans
    svg_chars = service.generate_preview_svg("split_chars_stagger", {"headline": "HOLA MUNDO"})
    assert "class=\"split-char\"" in svg_chars
    assert "id=\"sc_0\"" in svg_chars

    # 2. Split Words Pop has word tspans
    svg_words = service.generate_preview_svg("split_words_pop", {"headline": "CRECIMIENTO ACELERADO HOY"})
    assert "class=\"split-word\"" in svg_words
    assert "id=\"sw_0\"" in svg_words

    # 3. Typewriter has text & cursor
    svg_tw = service.generate_preview_svg("typewriter_cursor", {"headline": "Tecleando..."})
    assert "id=\"tw_text\"" in svg_tw
    assert "id=\"tw_cursor\"" in svg_tw

    # 4. Scramble Matrix has matrix_text target
    svg_matrix = service.generate_preview_svg("scramble_matrix", {"headline": "CODIGO"})
    assert "id=\"matrix_text\"" in svg_matrix
    assert "data-target=\"CODIGO\"" in svg_matrix

    # 5. Bar Chart has granular columns and labels
    svg_bar = service.generate_preview_svg("bar_chart_grow", {"headline": "+380%"})
    assert "class=\"bar-col\"" in svg_bar
    assert "data-target-h=" in svg_bar

    # 6. Percentage Gauge has circle bar and circumference
    svg_gauge = service.generate_preview_svg("percentage_circle_gauge", {"metric": "94%"})
    assert "id=\"gauge_bar\"" in svg_gauge
    assert "stroke-dasharray=\"691\"" in svg_gauge

    # 7. Crypto Stock has trend path
    svg_crypto = service.generate_preview_svg("crypto_stock_badge", {"headline": "+150%"})
    assert "id=\"crypto_trend_path\"" in svg_crypto

    # 8. CTA Subscribe Bell has button, bell, and hand cursor
    svg_cta = service.generate_preview_svg("cta_subscribe_bell", {"headline": "SUSCRIBETE"})
    assert "id=\"cta_btn\"" in svg_cta
    assert "id=\"cta_bell\"" in svg_cta
    assert "id=\"cta_cursor_hand\"" in svg_cta

    # 9. Attention Arrow has arrow icon and alert rings
    svg_arrow = service.generate_preview_svg("attention_arrow", {"headline": "MIRA ESTO"})
    assert "id=\"attention_arrow_icon\"" in svg_arrow
    assert "alert-ring" in svg_arrow

    # 10. Remotion Audio Waveform has individual wave bars
    svg_wave = service.generate_preview_svg("remotion_audio_waveform", {"headline": "VOZ"})
    assert "class=\"wave-bar\"" in svg_wave
    assert "id=\"wave_bar_0\"" in svg_wave


def test_all_89_presets_generate_valid_svg_and_metadata():
    service = MotionGraphicsService()
    presets = service.get_presets()
    assert len(presets) >= 89

    # Verify each preset generates valid SVG
    for p in presets:
        pid = p["id"]
        svg = service.generate_preview_svg(pid, {"headline": "TEST", "accent_color": "#00FFFF"})
        assert "<svg" in svg, f"Preset {pid} failed SVG generation"
        assert "</svg>" in svg, f"Preset {pid} missing closing SVG tag"


def test_three_new_galleries_presets():
    service = MotionGraphicsService()

    # Gallery 1: FX
    svg_vhs = service.generate_preview_svg("fx_vhs_retro", {"headline": "PLAY > 1984"})
    assert "vhs_tracking_bar" in svg_vhs
    assert "vhs_retro_card" in svg_vhs

    svg_cyber = service.generate_preview_svg("fx_cyberpunk_glitch", {"headline": "CYBER OVERDRIVE"})
    assert "cyber-slice" in svg_cyber
    assert "CYBER OVERDRIVE" in svg_cyber

    svg_matrix = service.generate_preview_svg("fx_matrix_stream", {"headline": "WAKE UP NEO"})
    assert "matrix_rain_columns" in svg_matrix
    assert "matrix_stream_card" in svg_matrix

    # Gallery 2: Cinematic Transitions
    svg_whip = service.generate_preview_svg("transition_whip_pan_blur", {"headline": "SCENE 2"})
    assert "whip_pan_wrapper" in svg_whip
    assert "whip_motion_streaks" in svg_whip

    svg_burn = service.generate_preview_svg("transition_film_burn_flash", {"headline": "WARM BURN"})
    assert "burnBloom" in svg_burn

    svg_shatter = service.generate_preview_svg("transition_shatter_glass_burst", {"headline": "SHATTER"})
    assert "shatter_glass_wrapper" in svg_shatter
    assert "shatter_shard_1" in svg_shatter

    svg_kaleido = service.generate_preview_svg("transition_kaleidoscope_spin", {"headline": "PRISM"})
    assert "kaleidoscope_wrapper" in svg_kaleido
    assert "kaleidoscope_mandala" in svg_kaleido

    svg_warp = service.generate_preview_svg("transition_rgb_warp_tunnel", {"headline": "WARP SPEED"})
    assert "rgb_warp_wrapper" in svg_warp
    assert "warp_ring_1" in svg_warp

    # Gallery 3: Video Editor Tools & Spectrum Visualizers
    svg_bars = service.generate_preview_svg("tool_audio_bars_spectrum", {"headline": "PODCAST STEREO"})
    assert "spectrum_bars_group" in svg_bars
    assert "spec-bar" in svg_bars

    svg_circ = service.generate_preview_svg("tool_circular_sound_wave", {"headline": "AUDIO PULSE"})
    assert "radial_sound_wrapper" in svg_circ
    assert "radial_spikes_group" in svg_circ

    svg_badge = service.generate_preview_svg("tool_neon_podcast_badge", {"headline": "EPISODE 42", "subtitle": "AI REVOLUTION"})
    assert "podcast_on_air_box" in svg_badge
    assert "on_air_neon_text" in svg_badge



