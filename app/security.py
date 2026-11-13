"""Centralised input validation for paths, URLs and values that reach FFmpeg/SVG.

The server only listens on loopback, but any web page the user visits can still
send requests to it (CSRF / DNS rebinding), and trend feeds bring third-party
text into the dashboard. Every route that accepts a path, URL or colour must go
through these helpers instead of trusting the raw value.
"""
from __future__ import annotations

import html
import ipaddress
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlparse

from fastapi import HTTPException

from app.config import settings

_HEX_COLOR = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def _is_within(path: Path, roots: Iterable[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def resolve_media_path(
    path_str: str,
    *,
    must_exist: bool = True,
    roots: Optional[Iterable[Path]] = None,
) -> Path:
    """Resolve ``path_str`` and ensure it lives inside an allowed media root.

    Bare file names are looked up in uploads/ and outputs/ (the dashboard sends
    names, n8n sends absolute paths). Symlinks are resolved before the check.
    """
    allowed = [Path(r).resolve() for r in (roots or settings.media_roots())]
    if not path_str or "\x00" in path_str:
        raise HTTPException(status_code=400, detail="Ruta de archivo vacía o inválida.")

    raw = Path(path_str)
    is_explicit = raw.is_absolute() or bool(raw.anchor) or path_str.startswith(("/", "\\"))
    candidates = [raw] if is_explicit else []
    candidates += [settings.UPLOADS_DIR / raw.name, settings.OUTPUTS_DIR / raw.name]

    for cand in candidates:
        resolved = cand.resolve()
        if not _is_within(resolved, allowed):
            continue
        if not must_exist or resolved.is_file():
            return resolved

    if is_explicit and not _is_within(raw.resolve(), allowed):
        raise HTTPException(
            status_code=403,
            detail="Ruta fuera de los directorios permitidos (storage/ o ALLOWED_MEDIA_DIRS).",
        )
    raise HTTPException(status_code=404, detail=f"No se encontró el archivo: {raw.name}")


def resolve_output_path(path_str: Optional[str]) -> Optional[Path]:
    """Validate an optional caller-chosen output path (must be an allowed root, .mp4)."""
    if not path_str:
        return None
    raw = Path(path_str)
    is_explicit = raw.is_absolute() or bool(raw.anchor) or path_str.startswith(("/", "\\"))
    out = resolve_media_path(path_str, must_exist=False) if is_explicit \
        else (settings.OUTPUTS_DIR / raw.name).resolve()
    if out.suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="La ruta de salida debe terminar en .mp4")
    return out


def safe_filename(name: str) -> str:
    """Strip directories and characters that break FFmpeg filter syntax or URLs."""
    base = Path(name or "").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._")
    return cleaned[:120] or "archivo"


def validate_webhook_url(url: Optional[str]) -> Optional[str]:
    """Allow only http(s) webhooks to configured hosts (default: loopback) to stop SSRF."""
    if not url:
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise HTTPException(status_code=400, detail="URL de webhook inválida (solo http/https).")
    allowed = {h.lower() for h in settings.WEBHOOK_ALLOWED_HOSTS}
    if host in allowed:
        return url
    try:
        if ipaddress.ip_address(host).is_loopback and {"127.0.0.1", "::1"} & allowed:
            return url
    except ValueError:
        pass
    raise HTTPException(
        status_code=400,
        detail=f"Host de webhook '{host}' no permitido. Añádelo a WEBHOOK_ALLOWED_HOSTS.",
    )


def sanitize_hex_color(value: Any, default: str = "#38BDF8") -> str:
    """Return a ``#RRGGBB``-style colour or ``default``; never lets text into FFmpeg filters."""
    if isinstance(value, str) and _HEX_COLOR.match(value.strip()):
        v = value.strip()
        return v if v.startswith("#") else f"#{v}"
    return default


def escape_markup_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """HTML/XML-escape every string param before it is interpolated into SVG markup."""
    out: Dict[str, Any] = {}
    for key, val in params.items():
        if isinstance(val, str):
            out[key] = sanitize_hex_color(val) if "color" in key else html.escape(val, quote=True)
        else:
            out[key] = val
    return out
