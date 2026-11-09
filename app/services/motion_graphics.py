import json
import logging
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont
from app.config import settings

logger = logging.getLogger(__name__)


class MotionGraphicsService:
    """Motion Graphics & Animated Visual Assets Engine for user videos.

    Inspired by HyperFrames / HeyGen workflows:
    - Generates transparent pixel-perfect visual overlays (Lower Thirds, Stat Callouts, Retention Bars, CTAs).
    - Produces live SVG/CSS markup for real-time browser preview.
    - Composites overlays seamlessly onto user videos using local FFmpeg with smooth transitions.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or settings.CACHE_DIR / "motion_graphics"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_bin = settings.resolve_ffmpeg_path()

    def get_presets(self) -> List[Dict[str, Any]]:
        """Returns the library of motion graphics presets."""
        return [
            {
                "id": "lower_third_glass",
                "name": "Lower Third Cinético (Glass Minimal)",
                "category": "Identificación & Speaker",
                "description": "Barra moderna de cristal semitransparente con acento neón, nombre del presentador y cargo.",
                "default_params": {
                    "title": "ALEX RIVERA",
                    "subtitle": "Especialista en IA & Automatización",
                    "accent_color": "#38BDF8",
                    "badge": "CREADOR",
                    "position": "bottom",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "stat_callout_neon",
                "name": "Métrica de Impacto (Stat Callout)",
                "category": "Datos & Viralidad",
                "description": "Tarjeta flotante con número gigante, cambio porcentual y brillo neón para retención.",
                "default_params": {
                    "metric": "+350%",
                    "explanation": "Crecimiento en velocidad de producción",
                    "badge": "CASO DE ÉXITO",
                    "accent_color": "#10B981",
                    "position": "bottom_card",
                    "start_time": 2.0,
                    "duration": 4.5,
                }
            },
            {
                "id": "viral_hook",
                "name": "Hook Explosivo (Título 0-3s)",
                "category": "Retención Inicial",
                "description": "Tarjeta central impactante con tipografía cinética para los primeros 3 segundos del video.",
                "default_params": {
                    "headline": "NO COMETAS ESTE ERROR",
                    "subheadline": "Mira esto antes de subir tu próximo video",
                    "badge": "ATENCIÓN",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 0.2,
                    "duration": 3.0,
                }
            },
            {
                "id": "cta_badge",
                "name": "Llamado a la Acción (Animated CTA)",
                "category": "Conversión",
                "description": "Botón flotante animado para incentivar comentarios, suscripciones o links en bio.",
                "default_params": {
                    "cta_text": "★ Sígueme para más trucos de IA",
                    "subtext": "Guarda este video para no perderlo",
                    "accent_color": "#818CF8",
                    "position": "bottom",
                    "start_time": 5.0,
                    "duration": 4.0,
                }
            },
            {
                "id": "retention_bar",
                "name": "Barra de Retención Viral (Progress Bar)",
                "category": "Retención TikTok/Reels",
                "description": "Barra de progreso animada en el borde inferior que avanza a lo largo del video.",
                "default_params": {
                    "bar_color": "#38BDF8",
                    "height_px": 14,
                    "position": "bottom_edge",
                    "start_time": 0.0,
                    "duration": 0.0,  # 0.0 means full video duration
                }
            }
        ]

    def probe_video(self, video_path: str) -> Dict[str, Any]:
        """Probes video metadata (duration, width, height, fps) using FFmpeg."""
        vid_p = Path(video_path).resolve()
        if not vid_p.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cmd = [
            self.ffmpeg_bin,
            "-i", str(vid_p),
            "-hide_banner"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stderr = res.stderr

        duration = 0.0
        width = 1080
        height = 1920
        fps = 30.0

        # Match Duration: 00:01:23.45
        dur_m = re.search(r"Duration:\s*(\d+):(\d+):([\d\.]+)", stderr)
        if dur_m:
            h, m, s = float(dur_m.group(1)), float(dur_m.group(2)), float(dur_m.group(3))
            duration = round(h * 3600 + m * 60 + s, 2)

        # Match Resolution: 1080x1920
        res_m = re.search(r"(\d{3,4})x(\d{3,4})", stderr)
        if res_m:
            width = int(res_m.group(1))
            height = int(res_m.group(2))

        # Match FPS: 30 fps
        fps_m = re.search(r"([\d\.]+)\s*fps", stderr)
        if fps_m:
            fps = float(fps_m.group(1))

        aspect_ratio = "9:16" if height > width else ("16:9" if width > height else "1:1")

        return {
            "path": str(vid_p),
            "filename": vid_p.name,
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "aspect_ratio": aspect_ratio,
            "size_mb": round(vid_p.stat().st_size / (1024 * 1024), 2)
        }

    def generate_preview_svg(self, preset_id: str, params: Dict[str, Any], width: int = 1080, height: int = 1920) -> str:
        """Returns SVG markup with transparent root for immediate browser preview."""
        accent = params.get("accent_color", "#38BDF8")

        if preset_id == "lower_third_glass":
            title = params.get("title", "PRESENTADOR").upper()
            subtitle = params.get("subtitle", "Especialista en Contenido")
            badge = params.get("badge", "CREADOR").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Transparent Root -->
  <g id="lower_third" transform="translate(60, 1420)">
    <!-- Glass background with dark blur -->
    <rect width="960" height="230" rx="28" fill="#0F172A" fill-opacity="0.88" stroke="#334155" stroke-width="2.5"/>
    <!-- Neon accent vertical bar -->
    <rect x="36" y="32" width="10" height="166" rx="5" fill="{accent}"/>
    <!-- Badge -->
    <rect x="70" y="36" width="140" height="34" rx="17" fill="{accent}" fill-opacity="0.18" stroke="{accent}" stroke-width="1.5"/>
    <text x="140" y="58" font-family="'Montserrat', sans-serif" font-size="14" font-weight="800" fill="{accent}" text-anchor="middle" letter-spacing="2">{badge}</text>
    <!-- Title -->
    <text x="70" y="118" font-family="'Montserrat', sans-serif" font-size="38" font-weight="900" fill="#FFFFFF" letter-spacing="1">{title}</text>
    <!-- Subtitle -->
    <text x="70" y="165" font-family="'Segoe UI', sans-serif" font-size="24" font-weight="500" fill="#94A3B8">{subtitle}</text>
  </g>
</svg>"""

        elif preset_id == "stat_callout_neon":
            metric = params.get("metric", "+350%")
            explanation = params.get("explanation", "Velocidad de producción")
            badge = params.get("badge", "IMPACTO").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="stat_callout" transform="translate(60, 1260)">
    <!-- Glass card -->
    <rect width="960" height="340" rx="32" fill="#0B132B" fill-opacity="0.90" stroke="{accent}" stroke-width="3"/>
    <!-- Badge -->
    <rect x="48" y="36" width="180" height="36" rx="18" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="138" y="60" font-family="'Montserrat', sans-serif" font-size="15" font-weight="800" fill="{accent}" text-anchor="middle" letter-spacing="2">{badge}</text>
    <!-- Metric -->
    <text x="48" y="170" font-family="'Impact', sans-serif" font-size="96" font-weight="900" fill="{accent}">{metric}</text>
    <!-- Explanation -->
    <text x="48" y="240" font-family="'Montserrat', sans-serif" font-size="28" font-weight="700" fill="#FFFFFF">{explanation}</text>
    <!-- Local badge -->
    <text x="48" y="295" font-family="'Segoe UI', sans-serif" font-size="18" font-weight="600" fill="#64748B">100% LOCAL &amp; AUTÓNOMO</text>
  </g>
