import logging
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from pydantic import BaseModel, Field
from app.config import settings
from app.services.motion_graphics import MotionGraphicsService
from app.security import resolve_media_path, resolve_output_path
from app.api.uploads import save_upload, VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/motion-graphics", tags=["Motion Graphics & Video Upload"])

mg_service = MotionGraphicsService()


class PreviewRequest(BaseModel):
    preset_id: str = Field(..., max_length=80)
    params: Dict[str, Any] = Field(default_factory=dict)
    width: int = Field(1080, ge=16, le=3840)
    height: int = Field(1920, ge=16, le=3840)


class ApplyMotionGraphicsRequest(BaseModel):
    video_path: str
    preset_id: str = Field(..., pattern=r"^[A-Za-z0-9_\-]{1,80}$")
    params: Dict[str, Any] = Field(default_factory=dict)
    output_path: Optional[str] = None


import json
import re
import httpx

class MotionAIGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Prompt en lenguaje natural describiendo el motion graphic")
    video_duration: Optional[float] = Field(30.0, description="Duración total del video para calibrar tiempos")


def _nlp_extract_motion_params(prompt: str, video_dur: float = 30.0) -> tuple[str, Dict[str, Any]]:
    """Comprehensive Natural Language Parser that extracts preset, parameters, times, and colors from any prompt."""
    p_lower = prompt.lower()

    # 1. Color Extraction
    color_map = {
        "rojo": "#EF4444", "red": "#EF4444",
        "verde": "#10B981", "green": "#10B981", "esmeralda": "#10B981",
        "azul": "#38BDF8", "blue": "#38BDF8", "celeste": "#38BDF8", "sky": "#38BDF8",
        "amarillo": "#F59E0B", "yellow": "#F59E0B", "dorado": "#F59E0B", "gold": "#F59E0B",
        "morado": "#A855F7", "purpura": "#A855F7", "violeta": "#A855F7", "purple": "#A855F7",
        "rosa": "#EC4899", "pink": "#EC4899", "fucsia": "#EC4899",
        "cian": "#06B6D4", "cyan": "#06B6D4", "turquesa": "#06B6D4",
        "naranja": "#F97316", "orange": "#F97316",
        "blanco": "#FFFFFF", "white": "#FFFFFF"
    }
    accent_color = None
    hex_match = re.search(r"#(?:[0-9a-fA-F]{3}){1,2}\b", prompt)
    if hex_match:
        accent_color = hex_match.group(0).upper()
    else:
        for cname, chex in color_map.items():
            if re.search(rf"\b{cname}\b", p_lower):
                accent_color = chex
                break

    # 2. Timing Extraction
    start_time = 1.0
    time_m = re.search(r"(?:al|en el|a los|segundo)\s*(\d+(?:\.\d+)?)\s*(?:segundos?|s\b)?", p_lower)
    if time_m:
        start_time = float(time_m.group(1))
    elif "al inicio" in p_lower or "al empezar" in p_lower or "primeros segundos" in p_lower:
        start_time = 0.2
    elif "al final" in p_lower:
        start_time = max(1.0, video_dur - 5.0)

    duration = 4.5
    dur_m = re.search(r"(?:durante|por|duracion de)\s*(\d+(?:\.\d+)?)\s*(?:segundos?|s\b)?", p_lower)
    if dur_m:
        duration = float(dur_m.group(1))

    # 3. Quoted text or specific message extraction
    extracted_text = None
    quote_m = re.search(r'["\'«]([^"\'»]+)["\'»]', prompt)
    if quote_m:
        extracted_text = quote_m.group(1).strip()
    else:
        diga_m = re.search(r"(?:que diga|con el texto|texto|titular|nombre)\s+([^,.;]+)", prompt, re.IGNORECASE)
        if diga_m:
            extracted_text = diga_m.group(1).strip()

    # 4. Multi-category Preset Classification
    if any(k in p_lower for k in ["flecha", "ojo", "apunta", "senala", "mira esto", "aqui", "fijate", "arrow"]):
        preset_id = "attention_arrow"
        params = {
            "label": extracted_text[:28].upper() if extracted_text else "¡OJO CON ESTO!",
            "sublabel": "Detalle clave que no debes perder",
            "accent_color": accent_color or "#EF4444",
            "start_time": start_time,
            "duration": duration,
            "spring_type": "bouncy"
        }

    elif any(k in p_lower for k in ["alerta", "peligro", "advertencia", "cuidado", "detente", "stop", "urgente", "riesgo", "warning"]):
        preset_id = "warning_alert"
        params = {
            "warning_title": extracted_text[:30].upper() if extracted_text else "¡DETÉNTE AQUÍ!",
            "warning_desc": "Si cometes este error arruinas tus resultados",
            "accent_color": accent_color or "#F59E0B",
            "start_time": start_time if time_m else 0.2,
            "duration": duration,
            "spring_type": "snappy"
        }

    elif any(k in p_lower for k in ["sigueme", "suscribete", "comenta", "comparte", "guarda", "link", "bio", "cta", "llamado", "boton"]):
        preset_id = "cta_badge"
        params = {
            "cta_text": extracted_text[:40] if extracted_text else "★ Sígueme para más trucos de IA",
            "subtext": "Guarda este video o comenta abajo tu opinión",
            "accent_color": accent_color or "#818CF8",
            "start_time": start_time,
            "duration": duration,
            "spring_type": "smooth"
        }

    elif any(k in p_lower for k in ["nombre", "presentador", "speaker", "autor", "creador", "lower third", "pie de foto", "yo soy", "cargo"]):
        preset_id = "lower_third_glass"
        title_val = extracted_text[:28].upper() if extracted_text else "ALEX RIVERA"
        params = {
            "title": title_val,
            "subtitle": "Especialista en Automatización & IA",
            "badge": "CREADOR",
            "accent_color": accent_color or "#38BDF8",
            "start_time": start_time,
            "duration": duration,
            "spring_type": "smooth"
        }

    elif any(k in p_lower for k in ["@", "arroba", "instagram", "tiktok", "twitter", "handle", "usuario", "canal", "redes"]):
        preset_id = "social_handle"
        handle_m = re.search(r"@[a-zA-Z0-9_\.]+", prompt)
        handle_val = handle_m.group(0) if handle_m else (f"@{extracted_text.replace(' ', '_').lower()}" if extracted_text else "@alexrivera_ai")
        params = {
            "handle": handle_val,
            "platform": "TikTok / Instagram",
            "accent_color": accent_color or "#EC4899",
            "start_time": start_time,
            "duration": duration,
            "spring_type": "smooth"
        }

    elif any(k in p_lower for k in ["hook", "gancho", "titular", "titulo", "secreto", "revela", "curiosidad", "sabias que", "truco", "impacto"]):
        preset_id = "viral_hook"
        params = {
            "headline": extracted_text[:35].upper() if extracted_text else "NO COMETAS ESTE ERROR",
            "subheadline": "Mira esto antes de publicar tu próximo video",
            "badge": "ATENCIÓN",
            "accent_color": accent_color or "#F59E0B",
            "start_time": start_time if time_m else 0.2,
            "duration": duration,
            "spring_type": "snappy"
        }

    elif any(k in p_lower for k in ["cifra", "numero", "dolares", "$", "100k", "reproducciones", "seguidores", "visitas", "fans"]):
        preset_id = "number_counter"
        num_m = re.search(r"[\+\$]?\d+(?:[\.,]\d+)?\s*(?:k|m|mil|millones)?", prompt, re.IGNORECASE)
        params = {
            "number_val": num_m.group(0).upper() if num_m else "+250,000",
            "label": extracted_text[:35] if extracted_text else "Nuevas Reproducciones Orgánicas",
            "badge": "MÉTRICA REAL",
            "accent_color": accent_color or "#06B6D4",
            "start_time": start_time,
            "duration": duration,
            "spring_type": "bouncy"
        }

    elif any(k in p_lower for k in ["porcentaje", "%", "metrica", "estadistica", "crecimiento", "aumento"]):
        preset_id = "stat_callout_neon"
        pct_m = re.search(r"[\+\-]?\d+(?:\.\d+)?%", prompt)
        params = {
            "metric": pct_m.group(0) if pct_m else "+350%",
            "explanation": extracted_text[:40] if extracted_text else "Crecimiento en velocidad de producción",
            "badge": "IMPACTO",
            "accent_color": accent_color or "#10B981",
            "start_time": start_time,
            "duration": duration,
            "spring_type": "snappy"
        }

    elif any(k in p_lower for k in ["cita", "frase", "dijo", "pensamiento", "reflexion", "filosofia", "refran"]):
        preset_id = "quote_card"
        params = {
            "quote": extracted_text or prompt,
            "author": "REGLA DE ORO",
            "accent_color": accent_color or "#A855F7",
            "start_time": start_time,
            "duration": duration,
            "spring_type": "smooth"
        }

    elif any(k in p_lower for k in ["barra", "progreso", "retencion", "linea", "timeline"]):
        preset_id = "retention_bar"
        params = {
            "bar_color": accent_color or "#38BDF8",
            "height_px": 14,
            "start_time": 0.0,
            "duration": 0.0
        }

    # HyperFrames Engine Prompts
    elif any(k in p_lower for k in ["hyperframe", "hyperframes", "swiss", "reticula", "brutalismo"]):
        preset_id = "hyperframes_swiss_grid"
        params = {
            "headline": extracted_text[:30].upper() if extracted_text else "SISTEMA DETERMINISTA",
            "subheadline": "Composición geométrica 100% reproducible",
            "badge": "HYPERFRAMES",
            "accent_color": accent_color or "#EF4444",
            "start_time": start_time,
            "duration": duration,
        }

    elif any(k in p_lower for k in ["chat ia", "chatgpt", "conversacion", "burbuja chat"]):
        preset_id = "hyperframes_ai_chat_reveal"
        params = {
            "headline": extracted_text or "¿Cómo multiplicar mi alcance orgánico?",
            "subheadline": "Respuesta IA: Optimiza tus primeros 3 segundos",
            "badge": "AI CHAT",
            "accent_color": accent_color or "#10B981",
            "start_time": start_time,
            "duration": duration,
        }

    elif any(k in p_lower for k in ["comparativa", "antes vs", "vs", "versus"]):
        preset_id = "hyperframes_comparison_table"
        params = {
            "headline": extracted_text[:35].upper() if extracted_text else "MÉTODO ANTIGUO vs FACTORY IA",
            "subheadline": "3 Horas de edición ➔ 30 Segundos automatizados",
            "badge": "COMPARATIVA",
            "accent_color": accent_color or "#10B981",
            "start_time": start_time,
            "duration": duration,
        }

    # Remotion Video Prompts
    elif any(k in p_lower for k in ["remotion", "waveform", "espectro", "audio", "sonoro"]):
        preset_id = "remotion_audio_waveform"
        params = {
            "headline": extracted_text[:30].upper() if extracted_text else "ESPECTRO DE AUDIO DINÁMICO",
            "subheadline": "Sincronización rítmica por palabra",
            "badge": "REMOTION AUDIO",
            "accent_color": accent_color or "#6366F1",
            "start_time": start_time,
            "duration": duration,
        }

    elif any(k in p_lower for k in ["mockup", "iphone", "pantalla", "app demo"]):
        preset_id = "remotion_device_mockup"
        params = {
            "headline": extracted_text[:30].upper() if extracted_text else "DEMO DE APLICACIÓN EN VIVO",
            "subheadline": "Encuadre flotante con Dynamic Island",
            "badge": "IPHONE MOCKUP",
            "accent_color": accent_color or "#3B82F6",
            "start_time": start_time,
            "duration": duration,
        }

    elif any(k in p_lower for k in ["notificacion", "push", "alerta ios"]):
        preset_id = "remotion_push_notification"
        params = {
            "headline": extracted_text[:35] if extracted_text else "¡Tu video se hizo viral!",
            "subheadline": "Superaste las 250,000 reproducciones",
            "badge": "NOTIFICACIÓN",
            "accent_color": accent_color or "#10B981",
            "start_time": start_time,
            "duration": duration,
        }

    # Manim (3Blue1Brown) Prompts
    elif any(k in p_lower for k in ["manim", "formula", "latex", "ecuacion", "matematica"]):
        preset_id = "manim_math_formula"
        params = {
            "headline": extracted_text or "E = mc²",
            "subheadline": "Derivación analítica paso a paso estilo Manim",
            "badge": "📐 MANIM",
            "accent_color": accent_color or "#F59E0B",
            "start_time": start_time,
            "duration": duration,
        }

    # Motion Canvas Prompts
    elif any(k in p_lower for k in ["motion canvas", "terminal", "codigo", "consola", "typescript"]):
        preset_id = "code_walkthrough_terminal"
        params = {
            "headline": extracted_text or "const video = await factory.render();",
            "subheadline": "Pipeline programático acelerado por hardware",
            "badge": "💻 TERMINAL",
            "accent_color": accent_color or "#06B6D4",
            "start_time": start_time,
            "duration": duration,
        }

    # Motion.dev Prompts
    elif any(k in p_lower for k in ["motion.dev", "rebote", "spring", "elastico", "bouncy"]):
        preset_id = "motion_spring_elastic_card"
        params = {
            "headline": extracted_text[:30].upper() if extracted_text else "REBOTE FÍSICO REAL",
            "subheadline": "Física de resortes calibrada para máxima retención",
            "badge": "MOTION SPRING",
            "accent_color": accent_color or "#06B6D4",
            "start_time": start_time,
            "duration": duration,
        }

    # Dynamic Card Stack Prompts
    elif any(k in p_lower for k in ["flip", "pila", "stack", "cards"]):
        preset_id = "flip_card_stack"
        params = {
            "headline": extracted_text[:30].upper() if extracted_text else "3 SECRETOS PARA CRECER",
            "subheadline": "1. Hook inicial • 2. Retención • 3. CTA",
            "badge": "CARD STACK",
            "accent_color": accent_color or "#38BDF8",
            "start_time": start_time,
            "duration": duration
        }

    elif any(k in p_lower for k in ["confeti", "particulas", "celebracion"]):
        preset_id = "physics_confetti_burst"
        params = {
            "headline": extracted_text[:30].upper() if extracted_text else "¡META ALCANZADA!",
            "subheadline": "+1,000,000 DE REPRODUCCIONES",
            "badge": "CELEBRACIÓN",
            "accent_color": accent_color or "#FACC15",
            "start_time": start_time,
            "duration": duration
        }

    else:
        # Dynamic smart fallback: adapt user's text into an impactful hook or badge
        clean_text = extracted_text or prompt.strip()
        if len(clean_text) <= 30:
            preset_id = "viral_hook"
            params = {
                "headline": clean_text.upper(),
                "subheadline": "Detalle fundamental para creadores",
                "badge": "DESTACADO",
                "accent_color": accent_color or "#38BDF8",
                "start_time": start_time,
                "duration": duration,
                "spring_type": "snappy"
            }
        else:
            preset_id = "quote_card"
            params = {
                "quote": clean_text[:80],
                "author": "CLAVE DEL VIDEO",
                "accent_color": accent_color or "#38BDF8",
                "start_time": start_time,
                "duration": duration,
                "spring_type": "smooth"
            }

    return preset_id, params


