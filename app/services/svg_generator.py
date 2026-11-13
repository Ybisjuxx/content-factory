import html
import logging
import uuid
from pathlib import Path
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


def _e(value: str) -> str:
    """Escape text for SVG/XML (call AFTER any .upper(), or entities break)."""
    return html.escape(str(value), quote=True)


def _fit(text: str, base_size: int, max_width: int) -> int:
    """Shrink a single-line headline so it fits ``max_width`` (≈0.62em per glyph)."""
    est = max(1, len(str(text))) * 0.62 * base_size
    return base_size if est <= max_width else max(28, int(base_size * max_width / est))


def _wrap_text(text: str, *, x: int, max_chars: int, line_height: int, max_lines: int) -> str:
    """Word-wrap into <tspan> lines.

    The cards used <foreignObject> + XHTML for multi-line text, which librsvg (the
    SVG rasteriser FFmpeg uses) does not render: body text was missing from every
    final video. Plain <text>/<tspan> renders everywhere.
    """
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        words, current = paragraph.split(), ""
        for word in words:
            while len(word) > max_chars:  # hard-break very long tokens (URLs, code)
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:max_chars])
                word = word[max_chars:]
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max_chars - 1].rstrip() + "…"
    return "\n".join(
        f'    <tspan x="{x}" dy="{0 if i == 0 else line_height}">{_e(line)}</tspan>'
        for i, line in enumerate(lines)
    )


class ProceduralSvgGenerator:
    """Generates modern, vertical 9:16 (1080x1920) SVG graphics cards for short-form video overlays."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.CACHE_DIR / "svg_cards"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_card(
        self,
        card_type: str = "stat",
        title: str = "HIGHLIGHT",
        content: str = "Important Concept",
        badge: str = "KEY TAKEAWAY",
    ) -> str:
        """Creates an SVG card file and returns its path."""
        # Text comes from the API / LLM: every interpolation goes through _e() / _wrap_text().
        title, content, badge = str(title), str(content), str(badge)
        if card_type not in {"stat", "quote", "terminal", "takeaway"}:
            card_type = "takeaway"
        file_id = str(uuid.uuid4())[:8]
        output_file = self.output_dir / f"card_{card_type}_{file_id}.svg"

        if card_type == "stat":
            svg_content = self._render_stat_card(title, content, badge)
        elif card_type == "quote":
            svg_content = self._render_quote_card(title, content)
        elif card_type == "terminal":
            svg_content = self._render_terminal_card(title, content)
        else:  # takeaway / bullet
            svg_content = self._render_takeaway_card(title, content, badge)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(svg_content)

        logger.info(f"Generated SVG card ({card_type}) at: {output_file}")
        return str(output_file.resolve())

    def _render_stat_card(self, metric: str, explanation: str, badge: str) -> str:
        return f"""<svg width="1080" height="1920" viewBox="0 0 1080 1920" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg_grad" x1="0" y1="0" x2="1080" y2="1920" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#0F172A" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#020617" stop-opacity="0.98"/>
    </linearGradient>
    <linearGradient id="glow_grad" x1="200" y1="600" x2="880" y2="1200" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#818CF8"/>
    </linearGradient>
    <filter id="card_shadow" x="60" y="500" width="960" height="920" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="24" stdDeviation="32" flood-color="#000000" flood-opacity="0.6"/>
    </filter>
  </defs>

  <!-- Ambient Backdrop -->
  <rect width="1080" height="1920" fill="url(#bg_grad)"/>

  <!-- Glowing Accent Circles -->
  <circle cx="540" cy="960" r="380" fill="#38BDF8" fill-opacity="0.12" filter="blur(60px)"/>
  <circle cx="540" cy="780" r="240" fill="#818CF8" fill-opacity="0.15" filter="blur(50px)"/>

  <!-- Glassmorphic Card Container -->
  <g filter="url(#card_shadow)">
    <rect x="100" y="580" width="880" height="760" rx="40" fill="#1E293B" fill-opacity="0.85" stroke="#334155" stroke-width="3"/>
  </g>

  <!-- Category Badge -->
  <rect x="390" y="660" width="300" height="56" rx="28" fill="#0EA5E9" fill-opacity="0.2" stroke="#38BDF8" stroke-width="2"/>
  <text x="540" y="696" font-family="Montserrat, Inter, sans-serif" font-size="20" font-weight="800" fill="#38BDF8" text-anchor="middle" letter-spacing="3">{_e(badge.upper())}</text>

  <!-- Giant Hero Metric -->
  <text x="540" y="930" font-family="Impact, Montserrat, sans-serif" font-size="{_fit(metric, 110, 760)}" font-weight="900" fill="url(#glow_grad)" text-anchor="middle" letter-spacing="2">
    {_e(metric)}
  </text>

  <!-- Subtitle Explanation -->
  <text x="540" y="1030" font-family="Montserrat, Inter, sans-serif" font-size="36" font-weight="600" fill="#F8FAFC" text-anchor="middle">
{_wrap_text(explanation, x=540, max_chars=34, line_height=46, max_lines=3)}
  </text>
  
  <!-- Subtle decorative line -->
  <line x1="340" y1="1130" x2="740" y2="1130" stroke="#475569" stroke-width="3" stroke-dasharray="12 12"/>
  <text x="540" y="1210" font-family="Montserrat, Inter, sans-serif" font-size="22" font-weight="500" fill="#94A3B8" text-anchor="middle">
    100% LOCAL &amp; SELF-HOSTED
  </text>