</svg>"""

        elif preset_id == "viral_hook":
            headline = params.get("headline", "NO COMETAS ESTE ERROR").upper()
            subheadline = params.get("subheadline", "Mira esto antes de publicar tu contenido")
            badge = params.get("badge", "ATENCIÓN").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="viral_hook" transform="translate(60, 720)">
    <!-- High-impact hook container -->
    <rect width="960" height="380" rx="36" fill="#18181B" fill-opacity="0.93" stroke="{accent}" stroke-width="3.5"/>
    <!-- Warning icon & badge -->
    <rect x="380" y="40" width="200" height="42" rx="21" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="2"/>
    <text x="480" y="67" font-family="'Montserrat', sans-serif" font-size="16" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="3">⚡ {badge}</text>
    <!-- Headline -->
    <text x="480" y="180" font-family="'Impact', sans-serif" font-size="62" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="1">{headline}</text>
    <!-- Subheadline -->
    <text x="480" y="260" font-family="'Montserrat', sans-serif" font-size="28" font-weight="600" fill="#E4E4E7" text-anchor="middle">{subheadline}</text>
    <line x1="280" y1="310" x2="680" y2="310" stroke="{accent}" stroke-width="2" stroke-dasharray="8 8"/>
  </g>
</svg>"""

        elif preset_id == "cta_badge":
            cta_text = params.get("cta_text", "★ Sígueme para más contenido")
            subtext = params.get("subtext", "Comenta abajo tu opinión")
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="cta_badge" transform="translate(100, 1500)">
    <rect width="880" height="170" rx="30" fill="#1E1B4B" fill-opacity="0.90" stroke="{accent}" stroke-width="3"/>
    <text x="440" y="75" font-family="'Montserrat', sans-serif" font-size="32" font-weight="900" fill="#FFFFFF" text-anchor="middle">{cta_text}</text>
    <text x="440" y="125" font-family="'Segoe UI', sans-serif" font-size="20" font-weight="600" fill="{accent}" text-anchor="middle">{subtext}</text>
  </g>