@router.post("/ai-generate")
def ai_generate_motion_graphic(req: MotionAIGenerateRequest) -> Dict[str, Any]:
    """Generates motion graphic configuration and spring physics using local AI from natural language prompt."""
    
    # 1. Attempt to consult local Ollama with fast timeout
    ollama_url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    try:
        available_sample = [p["id"] for p in mg_service.get_presets()[:20]]
        sys_prompt = f"""
Actúa como director de Motion Graphics para videos verticales (TikTok, Reels, Shorts).
Analiza el pedido del usuario en lenguaje natural: '{req.prompt}'
Elige el mejor preset cinético disponible en el catálogo (ejemplos: {', '.join(available_sample[:12])}).
Devuelve ÚNICAMENTE un JSON con:
{{
  "preset_id": "...",
  "accent_color": "#HEX",
  "start_time": 1.5,
  "duration": 4.5,
  "spring_type": "bouncy" | "snappy" | "smooth",
  "params": {{ ... }}
}}
"""
        with httpx.Client(timeout=2.5) as client:
            resp = client.post(
                ollama_url,
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": sys_prompt,
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.3}
                }
            )
            if resp.status_code == 200:
                raw_json = json.loads(resp.json().get("response", "{}"))
                if "preset_id" in raw_json and "params" in raw_json:
                    pid = raw_json["preset_id"]
                    p = raw_json["params"]
                    if "accent_color" not in p and "accent_color" in raw_json:
                        p["accent_color"] = raw_json["accent_color"]
                    if "start_time" not in p and "start_time" in raw_json:
                        p["start_time"] = raw_json["start_time"]
                    if "duration" not in p and "duration" in raw_json:
                        p["duration"] = raw_json["duration"]
                    svg = mg_service.generate_preview_svg(pid, p)
                    return {
                        "status": "success",
                        "source": "ollama_llm",
                        "preset_id": pid,
                        "params": p,
                        "spring_physics": {
                            "stiffness": 380 if raw_json.get("spring_type") == "bouncy" else 260,
                            "damping": 12 if raw_json.get("spring_type") == "bouncy" else 28,
                            "mass": 1.0
                        },
                        "svg_preview": svg
                    }
    except Exception as e:
        logger.debug(f"Ollama local not reachable or timed out ({e}), using NLP parser.")

    # 2. Rich Natural Language Heuristic Parser
    preset_id, params = _nlp_extract_motion_params(req.prompt, req.video_duration or 30.0)
    svg_preview = mg_service.generate_preview_svg(preset_id, params)

    return {
        "status": "success",
        "source": "nlp_heuristics",
        "preset_id": preset_id,
        "params": params,
        "spring_physics": {
            "stiffness": 380 if params.get("spring_type") == "bouncy" else 260,
            "damping": 12 if params.get("spring_type") == "bouncy" else 28,
            "mass": 1.0
        },
        "svg_preview": svg_preview
    }