</svg>"""

    def _render_takeaway_card(self, title: str, content: str, badge: str) -> str:
        return f"""<svg width="1080" height="1920" viewBox="0 0 1080 1920" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="tk_bg" x1="0" y1="0" x2="1080" y2="1920" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#0B0F19" stop-opacity="0.96"/>
      <stop offset="100%" stop-color="#030712" stop-opacity="0.98"/>
    </linearGradient>
    <filter id="tk_glow">
      <feDropShadow dx="0" dy="16" stdDeviation="24" flood-color="#10B981" flood-opacity="0.3"/>
    </filter>
  </defs>

  <rect width="1080" height="1920" fill="url(#tk_bg)"/>

  <!-- Card Body -->
  <rect x="100" y="600" width="880" height="720" rx="40" fill="#111827" fill-opacity="0.9" stroke="#1F2937" stroke-width="4" filter="url(#tk_glow)"/>

  <!-- Icon / Badge -->
  <rect x="160" y="660" width="220" height="50" rx="25" fill="#10B981" fill-opacity="0.2" stroke="#34D399" stroke-width="2"/>
  <text x="270" y="693" font-family="sans-serif" font-size="18" font-weight="800" fill="#34D399" text-anchor="middle" letter-spacing="2">{_e(badge.upper()[:18])}</text>

  <!-- Title -->
  <text x="160" y="790" font-family="Impact, sans-serif" font-size="{_fit(title, 64, 760)}" font-weight="900" fill="#F9FAFB">
    {_e(title.upper())}
  </text>

  <!-- Bullet / Main Content -->
  <text x="160" y="900" font-family="'Segoe UI', Montserrat, sans-serif" font-size="38" font-weight="500" fill="#E5E7EB">
{_wrap_text(content, x=160, max_chars=36, line_height=53, max_lines=7)}
  </text>
</svg>"""

    def _render_quote_card(self, speaker: str, quote_text: str) -> str:
        return f"""<svg width="1080" height="1920" viewBox="0 0 1080 1920" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="1080" height="1920" fill="#090D16" fill-opacity="0.96"/>
  
  <rect x="100" y="620" width="880" height="680" rx="36" fill="#131B2E" stroke="#1E293B" stroke-width="3"/>
  <text x="160" y="740" font-family="Georgia, serif" font-size="140" fill="#F59E0B" fill-opacity="0.6">“</text>
  
  <text x="160" y="810" font-family="Georgia, serif" font-size="42" font-style="italic" fill="#F1F5F9">
{_wrap_text(quote_text, x=160, max_chars=32, line_height=59, max_lines=6)}
  </text>
  
  <line x1="160" y1="1160" x2="300" y2="1160" stroke="#F59E0B" stroke-width="4"/>
  <text x="160" y="1220" font-family="sans-serif" font-size="28" font-weight="700" fill="#94A3B8">— {_e(speaker.upper())}</text>
</svg>"""

    def _render_terminal_card(self, command: str, output: str) -> str:
        return f"""<svg width="1080" height="1920" viewBox="0 0 1080 1920" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="1080" height="1920" fill="#030712" fill-opacity="0.97"/>
  
  <!-- Terminal Window -->
  <rect x="80" y="580" width="920" height="760" rx="24" fill="#0B132B" stroke="#1C2541" stroke-width="3"/>
  
  <!-- Window Header Bar -->
  <rect x="80" y="580" width="920" height="56" rx="24" fill="#1C2541"/>
  <circle cx="120" cy="608" r="8" fill="#EF4444"/>
  <circle cx="146" cy="608" r="8" fill="#F59E0B"/>
  <circle cx="172" cy="608" r="8" fill="#10B981"/>
  <text x="540" y="615" font-family="monospace" font-size="18" fill="#64748B" text-anchor="middle">terminal ~ local-video-factory</text>
  
  <!-- Terminal Code Area -->
  <text x="130" y="710" font-family="'Consolas', monospace" font-size="32" fill="#38BDF8">$ {_e(command)}</text>
  
  <text x="130" y="780" font-family="Consolas, monospace" font-size="26" fill="#10B981" xml:space="preserve">
{_wrap_text(output, x=130, max_chars=52, line_height=39, max_lines=13)}
  </text>
</svg>"""