</svg>"""

        else:  # retention_bar
            bar_color = params.get("bar_color", "#38BDF8")
            h = int(params.get("height_px", 14))
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="{height - h}" width="{width}" height="{h}" fill="{bar_color}"/>
</svg>"""

    def generate_overlay_png(
        self,
        preset_id: str,
        params: Dict[str, Any],
        width: int = 1080,
        height: int = 1920
    ) -> Path:
        """Generates a high-resolution transparent 1080x1920 RGBA PNG using Pillow."""
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Parse accent color hex to RGB
        hex_color = params.get("accent_color") or params.get("bar_color") or "#38BDF8"
        hex_color = hex_color.lstrip("#")
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        except Exception:
            r, g, b = 56, 189, 248

        accent_rgb = (r, g, b, 255)
        accent_dim = (r, g, b, 50)

        # Fallback system font loading
        font_large = ImageFont.load_default()
        font_med = ImageFont.load_default()
        font_small = ImageFont.load_default()

        file_id = str(uuid.uuid4())[:8]
        output_file = self.cache_dir / f"overlay_{preset_id}_{file_id}.png"

        if preset_id == "lower_third_glass":
            title = params.get("title", "PRESENTADOR").upper()
            subtitle = params.get("subtitle", "Especialista en Contenido")
            badge = params.get("badge", "CREADOR").upper()

            # Glass background
            draw.rounded_rectangle([60, 1420, 1020, 1650], radius=28, fill=(15, 23, 42, 225), outline=(51, 65, 85, 255), width=3)
            # Accent vertical stripe
            draw.rounded_rectangle([96, 1452, 106, 1618], radius=5, fill=accent_rgb)
            # Badge pill
            draw.rounded_rectangle([130, 1456, 270, 1490], radius=17, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((155, 1466), badge, fill=accent_rgb)
            # Title
            draw.text((130, 1515), title, fill=(255, 255, 255, 255))
            # Subtitle
            draw.text((130, 1565), subtitle, fill=(148, 163, 184, 255))

        elif preset_id == "stat_callout_neon":
            metric = params.get("metric", "+350%")
            explanation = params.get("explanation", "Velocidad de producción")
            badge = params.get("badge", "IMPACTO").upper()

            # Glass card
            draw.rounded_rectangle([60, 1260, 1020, 1600], radius=32, fill=(11, 19, 43, 230), outline=accent_rgb, width=3)
            # Badge
            draw.rounded_rectangle([108, 1296, 288, 1332], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((140, 1308), badge, fill=accent_rgb)
            # Metric
            draw.text((108, 1360), metric, fill=accent_rgb)
            # Explanation
            draw.text((108, 1460), explanation, fill=(255, 255, 255, 255))
            draw.text((108, 1520), "100% LOCAL & AUTONOMO", fill=(100, 116, 139, 255))

        elif preset_id == "viral_hook":
            headline = params.get("headline", "NO COMETAS ESTE ERROR").upper()
            subheadline = params.get("subheadline", "Mira esto antes de publicar")
            badge = params.get("badge", "ATENCION").upper()

            draw.rounded_rectangle([60, 720, 1020, 1100], radius=36, fill=(24, 24, 27, 240), outline=accent_rgb, width=4)
            # Badge
            draw.rounded_rectangle([440, 760, 640, 802], radius=21, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((490, 773), badge, fill=accent_rgb)
            # Headline
            draw.text((140, 850), headline, fill=(255, 255, 255, 255))
            # Subheadline
            draw.text((140, 930), subheadline, fill=(228, 228, 231, 255))

        elif preset_id == "cta_badge":
            cta_text = params.get("cta_text", "Sigueme para mas contenido")
            subtext = params.get("subtext", "Comenta abajo tu opinion")

            draw.rounded_rectangle([100, 1500, 980, 1670], radius=30, fill=(30, 27, 75, 230), outline=accent_rgb, width=3)
            draw.text((220, 1545), cta_text, fill=(255, 255, 255, 255))
            draw.text((260, 1600), subtext, fill=accent_rgb)

        else:  # retention_bar
            bar_h = int(params.get("height_px", 14))
            draw.rectangle([0, height - bar_h, width, height], fill=accent_rgb)

        img.save(output_file, "PNG")
        logger.info(f"Generated transparent motion graphic PNG at: {output_file}")
        return output_file

    def composite_motion_graphic(
        self,
        video_path: str,
        preset_id: str,
        params: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """Composites the motion graphic overlay onto the user video using local FFmpeg."""
        meta = self.probe_video(video_path)
        vid_w = meta["width"]
        vid_h = meta["height"]
        vid_dur = meta["duration"]

        start_time = float(params.get("start_time", 1.0))
        requested_duration = float(params.get("duration", 5.0))
        
        # If duration is 0 or exceeds video length, cap it
        if requested_duration <= 0.0 or (start_time + requested_duration) > vid_dur:
            duration = max(1.0, vid_dur - start_time)
        else:
            duration = requested_duration

        end_time = min(vid_dur, start_time + duration)
        fade_time = 0.3

        # Generate transparent overlay matching video dimensions
        overlay_png = self.generate_overlay_png(preset_id, params, width=vid_w, height=vid_h)

        if not output_path:
            out_filename = f"mg_{Path(video_path).stem}_{preset_id}_{str(uuid.uuid4())[:6]}.mp4"
            out_p = settings.OUTPUTS_DIR / out_filename
        else:
            out_p = Path(output_path).resolve()

        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Build FFmpeg command with smooth alpha fade in & out
        filter_complex = (
            f"[1:v]format=yuva420p,"
            f"fade=t=in:st=0:d={fade_time}:alpha=1,"
            f"fade=t=out:st={max(0.1, duration - fade_time)}:d={fade_time}:alpha=1,"
            f"setpts=PTS-STARTPTS+{start_time}/TB[over];"
            f"[0:v][over]overlay=0:0:enable='between(t,{start_time},{end_time})'[v_out]"
        )

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(Path(video_path).resolve()),
            "-loop", "1", "-t", str(duration), "-i", str(overlay_png.resolve()),
            "-filter_complex", filter_complex,
            "-map", "[v_out]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(out_p)
        ]

        logger.info(f"Running Motion Graphics FFmpeg compositing for {preset_id}...")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            logger.error(f"FFmpeg motion graphics failed:\n{res.stderr}")
            raise RuntimeError(f"FFmpeg motion graphics error: {res.stderr[:300]}")

        # Clean temp overlay
        try:
            overlay_png.unlink(missing_ok=True)
        except Exception:
            pass

        return str(out_p)