@router.get("/presets")
def list_presets() -> List[Dict[str, Any]]:
    """Returns all available motion graphics presets (built-in and custom)."""
    return mg_service.get_presets()


class CreatePresetRequest(BaseModel):
    id: Optional[str] = None
    name: str
    category: str = "🌟 Personalizados"
    description: str = "Preset personalizado guardado en la librería."
    default_params: Dict[str, Any] = Field(default_factory=dict)
    codepen_url: Optional[str] = None
    html_template: Optional[str] = None
    animation_script: Optional[str] = None


@router.post("/presets")
def create_custom_preset(req: CreatePresetRequest) -> Dict[str, Any]:
    """Adds a custom or imported CodePen preset into the library."""
    p_dict = req.model_dump()
    saved = mg_service.add_custom_preset(p_dict)
    return {"status": "success", "message": "Preset guardado en la librería.", "preset": saved}


@router.delete("/presets/{preset_id}")
def delete_custom_preset(preset_id: str) -> Dict[str, Any]:
    """Deletes a custom preset from the library."""
    success = mg_service.delete_custom_preset(preset_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Preset personalizado '{preset_id}' no encontrado o es de sólo lectura.")
    return {"status": "success", "message": f"Preset '{preset_id}' eliminado de la librería."}


@router.get("/engines")
def list_motion_graphics_engines() -> List[Dict[str, Any]]:
    """Returns all motion graphics repositories and engines integrated in the Content Factory suite."""
    modules_dir = settings.BASE_DIR / "modules"
    
    engines = [
        {
            "id": "motion_ai_kit",
            "name": "Motion AI Kit (Motion.dev / Framer Motion)",
            "repo": "motiondivision/motion",
            "path": str(modules_dir / "motion"),
            "status": "Instalado & Integrado",
            "type": "Física Elástica & WAAPI",
            "description": "Cálculo de curvas de física de muelles (spring physics) con rigidez, amortiguación y animaciones elásticas ultra fluidas en tiempo real.",
            "icon": "⚡"
        },
        {
            "id": "hyperframes",
            "name": "HyperFrames Engine (HeyGen)",
            "repo": "heygen-com/hyperframes",
            "path": str(modules_dir / "hyperframes"),
            "status": "Instalado & Integrado",
            "type": "Composición de Escenas & Overlays",
            "description": "Motor de superposición cinético sobre video con 10 presets profesionales y renderizado FFmpeg.",
            "icon": "✨"
        },
        {
            "id": "motion_canvas",
            "name": "Motion Canvas",
            "repo": "motion-canvas/motion-canvas",
            "path": str(modules_dir / "motion-canvas"),
            "status": "Instalado en modules/motion-canvas",
            "type": "Animación Procedural Vectorial (TypeScript)",
            "description": "Generador de gráficos vectoriales programáticos y transiciones continuas cuadro a cuadro con Canvas y WebCodecs.",
            "icon": "🎨"
        },
        {
            "id": "remotion",
            "name": "Remotion Studio",
            "repo": "remotion-dev/remotion",
            "path": str(modules_dir / "remotion"),
            "status": "Instalado en modules/remotion",
            "type": "Video Programático con React",
            "description": "Composición de video y motion graphics basado en componentes de React, transiciones y renderizado headless con Chromium + FFmpeg.",
            "icon": "⚛️"
        },
        {
            "id": "manim",
            "name": "Manim Community Engine (3Blue1Brown)",
            "repo": "ManimCommunity/manim",
            "path": str(modules_dir / "manim"),
            "status": "Instalado en modules/manim",
            "type": "Animación Matemática & Gráfica en Python",
            "description": "Motor en Python para crear animaciones matemáticas exactas, gráficos de datos, curvas vectoriales y visualizaciones técnicas.",
            "icon": "📐"
        }
    ]

    for eng in engines:
        p = Path(eng["path"])
        eng["is_cloned"] = p.exists() and p.is_dir()
        if not eng["is_cloned"]:
            eng["status"] = "No instalado (opcional)"
        eng.pop("path")  # don't leak absolute filesystem layout to the browser

    return engines


@router.post("/upload")
async def upload_recorded_video(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a user-recorded video to the local factory storage."""
    target_path = await save_upload(file, VIDEO_EXTENSIONS)

    # Probe video
    try:
        meta = mg_service.probe_video(str(target_path))
        return {
            "status": "success",
            "message": "Video subido correctamente al almacenamiento local.",
            "metadata": meta,
            "preview_url": f"/storage/uploads/{target_path.name}"
        }
    except Exception as e:
        logger.warning(f"Failed to probe uploaded video: {e}")
        return {
            "status": "success",
            "message": "Video subido, pero no se pudo leer metadatos detallados.",
            "path": str(target_path),
            "filename": target_path.name,
            "preview_url": f"/storage/uploads/{target_path.name}"
        }


@router.get("/uploads")
def list_uploaded_videos() -> List[Dict[str, Any]]:
    """List all previously uploaded user videos."""
    if not settings.UPLOADS_DIR.exists():
        return []

    videos = []
    for f in settings.UPLOADS_DIR.glob("*.*"):
        if f.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
            videos.append({
                "filename": f.name,
                "path": str(f.resolve()),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "url": f"/storage/uploads/{f.name}"
            })
    return sorted(videos, key=lambda x: x["filename"], reverse=True)


@router.post("/preview")
def preview_motion_graphic(req: PreviewRequest) -> Dict[str, Any]:
    """Generates an SVG preview markup for instant browser display."""
    svg_markup = mg_service.generate_preview_svg(
        preset_id=req.preset_id,
        params=req.params,
        width=req.width,
        height=req.height
    )
    return {"preset_id": req.preset_id, "svg": svg_markup}


@router.post("/apply")
def apply_motion_graphic(req: ApplyMotionGraphicsRequest) -> Dict[str, Any]:
    """Applies a selected motion graphic overlay onto the user video using local FFmpeg."""
    video = resolve_media_path(req.video_path)
    output = resolve_output_path(req.output_path)

    try:
        out_path = mg_service.composite_motion_graphic(
            video_path=str(video),
            preset_id=req.preset_id,
            params=req.params,
            output_path=str(output) if output else None
        )
        out_file = Path(out_path)
        return {
            "status": "completed",
            "message": "Motion graphic integrado exitosamente en el video.",
            "output_path": str(out_file),
            "filename": out_file.name,
            "preview_url": f"/storage/outputs/{out_file.name}",
            "size_mb": round(out_file.stat().st_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Error applying motion graphic: {e}")
        raise HTTPException(status_code=500, detail="Error en renderizado de motion graphics. Revisa storage/server.log.")

