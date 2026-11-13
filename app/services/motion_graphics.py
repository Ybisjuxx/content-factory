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
from app.security import escape_markup_params, safe_filename, sanitize_hex_color

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
        self.custom_presets_file = self.cache_dir / "custom_presets.json"

    def get_presets(self) -> List[Dict[str, Any]]:
        """Returns the complete library of motion graphics presets (built-in and custom)."""
        built_in = [
            # 0. Transiciones Cinemáticas & Wipes de Video
            {
                "id": "transition_neon_slice_wipe",
                "name": "Transición: Barrido Neón Diagonal (Slice Wipe)",
                "category": "Transiciones Cinemáticas",
                "description": "Haz de luz láser neón que cruza la pantalla en diagonal con estela luminosa para cambiar de plano o escena.",
                "default_params": {
                    "headline": "CAMBIO DE ESCENA",
                    "subheadline": "Transición Cinemática 60 FPS",
                    "badge": "NEON SLICE",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.5,
                }
            },
            {
                "id": "transition_flip_3d_turn",
                "name": "Transición: Volteo 3D de Plano (Perspective Flip)",
                "category": "Transiciones Cinemáticas",
                "description": "Giro espacial tridimensional del encuadre sobre el eje Y con reflejo y profundidad para cortes de video.",
                "default_params": {
                    "headline": "NUEVO CAPÍTULO",
                    "subheadline": "Giro Tridimensional de Escena",
                    "badge": "3D FLIP",
                    "accent_color": "#EC4899",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.5,
                }
            },
            {
                "id": "transition_stagger_grid_curtain",
                "name": "Transición: Persiana de Malla en Cascada (Stagger Grid)",
                "category": "Transiciones Cinemáticas",
                "description": "Malla de bloques geométricos translúcidos que cubren la pantalla en cascada elástica y la descubren para transicionar.",
                "default_params": {
                    "headline": "SIGUIENTE TEMA",
                    "subheadline": "Cascada Dinámica de Revelación",
                    "badge": "GRID CURTAIN",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.8,
                }
            },
            {
                "id": "transition_kinetic_zoom_push",
                "name": "Transición: Empuje de Cámara & Warp (Zoom Rush)",
                "category": "Transiciones Cinemáticas",
                "description": "Empuje de velocidad hiperbólica hacia adelante con anillos de enfoque cinemático y aceleración de corte inercial.",
                "default_params": {
                    "headline": "VELOCIDAD HIPERBÓLICA",
                    "subheadline": "Aceleración de Corte Inercial",
                    "badge": "ZOOM RUSH",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.2,
                }
            },
            {
                "id": "transition_split_mask_reveal",
                "name": "Transición: Apertura en Dos Mitades (Split Gate)",
                "category": "Transiciones Cinemáticas",
                "description": "Pantalla dividida con haz central que se abre en dos compuertas deslizantes hacia arriba y abajo revelando la nueva toma.",
                "default_params": {
                    "headline": "REVELACIÓN DE TOMA",
                    "subheadline": "Compuerta Cinemática Deslizante",
                    "badge": "SPLIT GATE",
                    "accent_color": "#818CF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.5,
                }
            },
            {
                "id": "transition_glitch_flash_warp",
                "name": "Transición: Cyber Glitch & Flash Estroboscópico",
                "category": "Transiciones Cinemáticas",
                "description": "Corte rítmico con destello estroboscópico, distorsión horizontal y aberración cromática para hooks de impacto.",
                "default_params": {
                    "headline": "GLITCH CINEMÁTICO",
                    "subheadline": "Distorsión Digital de Impacto",
                    "badge": "CYBER GLITCH",
                    "accent_color": "#F43F5E",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.0,
                }
            },
            {
                "id": "transition_circle_iris_expand",
                "name": "Transición: Apertura Iris Circular (Radial Iris)",
                "category": "Transiciones Cinemáticas",
                "description": "Apertura circular expansiva con anillo de halo neón desde el punto focal hacia los bordes de la pantalla.",
                "default_params": {
                    "headline": "FOCO PRINCIPAL",
                    "subheadline": "Expansión Radial Cinemática",
                    "badge": "RADIAL IRIS",
                    "accent_color": "#06B6D4",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.4,
                }
            },

            # 1. Tipografía Cinética (SplitText & Scramble)
            {
                "id": "split_chars_stagger",
                "name": "SplitText: Carácter por Carácter (Cascada 3D)",
                "category": "Tipografía Cinética",
                "description": "Desglose cinético letra por letra con rotación 3D y rebote elástico.",
                "default_params": {
                    "headline": "TITULAR CINÉTICO",
                    "subheadline": "Efecto letra por letra con física cinemática",
                    "badge": "SPLITTEXT",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 4.0,
                    "spring_type": "bouncy"
                }
            },
            {
                "id": "split_words_pop",
                "name": "SplitText: Palabra por Palabra Pop (TikTok Viral)",
                "category": "Tipografía Cinética",
                "description": "Aparición palabra por palabra con escala elástica para retención instantánea.",
                "default_params": {
                    "headline": "EL SECRETO VIRAL",
                    "subheadline": "Palabras sincronizadas con ritmo dinámico",
                    "badge": "VIRAL POP",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 3.5,
                    "spring_type": "bouncy"
                }
            },
            {
                "id": "split_lines_mask",
                "name": "SplitText: Revelación por Líneas con Máscara",
                "category": "Tipografía Cinética",
                "description": "Líneas de texto que emergen desde una máscara invisible estilo documental premium.",
                "default_params": {
                    "headline": "EL FUTURO ES HOY",
                    "subheadline": "Documental cinematográfico con animación de máscara",
                    "badge": "CINEMATIC",
                    "accent_color": "#818CF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                    "spring_type": "smooth"
                }
            },
            {
                "id": "scramble_matrix",
                "name": "ScrambleText: Decodificación Cyberpunk",
                "category": "Tipografía Cinética",
                "description": "Efecto Matrix de caracteres aleatorios que se decodifican hasta revelar el mensaje.",
                "default_params": {
                    "headline": "SISTEMA DESBLOQUEADO",
                    "subheadline": "Acceso al protocolo de inteligencia artificial",
                    "badge": "CYBERPUNK",
                    "accent_color": "#06B6D4",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 4.0,
                    "spring_type": "snappy"
                }
            },
            {
                "id": "typewriter_cursor",
                "name": "Máquina de Escribir con Cursor Parpadeante",
                "category": "Tipografía Cinética",
                "description": "Mecanografiado progresivo letra por letra con cursor parpadeante en tiempo real.",
                "default_params": {
                    "headline": "PROMPT DE IA GENERADO...",
                    "subheadline": "Construyendo modelo predictivo en vivo",
                    "badge": "TYPEWRITER",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 4.5,
                    "spring_type": "smooth"
                }
            },
            {
                "id": "kinetic_typography_scale",
                "name": "Tipografía Cinética Explosiva (Impact Zoom)",
                "category": "Tipografía Cinética",
                "description": "Texto gigante con zoom de impacto que frena en seco para captar la atención.",
                "default_params": {
                    "headline": "¡MIRA ESTO AHORA!",
                    "subheadline": "Impacto visual con escala desacelerada",
                    "badge": "IMPACTO",
                    "accent_color": "#EF4444",
                    "position": "center",
                    "start_time": 0.2,
                    "duration": 3.0,
                    "spring_type": "snappy"
                }
            },

            # 2. Identificación & Títulos (Lower Thirds & Glass)
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
                "id": "lower_third_neon_edge",
                "name": "Lower Third Cyber Neón con Borde Brillante",
                "category": "Identificación & Speaker",
                "description": "Borde perimetral neón con resplandor pulsante y tipografía técnica.",
                "default_params": {
                    "title": "ING. CARLOS VÉLEZ",
                    "subtitle": "Arquitecto de Sistemas Distribuidos",
                    "accent_color": "#10B981",
                    "badge": "CYBER TECH",
                    "position": "bottom",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "lower_third_magazine",
                "name": "Lower Third Editorial / Magazine (Clean Line)",
                "category": "Identificación & Speaker",
                "description": "Diseño editorial de revista de lujo con trazo fino minimalista y tipografía serif.",
                "default_params": {
                    "title": "SOFÍA MONTES",
                    "subtitle": "Directora Creativa & Estrategia",
                    "accent_color": "#F43F5E",
                    "badge": "EDITORIAL",
                    "position": "bottom",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "social_handle",
                "name": "Badge de Redes Sociales (@Handle)",
                "category": "Identificación & Speaker",
                "description": "Cápsula flotante minimalista con tu arroba de TikTok, Instagram, YouTube o X.",
                "default_params": {
                    "handle": "@alexrivera_ai",
                    "platform": "TikTok / Instagram",
                    "accent_color": "#EC4899",
                    "position": "top_left",
                    "start_time": 2.0,
                    "duration": 6.0,
                    "spring_type": "smooth"
                }
            },
            {
                "id": "quote_card",
                "name": "Tarjeta de Cita / Frase en Cristal",
                "category": "Identificación & Speaker",
                "description": "Tarjeta elegante de vidrio esmerilado con comillas cinéticas para destacar una frase poderosa.",
                "default_params": {
                    "quote": "La clave de la viralidad no es la suerte, sino la retención del primer segundo.",
                    "author": "REGLA DE ORO",
                    "accent_color": "#A855F7",
                    "position": "center",
                    "start_time": 2.0,
                    "duration": 5.0,
                    "spring_type": "snappy"
                }
            },
            {
                "id": "news_ticker_breaking",
                "name": "Cintillo de Última Hora (Breaking News)",
                "category": "Identificación & Speaker",
                "description": "Franja inferior de noticias urgentes con alerta roja parpadeante de última hora.",
                "default_params": {
                    "headline": "ÚLTIMA HORA: LANZAMIENTO OFICIAL",
                    "subheadline": "Nueva actualización liberada para todos los usuarios",
                    "badge": "🔴 NOTICIA",
                    "accent_color": "#EF4444",
                    "position": "bottom_edge",
                    "start_time": 1.0,
                    "duration": 6.0,
                }
            },
            {
                "id": "creator_profile_pill",
                "name": "Pill de Perfil Verificado (Blue Checkmark)",
                "category": "Identificación & Speaker",
                "description": "Píldora flotante con icono de usuario verificado oficial y conteo de comunidad.",
                "default_params": {
                    "title": "Alex Rivera ✔",
                    "subtitle": "500K Seguidores en Comunidad",
                    "badge": "VERIFICADO",
                    "accent_color": "#38BDF8",
                    "position": "top_left",
                    "start_time": 1.5,
                    "duration": 5.0,
                }
            },

            # 3. Métricas, Estadísticas & Finanzas
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
                "id": "number_counter",
                "name": "Contador Numérico Dinámico",
                "category": "Datos & Viralidad",
                "description": "Cifra gigante con anillo de brillo neón para enfatizar resultados o seguidores.",
                "default_params": {
                    "number_val": "+250,000",
                    "label": "Nuevas Reproducciones Orgánicas",
                    "badge": "MÉTRICA REAL",
                    "accent_color": "#06B6D4",
                    "position": "bottom_card",
                    "start_time": 1.0,
                    "duration": 4.5,
                    "spring_type": "bouncy"
                }
            },
            {
                "id": "crypto_stock_badge",
                "name": "Ticker Bursátil / Crypto (Subida Verde)",
                "category": "Datos & Viralidad",
                "description": "Insignia financiera animada con porcentaje de subida en verde neón y flecha de tendencia.",
                "default_params": {
                    "headline": "BTC / USD  ▲ +24.8%",
                    "subheadline": "$98,450.00 — Máximo Histórico",
                    "badge": "MERCADO",
                    "accent_color": "#10B981",
                    "position": "top_right",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "percentage_circle_gauge",
                "name": "Medidor Circular de Porcentaje (Radial Gauge)",
                "category": "Datos & Viralidad",
                "description": "Arco de progreso circular que se completa con brillo neón hasta el 88%.",
                "default_params": {
                    "headline": "88% EFECTIVIDAD",
                    "subheadline": "Tasa de conversión alcanzada",
                    "badge": "RENDIMIENTO",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 1.5,
                    "duration": 4.0,
                }
            },
            {
                "id": "bar_chart_grow",
                "name": "Gráfico de Barras Animado en Crecimiento",
                "category": "Datos & Viralidad",
                "description": "Comparativa de barras verticales que crecen dinámicamente frente al espectador.",
                "default_params": {
                    "headline": "ANTES vs AHORA",
                    "subheadline": "Incremento de 10x en visualizaciones",
                    "badge": "COMPARATIVA",
                    "accent_color": "#F59E0B",
                    "position": "bottom_card",
                    "start_time": 1.5,
                    "duration": 4.5,
                }
            },

            # 4. Retención & Cues Visuales (Hooks)
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
                "id": "attention_arrow",
                "name": "Flecha de Atención & Alerta Neón",
                "category": "Retención & Cues",
                "description": "Flecha brillante y badge palpitante para dirigir la mirada del espectador a un detalle clave.",
                "default_params": {
                    "label": "¡OJO CON ESTO!",
                    "sublabel": "Detalle que la mayoría ignora",
                    "accent_color": "#EF4444",
                    "direction": "down",
                    "position": "center",
                    "start_time": 1.5,
                    "duration": 4.0,
                    "spring_type": "bouncy"
                }
            },
            {
                "id": "warning_alert",
                "name": "Alerta Crítica (Detén el Scroll)",
                "category": "Retención & Cues",
                "description": "Caja de alerta estilo advertencia con franjas diagonales de alto impacto para hooks.",
                "default_params": {
                    "warning_title": "¡DETÉNTE AQUÍ!",
                    "warning_desc": "Si haces esto tu cuenta puede ser penalizada",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 0.2,
                    "duration": 3.2,
                    "spring_type": "snappy"
                }
            },
            {
                "id": "highlighter_marker_draw",
                "name": "Marcador Fluorescente Subrayado (DrawSVG Marker)",
                "category": "Retención & Cues",
                "description": "Trazo amarillo fluorescente que subraya la palabra clave como si se dibujara en vivo.",
                "default_params": {
                    "headline": "PALABRA CLAVE",
                    "subheadline": "El concepto fundamental del video",
                    "badge": "DESTACADO",
                    "accent_color": "#FACC15",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 4.0,
                }
            },
            {
                "id": "retention_bar",
                "name": "Barra de Retención Viral (Progress Bar)",
                "category": "Retención & Cues",
                "description": "Barra de progreso animada en el borde inferior que avanza a lo largo del video.",
                "default_params": {
                    "bar_color": "#38BDF8",
                    "height_px": 14,
                    "position": "bottom_edge",
                    "start_time": 0.0,
                    "duration": 0.0,
                }
            },
            {
                "id": "retention_timer_countdown",
                "name": "Cuenta Regresiva de Retención (00:03 Cronómetro)",
                "category": "Retención & Cues",
                "description": "Cronómetro visual que indica al espectador que espere hasta el final del video.",
                "default_params": {
                    "headline": "⏱ ESPERA AL SEGUNDO 10",
                    "subheadline": "El resultado final te sorprenderá",
                    "badge": "CRONÓMETRO",
                    "accent_color": "#EC4899",
                    "position": "top_right",
                    "start_time": 0.5,
                    "duration": 4.0,
                }
            },

            # 5. Conversión & CTAs
            {
                "id": "cta_badge",
                "name": "Llamado a la Acción (Animated CTA)",
                "category": "Conversión & CTAs",
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
                "id": "cta_link_in_bio",
                "name": "Badge: Enlace en Biografía (Link in Bio)",
                "category": "Conversión & CTAs",
                "description": "Botón con flecha indicativa y texto directo hacia el link del perfil.",
                "default_params": {
                    "headline": "🔗 ENLACE EN LA BIO",
                    "subheadline": "Descarga las herramientas gratis en el perfil",
                    "badge": "ACCESO GRATIS",
                    "accent_color": "#38BDF8",
                    "position": "bottom",
                    "start_time": 4.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "save_share_reminder",
                "name": "Recordatorio: Guarda y Comparte (Bookmark)",
                "category": "Conversión & CTAs",
                "description": "Animación que señala el botón de favoritos y compartir para impulsar el algoritmo.",
                "default_params": {
                    "headline": "🔖 GUARDA ESTE VIDEO",
                    "subheadline": "Compártelo con un amigo que lo necesite",
                    "badge": "ALGORITMO",
                    "accent_color": "#F59E0B",
                    "position": "bottom_right",
                    "start_time": 5.0,
                    "duration": 4.0,
                }
            },
            {
                "id": "discount_code_badge",
                "name": "Tarjeta de Cupón / Código Descuento (-50% OFF)",
                "category": "Conversión & CTAs",
                "description": "Cupón con borde punteado para monetización y promociones de productos o afiliados.",
                "default_params": {
                    "headline": "CÓDIGO: FACTORY50",
                    "subheadline": "50% de descuento válido por 24 horas",
                    "badge": "🏷 OFERTA ESPECIAL",
                    "accent_color": "#10B981",
                    "position": "bottom",
                    "start_time": 3.0,
                    "duration": 5.0,
                }
            },

            # 6. Animación Científica & Matemática (Manim / 3Blue1Brown)
            {
                "id": "manim_math_formula",
                "name": "Manim: Fórmula Matemática & Derivación (LaTeX)",
                "category": "Animación Científica (Manim)",
                "description": "Tarjeta analítica de fórmula matemática (ej. E = mc² o Bayes) con desglose y estilo 3Blue1Brown.",
                "default_params": {
                    "headline": "E = mc²",
                    "subheadline": "Energía = Masa × Velocidad de la Luz al Cuadrado",
                    "badge": "📐 FÓRMULA MANIM",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "manim_coordinate_plot",
                "name": "Manim: Gráfico de Función Cartesiana (f(x))",
                "category": "Animación Científica (Manim)",
                "description": "Plano cartesiano con ejes X/Y, cuadrícula técnica y trazado vectorial de curva matemática continua.",
                "default_params": {
                    "headline": "f(x) = 1 / (1 + e^-x)",
                    "subheadline": "Función Sigmoide de Activación Neuronal",
                    "badge": "📈 PLANO CARTESIANO",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "manim_geometry_vector",
                "name": "Manim: Vectores & Geometría Analítica",
                "category": "Animación Científica (Manim)",
                "description": "Representación geométrica con flechas vectoriales en 2D/3D y cálculo de producto punto.",
                "default_params": {
                    "headline": "v · w = ||v|| ||w|| cos(θ)",
                    "subheadline": "Proyección y ortogonalidad en espacio euclídeo",
                    "badge": "📐 GEOMETRÍA",
                    "accent_color": "#EC4899",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "manim_neural_network_layers",
                "name": "Manim: Capas de Red Neuronal Profunda",
                "category": "Animación Científica (Manim)",
                "description": "Visualización estilo 3Blue1Brown de capas densas con neuronas interconectadas y pesos sinápticos.",
                "default_params": {
                    "headline": "RED NEURONAL MULTICAPA",
                    "subheadline": "Capa de Entrada ➔ Ocultas (ReLU) ➔ Salida Softmax",
                    "badge": "🧠 DEEP LEARNING",
                    "accent_color": "#818CF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "manim_fourier_series",
                "name": "Manim: Serie de Fourier & Epiciclos",
                "category": "Animación Científica (Manim)",
                "description": "Vectores rotatorios en cadena trazando ondas armónicas complejas con elegancia matemática.",
                "default_params": {
                    "headline": "TRANSFORMADA DE FOURIER",
                    "subheadline": "Descomposición armónica en el dominio de la frecuencia",
                    "badge": "〰️ FOURIER",
                    "accent_color": "#06B6D4",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },

            # 7. Código & Diagramas Procedurales (Motion Canvas)
            {
                "id": "code_walkthrough_terminal",
                "name": "Motion Canvas: Terminal de Código con Cursor",
                "category": "Código & Diagramas (Motion Canvas)",
                "description": "Ventana de código macOS (botones rojo/amarillo/verde), sintaxis coloreada, números de línea y cursor titilante.",
                "default_params": {
                    "headline": "const short = await factory.render();",
                    "subheadline": "Pipeline programático con TypeScript y WebCodecs",
                    "badge": "💻 TERMINAL",
                    "accent_color": "#06B6D4",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "flowchart_nodes_diagram",
                "name": "Motion Canvas: Diagrama de Nodos & Arquitectura",
                "category": "Código & Diagramas (Motion Canvas)",
                "description": "Tres nodos interconectados con pulsos de datos vectoriales simulando una arquitectura de microservicios.",
                "default_params": {
                    "headline": "API Gateway ➔ Workers ➔ FFmpeg",
                    "subheadline": "Arquitectura concurrente sin servidor externo",
                    "badge": "🔀 ARQUITECTURA",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "tech_stack_pill_orbit",
                "name": "Motion Canvas: Stack Tecnológico (Badges)",
                "category": "Código & Diagramas (Motion Canvas)",
                "description": "Insignias conectadas con tecnologías destacadas (Python • Fast-API • Motion • Remotion).",
                "default_params": {
                    "headline": "Python 3.12 + FastAPI + Remotion",
                    "subheadline": "Stack ultra eficiente 100% offline y local",
                    "badge": "⚡ TECH STACK",
                    "accent_color": "#A855F7",
                    "position": "bottom",
                    "start_time": 2.0,
                    "duration": 4.5,
                }
            },
            {
                "id": "motion_canvas_matrix_transform",
                "name": "Motion Canvas: Transformación Vectorial & Matrices",
                "category": "Código & Diagramas (Motion Canvas)",
                "description": "Espacio vectorial 2D transformándose suavemente mediante multiplicación matricial de rotación y escalado.",
                "default_params": {
                    "headline": "[ cos θ  -sin θ ] · [ x ]",
                    "subheadline": "Álgebra lineal programática renderizada en Canvas",
                    "badge": "🔢 MATRICES",
                    "accent_color": "#EC4899",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "motion_canvas_binary_tree",
                "name": "Motion Canvas: Árbol Binario & Algoritmos",
                "category": "Código & Diagramas (Motion Canvas)",
                "description": "Estructura de datos con recorrido BFS/DFS iluminando nodos activos para explicaciones técnicas.",
                "default_params": {
                    "headline": "BÚSQUEDA BINARIA O(log n)",
                    "subheadline": "Recorrido recursivo paso a paso de alta fidelidad",
                    "badge": "🌳 ALGORITMOS",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },

            # 8. Social UI & Video Programático (Remotion)
            {
                "id": "remotion_audio_waveform",
                "name": "Remotion: Espectro Sonoro (Waveform Reactivo)",
                "category": "Social & Video UI (Remotion)",
                "description": "Ecualizador de audio visual con barras oscilantes simulando la respuesta en frecuencia de la voz/música.",
                "default_params": {
                    "headline": "ESPECTRO DE AUDIO DINÁMICO",
                    "subheadline": "Sincronización rítmica por palabra Faster-Whisper",
                    "badge": "🎙️ AUDIO SPECTRUM",
                    "accent_color": "#6366F1",
                    "position": "bottom",
                    "start_time": 0.5,
                    "duration": 6.0,
                }
            },
            {
                "id": "remotion_device_mockup",
                "name": "Remotion: Mockup Flotante de iPhone (Dynamic Island)",
                "category": "Social & Video UI (Remotion)",
                "description": "Chasis minimalista de smartphone con Dynamic Island, bisel estilizado y marco para capturas o apps.",
                "default_params": {
                    "headline": "DEMO DE APLICACIÓN EN VIVO",
                    "subheadline": "Grabación enmarcada con perspectiva 3D",
                    "badge": "📱 MOCKUP IPHONE",
                    "accent_color": "#3B82F6",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "remotion_push_notification",
                "name": "Remotion: Notificación Push Estilo iOS",
                "category": "Social & Video UI (Remotion)",
                "description": "Banner de notificación emergente estilo iOS con logo de app, nombre de remitente, hora y mensaje.",
                "default_params": {
                    "headline": "¡Tu video se hizo viral!",
                    "subheadline": "Superaste las 250,000 reproducciones orgánicas",
                    "badge": "🔔 NOTIFICACIÓN",
                    "accent_color": "#10B981",
                    "position": "top",
                    "start_time": 0.5,
                    "duration": 4.0,
                }
            },
            {
                "id": "remotion_split_screen_duet",
                "name": "Remotion: Pantalla Dividida (Dúo / Podcast)",
                "category": "Social & Video UI (Remotion)",
                "description": "División de encuadre en dos cuadrantes estilizados con marco neón para reacciones o entrevistas.",
                "default_params": {
                    "headline": "DEBATE / REACCIÓN VIRAL",
                    "subheadline": "Host A vs Creador Invitado B",
                    "badge": "👥 SPLIT SCREEN",
                    "accent_color": "#EC4899",
                    "position": "center",
                    "start_time": 0.0,
                    "duration": 6.0,
                }
            },
            {
                "id": "remotion_kinetic_subtitles",
                "name": "Remotion: Subtítulos Reactivos por Palabra",
                "category": "Social & Video UI (Remotion)",
                "description": "Texto dinámico sincronizado con audio, resaltado palabra por palabra en amarillo neón con fondo oscuro.",
                "default_params": {
                    "headline": "ESTE ES EL SECRETO EXACTO",
                    "subheadline": "Sincronizado a 60 fps con Faster-Whisper",
                    "badge": "SUBTÍTULOS REMOTION",
                    "accent_color": "#FACC15",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.0,
                }
            },
            {
                "id": "remotion_audiogram_glow",
                "name": "Remotion: Audiograma de Podcast con Anillo Neón",
                "category": "Social & Video UI (Remotion)",
                "description": "Tarjeta circular con forma de onda de audio radial y brillo estroboscópico para clips de podcast.",
                "default_params": {
                    "headline": "PODCAST EPISODIO #42",
                    "subheadline": "Conversación con expertos en Inteligencia Artificial",
                    "badge": "AUDIOGRAMA",
                    "accent_color": "#818CF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "remotion_social_stat_counter",
                "name": "Remotion: Contador de Redes Sociales con Avatar",
                "category": "Social & Video UI (Remotion)",
                "description": "Tarjeta flotante estilo perfil social con foto, insignia verificada y contador animado de seguidores.",
                "default_params": {
                    "headline": "+100,000 SEGUIDORES",
                    "subheadline": "Comunidad en crecimiento exponencial",
                    "badge": "CRECIMIENTO SOCIAL",
                    "accent_color": "#EC4899",
                    "position": "top",
                    "start_time": 1.0,
                    "duration": 4.5,
                }
            },
            {
                "id": "remotion_kinetic_quote_reel",
                "name": "Remotion: Frase Editorial Reel con Tipografía Dinámica",
                "category": "Social & Video UI (Remotion)",
                "description": "Cita célebre cinematográfica con tipografía editorial en alto contraste para reflexiones de retención.",
                "default_params": {
                    "headline": "«LA CONSTANCIA VENCE AL TALENTO»",
                    "subheadline": "Principio fundamental para creadores de contenido",
                    "badge": "EDITORIAL REEL",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },

            # 9. Layout & Morphing (Cinemática Avanzada para Video)
            {
                "id": "flip_card_stack",
                "name": "Pila de Tarjetas Dinámica (Card Stack Shuffle)",
                "category": "Layout & Morphing",
                "description": "Pila de tarjetas 3D interactivas con reorganización cinemática y transición suave integrada.",
                "default_params": {
                    "headline": "3 SECRETOS PARA CRECER",
                    "subheadline": "1. Hook inicial • 2. Retención • 3. CTA claro",
                    "badge": "CARD STACK",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "proximity_scale_grid",
                "name": "Proximity Scale Grid: Rejilla Reactiva Dinámica",
                "category": "Layout & Morphing",
                "description": "Matriz de micro-tarjetas que escalan dinámicamente según la proximidad al punto focal, captando atención instantánea.",
                "default_params": {
                    "headline": "FOCO DE ATENCIÓN",
                    "subheadline": "Distorsión magnética por proximidad",
                    "badge": "PROXIMITY GRID",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.5,
                }
            },
            {
                "id": "velocity_skew",
                "name": "Velocity Skew: Deformación Cinética por Inercia",
                "category": "Retención & Cues",
                "description": "Tarjeta cinemática que se inclina dinámicamente con inercia física de aceleración y desaceleración brusca.",
                "default_params": {
                    "headline": "VELOCIDAD EXTREMA",
                    "subheadline": "Inercia y aceleración calculada en tiempo real",
                    "badge": "VELOCITY SKEW",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.0,
                }
            },
            {
                "id": "scrubbed_bento_gallery",
                "name": "Bento Gallery: Mosaico Asimétrico Dinámico",
                "category": "Layout & Morphing",
                "description": "Mosaico Bento estilo Apple/TikTok con 3 cuadrantes asimétricos con bordes neón y resaltado simultáneo.",
                "default_params": {
                    "headline": "CARACTERÍSTICAS PRO",
                    "subheadline": "1. Ultrarrápido • 2. IA Local • 3. Sin Coste",
                    "badge": "BENTO SHOWCASE",
                    "accent_color": "#A855F7",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "directional_marquee",
                "name": "Marquee Bidireccional: Cintas Cinéticas Cruzadas",
                "category": "Tipografía Cinética",
                "description": "Dos cintas tipográficas de texto continuo en direcciones opuestas para captar la atención de inmediato en el hook inicial.",
                "default_params": {
                    "headline": "NOTICIA DE IMPACTO • TENDENCIA VIRAL • NO TE LO PIERDAS",
                    "subheadline": "ACCESO ANTICIPADO • NUEVO ALGORITMO • DESCÚBRELO HOY",
                    "badge": "MARQUEE TAPE",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 0.2,
                    "duration": 4.0,
                    "codepen_url": "https://codepen.io/GreenSock/pen/zYaxEKV"
                }
            },
            {
                "id": "cursor_tilt_3d",
                "name": "Perspective Tilt 3D: Tarjeta Holográfica Espacial",
                "category": "Identificación & Speaker",
                "description": "Tarjeta en perspectiva 3D con reflejo luminoso y brillo que rota espacialmente sobre el metraje de video.",
                "default_params": {
                    "headline": "MODELO HOLOGRÁFICO",
                    "subheadline": "Perspectiva tridimensional flotante con reflejo",
                    "badge": "3D PERSPECTIVE",
                    "accent_color": "#EC4899",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 4.5,
                    "codepen_url": "https://codepen.io/GreenSock/pen/qBzaNQy"
                }
            },
            {
                "id": "physics_confetti_burst",
                "name": "Physics2D Burst: Explosión de Partículas & Confeti",
                "category": "Datos & Viralidad",
                "description": "Explosión de confeti y partículas coloridas con física de gravedad para celebrar hitos, métricas récord o descuentos.",
                "default_params": {
                    "headline": "¡META ALCANZADA!",
                    "subheadline": "+1,000,000 DE REPRODUCCIONES",
                    "badge": "CELEBRACIÓN",
                    "accent_color": "#FACC15",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 4.0,
                    "codepen_url": "https://codepen.io/GreenSock/pen/VwGdvj"
                }
            },

            # 10. Cinemática Determinista (HyperFrames Engine)
            {
                "id": "hyperframes_swiss_grid",
                "name": "HyperFrames: Retícula Suiza Asimétrica (Brutalismo)",
                "category": "Cinemática Determinista (HyperFrames)",
                "description": "Diseño editorial suizo con líneas geométricas precisas, proporciones áureas y contraste brutalista.",
                "default_params": {
                    "headline": "SISTEMA DETERMINISTA",
                    "subheadline": "Composición geométrica 100% reproducible por fotograma",
                    "badge": "SWISS GRID",
                    "accent_color": "#EF4444",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.5,
                }
            },
            {
                "id": "hyperframes_kinetic_type",
                "name": "HyperFrames: Tipografía Cinética Gigante",
                "category": "Cinemática Determinista (HyperFrames)",
                "description": "Texto a pantalla completa con máscara de recorte y desplazamiento vectorial continuo.",
                "default_params": {
                    "headline": "IMPACTO VISUAL",
                    "subheadline": "Tipografía pesada con renderizado vectorial subpíxel",
                    "badge": "KINETIC TYPE",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.0,
                }
            },
            {
                "id": "hyperframes_ai_chat_reveal",
                "name": "HyperFrames: Interfaz de Chat IA en Tiempo Real",
                "category": "Cinemática Determinista (HyperFrames)",
                "description": "Burbujas de conversación tipo ChatGPT/Claude que se revelan con pulsos luminosos y respuestas automáticas.",
                "default_params": {
                    "headline": "¿Cómo multiplicar mi alcance x10?",
                    "subheadline": "Respuesta IA: Optimiza tu hook inicial y retención de 3s",
                    "badge": "AI CHAT PROMPT",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "hyperframes_product_promo",
                "name": "HyperFrames: Vitrina de Producto con Badges",
                "category": "Cinemática Determinista (HyperFrames)",
                "description": "Tarjeta flotante con especificaciones técnicas, precio o beneficio clave y resplandor perimetral.",
                "default_params": {
                    "headline": "NUEVO MODELO DISPONIBLE",
                    "subheadline": "GPU Local • Sin Suscripción • Rendimiento Extremo",
                    "badge": "LANZAMIENTO",
                    "accent_color": "#F59E0B",
                    "position": "bottom",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "hyperframes_comparison_table",
                "name": "HyperFrames: Tabla Comparativa A vs B",
                "category": "Cinemática Determinista (HyperFrames)",
                "description": "Dos paneles con iconos de cruz y palomita verde comparando el método obsoleto vs la nueva solución.",
                "default_params": {
                    "headline": "MÉTODO ANTIGUO vs FACTORY IA",
                    "subheadline": "3 Horas de edición ➔ 30 Segundos automatizados",
                    "badge": "COMPARATIVA PRO",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 5.0,
                }
            },
            {
                "id": "hyperframes_decision_tree",
                "name": "HyperFrames: Diagrama de Flujo / Árbol de Decisiones",
                "category": "Cinemática Determinista (HyperFrames)",
                "description": "Bifurcación de rutas que guía visualmente al espectador a través de un proceso lógico o embudo.",
                "default_params": {
                    "headline": "RUTA DE CONVERSIÓN",
                    "subheadline": "Paso 1: Gancho ➔ Paso 2: Valor ➔ Paso 3: CTA",
                    "badge": "FLUJO DECISIÓN",
                    "accent_color": "#A855F7",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 4.5,
                }
            },

            # 11. Física & Gestos (Motion.dev Engine)
            {
                "id": "motion_spring_elastic_card",
                "name": "Motion.dev: Tarjeta Elástica Bouncy Spring",
                "category": "Física & Gestos (Motion.dev)",
                "description": "Efecto de rebote físico calibrado con stiffness 300 y damping 15 para entradas orgánicas y llamativas.",
                "default_params": {
                    "headline": "REBOTE FÍSICO REAL",
                    "subheadline": "Curva elástica natural sin rigidez digital",
                    "badge": "MOTION SPRING",
                    "accent_color": "#06B6D4",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.0,
                }
            },
            {
                "id": "motion_stagger_pill_cascade",
                "name": "Motion.dev: Cascada Escalonada (Stagger Pills)",
                "category": "Física & Gestos (Motion.dev)",
                "description": "Tres pastillas informativas que caen una tras otra con desfase rítmico para enumerar beneficios.",
                "default_params": {
                    "headline": "3 VENTAJAS INMEDIATAS",
                    "subheadline": "1. 100% Local • 2. Cero Coste • 3. Máxima Privacidad",
                    "badge": "STAGGER CASCADE",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 4.5,
                }
            },
            {
                "id": "motion_layout_morph_expand",
                "name": "Motion.dev: Expansión de Layout Morphing",
                "category": "Física & Gestos (Motion.dev)",
                "description": "Una pequeña pastilla que se expande suavemente hasta convertirse en una tarjeta panorámica de contenido.",
                "default_params": {
                    "headline": "EXPANSIÓN CINEMÁTICA",
                    "subheadline": "De píldora compacta a ventana informativa completa",
                    "badge": "LAYOUT MORPH",
                    "accent_color": "#818CF8",
                    "position": "center",
                    "start_time": 0.8,
                    "duration": 4.5,
                }
            },
            {
                "id": "motion_inertia_draggable_card",
                "name": "Motion.dev: Inercia de Arrastre Dinámica",
                "category": "Física & Gestos (Motion.dev)",
                "description": "Tarjeta que simula ser deslizada por el presentador y frena con fricción física realista.",
                "default_params": {
                    "headline": "INTERACCIÓN DINÁMICA",
                    "subheadline": "Deslizamiento con fricción e inercia gestual",
                    "badge": "INERTIA DRAG",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.0,
                }
            },

            # 12. Efectos Vectoriales & Stagger (Anime.js Engine)
            {
                "id": "anime_stagger_grid_ripple",
                "name": "Anime.js: Onda de Cuadrícula Escalonada (Grid Ripple)",
                "category": "Efectos Vectoriales (Anime.js)",
                "description": "Onda expansiva concéntrica sobre una cuadrícula de micro-elementos con desfase radial calculado por Anime.js.",
                "default_params": {
                    "headline": "ONDA ESCALONADA ANIME.JS",
                    "subheadline": "Stagger radial con física elástica multicapa",
                    "badge": "ANIME.JS STAGGER",
                    "accent_color": "#A855F7",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.5,
                }
            },
            {
                "id": "anime_svg_path_draw",
                "name": "Anime.js: Trazado Vectorial con Luz Neón (Line Draw)",
                "category": "Efectos Vectoriales (Anime.js)",
                "description": "Animación de trazo SVG donde las líneas geométricas y contornos de la tarjeta se dibujan progresivamente.",
                "default_params": {
                    "headline": "TRAZADO VECTORIAL SVG",
                    "subheadline": "Stroke-dashoffset continuo de alta precisión",
                    "badge": "SVG LINE DRAW",
                    "accent_color": "#06B6D4",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.5,
                }
            },
            {
                "id": "anime_kinetic_elastic_pop",
                "name": "Anime.js: Rebote Elástico Multicapa (Elastic Spring)",
                "category": "Efectos Vectoriales (Anime.js)",
                "description": "Aparición con triple rebote armónico y escala sobredimensionada para titulares virales de alto impacto.",
                "default_params": {
                    "headline": "REBOTE ARMÓNICO ELÁSTICO",
                    "subheadline": "Curva easeOutElastic con factor de amortiguación",
                    "badge": "ELASTIC POP",
                    "accent_color": "#EC4899",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.0,
                }
            },
            {
                "id": "anime_circle_pulse_radar",
                "name": "Anime.js: Radar Circular de Captura de Atención",
                "category": "Efectos Vectoriales (Anime.js)",
                "description": "Ondas circulares concéntricas que pulsan hacia afuera simulando un sonar o detector de radar.",
                "default_params": {
                    "headline": "RADAR DE ATENCIÓN",
                    "subheadline": "Pulsos continuos para retener el scroll del espectador",
                    "badge": "RADAR PULSE",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.5,
                }
            },
            {
                "id": "anime_number_counter_odometer",
                "name": "Anime.js: Contador Odómetro de Cifras Dinámicas",
                "category": "Efectos Vectoriales (Anime.js)",
                "description": "Conteo numérico ultra suave con aceleración cuadrática para estadísticas, ganancias y métricas clave.",
                "default_params": {
                    "headline": "$124,500.00 USD",
                    "subheadline": "Facturación mensual generada en automático",
                    "badge": "ODÓMETRO",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 0.8,
                    "duration": 4.5,
                }
            },
            {
                "id": "anime_morphing_blob",
                "name": "Anime.js: Morphing de Formas Orgánicas Líquidas",
                "category": "Efectos Vectoriales (Anime.js)",
                "description": "Polígono SVG fluido que muta orgánicamente de forma entre fotogramas para estética futurista.",
                "default_params": {
                    "headline": "MORFOLOGÍA FLUIDA",
                    "subheadline": "Interpolación de coordenadas de nodos vectoriales",
                    "badge": "ORGANIC MORPH",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.5,
                }
            },
            {
                "id": "fx_vhs_retro",
                "name": "Filtro: Cinta VHS Retro (Glitch & Timestamp)",
                "category": "Efectos Cinemáticos & Filtros",
                "description": "Estética analógica de cinta de video vintage de los 80/90s con líneas de tracking, aberración cromática y sello de tiempo REC.",
                "default_params": {
                    "headline": "PLAY 00:12:45",
                    "subheadline": "TRACKING AUTOMÁTICO • CINTA SP",
                    "badge": "REC ●",
                    "accent_color": "#06B6D4",
                    "position": "center",
                    "start_time": 0.0,
                    "duration": 4.0
}
            },
            {
                "id": "fx_film_grain_noir",
                "name": "Filtro: Cine Noir & Grano 35mm (Vintage Contrast)",
                "category": "Efectos Cinemáticos & Filtros",
                "description": "Acabado de celuloide cinematográfico con barras letterbox 2.39:1, viñeteado radial y estética de alto impacto.",
                "default_params": {
                    "headline": "CINEMA 35MM NOIR",
                    "subheadline": "Aspect Ratio 2.39:1 • Kodak 5219",
                    "badge": "35MM FILM",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 0.0,
                    "duration": 4.0
}
            },
            {
                "id": "fx_cyberpunk_glitch",
                "name": "Efecto: Cyberpunk Neon Glitch & Digital Tear",
                "category": "Efectos Cinemáticos & Filtros",
                "description": "Distorsión cromática cian y magenta con desgarro horizontal de fotograma y coordenadas holográficas cyberpunk.",
                "default_params": {
                    "headline": "CYBER DISTORTION",
                    "subheadline": "SYS.OVERRIDE: 0x99A_HACK_V3",
                    "badge": "NEON GLITCH",
                    "accent_color": "#EC4899",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 3.5
}
            },
            {
                "id": "fx_light_leak_bokeh",
                "name": "Efecto: Light Leak Dorado (Anamorphic Flare)",
                "category": "Efectos Cinemáticos & Filtros",
                "description": "Destello de lente anamórfico dorado cálido que inunda el centro del video con orbes bokeh de luz suave.",
                "default_params": {
                    "headline": "GOLDEN HOUR LEAK",
                    "subheadline": "Destello Anamórfico de Lente Óptica",
                    "badge": "LENS FLARE",
                    "accent_color": "#F59E0B",
                    "position": "center",
                    "start_time": 0.2,
                    "duration": 3.8
}
            },
            {
                "id": "fx_matrix_stream",
                "name": "Efecto: Cascada Digital Matrix (Code Stream HUD)",
                "category": "Efectos Cinemáticos & Filtros",
                "description": "Columnas de código digital descendente en verde esmeralda neón con decodificación en vivo para videos de tech e IA.",
                "default_params": {
                    "headline": "MATRIX DECRYPTOR",
                    "subheadline": "Protocolo de Acceso Cuántico 100% Autónomo",
                    "badge": "STREAM_AI",
                    "accent_color": "#10B981",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 4.0
}
            },
            {
                "id": "transition_whip_pan_blur",
                "name": "Transición: Whip-Pan Cinemático (Barrido de Velocidad)",
                "category": "Transiciones Cinemáticas",
                "description": "Giro ultrarrápido de cámara con estelas de desenfoque de movimiento direccional para saltos enérgicos de escena.",
                "default_params": {
                    "headline": "WHIP-PAN VELOCITY",
                    "subheadline": "Transición de Cámara en Movimiento 60 FPS",
                    "badge": "WHIP PAN",
                    "accent_color": "#38BDF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.2
}
            },
            {
                "id": "transition_film_burn_flash",
                "name": "Transición: Quemadura de Película (Film Burn Wipe)",
                "category": "Transiciones Cinemáticas",
                "description": "Erupción de luz ámbar incandescente estilo rollo de celuloide quemado con destello cálido orgánico.",
                "default_params": {
                    "headline": "BURNING FILM WIPE",
                    "subheadline": "Transición de Quemadura Orgánica de Fotograma",
                    "badge": "FILM BURN",
                    "accent_color": "#F97316",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.4
}
            },
            {
                "id": "transition_shatter_glass_burst",
                "name": "Transición: Estallido de Cristal Shards (Shatter FX)",
                "category": "Transiciones Cinemáticas",
                "description": "Impacto explosivo de fragmentos y esquirlas de cristal prismático 3D que rompen el plano para revelar el nuevo corte.",
                "default_params": {
                    "headline": "SHATTER BURST FX",
                    "subheadline": "Fragmentación Prismática 3D",
                    "badge": "SHATTER",
                    "accent_color": "#818CF8",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.5
}
            },
            {
                "id": "transition_kaleidoscope_spin",
                "name": "Transición: Caleidoscopio Hexagonal (Geometric Spin)",
                "category": "Transiciones Cinemáticas",
                "description": "Giro rotatorio con simetría radial de 6 ejes que pliega la pantalla en un caleidoscopio geométrico fascinante.",
                "default_params": {
                    "headline": "GEOMETRIC MANDALA",
                    "subheadline": "Rotación Caleidoscópica de 6 Vértices",
                    "badge": "KALEIDO",
                    "accent_color": "#C084FC",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.6
}
            },
            {
                "id": "transition_rgb_warp_tunnel",
                "name": "Transición: Túnel Hiperespacio RGB (Chromatic Tunnel)",
                "category": "Transiciones Cinemáticas",
                "description": "Zoom hiper-acelerado a través de anillos concéntricos con desfase cromático rojo, verde y azul estilo salto espacial.",
                "default_params": {
                    "headline": "WARP TUNNEL SPEED",
                    "subheadline": "Aceleración Relativista RGB",
                    "badge": "RGB WARP",
                    "accent_color": "#06B6D4",
                    "position": "center",
                    "start_time": 1.0,
                    "duration": 2.3
}
            },
            {
                "id": "tool_audio_bars_spectrum",
                "name": "Herramienta: Espectrograma de Audio Reactivo (Multi-Banda)",
                "category": "Herramientas & Audio-Visualizadores",
                "description": "Visualizador ecualizador de 18 frecuencias con caps de rebote flotantes y tarjeta de reproducción musical para podcasts y reels.",
                "default_params": {
                    "headline": "PODCAST BEATS VOL. 4",
                    "subheadline": "44.1 kHz • Stereo Spectrum Reactivo",
                    "badge": "AUDIO SPECTRUM",
                    "accent_color": "#A855F7",
                    "position": "bottom",
                    "start_time": 0.5,
                    "duration": 5.0
}
            },
            {
                "id": "tool_circular_sound_wave",
                "name": "Herramienta: Onda Sonora Circular (Radial Beat Pulse)",
                "category": "Herramientas & Audio-Visualizadores",
                "description": "Esfera central con corona de 24 picos de onda radiales que reaccionan con pulsaciones al ritmo del bajo musical.",
                "default_params": {
                    "headline": "BASS PULSE 128 BPM",
                    "subheadline": "Onda Sonora Radial Acústica",
                    "badge": "RADIAL SOUND",
                    "accent_color": "#EC4899",
                    "position": "center",
                    "start_time": 0.5,
                    "duration": 5.0
}
            },
            {
                "id": "tool_neon_podcast_badge",
                "name": "Herramienta: Cue de Grabación Podcast ('ON AIR' Live)",
                "category": "Herramientas & Audio-Visualizadores",
                "description": "Letrero de estudio profesional 'ON AIR' de gas neón rojo parpadeante con aguja analógica de VU Meter.",
                "default_params": {
                    "headline": "EPISODIO 42: INTELIGENCIA ARTIFICIAL",
                    "subheadline": "Transmitiendo en Vivo • Micrófono Condensador Shure SM7B",
                    "badge": "● ON AIR",
                    "accent_color": "#EF4444",
                    "position": "top",
                    "start_time": 0.2,
                    "duration": 4.5
}
            },
]

        # Merge custom presets saved in user library
        custom_presets = []
        if self.custom_presets_file.exists():
            try:
                with open(self.custom_presets_file, "r", encoding="utf-8") as f:
                    custom_presets = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading custom presets: {e}")

        # Combine all presets and deduplicate by id
        all_presets = built_in + custom_presets
        seen_ids = set()
        unique_presets = []
        for p in all_presets:
            p_id = p.get("id")
            if p_id and p_id not in seen_ids:
                seen_ids.add(p_id)
                unique_presets.append(p)

        return unique_presets

    def add_custom_preset(self, preset_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves a user or imported CodePen preset to the custom presets library."""
        preset_id = preset_data.get("id") or f"custom_{uuid.uuid4().hex[:6]}"
        preset_data["id"] = preset_id
        preset_data["is_custom"] = True
        if "category" not in preset_data:
            preset_data["category"] = "🌟 Personalizados"

        existing = []
        if self.custom_presets_file.exists():
            try:
                with open(self.custom_presets_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        updated = [p for p in existing if p.get("id") != preset_id]
        updated.append(preset_data)

        with open(self.custom_presets_file, "w", encoding="utf-8") as f:
            json.dump(updated, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved custom preset '{preset_id}' to library.")
        return preset_data

    def delete_custom_preset(self, preset_id: str) -> bool:
        """Deletes a custom preset from the library."""
        if not self.custom_presets_file.exists():
            return False
        try:
            with open(self.custom_presets_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
            new_list = [p for p in existing if p.get("id") != preset_id]
            with open(self.custom_presets_file, "w", encoding="utf-8") as f:
                json.dump(new_list, f, indent=2, ensure_ascii=False)
            return len(new_list) < len(existing)
        except Exception as e:
            logger.error(f"Error deleting custom preset: {e}")
            return False

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
        # Params come from the browser, LLM output or imported presets: escape before
        # interpolating into markup (prevents stored/reflected XSS via SVG).
        params = escape_markup_params(params or {})
        width, height = int(width), int(height)
        accent = params.get("accent_color", "#38BDF8")

        # Real Transition Presets (Full-Screen Kinetic Video Transitions)
        if preset_id == "transition_neon_slice_wipe":
            headline = params.get("headline") or "CAMBIO DE ESCENA"
            subheadline = params.get("subheadline") or "Transición Cinemática 60 FPS"
            badge = params.get("badge", "NEON SLICE").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="sliceCurtainGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#030712" stop-opacity="0.95"/>
      <stop offset="50%" stop-color="#0B132B" stop-opacity="0.92"/>
      <stop offset="100%" stop-color="#020617" stop-opacity="0.96"/>
    </linearGradient>
  </defs>
  <g id="slice_transition_wrapper">
    <polygon id="slice_curtain" points="-200,-100 {width+200},-100 {width+200},{height+100} -200,{height+100}" fill="url(#sliceCurtainGrad)"/>
    <line id="slice_beam" x1="-300" y1="{height+300}" x2="{width+300}" y2="-300" stroke="{accent}" stroke-width="18" stroke-linecap="round"/>
    <line id="slice_glow" x1="-300" y1="{height+300}" x2="{width+300}" y2="-300" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>
    <circle cx="340" cy="850" r="6" fill="#FFFFFF"/>
    <circle cx="720" cy="1050" r="8" fill="{accent}"/>
    <circle cx="580" cy="920" r="10" fill="{accent}" fill-opacity="0.6"/>
    <g id="slice_content" transform="translate(100, {height//2 - 120})">
      <rect width="880" height="240" rx="30" fill="#000000" fill-opacity="0.8" stroke="{accent}" stroke-width="3"/>
      <rect x="40" y="25" width="220" height="34" rx="17" fill="{accent}" fill-opacity="0.25" stroke="{accent}" stroke-width="1.5"/>
      <text x="150" y="48" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">⚡ {badge}</text>
      <text x="440" y="130" font-family="'Impact', sans-serif" font-size="52" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="2">{headline}</text>
      <text x="440" y="190" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_flip_3d_turn":
            headline = params.get("headline") or "NUEVO CAPÍTULO"
            subheadline = params.get("subheadline") or "Giro Tridimensional de Escena"
            badge = params.get("badge", "3D FLIP").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="flip_3d_wrapper">
    <g id="flip_3d_layer" transform="translate(60, 240)">
      <rect width="960" height="1440" rx="42" fill="#050814" fill-opacity="0.96" stroke="{accent}" stroke-width="5"/>
      <path d="M 0 0 L 400 0 L 200 1440 L 0 1440 Z" fill="{accent}" fill-opacity="0.08"/>
      <rect x="360" y="520" width="240" height="42" rx="21" fill="{accent}" fill-opacity="0.25" stroke="{accent}" stroke-width="2"/>
      <text x="480" y="547" font-family="'Montserrat', sans-serif" font-size="15" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">🔀 {badge}</text>
      <text x="480" y="660" font-family="'Impact', sans-serif" font-size="60" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
      <text x="480" y="740" font-family="'Montserrat', sans-serif" font-size="24" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
      <line x1="160" y1="820" x2="800" y2="820" stroke="{accent}" stroke-opacity="0.4" stroke-width="3" stroke-dasharray="16 12"/>
      <text x="480" y="900" font-family="'Impact', sans-serif" font-size="34" font-weight="900" fill="#64748B" text-anchor="middle">TRANSICIÓN FLIP 60 FPS</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_stagger_grid_curtain":
            headline = params.get("headline") or "SIGUIENTE TEMA"
            subheadline = params.get("subheadline") or "Cascada Dinámica de Revelación"
            badge = params.get("badge", "GRID CURTAIN").upper()
            tiles_svg = []
            cols, rows = 4, 6
            tile_w = width // cols
            tile_h = height // rows
            for r in range(rows):
                for c in range(cols):
                    tiles_svg.append(f'<rect class="grid-curtain-tile" x="{c*tile_w + 6}" y="{r*tile_h + 6}" width="{tile_w - 12}" height="{tile_h - 12}" rx="18" fill="#030712" fill-opacity="0.94" stroke="{accent}" stroke-width="2.5" stroke-opacity="0.8"/>')
            tiles_str = "".join(tiles_svg)
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="stagger_curtain_wrapper">
    <g id="stagger_curtain_tiles">
      {tiles_str}
    </g>
    <g id="stagger_grid_badge" transform="translate(100, {height//2 - 130})">
      <rect width="880" height="260" rx="30" fill="#020617" fill-opacity="0.96" stroke="{accent}" stroke-width="4"/>
      <rect x="340" y="25" width="200" height="36" rx="18" fill="{accent}" fill-opacity="0.25" stroke="{accent}" stroke-width="2"/>
      <text x="440" y="49" font-family="'Montserrat', sans-serif" font-size="14" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">✨ {badge}</text>
      <text x="440" y="135" font-family="'Impact', sans-serif" font-size="52" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
      <text x="440" y="200" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_kinetic_zoom_push":
            headline = params.get("headline") or "VELOCIDAD HIPERBÓLICA"
            subheadline = params.get("subheadline") or "Aceleración de Corte Inercial"
            badge = params.get("badge", "ZOOM RUSH").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="zoom_rush_wrapper">
    <rect width="{width}" height="{height}" fill="#030712" fill-opacity="0.85"/>
    <ellipse id="speed_ring_1" cx="{width//2}" cy="{height//2}" rx="500" ry="880" fill="none" stroke="{accent}" stroke-width="4" stroke-opacity="0.4" stroke-dasharray="32 20"/>
    <ellipse id="speed_ring_2" cx="{width//2}" cy="{height//2}" rx="360" ry="630" fill="none" stroke="{accent}" stroke-width="5" stroke-opacity="0.7"/>
    <ellipse id="speed_ring_3" cx="{width//2}" cy="{height//2}" rx="200" ry="350" fill="none" stroke="#FFFFFF" stroke-width="6"/>
    <g id="zoom_push_content" transform="translate(120, {height//2 - 110})">
      <rect width="840" height="220" rx="28" fill="#050914" fill-opacity="0.95" stroke="{accent}" stroke-width="3.5"/>
      <rect x="320" y="22" width="200" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
      <text x="420" y="44" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">🚀 {badge}</text>
      <text x="420" y="125" font-family="'Impact', sans-serif" font-size="52" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
      <text x="420" y="180" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_split_mask_reveal":
            headline = params.get("headline") or "REVELACIÓN DE TOMA"
            subheadline = params.get("subheadline") or "Compuerta Cinemática Deslizante"
            badge = params.get("badge", "SPLIT GATE").upper()
            mid = height // 2
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="split_gate_wrapper">
    <g id="split_top_half">
      <rect x="0" y="0" width="{width}" height="{mid}" fill="#030712" fill-opacity="0.95"/>
      <line x1="0" y1="{mid}" x2="{width}" y2="{mid}" stroke="{accent}" stroke-width="8"/>
      <line x1="0" y1="{mid-4}" x2="{width}" y2="{mid-4}" stroke="#FFFFFF" stroke-width="2"/>
    </g>
    <g id="split_bottom_half">
      <rect x="0" y="{mid}" width="{width}" height="{mid}" fill="#030712" fill-opacity="0.95"/>
      <line x1="0" y1="{mid}" x2="{width}" y2="{mid}" stroke="{accent}" stroke-width="8"/>
    </g>
    <g id="split_lock_badge" transform="translate(100, {mid - 120})">
      <rect width="880" height="240" rx="30" fill="#090E1A" fill-opacity="0.98" stroke="{accent}" stroke-width="4"/>
      <rect x="340" y="25" width="200" height="34" rx="17" fill="{accent}" fill-opacity="0.25" stroke="{accent}" stroke-width="1.5"/>
      <text x="440" y="48" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">🔒 {badge}</text>
      <text x="440" y="130" font-family="'Impact', sans-serif" font-size="52" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
      <text x="440" y="190" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_glitch_flash_warp":
            headline = params.get("headline") or "GLITCH CINEMÁTICO"
            subheadline = params.get("subheadline") or "Distorsión Digital de Impacto"
            badge = params.get("badge", "CYBER GLITCH").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="glitch_warp_wrapper">
    <rect id="glitch_strobe" width="{width}" height="{height}" fill="{accent}" fill-opacity="0.2"/>
    <rect class="glitch-bar" x="0" y="280" width="{width}" height="60" fill="#F43F5E" fill-opacity="0.7"/>
    <rect class="glitch-bar" x="0" y="680" width="{width}" height="90" fill="{accent}" fill-opacity="0.75"/>
    <rect class="glitch-bar" x="0" y="1200" width="{width}" height="50" fill="#10B981" fill-opacity="0.6"/>
    <rect class="glitch-bar" x="0" y="1580" width="{width}" height="80" fill="{accent}" fill-opacity="0.7"/>
    <g id="glitch_cyber_badge" transform="translate(100, {height//2 - 130})">
      <rect width="880" height="260" rx="26" fill="#000000" fill-opacity="0.94" stroke="{accent}" stroke-width="4"/>
      <rect x="40" y="25" width="220" height="36" rx="18" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
      <text x="150" y="49" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">⚡ {badge}</text>
      <text x="440" y="135" font-family="'Impact', sans-serif" font-size="54" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="2">{headline}</text>
      <text x="440" y="200" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_circle_iris_expand":
            headline = params.get("headline") or "FOCO PRINCIPAL"
            subheadline = params.get("subheadline") or "Expansión Radial Cinemática"
            badge = params.get("badge", "RADIAL IRIS").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="iris_expand_wrapper">
    <rect width="{width}" height="{height}" fill="#030712" fill-opacity="0.7"/>
    <circle id="iris_expand_circle" cx="{width//2}" cy="{height//2}" r="500" fill="#060A14" fill-opacity="0.95" stroke="{accent}" stroke-width="8"/>
    <circle cx="{width//2}" cy="{height//2}" r="460" fill="none" stroke="{accent}" stroke-opacity="0.3" stroke-width="2" stroke-dasharray="16 12"/>
    <g id="iris_content" transform="translate(120, {height//2 - 110})">
      <rect width="840" height="220" rx="28" fill="#000000" fill-opacity="0.8" stroke="{accent}" stroke-width="3"/>
      <rect x="320" y="20" width="200" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
      <text x="420" y="43" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">⭕ {badge}</text>
      <text x="420" y="125" font-family="'Impact', sans-serif" font-size="50" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
      <text x="420" y="180" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        
        elif preset_id == "fx_vhs_retro":
            headline = params.get("headline") or "PLAY 00:12:45"
            subheadline = params.get("subheadline") or "TRACKING AUTOMÁTICO • CINTA SP"
            badge = params.get("badge") or "REC ●"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="fx_vhs_retro_wrapper">
    <!-- Top HUD: REC indicator & SP mode -->
    <g id="vhs_top_hud" transform="translate(60, 80)">
      <circle id="vhs_rec_dot" cx="20" cy="20" r="10" fill="#EF4444"/>
      <text x="42" y="27" font-family="'Courier New', monospace" font-size="24" font-weight="900" fill="#EF4444" letter-spacing="2">{badge}</text>
      <text x="{width - 240}" y="27" font-family="'Courier New', monospace" font-size="22" font-weight="700" fill="#FACC15">SP 0:00:00</text>
    </g>
    <!-- Analog tracking noise lines -->
    <g id="vhs_tracking_bar">
      <rect x="0" y="480" width="{width}" height="18" fill="#FFFFFF" fill-opacity="0.35"/>
      <rect x="0" y="504" width="{width}" height="6" fill="{accent}" fill-opacity="0.4"/>
      <rect x="0" y="1420" width="{width}" height="14" fill="#FFFFFF" fill-opacity="0.25"/>
    </g>
    <!-- Center retro VHS title card with chromatic drop shadow -->
    <g id="vhs_retro_card" transform="translate(80, {height//2 - 120})">
      <rect x="-8" y="6" width="920" height="240" rx="16" fill="#EC4899" fill-opacity="0.4"/>
      <rect x="6" y="-6" width="920" height="240" rx="16" fill="#06B6D4" fill-opacity="0.4"/>
      <rect width="920" height="240" rx="16" fill="#050B14" fill-opacity="0.9" stroke="{accent}" stroke-width="3"/>
      <text x="460" y="70" font-family="'Courier New', monospace" font-size="20" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="4">VHS HI-FI STEREO</text>
      <text x="460" y="140" font-family="'Impact', sans-serif" font-size="60" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="3">{headline}</text>
      <text x="460" y="195" font-family="'Courier New', monospace" font-size="20" font-weight="700" fill="#94A3B8" text-anchor="middle">{subheadline}</text>
    </g>
    <!-- Bottom VCR playback indicator -->
    <g id="vhs_bottom_hud" transform="translate(80, {height - 90})">
      <text x="0" y="0" font-family="'Courier New', monospace" font-size="22" font-weight="900" fill="#22C55E">PLAY ► 30 FPS</text>
      <text x="{width - 340}" y="0" font-family="'Courier New', monospace" font-size="22" font-weight="700" fill="#94A3B8">AUTO-TRACK: OK</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "fx_film_grain_noir":
            headline = params.get("headline") or "CINEMA 35MM NOIR"
            subheadline = params.get("subheadline") or "Aspect Ratio 2.39:1 • Kodak 5219"
            badge = params.get("badge") or "35MM FILM"
            bar_h = 180
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="noirVignette" cx="50%" cy="50%" r="50%">
      <stop offset="60%" stop-color="#000000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.85"/>
    </radialGradient>
  </defs>
  <!-- Full screen vignette -->
  <rect width="{width}" height="{height}" fill="url(#noirVignette)"/>
  <!-- Top Letterbox Bar -->
  <rect id="film_letterbox_top" x="0" y="0" width="{width}" height="{bar_h}" fill="#000000"/>
  <!-- Bottom Letterbox Bar -->
  <rect id="film_letterbox_bottom" x="0" y="{height - bar_h}" width="{width}" height="{bar_h}" fill="#000000"/>
  <!-- Cinematic Title Card -->
  <g id="film_noir_card" transform="translate(100, {height//2 - 110})">
    <rect width="880" height="220" rx="4" fill="#000000" fill-opacity="0.85" stroke="#FFFFFF" stroke-width="1.5" stroke-opacity="0.3"/>
    <rect x="340" y="22" width="200" height="30" rx="2" fill="#F59E0B" fill-opacity="0.2" stroke="#F59E0B" stroke-width="1"/>
    <text x="440" y="42" font-family="'Courier New', monospace" font-size="12" font-weight="900" fill="#F59E0B" text-anchor="middle" letter-spacing="3">🎞 {badge}</text>
    <text x="440" y="125" font-family="'Georgia', serif" font-size="44" font-weight="900" fill="#F8FAFC" text-anchor="middle" letter-spacing="4">{headline}</text>
    <text x="440" y="175" font-family="'Courier New', monospace" font-size="18" font-weight="700" fill="#94A3B8" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "fx_cyberpunk_glitch":
            headline = params.get("headline") or "CYBER DISTORTION"
            subheadline = params.get("subheadline") or "SYS.OVERRIDE: 0x99A_HACK_V3"
            badge = params.get("badge") or "NEON GLITCH"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="fx_cyberpunk_wrapper">
    <!-- Horizontal digital slice bars -->
    <rect class="cyber-slice" x="0" y="320" width="{width}" height="24" fill="#EC4899" fill-opacity="0.6"/>
    <rect class="cyber-slice" x="0" y="780" width="{width}" height="40" fill="#06B6D4" fill-opacity="0.65"/>
    <rect class="cyber-slice" x="0" y="1320" width="{width}" height="18" fill="#FACC15" fill-opacity="0.5"/>
    <!-- Cyberpunk Dual Layer Card -->
    <g id="cyberpunk_card" transform="translate(100, {height//2 - 130})">
      <!-- Magenta chromatic drop layer -->
      <g id="cyber_layer_pink" transform="translate(-10, 6)">
        <rect width="880" height="260" rx="18" fill="none" stroke="#EC4899" stroke-width="3" stroke-opacity="0.7"/>
      </g>
      <!-- Cyan chromatic drop layer -->
      <g id="cyber_layer_cyan" transform="translate(10, -6)">
        <rect width="880" height="260" rx="18" fill="none" stroke="#06B6D4" stroke-width="3" stroke-opacity="0.7"/>
      </g>
      <!-- Main dark HUD plate -->
      <rect width="880" height="260" rx="18" fill="#030712" fill-opacity="0.94" stroke="{accent}" stroke-width="3"/>
      <!-- HUD bracket corners -->
      <path d="M 30 50 L 30 30 L 60 30" stroke="{accent}" stroke-width="3" fill="none"/>
      <path d="M 850 50 L 850 30 L 820 30" stroke="{accent}" stroke-width="3" fill="none"/>
      <path d="M 30 210 L 30 230 L 60 230" stroke="{accent}" stroke-width="3" fill="none"/>
      <path d="M 850 210 L 850 230 L 820 230" stroke="{accent}" stroke-width="3" fill="none"/>
      <!-- Badge -->
      <rect x="50" y="40" width="180" height="32" rx="6" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
      <text x="140" y="62" font-family="'Courier New', monospace" font-size="12" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">⚡ {badge}</text>
      <text x="440" y="145" font-family="'Impact', sans-serif" font-size="56" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="3">{headline}</text>
      <text x="440" y="200" font-family="'Courier New', monospace" font-size="19" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "fx_light_leak_bokeh":
            headline = params.get("headline") or "GOLDEN HOUR LEAK"
            subheadline = params.get("subheadline") or "Destello Anamórfico de Lente Óptica"
            badge = params.get("badge") or "LENS FLARE"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="flareGrad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#FDE047" stop-opacity="0.95"/>
      <stop offset="40%" stop-color="#F97316" stop-opacity="0.75"/>
      <stop offset="100%" stop-color="#F59E0B" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="beamGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#F97316" stop-opacity="0"/>
      <stop offset="50%" stop-color="#FEF08A" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#F97316" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <!-- Floating Bokeh Orbs -->
  <circle class="bokeh-orb" cx="220" cy="480" r="140" fill="url(#flareGrad)" fill-opacity="0.4"/>
  <circle class="bokeh-orb" cx="840" cy="1380" r="180" fill="url(#flareGrad)" fill-opacity="0.45"/>
  <circle class="bokeh-orb" cx="720" cy="620" r="90" fill="url(#flareGrad)" fill-opacity="0.35"/>
  <!-- Horizontal Anamorphic Flare Streak -->
  <ellipse id="anamorphic_flare_beam" cx="{width//2}" cy="{height//2}" rx="{width*0.8}" ry="24" fill="url(#beamGrad)"/>
  <!-- Elegant Floating Card -->
  <g id="light_leak_card" transform="translate(100, {height//2 - 120})">
    <rect width="880" height="240" rx="32" fill="#0F172A" fill-opacity="0.82" stroke="#F59E0B" stroke-width="2.5"/>
    <rect x="340" y="24" width="200" height="34" rx="17" fill="#F59E0B" fill-opacity="0.2" stroke="#F59E0B" stroke-width="1.5"/>
    <text x="440" y="47" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="#FDE047" text-anchor="middle" letter-spacing="2">☀️ {badge}</text>
    <text x="440" y="130" font-family="'Montserrat', sans-serif" font-size="46" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="2">{headline}</text>
    <text x="440" y="185" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="#FCD34D" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "fx_matrix_stream":
            headline = params.get("headline") or "MATRIX DECRYPTOR"
            subheadline = params.get("subheadline") or "Protocolo de Acceso Cuántico 100% Autónomo"
            badge = params.get("badge") or "STREAM_AI"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="fx_matrix_wrapper">
    <!-- Matrix digital rain columns -->
    <g id="matrix_rain_columns" font-family="'Courier New', monospace" font-size="20" fill="#10B981" font-weight="700" fill-opacity="0.45">
      <text x="80" y="300">1 0 1 1 0 1 0 0 1 1 0</text>
      <text x="240" y="240">0 1 0 0 1 1 1 0 1 0 1</text>
      <text x="460" y="280">1 1 0 1 0 0 1 0 1 1 0</text>
      <text x="680" y="220">0 0 1 1 0 1 1 0 0 1 1</text>
      <text x="920" y="290">1 0 1 0 1 0 1 1 0 0 1</text>
      <text x="140" y="1380">1 0 0 1 1 0 1 0 1 1 0</text>
      <text x="420" y="1440">0 1 1 0 0 1 0 1 1 0 1</text>
      <text x="760" y="1400">1 1 0 1 1 0 0 1 0 1 0</text>
    </g>
    <!-- Console Card -->
    <g id="matrix_stream_card" transform="translate(100, {height//2 - 125})">
      <rect width="880" height="250" rx="20" fill="#020804" fill-opacity="0.94" stroke="#10B981" stroke-width="3"/>
      <rect x="40" y="25" width="180" height="34" rx="8" fill="#10B981" fill-opacity="0.2" stroke="#10B981" stroke-width="1.5"/>
      <text x="130" y="48" font-family="'Courier New', monospace" font-size="13" font-weight="900" fill="#34D399" text-anchor="middle" letter-spacing="2">💻 {badge}</text>
      <text x="40" y="135" font-family="'Courier New', monospace" font-size="52" font-weight="900" fill="#ECFDF5" letter-spacing="2">&gt; {headline}</text>
      <text x="40" y="195" font-family="'Courier New', monospace" font-size="20" font-weight="700" fill="#10B981">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_whip_pan_blur":
            headline = params.get("headline") or "WHIP-PAN VELOCITY"
            subheadline = params.get("subheadline") or "Transición de Cámara en Movimiento 60 FPS"
            badge = params.get("badge") or "WHIP PAN"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="whip_pan_wrapper">
    <!-- Directional Speed Streak Bars -->
    <g id="whip_motion_streaks">
      <polygon points="-100,180 {width+100},80 {width+100},160 -100,260" fill="{accent}" fill-opacity="0.6"/>
      <polygon points="-100,520 {width+100},420 {width+100},560 -100,660" fill="#FFFFFF" fill-opacity="0.3"/>
      <polygon points="-100,880 {width+100},780 {width+100},980 -100,1080" fill="{accent}" fill-opacity="0.7"/>
      <polygon points="-100,1280 {width+100},1180 {width+100},1340 -100,1440" fill="#38BDF8" fill-opacity="0.5"/>
      <polygon points="-100,1620 {width+100},1520 {width+100},1700 -100,1800" fill="{accent}" fill-opacity="0.6"/>
    </g>
    <!-- Center Whip Badge -->
    <g id="whip_pan_badge" transform="translate(100, {height//2 - 120})">
      <rect width="880" height="240" rx="28" fill="#030712" fill-opacity="0.95" stroke="{accent}" stroke-width="4"/>
      <text x="440" y="60" font-family="'Impact', sans-serif" font-size="22" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="4">⚡ {badge}</text>
      <text x="440" y="135" font-family="'Impact', sans-serif" font-size="56" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="3">{headline}</text>
      <text x="440" y="195" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_film_burn_flash":
            headline = params.get("headline") or "BURNING FILM WIPE"
            subheadline = params.get("subheadline") or "Transición de Quemadura Orgánica de Fotograma"
            badge = params.get("badge") or "FILM BURN"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="burnBloom" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="1"/>
      <stop offset="35%" stop-color="#FEF08A" stop-opacity="0.95"/>
      <stop offset="70%" stop-color="#F97316" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="#7C2D12" stop-opacity="0.2"/>
    </radialGradient>
  </defs>
  <!-- Full Screen Molten Burn Flare -->
  <g id="film_burn_wrapper">
    <ellipse id="film_burn_flash" cx="{width//2}" cy="{height//2}" rx="{width*0.7}" ry="{height*0.6}" fill="url(#burnBloom)"/>
    <!-- Center Burn Title Content -->
    <g id="film_burn_content" transform="translate(100, {height//2 - 120})">
      <rect width="880" height="240" rx="30" fill="#0C0A09" fill-opacity="0.92" stroke="#F97316" stroke-width="4"/>
      <rect x="340" y="22" width="200" height="34" rx="17" fill="#F97316" fill-opacity="0.25" stroke="#F97316" stroke-width="1.5"/>
      <text x="440" y="45" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="#FDE047" text-anchor="middle" letter-spacing="2">🔥 {badge}</text>
      <text x="440" y="130" font-family="'Impact', sans-serif" font-size="54" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="2">{headline}</text>
      <text x="440" y="190" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="#FB923C" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_shatter_glass_burst":
            headline = params.get("headline") or "SHATTER BURST FX"
            subheadline = params.get("subheadline") or "Fragmentación Prismática 3D"
            badge = params.get("badge") or "SHATTER"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="shatter_glass_wrapper">
    <!-- Prismatic Shard Polygons -->
    <polygon id="shatter_shard_1" points="0,0 {width//2},{height//3} 120,{height//2}" fill="{accent}" fill-opacity="0.45" stroke="#FFFFFF" stroke-width="2"/>
    <polygon id="shatter_shard_2" points="{width},0 {width//2},{height//3} {width-100},{height//2}" fill="#818CF8" fill-opacity="0.5" stroke="#FFFFFF" stroke-width="2"/>
    <polygon id="shatter_shard_3" points="0,{height} {width//2},{height*2//3} 100,{height//2}" fill="#6366F1" fill-opacity="0.4" stroke="#FFFFFF" stroke-width="2"/>
    <polygon id="shatter_shard_4" points="{width},{height} {width//2},{height*2//3} {width-120},{height//2}" fill="{accent}" fill-opacity="0.5" stroke="#FFFFFF" stroke-width="2"/>
    <!-- Center Core Badge -->
    <g id="shatter_core_badge" transform="translate(100, {height//2 - 120})">
      <rect width="880" height="240" rx="24" fill="#050816" fill-opacity="0.94" stroke="#818CF8" stroke-width="3.5"/>
      <text x="440" y="60" font-family="'Montserrat', sans-serif" font-size="14" font-weight="900" fill="#A5B4FC" text-anchor="middle" letter-spacing="3">💎 {badge}</text>
      <text x="440" y="135" font-family="'Impact', sans-serif" font-size="54" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="2">{headline}</text>
      <text x="440" y="190" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_kaleidoscope_spin":
            headline = params.get("headline") or "GEOMETRIC MANDALA"
            subheadline = params.get("subheadline") or "Rotación Caleidoscópica de 6 Vértices"
            badge = params.get("badge") or "KALEIDO"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="kaleidoscope_wrapper">
    <!-- 6-Fold Kaleidoscope Mandala Group -->
    <g id="kaleidoscope_mandala" transform="translate({width//2}, {height//2})">
      <polygon points="0,-400 120,-150 -120,-150" fill="{accent}" fill-opacity="0.5" stroke="#FFFFFF" stroke-width="2"/>
      <polygon points="0,-400 120,-150 -120,-150" transform="rotate(60)" fill="#C084FC" fill-opacity="0.5" stroke="#FFFFFF" stroke-width="2"/>
      <polygon points="0,-400 120,-150 -120,-150" transform="rotate(120)" fill="{accent}" fill-opacity="0.5" stroke="#FFFFFF" stroke-width="2"/>
      <polygon points="0,-400 120,-150 -120,-150" transform="rotate(180)" fill="#C084FC" fill-opacity="0.5" stroke="#FFFFFF" stroke-width="2"/>
      <polygon points="0,-400 120,-150 -120,-150" transform="rotate(240)" fill="{accent}" fill-opacity="0.5" stroke="#FFFFFF" stroke-width="2"/>
      <polygon points="0,-400 120,-150 -120,-150" transform="rotate(300)" fill="#C084FC" fill-opacity="0.5" stroke="#FFFFFF" stroke-width="2"/>
      <circle r="180" fill="#0F0826" stroke="#FFFFFF" stroke-width="3"/>
    </g>
    <!-- Center Title -->
    <g id="kaleido_core" transform="translate(100, {height//2 - 110})">
      <rect width="880" height="220" rx="30" fill="#090518" fill-opacity="0.92" stroke="#C084FC" stroke-width="3"/>
      <text x="440" y="55" font-family="'Montserrat', sans-serif" font-size="14" font-weight="900" fill="#E9D5FF" text-anchor="middle" letter-spacing="3">🔮 {badge}</text>
      <text x="440" y="125" font-family="'Impact', sans-serif" font-size="52" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="2">{headline}</text>
      <text x="440" y="180" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "transition_rgb_warp_tunnel":
            headline = params.get("headline") or "WARP TUNNEL SPEED"
            subheadline = params.get("subheadline") or "Aceleración Relativista RGB"
            badge = params.get("badge") or "RGB WARP"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="rgb_warp_wrapper">
    <!-- Tunnel rings -->
    <circle id="warp_ring_1" cx="{width//2}" cy="{height//2}" r="120" stroke="#EC4899" stroke-width="8" fill="none"/>
    <circle id="warp_ring_2" cx="{width//2}" cy="{height//2}" r="260" stroke="#06B6D4" stroke-width="6" fill="none"/>
    <circle id="warp_ring_3" cx="{width//2}" cy="{height//2}" r="440" stroke="#FACC15" stroke-width="8" fill="none"/>
    <circle id="warp_ring_4" cx="{width//2}" cy="{height//2}" r="640" stroke="#818CF8" stroke-width="12" fill="none"/>
    <!-- Cockpit Title Card -->
    <g id="warp_tunnel_badge" transform="translate(100, {height//2 - 120})">
      <rect width="880" height="240" rx="28" fill="#020617" fill-opacity="0.94" stroke="{accent}" stroke-width="3.5"/>
      <text x="440" y="60" font-family="'Courier New', monospace" font-size="14" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="4">🚀 {badge}</text>
      <text x="440" y="135" font-family="'Impact', sans-serif" font-size="54" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="3">{headline}</text>
      <text x="440" y="195" font-family="'Courier New', monospace" font-size="21" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "tool_audio_bars_spectrum":
            headline = params.get("headline") or "PODCAST BEATS VOL. 4"
            subheadline = params.get("subheadline") or "44.1 kHz • Stereo Spectrum Reactivo"
            badge = params.get("badge") or "AUDIO SPECTRUM"
            # 18 frequency bars
            bars_svg = ""
            for i in range(18):
                bx = 100 + i * 48
                bh = 60 + (i % 5) * 45 + (18 - abs(i - 9)) * 8
                bars_svg += f'<rect class="spec-bar" x="{bx}" y="{1540 - bh}" width="34" height="{bh}" rx="6" fill="{accent}" fill-opacity="0.85"/>\n'
                bars_svg += f'<rect class="spec-peak" x="{bx}" y="{1540 - bh - 16}" width="34" height="6" rx="3" fill="#FFFFFF"/>\n'
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="spectrum_bars_group">
    {bars_svg}
  </g>
  <!-- Player Card -->
  <g id="spectrum_player_card" transform="translate(80, 1580)">
    <rect width="920" height="210" rx="24" fill="#0D071E" fill-opacity="0.92" stroke="{accent}" stroke-width="2.5"/>
    <circle cx="70" cy="105" r="38" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="2"/>
    <path d="M 62 88 L 84 105 L 62 122 Z" fill="{accent}"/>
    <text x="130" y="85" font-family="'Montserrat', sans-serif" font-size="12" font-weight="900" fill="{accent}" letter-spacing="2">🎵 {badge}</text>
    <text x="130" y="130" font-family="'Montserrat', sans-serif" font-size="34" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="130" y="172" font-family="'Montserrat', sans-serif" font-size="20" font-weight="600" fill="#A855F7">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "tool_circular_sound_wave":
            headline = params.get("headline") or "BASS PULSE 128 BPM"
            subheadline = params.get("subheadline") or "Onda Sonora Radial Acústica"
            badge = params.get("badge") or "RADIAL SOUND"
            # 24 radial bars
            spikes_svg = ""
            for i in range(24):
                rot = i * 15
                h_val = 30 + (i % 6) * 20
                spikes_svg += f'<rect x="-8" y="-280" width="16" height="{h_val}" rx="8" fill="{accent}" fill-opacity="0.8" transform="rotate({rot})"/>\n'
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="radial_sound_wrapper" transform="translate({width//2}, {height//2})">
    <g id="radial_spikes_group">
      {spikes_svg}
    </g>
    <!-- Center speaker cone -->
    <circle id="sound_speaker_core" r="190" fill="#0F0418" stroke="{accent}" stroke-width="6"/>
    <circle r="140" fill="{accent}" fill-opacity="0.25"/>
    <circle r="60" fill="{accent}" fill-opacity="0.9"/>
  </g>
  <!-- Title Badge -->
  <g id="radial_sound_badge" transform="translate(100, {height - 320})">
    <rect width="880" height="200" rx="24" fill="#05010B" fill-opacity="0.9" stroke="{accent}" stroke-width="2.5"/>
    <text x="440" y="55" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">🔊 {badge}</text>
    <text x="440" y="115" font-family="'Impact', sans-serif" font-size="46" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
    <text x="440" y="165" font-family="'Montserrat', sans-serif" font-size="20" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "tool_neon_podcast_badge":
            headline = params.get("headline") or "EPISODIO 42: INTELIGENCIA ARTIFICIAL"
            subheadline = params.get("subheadline") or "Transmitiendo en Vivo • Micrófono SM7B"
            badge = params.get("badge") or "● ON AIR"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Top ON AIR Neon Sign -->
  <g id="podcast_on_air_box" transform="translate(160, 140)">
    <rect width="760" height="150" rx="20" fill="#180404" stroke="#EF4444" stroke-width="4"/>
    <text id="on_air_neon_text" x="380" y="105" font-family="'Impact', sans-serif" font-size="82" font-weight="900" fill="#EF4444" text-anchor="middle" letter-spacing="8">{badge}</text>
  </g>
  <!-- Podcast Episode Card -->
  <g id="podcast_info_card" transform="translate(80, 1460)">
    <rect width="920" height="230" rx="24" fill="#0C0A0A" fill-opacity="0.92" stroke="#EF4444" stroke-width="2.5"/>
    <!-- Mic indicator icon -->
    <circle cx="80" cy="115" r="42" fill="#EF4444" fill-opacity="0.2" stroke="#EF4444" stroke-width="2"/>
    <text x="80" y="128" font-size="34" text-anchor="middle">🎙️</text>
    <text x="150" y="75" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="#EF4444" letter-spacing="2">STUDIO LIVE BROADCAST</text>
    <text x="150" y="130" font-family="'Montserrat', sans-serif" font-size="36" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="150" y="180" font-family="'Montserrat', sans-serif" font-size="20" font-weight="600" fill="#F87171">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "lower_third_glass":
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

        elif preset_id == "attention_arrow":
            label = params.get("label") or params.get("headline") or "¡OJO CON ESTO!"
            sublabel = params.get("sublabel") or params.get("subheadline") or "Detalle clave que no viste"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="attention_arrow" transform="translate(60, 680)">
    <!-- Glowing bouncing arrow pointing downward -->
    <g id="attention_arrow_icon" transform="translate(480, 50)">
      <circle class="alert-ring alert-ring-1" r="50" fill="none" stroke="{accent}" stroke-width="3" stroke-opacity="0.8"/>
      <circle class="alert-ring alert-ring-2" r="80" fill="none" stroke="{accent}" stroke-width="2" stroke-opacity="0.4"/>
      <path d="M 0,-40 L 0,38 M -26,10 L 0,42 L 26,10" fill="none" stroke="{accent}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="0" cy="0" r="14" fill="{accent}"/>
    </g>
    <!-- Card below arrow -->
    <g id="attention_arrow_card" transform="translate(40, 160)">
      <rect width="880" height="200" rx="28" fill="#18181B" fill-opacity="0.96" stroke="{accent}" stroke-width="3.5"/>
      <text id="arrow_label_text" x="440" y="80" font-family="'Impact', sans-serif" font-size="44" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="2">👀 {label.upper()}</text>
      <text id="arrow_sublabel_text" x="440" y="145" font-family="'Segoe UI', sans-serif" font-size="22" font-weight="600" fill="{accent}" text-anchor="middle">{sublabel}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "social_handle":
            handle = params.get("handle", "@creador_digital")
            platform = params.get("platform", "TikTok / Instagram")
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="social_handle" transform="translate(60, 120)">
    <rect width="460" height="96" rx="48" fill="#09090B" fill-opacity="0.90" stroke="{accent}" stroke-width="2.5"/>
    <circle cx="48" cy="48" r="28" fill="{accent}" fill-opacity="0.25"/>
    <text x="48" y="58" font-family="'Segoe UI', sans-serif" font-size="24" fill="{accent}" text-anchor="middle">⚡</text>
    <text x="96" y="44" font-family="'Montserrat', sans-serif" font-size="22" font-weight="900" fill="#FFFFFF">{handle}</text>
    <text x="96" y="72" font-family="'Segoe UI', sans-serif" font-size="14" font-weight="600" fill="{accent}">{platform}</text>
  </g>
</svg>"""

        elif preset_id == "quote_card":
            quote = params.get("quote", "La clave no es la suerte, es la retención.")
            author = params.get("author", "REGLA DE ORO").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="quote_card" transform="translate(60, 750)">
    <rect width="960" height="340" rx="32" fill="#0F172A" fill-opacity="0.92" stroke="{accent}" stroke-width="3"/>
    <text x="70" y="80" font-family="'Impact', serif" font-size="70" fill="{accent}" fill-opacity="0.6">“</text>
    <text x="70" y="160" font-family="'Montserrat', sans-serif" font-size="30" font-weight="700" fill="#FFFFFF">{quote[:48]}</text>
    <text x="70" y="210" font-family="'Montserrat', sans-serif" font-size="28" font-weight="600" fill="#E2E8F0">{quote[48:100]}</text>
    <rect x="70" y="260" width="160" height="32" rx="16" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="150" y="282" font-family="'Montserrat', sans-serif" font-size="14" font-weight="800" fill="{accent}" text-anchor="middle">— {author}</text>
  </g>
</svg>"""

        elif preset_id == "number_counter":
            number_val = params.get("number_val", "+150,000")
            label = params.get("label", "Nuevas Reproducciones")
            badge = params.get("badge", "MÉTRICA REAL").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="number_counter" transform="translate(60, 1280)">
    <rect width="960" height="300" rx="32" fill="#082F49" fill-opacity="0.92" stroke="{accent}" stroke-width="3"/>
    <rect x="50" y="32" width="160" height="32" rx="16" fill="{accent}" fill-opacity="0.25" stroke="{accent}" stroke-width="1.5"/>
    <text x="130" y="54" font-family="'Montserrat', sans-serif" font-size="13" font-weight="800" fill="{accent}" text-anchor="middle">{badge}</text>
    <text x="50" y="160" font-family="'Impact', sans-serif" font-size="94" font-weight="900" fill="{accent}">{number_val}</text>
    <text x="50" y="230" font-family="'Montserrat', sans-serif" font-size="28" font-weight="700" fill="#FFFFFF">{label}</text>
  </g>
</svg>"""

        elif preset_id == "warning_alert":
            w_title = params.get("warning_title", "¡DETÉNTE AQUÍ!").upper()
            w_desc = params.get("warning_desc", "Error que destruye tu retención")
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="warning_alert" transform="translate(60, 750)">
    <rect width="960" height="280" rx="28" fill="#1C1917" fill-opacity="0.95" stroke="{accent}" stroke-width="4"/>
    <rect x="0" y="0" width="960" height="14" rx="7" fill="{accent}"/>
    <text x="480" y="110" font-family="'Impact', sans-serif" font-size="64" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">⚠️ {w_title}</text>
    <text x="480" y="190" font-family="'Montserrat', sans-serif" font-size="26" font-weight="700" fill="#F5F5F4" text-anchor="middle">{w_desc}</text>
  </g>
</svg>"""

        elif preset_id == "split_chars_stagger":
            headline = params.get("headline") or params.get("title") or "TITULAR CINÉTICO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Efecto letra por letra con física cinemática"
            badge = params.get("badge", "SPLITTEXT 3D").upper()
            chars = list(headline.upper())
            char_elements = "".join(f'<tspan class="split-char" id="sc_{i}">{c if c != " " else "&#160;"}</tspan>' for i, c in enumerate(chars))
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="split_chars_stagger" transform="translate(60, 680)">
    <rect id="split_chars_bg" width="960" height="380" rx="32" fill="#0A0A0C" fill-opacity="0.94" stroke="{accent}" stroke-width="3"/>
    <rect id="split_chars_badge" x="380" y="36" width="200" height="38" rx="19" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="480" y="61" font-family="'Montserrat', sans-serif" font-size="14" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">✨ {badge}</text>
    <text id="split_chars_headline" x="480" y="190" font-family="'Impact', sans-serif" font-size="58" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="3">{char_elements}</text>
    <text id="split_chars_subheadline" x="480" y="270" font-family="'Segoe UI', sans-serif" font-size="24" font-weight="600" fill="#CBD5E1" text-anchor="middle">{subheadline}</text>
    <line id="split_chars_line" x1="180" y1="320" x2="780" y2="320" stroke="{accent}" stroke-width="3"/>
  </g>
</svg>"""

        elif preset_id == "split_words_pop":
            headline = params.get("headline") or params.get("title") or "PALABRA POR PALABRA VIRAL"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Escala elástica instantánea para TikTok"
            badge = params.get("badge", "WORD POP").upper()
            words = headline.split(" ")
            word_elements = "".join(f'<tspan class="split-word" id="sw_{i}">{w} </tspan>' for i, w in enumerate(words))
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="split_words_pop" transform="translate(60, 680)">
    <rect id="split_words_bg" width="960" height="380" rx="32" fill="#090A10" fill-opacity="0.95" stroke="{accent}" stroke-width="3.5"/>
    <rect id="split_words_badge" x="380" y="36" width="200" height="38" rx="19" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="480" y="61" font-family="'Montserrat', sans-serif" font-size="14" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">💥 {badge}</text>
    <text id="split_words_headline" x="480" y="190" font-family="'Impact', sans-serif" font-size="54" font-weight="900" fill="{accent}" text-anchor="middle">{word_elements}</text>
    <text id="split_words_subheadline" x="480" y="270" font-family="'Segoe UI', sans-serif" font-size="24" font-weight="600" fill="#FFFFFF" text-anchor="middle">{subheadline}</text>
    <rect id="split_words_accent_pill" x="280" y="320" width="400" height="6" rx="3" fill="{accent}"/>
  </g>
</svg>"""

        elif preset_id == "typewriter_cursor":
            headline = params.get("headline") or params.get("title") or "Escribiendo en tiempo real..."
            subheadline = params.get("subheadline") or params.get("subtitle") or "Cursor titilante y tecleo mecánico"
            badge = params.get("badge", "TYPEWRITER").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="typewriter_cursor" transform="translate(60, 680)">
    <rect id="tw_bg" width="960" height="360" rx="28" fill="#040711" fill-opacity="0.96" stroke="{accent}" stroke-width="3"/>
    <rect id="tw_badge_pill" x="50" y="32" width="200" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="150" y="55" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle">⌨️ {badge}</text>
    <text id="tw_text" x="50" y="170" font-family="'Consolas', monospace" font-size="44" font-weight="700" fill="#FFFFFF" data-full="{headline}"></text>
    <text id="tw_cursor" x="50" y="170" font-family="'Consolas', monospace" font-size="44" font-weight="700" fill="{accent}">▌</text>
    <text id="tw_subheadline" x="50" y="260" font-family="'Segoe UI', sans-serif" font-size="22" font-weight="600" fill="#94A3B8">{subheadline}</text>
    <line x1="50" y1="300" x2="910" y2="300" stroke="{accent}" stroke-opacity="0.3" stroke-width="1.5"/>
  </g>
</svg>"""

        elif preset_id == "scramble_matrix":
            headline = params.get("headline") or params.get("title") or "ACCESO CONCEDIDO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Decodificación cuántica en tiempo real"
            badge = params.get("badge", "MATRIX CYPHER").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="scramble_matrix" transform="translate(60, 680)">
    <rect id="matrix_bg" width="960" height="360" rx="28" fill="#020D08" fill-opacity="0.96" stroke="{accent}" stroke-width="3"/>
    <rect id="matrix_badge_pill" x="50" y="32" width="210" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="155" y="55" font-family="monospace" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle">📟 {badge}</text>
    <text id="matrix_text" x="480" y="180" font-family="'Courier New', monospace" font-size="52" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="4" data-target="{headline}">010110010110</text>
    <text id="matrix_subheadline" x="480" y="260" font-family="'Segoe UI', sans-serif" font-size="22" font-weight="600" fill="#6EE7B7" text-anchor="middle">{subheadline}</text>
    <line x1="120" y1="305" x2="840" y2="305" stroke="{accent}" stroke-width="2" stroke-dasharray="12 6"/>
  </g>
</svg>"""

        elif preset_id == "split_lines_mask":
            headline = params.get("headline") or params.get("title") or "LÍNEAS CINÉTICAS"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Máscara de corte vertical sincronizada"
            badge = params.get("badge", "MASK REVEAL").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <clipPath id="splitMask1"><rect x="0" y="80" width="960" height="110"/></clipPath>
    <clipPath id="splitMask2"><rect x="0" y="190" width="960" height="110"/></clipPath>
  </defs>
  <g id="split_lines_mask" transform="translate(60, 680)">
    <rect id="split_lines_bg" width="960" height="360" rx="28" fill="#080C16" fill-opacity="0.95" stroke="{accent}" stroke-width="3"/>
    <rect x="50" y="28" width="180" height="32" rx="16" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="140" y="50" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle">✂️ {badge}</text>
    <g clip-path="url(#splitMask1)">
      <text id="split_line_1" x="480" y="155" font-family="'Impact', sans-serif" font-size="54" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
    </g>
    <g clip-path="url(#splitMask2)">
      <text id="split_line_2" x="480" y="250" font-family="'Montserrat', sans-serif" font-size="26" font-weight="700" fill="{accent}" text-anchor="middle">{subheadline}</text>
    </g>
    <line id="split_line_divider" x1="100" y1="188" x2="860" y2="188" stroke="{accent}" stroke-width="2"/>
  </g>
</svg>"""

        elif preset_id == "kinetic_typography_scale":
            headline = params.get("headline") or params.get("title") or "IMPACTO TOTAL"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Escala monumental y sacudida de cámara"
            badge = params.get("badge", "KINETIC SCALE").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="kinetic_typography_scale" transform="translate(60, 640)">
    <rect id="kt_bg" width="960" height="420" rx="36" fill="#0F051D" fill-opacity="0.96" stroke="{accent}" stroke-width="4"/>
    <rect id="kt_badge" x="380" y="32" width="200" height="36" rx="18" fill="{accent}" fill-opacity="0.25" stroke="{accent}" stroke-width="1.5"/>
    <text x="480" y="56" font-family="'Montserrat', sans-serif" font-size="14" font-weight="900" fill="{accent}" text-anchor="middle">⚡ {badge}</text>
    <text id="kt_headline" x="480" y="210" font-family="'Impact', sans-serif" font-size="76" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="4">{headline}</text>
    <text id="kt_subheadline" x="480" y="295" font-family="'Montserrat', sans-serif" font-size="26" font-weight="800" fill="{accent}" text-anchor="middle">{subheadline}</text>
    <line id="kt_accent_line" x1="200" y1="350" x2="760" y2="350" stroke="#FFFFFF" stroke-width="3"/>
  </g>
</svg>"""

        elif preset_id == "bar_chart_grow":
            headline = params.get("headline") or params.get("metric") or "CRECIMIENTO +380%"
            subheadline = params.get("subheadline") or params.get("explanation") or "Evolución mensual de audiencia y engagement"
            badge = params.get("badge", "BAR CHART").upper()
            bars_data = [
                {"label": "MES 1", "h": 60, "val": "20%", "x": 100},
                {"label": "MES 2", "h": 110, "val": "45%", "x": 270},
                {"label": "MES 3", "h": 170, "val": "70%", "x": 440},
                {"label": "MES 4", "h": 220, "val": "92%", "x": 610},
                {"label": "ACTUAL", "h": 260, "val": "+380%", "x": 780},
            ]
            bars_svg = ""
            for i, b in enumerate(bars_data):
                fill_color = accent if i == 4 else "#334155"
                bars_svg += f"""
      <g class="bar-group" id="bar_group_{i}">
        <rect class="bar-col" id="bar_col_{i}" x="{b['x']}" y="{360 - b['h']}" width="80" height="{b['h']}" rx="14" fill="{fill_color}" data-target-h="{b['h']}" data-target-y="{360 - b['h']}"/>
        <text class="bar-val" id="bar_val_{i}" x="{b['x'] + 40}" y="{360 - b['h'] - 15}" font-family="'Impact', sans-serif" font-size="18" font-weight="900" fill="{accent if i == 4 else '#94A3B8'}" text-anchor="middle">{b['val']}</text>
        <text x="{b['x'] + 40}" y="390" font-family="'Segoe UI', sans-serif" font-size="14" font-weight="700" fill="#64748B" text-anchor="middle">{b['label']}</text>
      </g>"""
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="bar_chart_grow" transform="translate(60, 1140)">
    <rect width="960" height="460" rx="32" fill="#040D1A" fill-opacity="0.96" stroke="{accent}" stroke-width="3"/>
    <rect x="40" y="30" width="180" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="130" y="53" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle">📊 {badge}</text>
    <text x="40" y="105" font-family="'Impact', sans-serif" font-size="36" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="40" y="138" font-family="'Segoe UI', sans-serif" font-size="18" font-weight="600" fill="#94A3B8">{subheadline}</text>
    <line x1="80" y1="360" x2="880" y2="360" stroke="#1E293B" stroke-width="2"/>
    {bars_svg}
  </g>
</svg>"""

        elif preset_id == "percentage_circle_gauge":
            headline = params.get("headline") or params.get("metric") or "94%"
            subheadline = params.get("subheadline") or params.get("explanation") or "Tasa de Retención del Espectador"
            badge = params.get("badge", "GAUGE METRIC").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="percentage_circle_gauge" transform="translate(60, 1180)">
    <rect width="960" height="400" rx="32" fill="#030C16" fill-opacity="0.96" stroke="{accent}" stroke-width="3"/>
    <g transform="translate(240, 200) rotate(-90)">
      <circle r="110" fill="none" stroke="#1E293B" stroke-width="18"/>
      <circle id="gauge_bar" r="110" fill="none" stroke="{accent}" stroke-width="18" stroke-linecap="round" stroke-dasharray="691" stroke-dashoffset="691"/>
    </g>
    <text id="gauge_percent_text" x="240" y="215" font-family="'Impact', sans-serif" font-size="62" font-weight="900" fill="#FFFFFF" text-anchor="middle" data-target="94">{headline}</text>
    <rect x="420" y="60" width="180" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="510" y="83" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle">🎯 {badge}</text>
    <text x="420" y="160" font-family="'Impact', sans-serif" font-size="44" font-weight="900" fill="#FFFFFF">RETENCIÓN MÁXIMA</text>
    <text x="420" y="220" font-family="'Segoe UI', sans-serif" font-size="22" font-weight="600" fill="{accent}">{subheadline}</text>
    <text x="420" y="265" font-family="'Segoe UI', sans-serif" font-size="16" font-weight="500" fill="#94A3B8">Supera el 90% de los videos del nicho</text>
  </g>
</svg>"""

        elif preset_id == "crypto_stock_badge":
            headline = params.get("headline") or params.get("metric") or "+148.5% ATH"
            subheadline = params.get("subheadline") or params.get("explanation") or "Bitcoin Breakout • Rompimiento Alcista"
            badge = params.get("badge", "BULLISH BREAKOUT").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="cryptoGlow" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.0"/>
    </linearGradient>
  </defs>
  <g id="crypto_stock_badge" transform="translate(60, 1200)">
    <rect width="960" height="360" rx="32" fill="#02170E" fill-opacity="0.96" stroke="{accent}" stroke-width="3"/>
    <rect id="crypto_badge_pill" x="50" y="32" width="230" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="165" y="55" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle">🚀 {badge}</text>
    <text id="crypto_price_val" x="50" y="140" font-family="'Impact', sans-serif" font-size="64" font-weight="900" fill="{accent}">{headline}</text>
    <text x="50" y="195" font-family="'Segoe UI', sans-serif" font-size="24" font-weight="700" fill="#FFFFFF">{subheadline}</text>
    <path id="crypto_area" d="M 500 280 L 580 230 L 660 250 L 740 180 L 820 150 L 900 90 L 900 280 Z" fill="url(#cryptoGlow)"/>
    <path id="crypto_trend_path" d="M 500 280 L 580 230 L 660 250 L 740 180 L 820 150 L 900 90" fill="none" stroke="{accent}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="600" stroke-dashoffset="600"/>
    <circle id="crypto_pulsing_dot" cx="900" cy="90" r="8" fill="#FFFFFF"/>
    <line x1="50" y1="280" x2="900" y2="280" stroke="#064E3B" stroke-width="2"/>
  </g>
</svg>"""

        elif preset_id == "cta_subscribe_bell":
            headline = params.get("headline") or params.get("cta_text") or "SUSCRÍBETE AL CANAL"
            subheadline = params.get("subheadline") or params.get("subtext") or "Activa la campanita para no perderte nada"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="cta_subscribe_bell" transform="translate(60, 1420)">
    <rect id="cta_main_card" width="960" height="240" rx="36" fill="#0A0A0C" fill-opacity="0.95" stroke="{accent}" stroke-width="3.5"/>
    <g id="cta_btn" transform="translate(60, 60)">
      <rect id="cta_btn_rect" width="460" height="110" rx="28" fill="#DC2626"/>
      <text id="cta_btn_text" x="230" y="70" font-family="'Montserrat', sans-serif" font-size="30" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
    </g>
    <g id="cta_bell_wrapper" transform="translate(620, 115)">
      <g id="cta_bell">
        <path d="M -18,12 C -18,-18 18,-18 18,12 L 24,18 L -24,18 Z M -6,22 C -6,26 6,26 6,22" fill="{accent}"/>
        <circle cx="0" cy="-20" r="5" fill="{accent}"/>
      </g>
      <path class="bell-wave bell-wave-1" d="M 32,-10 A 30 30 0 0 1 32,20" fill="none" stroke="{accent}" stroke-width="4" stroke-linecap="round"/>
      <path class="bell-wave bell-wave-2" d="M 46,-20 A 45 45 0 0 1 46,30" fill="none" stroke="{accent}" stroke-width="4" stroke-linecap="round"/>
    </g>
    <g id="cta_cursor_hand" transform="translate(700, 260)">
      <polygon points="0,0 12,32 18,22 32,22" fill="#FFFFFF" stroke="#000000" stroke-width="2"/>
    </g>
    <text x="480" y="210" font-family="'Segoe UI', sans-serif" font-size="18" font-weight="600" fill="#94A3B8" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "highlighter_marker_draw":
            headline = params.get("headline") or params.get("title") or "CONCEPTO CLAVE CRÍTICO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Subrayado con rotulador fluorescente"
            badge = params.get("badge", "HIGHLIGHTER").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="highlighter_marker_draw" transform="translate(60, 720)">
    <rect id="marker_bg" width="960" height="300" rx="28" fill="#0F172A" fill-opacity="0.96" stroke="#334155" stroke-width="3"/>
    <rect x="50" y="30" width="180" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="140" y="53" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle">🖊️ {badge}</text>
    <path id="marker_stroke_path" d="M 60 160 L 900 160" fill="none" stroke="{accent}" stroke-width="50" stroke-linecap="round" stroke-opacity="0.45" stroke-dasharray="840" stroke-dashoffset="840"/>
    <text id="marker_headline" x="480" y="175" font-family="'Impact', sans-serif" font-size="52" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="2">{headline}</text>
    <text id="marker_subheadline" x="480" y="245" font-family="'Segoe UI', sans-serif" font-size="22" font-weight="600" fill="#CBD5E1" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "retention_timer_countdown":
            headline = params.get("headline") or params.get("title") or "CUENTA REGRESIVA"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Segundos restantes de atención crítica"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="retention_timer_countdown" transform="translate(60, 780)">
    <rect width="960" height="240" rx="28" fill="#0F172A" fill-opacity="0.95" stroke="{accent}" stroke-width="3"/>
    <g transform="translate(140, 120) rotate(-90)">
      <circle r="60" fill="none" stroke="#334155" stroke-width="10"/>
      <circle id="timer_circle_bar" r="60" fill="none" stroke="{accent}" stroke-width="10" stroke-linecap="round" stroke-dasharray="377" stroke-dashoffset="0"/>
    </g>
    <text id="mgTimerCountdownVal" x="140" y="130" font-family="'Impact', sans-serif" font-size="34" font-weight="900" fill="#FFFFFF" text-anchor="middle">00:05</text>
    <text x="260" y="105" font-family="'Impact', sans-serif" font-size="44" font-weight="900" fill="{accent}">{headline}</text>
    <text x="260" y="155" font-family="'Montserrat', sans-serif" font-size="22" font-weight="600" fill="#FFFFFF">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "creator_profile_pill":
            headline = params.get("headline") or params.get("title") or "CREADOR PRO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "1.2M Seguidores • @creador"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="creator_profile_pill" transform="translate(100, 780)">
    <rect id="creator_pill_bg" width="880" height="190" rx="40" fill="#030712" fill-opacity="0.95" stroke="{accent}" stroke-width="3.5"/>
    <circle cx="95" cy="95" r="50" fill="{accent}" fill-opacity="0.3" stroke="{accent}" stroke-width="3"/>
    <text x="95" y="105" font-family="'Impact', sans-serif" font-size="36" fill="{accent}" text-anchor="middle">★</text>
    <text x="180" y="85" font-family="'Impact', sans-serif" font-size="40" font-weight="900" fill="#FFFFFF">{headline}</text>
    <rect x="180" y="105" width="28" height="28" rx="14" fill="#38BDF8"/>
    <text x="194" y="124" font-family="'Segoe UI', sans-serif" font-size="16" font-weight="900" fill="#000000" text-anchor="middle">✓</text>
    <text x="220" y="126" font-family="'Segoe UI', sans-serif" font-size="20" font-weight="700" fill="{accent}">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "manim_math_formula":
            headline = params.get("headline") or params.get("title") or "E = mc²"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Equivalencia Masa-Energía"
            badge = params.get("badge", "MANIM MATH").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="manim_math_formula" transform="translate(60, 740)">
    <rect width="960" height="340" rx="28" fill="#030712" fill-opacity="0.95" stroke="{accent}" stroke-width="3"/>
    <rect x="50" y="32" width="190" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="145" y="55" font-family="'Montserrat', sans-serif" font-size="13" font-weight="800" fill="{accent}" text-anchor="middle">{badge}</text>
    <text x="480" y="175" font-family="'Times New Roman', serif" font-style="italic" font-size="78" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="4">{headline}</text>
    <line x1="160" y1="225" x2="800" y2="225" stroke="{accent}" stroke-width="2" stroke-dasharray="10 6"/>
    <text x="480" y="280" font-family="'Segoe UI', sans-serif" font-size="24" font-weight="600" fill="#9CA3AF" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "manim_coordinate_plot":
            headline = params.get("headline") or params.get("title") or "f(x) = Sigmoide"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Plano Cartesiano 3Blue1Brown"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="manim_coordinate_plot" transform="translate(60, 720)">
    <rect width="960" height="420" rx="28" fill="#050B14" fill-opacity="0.96" stroke="{accent}" stroke-width="3"/>
    <!-- Axes -->
    <line x1="120" y1="340" x2="840" y2="340" stroke="#475569" stroke-width="2.5"/>
    <line x1="200" y1="80" x2="200" y2="360" stroke="#475569" stroke-width="2.5"/>
    <!-- Sigmoid curve -->
    <path d="M 200 320 C 350 320, 420 180, 800 120" fill="none" stroke="{accent}" stroke-width="5" stroke-linecap="round"/>
    <circle cx="480" cy="210" r="8" fill="{accent}"/>
    <text x="830" y="330" font-family="'Segoe UI', sans-serif" font-size="18" font-weight="700" fill="#94A3B8">X</text>
    <text x="215" y="100" font-family="'Segoe UI', sans-serif" font-size="18" font-weight="700" fill="#94A3B8">Y</text>
    <text x="480" y="60" font-family="'Montserrat', sans-serif" font-size="28" font-weight="800" fill="#FFFFFF" text-anchor="middle">{headline}</text>
    <text x="480" y="390" font-family="'Segoe UI', sans-serif" font-size="20" font-weight="500" fill="#94A3B8" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "manim_geometry_vector":
            headline = params.get("headline") or params.get("title") or "v · w = ||v|| ||w|| cos(θ)"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Producto Punto y Proyecciones"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="manim_geometry_vector" transform="translate(60, 740)">
    <rect width="960" height="340" rx="28" fill="#0B0F19" fill-opacity="0.95" stroke="{accent}" stroke-width="3"/>
    <!-- Vectors -->
    <line x1="200" y1="250" x2="520" y2="120" stroke="{accent}" stroke-width="4" marker-end="url(#arrow)"/>
    <line x1="200" y1="250" x2="600" y2="250" stroke="#10B981" stroke-width="4"/>
    <path d="M 270 250 A 70 70 0 0 0 250 220" fill="none" stroke="#F59E0B" stroke-width="2"/>
    <text x="280" y="235" font-family="'Segoe UI', sans-serif" font-size="16" font-weight="bold" fill="#F59E0B">θ</text>
    <text x="480" y="65" font-family="'Times New Roman', serif" font-size="36" font-weight="bold" fill="#FFFFFF" text-anchor="middle">{headline}</text>
    <text x="480" y="305" font-family="'Segoe UI', sans-serif" font-size="20" font-weight="600" fill="#94A3B8" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "code_walkthrough_terminal":
            headline = params.get("headline") or params.get("title") or "const short = await factory.render();"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Motion Canvas Procedural WebCodecs"
            badge = params.get("badge", "TYPESCRIPT").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="code_walkthrough_terminal" transform="translate(60, 720)">
    <rect id="code_terminal_window" width="960" height="360" rx="24" fill="#0D1117" fill-opacity="0.97" stroke="{accent}" stroke-width="3"/>
    <!-- macOS traffic buttons -->
    <g id="code_traffic_dots">
      <circle cx="45" cy="40" r="7" fill="#EF4444"/>
      <circle cx="70" cy="40" r="7" fill="#F59E0B"/>
      <circle cx="95" cy="40" r="7" fill="#10B981"/>
    </g>
    <text x="480" y="46" font-family="'Consolas', monospace" font-size="14" font-weight="600" fill="#6E7681" text-anchor="middle">terminal.ts — {badge}</text>
    <line x1="0" y1="75" x2="960" y2="75" stroke="#30363D" stroke-width="1.5"/>
    <!-- Code lines -->
    <g class="code-line" id="code_line_1">
      <text x="40" y="130" font-family="'Consolas', monospace" font-size="20" fill="#6E7681">1</text>
      <text x="80" y="130" font-family="'Consolas', monospace" font-size="22" font-weight="700" fill="#EC4899">import</text>
      <text x="175" y="130" font-family="'Consolas', monospace" font-size="22" fill="#E6EDF3">{{ createShort }}</text>
      <text x="360" y="130" font-family="'Consolas', monospace" font-size="22" font-weight="700" fill="#EC4899">from</text>
      <text x="440" y="130" font-family="'Consolas', monospace" font-size="22" fill="#7EE787">"@motion-canvas/2d";</text>
    </g>
    <g class="code-line" id="code_line_2">
      <text x="40" y="190" font-family="'Consolas', monospace" font-size="20" fill="#6E7681">2</text>
      <text x="80" y="190" font-family="'Consolas', monospace" font-size="24" font-weight="700" fill="{accent}">{headline}</text>
      <text id="term_cursor" x="720" y="190" font-family="'Consolas', monospace" font-size="24" font-weight="700" fill="{accent}">▌</text>
    </g>
    <g class="code-line" id="code_line_3">
      <text x="40" y="250" font-family="'Consolas', monospace" font-size="20" fill="#6E7681">3</text>
      <text x="80" y="250" font-family="'Consolas', monospace" font-size="20" fill="#8B949E">// {subheadline}</text>
    </g>
  </g>
</svg>"""

        elif preset_id == "flowchart_nodes_diagram":
            headline = params.get("headline") or params.get("title") or "API Gateway ➔ Workers ➔ FFmpeg"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Arquitectura Distribuida"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="flowchart_nodes_diagram" transform="translate(60, 750)">
    <rect width="960" height="300" rx="24" fill="#090D16" fill-opacity="0.95" stroke="{accent}" stroke-width="3"/>
    <!-- Node 1 -->
    <g class="flow-node" id="flow_node_1">
      <rect x="60" y="90" width="220" height="80" rx="16" fill="#1E293B" stroke="{accent}" stroke-width="2"/>
      <text x="170" y="138" font-family="'Segoe UI', sans-serif" font-size="18" font-weight="700" fill="#FFFFFF" text-anchor="middle">API Fast-API</text>
    </g>
    <!-- Arrow 1 -->
    <line id="flow_arrow_1" x1="280" y1="130" x2="360" y2="130" stroke="{accent}" stroke-width="4" stroke-dasharray="80" stroke-dashoffset="80"/>
    <!-- Node 2 -->
    <g class="flow-node" id="flow_node_2">
      <rect x="370" y="90" width="220" height="80" rx="16" fill="#1E293B" stroke="#10B981" stroke-width="2"/>
      <text x="480" y="138" font-family="'Segoe UI', sans-serif" font-size="18" font-weight="700" fill="#10B981" text-anchor="middle">Worker Pipeline</text>
    </g>
    <!-- Arrow 2 -->
    <line id="flow_arrow_2" x1="590" y1="130" x2="670" y2="130" stroke="#10B981" stroke-width="4" stroke-dasharray="80" stroke-dashoffset="80"/>
    <!-- Node 3 -->
    <g class="flow-node" id="flow_node_3">
      <rect x="680" y="90" width="220" height="80" rx="16" fill="#1E293B" stroke="#F59E0B" stroke-width="2"/>
      <text x="790" y="138" font-family="'Segoe UI', sans-serif" font-size="18" font-weight="700" fill="#F59E0B" text-anchor="middle">FFmpeg Engine</text>
    </g>
    <!-- Subtitle -->
    <text x="480" y="240" font-family="'Montserrat', sans-serif" font-size="20" font-weight="600" fill="#FFFFFF" text-anchor="middle">{headline}</text>
  </g>
</svg>"""

        elif preset_id == "tech_stack_pill_orbit":
            headline = params.get("headline") or params.get("title") or "Python • Fast-API • Remotion"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Stack Tecnológico Multi-Motor"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="tech_stack_pill_orbit" transform="translate(60, 1440)">
    <rect width="960" height="190" rx="28" fill="#180B2E" fill-opacity="0.94" stroke="{accent}" stroke-width="3"/>
    <text x="480" y="80" font-family="'Montserrat', sans-serif" font-size="30" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
    <text x="480" y="135" font-family="'Segoe UI', sans-serif" font-size="19" font-weight="600" fill="{accent}" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "remotion_audio_waveform":
            headline = params.get("headline") or params.get("title") or "ESPECTRO DE AUDIO REACTIVO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Sincronización Rítmica Remotion"
            wave_heights = [60, 100, 130, 90, 40, 110, 140, 80, 120, 50, 100, 140, 70, 110, 60, 100, 40]
            bars_svg = "".join(f'<rect class="wave-bar" id="wave_bar_{i}" x="{i * 35}" y="{140 - wave_heights[i%17]}" width="16" height="{wave_heights[i%17]}" rx="8" fill="{accent}" data-base-h="{wave_heights[i%17]}"/>' for i in range(17))
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="remotion_audio_waveform" transform="translate(60, 1380)">
    <rect id="wave_bg" width="960" height="260" rx="28" fill="#0B0F19" fill-opacity="0.95" stroke="{accent}" stroke-width="3"/>
    <g id="wave_bars_group" transform="translate(180, 50)">
      {bars_svg}
    </g>
    <text id="wave_headline" x="480" y="225" font-family="'Montserrat', sans-serif" font-size="22" font-weight="800" fill="#FFFFFF" text-anchor="middle">{headline}</text>
  </g>
</svg>"""

        elif preset_id == "remotion_device_mockup":
            headline = params.get("headline") or params.get("title") or "DEMO DE APLICACIÓN EN VIVO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Grabación Enmarcada en iPhone"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="remotion_device_mockup" transform="translate(180, 520)">
    <!-- Phone body -->
    <rect width="720" height="960" rx="60" fill="#030712" stroke="#374151" stroke-width="8"/>
    <!-- Screen -->
    <rect x="25" y="25" width="670" height="910" rx="42" fill="#0F172A" stroke="{accent}" stroke-width="2"/>
    <!-- Dynamic Island -->
    <rect x="280" y="45" width="160" height="34" rx="17" fill="#000000"/>
    <circle cx="395" cy="62" r="5" fill="#1E293B"/>
    <text x="360" y="450" font-family="'Montserrat', sans-serif" font-size="34" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
    <text x="360" y="520" font-family="'Segoe UI', sans-serif" font-size="22" font-weight="600" fill="{accent}" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "remotion_push_notification":
            headline = params.get("headline") or params.get("title") or "¡Tu video se hizo viral!"
            subheadline = params.get("subheadline") or params.get("subtitle") or "+250,000 reproducciones orgánicas"
            badge = params.get("badge", "NOTIFICACIÓN").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="remotion_push_notification" transform="translate(80, 180)">
    <!-- iOS Push Card -->
    <rect width="920" height="190" rx="36" fill="#1C1917" fill-opacity="0.94" stroke="#44403C" stroke-width="2"/>
    <!-- App icon -->
    <rect x="40" y="40" width="48" height="48" rx="14" fill="{accent}"/>
    <text x="64" y="72" font-family="'Segoe UI', sans-serif" font-size="24" font-weight="bold" fill="#000000" text-anchor="middle">★</text>
    <!-- App Header -->
    <text x="105" y="60" font-family="'Segoe UI', sans-serif" font-size="17" font-weight="700" fill="#A8A29E">CONTENT FACTORY</text>
    <text x="860" y="60" font-family="'Segoe UI', sans-serif" font-size="15" font-weight="500" fill="#78716C" text-anchor="end">AHORA</text>
    <!-- Title & Body -->
    <text x="105" y="105" font-family="'Segoe UI', sans-serif" font-size="24" font-weight="800" fill="#FFFFFF">{headline}</text>
    <text x="105" y="145" font-family="'Segoe UI', sans-serif" font-size="19" font-weight="500" fill="#D6D3D1">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "remotion_split_screen_duet":
            headline = params.get("headline") or params.get("title") or "DEBATE / DUETO EN VIVO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Host A vs Invitado B"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="remotion_split_screen_duet" transform="translate(0, 0)">
    <!-- Split line -->
    <line x1="0" y1="{height//2}" x2="{width}" y2="{height//2}" stroke="{accent}" stroke-width="4"/>
    <!-- Speaker tags -->
    <rect x="50" y="{height//2 - 70}" width="240" height="50" rx="14" fill="#000000" fill-opacity="0.8" stroke="{accent}" stroke-width="1.5"/>
    <text x="170" y="{height//2 - 38}" font-family="'Montserrat', sans-serif" font-size="18" font-weight="800" fill="#FFFFFF" text-anchor="middle">ORADOR 1</text>
    <rect x="50" y="{height//2 + 20}" width="240" height="50" rx="14" fill="#000000" fill-opacity="0.8" stroke="{accent}" stroke-width="1.5"/>
    <text x="170" y="{height//2 + 52}" font-family="'Montserrat', sans-serif" font-size="18" font-weight="800" fill="{accent}" text-anchor="middle">ORADOR 2</text>
  </g>
</svg>"""

        elif preset_id == "flip_card_stack":
            headline = params.get("headline") or params.get("title") or "3 SECRETOS PARA CRECER"
            subheadline = params.get("subheadline") or params.get("subtitle") or "1. Hook inicial • 2. Retención • 3. CTA"
            badge = params.get("badge", "CARD STACK").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="flip_card_stack" transform="translate(100, 720)">
    <!-- Back Card 3 -->
    <rect x="60" y="44" width="760" height="260" rx="28" fill="#0B132B" fill-opacity="0.65" stroke="#1E293B" stroke-width="2"/>
    <!-- Middle Card 2 -->
    <rect x="30" y="22" width="820" height="260" rx="28" fill="#0F172A" fill-opacity="0.82" stroke="#334155" stroke-width="2.5"/>
    <!-- Front Card 1 -->
    <rect x="0" y="0" width="880" height="260" rx="30" fill="#030712" fill-opacity="0.96" stroke="{accent}" stroke-width="3.5"/>
    <rect x="40" y="30" width="160" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="120" y="53" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">{badge}</text>
    <text x="40" y="130" font-family="'Impact', sans-serif" font-size="44" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="40" y="195" font-family="'Montserrat', sans-serif" font-size="22" font-weight="600" fill="#94A3B8">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "proximity_scale_grid":
            headline = params.get("headline") or params.get("title") or "FOCO DE ATENCIÓN"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Distorsión magnética por proximidad"
            badge = params.get("badge", "PROXIMITY GRID").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="proximity_grid_wrapper" transform="translate(60, 680)">
    <rect width="960" height="480" rx="32" fill="#030712" fill-opacity="0.94" stroke="{accent}" stroke-width="3"/>
    <rect x="40" y="32" width="230" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="155" y="55" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">{badge}</text>
    <text x="920" y="55" font-family="'Segoe UI', sans-serif" font-size="14" font-weight="700" fill="#64748B" text-anchor="end">GRID FX PRO</text>
    <g id="proximityGridCells" transform="translate(40, 95)">
      <rect class="proximity-cell" x="0" y="0" width="270" height="95" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
      <rect class="proximity-cell" x="305" y="0" width="270" height="95" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
      <rect class="proximity-cell" x="610" y="0" width="270" height="95" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
      <rect class="proximity-cell" x="0" y="115" width="270" height="105" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
      <rect class="proximity-cell proximity-focal" x="295" y="105" width="290" height="125" rx="22" fill="#1E293B" stroke="{accent}" stroke-width="4"/>
      <rect class="proximity-cell" x="610" y="115" width="270" height="105" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
      <text x="440" y="160" font-family="'Impact', sans-serif" font-size="28" font-weight="900" fill="{accent}" text-anchor="middle">{headline}</text>
      <text x="440" y="195" font-family="'Montserrat', sans-serif" font-size="15" font-weight="700" fill="#F8FAFC" text-anchor="middle">{subheadline}</text>
      <rect class="proximity-cell" x="0" y="240" width="270" height="95" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
      <rect class="proximity-cell" x="305" y="240" width="270" height="95" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
      <rect class="proximity-cell" x="610" y="240" width="270" height="95" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
    </g>
  </g>
</svg>"""

        elif preset_id == "velocity_skew":
            headline = params.get("headline") or params.get("title") or "VELOCIDAD EXTREMA"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Inercia y aceleración calculada en tiempo real"
            badge = params.get("badge", "VELOCITY SKEW").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="velocity_skew_card" transform="translate(100, 780) skewX(-7) skewY(2)">
    <line x1="-60" y1="50" x2="940" y2="50" stroke="{accent}" stroke-opacity="0.3" stroke-width="2" stroke-dasharray="16 12"/>
    <line x1="-40" y1="180" x2="960" y2="180" stroke="{accent}" stroke-opacity="0.3" stroke-width="2" stroke-dasharray="24 16"/>
    <rect width="880" height="260" rx="28" fill="#030712" fill-opacity="0.96" stroke="{accent}" stroke-width="3.5"/>
    <rect x="40" y="30" width="200" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="140" y="53" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">{badge}</text>
    <text x="840" y="53" font-family="'Segoe UI', sans-serif" font-size="14" font-weight="700" fill="#64748B" text-anchor="end">INERTIA FX</text>
    <text x="40" y="135" font-family="'Impact', sans-serif" font-size="52" font-style="italic" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="40" y="200" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "scrubbed_bento_gallery":
            headline = params.get("headline") or params.get("title") or "CARACTERÍSTICAS PRO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "1. Ultrarrápido • 2. IA Local • 3. Sin Coste"
            badge = params.get("badge", "BENTO SHOWCASE").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="bento_gallery_group" transform="translate(60, 700)">
    <rect x="0" y="0" width="560" height="360" rx="30" fill="#030712" fill-opacity="0.95" stroke="{accent}" stroke-width="3.5"/>
    <rect x="35" y="32" width="180" height="32" rx="16" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="125" y="53" font-family="'Montserrat', sans-serif" font-size="12" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">{badge}</text>
    <text x="35" y="130" font-family="'Impact', sans-serif" font-size="44" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="35" y="195" font-family="'Montserrat', sans-serif" font-size="20" font-weight="600" fill="#94A3B8">{subheadline}</text>
    <text x="35" y="320" font-family="'Segoe UI', sans-serif" font-size="13" font-weight="700" fill="#64748B">BENTO FX</text>
    <rect x="585" y="0" width="375" height="170" rx="26" fill="#0B132B" fill-opacity="0.92" stroke="#334155" stroke-width="2.5"/>
    <text x="615" y="55" font-family="'Montserrat', sans-serif" font-size="13" font-weight="800" fill="{accent}">⚡ TIEMPO RÉCORD</text>
    <text x="615" y="115" font-family="'Impact', sans-serif" font-size="36" font-weight="900" fill="#FFFFFF">10x MÁS RÁPIDO</text>
    <rect x="585" y="190" width="375" height="170" rx="26" fill="#0F172A" fill-opacity="0.92" stroke="#334155" stroke-width="2.5"/>
    <text x="615" y="245" font-family="'Montserrat', sans-serif" font-size="13" font-weight="800" fill="#10B981">🔒 PRIVACIDAD 100%</text>
    <text x="615" y="305" font-family="'Impact', sans-serif" font-size="36" font-weight="900" fill="#FFFFFF">LOCAL OFFLINE</text>
  </g>
</svg>"""

        elif preset_id == "directional_marquee":
            headline = params.get("headline") or params.get("title") or "NOTICIA DE IMPACTO • TENDENCIA VIRAL • NO TE LO PIERDAS"
            subheadline = params.get("subheadline") or params.get("subtitle") or "ACCESO ANTICIPADO • NUEVO ALGORITMO • DESCÚBRELO HOY"
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="marquee_tape_top" transform="translate(-80, 800) rotate(-3)">
    <rect width="1240" height="70" fill="{accent}"/>
    <text x="620" y="47" font-family="'Impact', sans-serif" font-size="34" font-weight="900" fill="#000000" text-anchor="middle" letter-spacing="3">{str(headline).upper()}</text>
  </g>
  <g id="marquee_tape_bottom" transform="translate(-80, 860) rotate(2)">
    <rect width="1240" height="70" fill="#030712" fill-opacity="0.95" stroke="{accent}" stroke-width="3"/>
    <text x="620" y="47" font-family="'Impact', sans-serif" font-size="30" font-weight="900" fill="#FFFFFF" text-anchor="middle" letter-spacing="3">{str(subheadline).upper()}</text>
  </g>
</svg>"""

        elif preset_id == "cursor_tilt_3d":
            headline = params.get("headline") or params.get("title") or "MODELO HOLOGRÁFICO"
            subheadline = params.get("subheadline") or params.get("subtitle") or "Perspectiva tridimensional flotante"
            badge = params.get("badge", "3D PERSPECTIVE").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="cursor_tilt_3d_card" transform="translate(110, 730) rotate(-4) scale(0.98)">
    <rect x="25" y="30" width="860" height="300" rx="32" fill="#000000" fill-opacity="0.6"/>
    <rect x="0" y="0" width="860" height="300" rx="32" fill="#080C14" fill-opacity="0.95" stroke="{accent}" stroke-width="3.5"/>
    <path d="M 0 0 L 220 0 L 80 300 L 0 300 Z" fill="{accent}" fill-opacity="0.08"/>
    <rect x="40" y="35" width="200" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="140" y="58" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">{badge}</text>
    <text x="820" y="58" font-family="'Segoe UI', sans-serif" font-size="14" font-weight="700" fill="#64748B" text-anchor="end">3D TILT FX</text>
    <text x="40" y="145" font-family="'Impact', sans-serif" font-size="52" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="40" y="220" font-family="'Montserrat', sans-serif" font-size="24" font-weight="700" fill="{accent}">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "physics_confetti_burst":
            headline = params.get("headline") or params.get("title") or "¡META ALCANZADA!"
            subheadline = params.get("subheadline") or params.get("subtitle") or "+1,000,000 DE REPRODUCCIONES"
            badge = params.get("badge", "CELEBRACIÓN").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="confetti_particles">
    <rect x="140" y="620" width="22" height="12" rx="4" fill="#FACC15" transform="rotate(25 140 620)"/>
    <circle cx="280" cy="590" r="10" fill="#EC4899"/>
    <rect x="850" y="610" width="24" height="14" rx="4" fill="#10B981" transform="rotate(-35 850 610)"/>
    <circle cx="920" cy="680" r="12" fill="#38BDF8"/>
    <rect x="180" y="990" width="26" height="14" rx="4" fill="#A855F7" transform="rotate(40 180 990)"/>
    <rect x="820" y="1020" width="20" height="10" rx="3" fill="#F59E0B" transform="rotate(-20 820 1020)"/>
    <circle cx="220" cy="1060" r="8" fill="#F43F5E"/>
    <circle cx="880" cy="1080" r="11" fill="#38BDF8"/>
  </g>
  <g id="celebration_card" transform="translate(100, 720)">
    <rect width="880" height="280" rx="32" fill="#030712" fill-opacity="0.96" stroke="{accent}" stroke-width="4"/>
    <rect x="340" y="30" width="200" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="440" y="53" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">🎉 {badge}</text>
    <text x="440" y="140" font-family="'Impact', sans-serif" font-size="56" font-weight="900" fill="#FFFFFF" text-anchor="middle">{headline}</text>
    <text x="440" y="215" font-family="'Montserrat', sans-serif" font-size="24" font-weight="800" fill="{accent}" text-anchor="middle">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "anime_stagger_grid_ripple":
            headline = params.get("headline") or "ONDA ESCALONADA ANIME.JS"
            subheadline = params.get("subheadline") or "Stagger radial con física elástica"
            badge = params.get("badge", "ANIME.JS STAGGER").upper()
            dots_svg = "".join(f'<circle id="stagger_dot_{r}_{c}" cx="{140 + c*180}" cy="{480 + r*70}" r="8" fill="{accent}" fill-opacity="{0.35 + (r+c)*0.06}" data-row="{r}" data-col="{c}"/>' for r in range(4) for c in range(5))
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="anime_grid_dots">
    {dots_svg}
  </g>
  <g id="anime_stagger_card" transform="translate(100, 800)">
    <rect width="880" height="280" rx="32" fill="#090514" fill-opacity="0.95" stroke="{accent}" stroke-width="3.5"/>
    <rect x="40" y="32" width="240" height="36" rx="18" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="160" y="56" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">✨ {badge}</text>
    <text x="840" y="56" font-family="monospace" font-size="12" font-weight="700" fill="{accent}" text-anchor="end">⚡ ANIME.JS V4</text>
    <text x="40" y="135" font-family="'Impact', sans-serif" font-size="44" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="40" y="200" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}">{subheadline}</text>
    <rect x="40" y="240" width="800" height="5" rx="2.5" fill="{accent}" fill-opacity="0.5"/>
  </g>
</svg>"""

        elif preset_id == "anime_svg_path_draw":
            headline = params.get("headline") or "TRAZADO VECTORIAL SVG"
            subheadline = params.get("subheadline") or "Stroke-dashoffset continuo de alta precisión"
            badge = params.get("badge", "SVG LINE DRAW").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="anime_draw_card" transform="translate(100, 720)">
    <rect width="880" height="300" rx="32" fill="#030712" fill-opacity="0.94"/>
    <rect id="animeNeonBorderPath" width="880" height="300" rx="32" fill="none" stroke="{accent}" stroke-width="4" stroke-dasharray="2360" stroke-dashoffset="0"/>
    <rect x="40" y="32" width="220" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="150" y="55" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">⚡ {badge}</text>
    <text x="840" y="55" font-family="monospace" font-size="12" font-weight="700" fill="{accent}" text-anchor="end">ANIME.JS PATH</text>
    <text x="40" y="140" font-family="'Impact', sans-serif" font-size="48" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="40" y="210" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "anime_circle_pulse_radar":
            headline = params.get("headline") or "RADAR DE ATENCIÓN"
            subheadline = params.get("subheadline") or "Pulsos continuos para retener el scroll"
            badge = params.get("badge", "RADAR PULSE").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="anime_radar_rings" transform="translate(540, 700)">
    <circle id="radar_ring_3" r="160" fill="none" stroke="{accent}" stroke-width="2" stroke-opacity="0.25"/>
    <circle id="radar_ring_2" r="110" fill="none" stroke="{accent}" stroke-width="2.5" stroke-opacity="0.5"/>
    <circle id="radar_ring_1" r="60" fill="none" stroke="{accent}" stroke-width="3" stroke-opacity="0.8"/>
    <circle cx="0" cy="0" r="16" fill="{accent}"/>
  </g>
  <g id="anime_radar_card" transform="translate(100, 940)">
    <rect width="880" height="260" rx="30" fill="#0B0F19" fill-opacity="0.95" stroke="{accent}" stroke-width="3.5"/>
    <rect x="40" y="28" width="200" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="140" y="51" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">🎯 {badge}</text>
    <text x="40" y="125" font-family="'Impact', sans-serif" font-size="44" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="40" y="190" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "anime_kinetic_elastic_pop":
            headline = params.get("headline") or "REBOTE ARMÓNICO ELÁSTICO"
            subheadline = params.get("subheadline") or "Curva easeOutElastic con factor de amortiguación"
            badge = params.get("badge", "ELASTIC POP").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="anime_elastic_container" transform="translate(100, 780)">
    <rect id="anime_elastic_card" width="880" height="290" rx="32" fill="#0C071C" fill-opacity="0.96" stroke="{accent}" stroke-width="4"/>
    <rect id="anime_elastic_badge" x="40" y="32" width="220" height="36" rx="18" fill="{accent}" fill-opacity="0.25" stroke="{accent}" stroke-width="1.5"/>
    <text x="150" y="56" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">💥 {badge}</text>
    <text x="840" y="56" font-family="monospace" font-size="12" font-weight="700" fill="{accent}" text-anchor="end">ANIME.JS SPRING</text>
    <text id="anime_elastic_headline" x="40" y="140" font-family="'Impact', sans-serif" font-size="46" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text id="anime_elastic_subheadline" x="40" y="210" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "anime_number_counter_odometer":
            headline = params.get("headline") or "$124,500.00 USD"
            subheadline = params.get("subheadline") or "Facturación mensual generada en automático"
            badge = params.get("badge", "ODÓMETRO").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="anime_odometer_card" transform="translate(100, 780)">
    <rect width="880" height="280" rx="32" fill="#06120D" fill-opacity="0.96" stroke="{accent}" stroke-width="3.5"/>
    <rect x="40" y="30" width="180" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="130" y="53" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">📈 {badge}</text>
    <text x="840" y="53" font-family="monospace" font-size="12" font-weight="700" fill="{accent}" text-anchor="end">ANIME.JS METRIC</text>
    <text id="anime_odometer_val" x="40" y="148" font-family="'Impact', sans-serif" font-size="54" font-weight="900" fill="#FFFFFF" data-target="124500">{headline}</text>
    <text x="40" y="210" font-family="'Montserrat', sans-serif" font-size="20" font-weight="700" fill="{accent}">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "anime_morphing_blob":
            headline = params.get("headline") or "MORFOLOGÍA FLUIDA"
            subheadline = params.get("subheadline") or "Interpolación de coordenadas de nodos vectoriales"
            badge = params.get("badge", "ORGANIC MORPH").upper()
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="blobGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#4F46E5" stop-opacity="0.15"/>
    </linearGradient>
  </defs>
  <g id="anime_blob_wrapper" transform="translate(540, 700)">
    <path id="anime_blob_path" d="M 0,-150 C 90,-140 160,-80 150,0 C 140,90 80,160 0,150 C -90,140 -160,70 -150,0 C -140,-80 -80,-160 0,-150 Z" fill="url(#blobGradient)" stroke="{accent}" stroke-width="2"/>
  </g>
  <g id="anime_morph_card" transform="translate(100, 920)">
    <rect width="880" height="260" rx="30" fill="#080B16" fill-opacity="0.95" stroke="{accent}" stroke-width="3"/>
    <rect x="40" y="28" width="210" height="34" rx="17" fill="{accent}" fill-opacity="0.2" stroke="{accent}" stroke-width="1.5"/>
    <text x="145" y="51" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">💧 {badge}</text>
    <text x="40" y="125" font-family="'Impact', sans-serif" font-size="44" font-weight="900" fill="#FFFFFF">{headline}</text>
    <text x="40" y="190" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}">{subheadline}</text>
  </g>
</svg>"""

        elif preset_id == "retention_bar":
            bar_color = params.get("bar_color", accent)
            h = int(params.get("height_px", 14))
            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Track -->
  <rect x="0" y="{height - h}" width="{width}" height="{h}" fill="#0F172A" fill-opacity="0.6"/>
  <!-- Dynamic fill with target ID -->
  <rect id="mgRetentionBarFill" x="0" y="{height - h}" width="{int(width * 0.45)}" height="{h}" fill="{bar_color}"/>
</svg>"""

        else:  # High-tech glassmorphism card for custom presets
            h_text = params.get("headline") or params.get("title") or "EFECTO CINÉTICO"
            s_text = params.get("subheadline") or params.get("subtitle") or "Animación fluida acelerada por hardware"
            badge = params.get("badge") or "MOTION FX"
            badge = str(badge).upper()
            pos = params.get("position", "center")
            top_y = 1350 if pos in ["bottom", "bottom_card"] else (140 if pos in ["top", "top_card"] else 740)

            return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="custom_card_{preset_id}" transform="translate(100, {top_y})">
    <rect width="880" height="280" rx="30" fill="#030712" fill-opacity="0.94" stroke="{accent}" stroke-width="3.5"/>
    <rect x="40" y="30" width="220" height="34" rx="17" fill="{accent}" fill-opacity="0.18" stroke="{accent}" stroke-width="1.5"/>
    <text x="150" y="52" font-family="'Montserrat', sans-serif" font-size="13" font-weight="900" fill="{accent}" text-anchor="middle" letter-spacing="2">✨ {badge}</text>
    <text x="40" y="130" font-family="'Impact', sans-serif" font-size="46" font-weight="900" fill="#FFFFFF">{h_text}</text>
    <text x="40" y="195" font-family="'Montserrat', sans-serif" font-size="22" font-weight="700" fill="{accent}">{s_text}</text>
    <rect x="40" y="240" width="800" height="5" rx="2.5" fill="{accent}" fill-opacity="0.4"/>
  </g>
</svg>"""

    def _get_font(self, font_name: str, size: int) -> ImageFont.ImageFont:
        """Helper to safely load system TrueType fonts with fallback."""
        candidates = [
            f"C:/Windows/Fonts/{font_name}",
            f"C:/Windows/Fonts/{font_name.lower()}",
            f"{font_name}",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for c in candidates:
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def generate_overlay_png(
        self,
        preset_id: str,
        params: Dict[str, Any],
        width: int = 1080,
        height: int = 1920
    ) -> Path:
        """Generates a high-resolution transparent 1080x1920 RGBA PNG using Pillow with TrueType fonts."""
        # Always enforce standard reference resolution (1080x1920 for portrait, 1920x1080 for landscape)
        ref_w = 1920 if width > height else 1080
        ref_h = 1080 if width > height else 1920

        img = Image.new("RGBA", (ref_w, ref_h), (0, 0, 0, 0))
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

        # Crisp font hierarchy
        f_title = self._get_font("segoeui.ttf", 44)
        f_subtitle = self._get_font("segoeui.ttf", 26)
        f_badge = self._get_font("arial.ttf", 18)
        f_metric = self._get_font("impact.ttf", 76)
        f_quote = self._get_font("segoeui.ttf", 34)

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
            draw.rounded_rectangle([130, 1456, 280, 1494], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((150, 1464), badge, font=f_badge, fill=accent_rgb)
            # Title
            draw.text((130, 1512), title, font=f_title, fill=(255, 255, 255, 255))
            # Subtitle
            draw.text((130, 1572), subtitle, font=f_subtitle, fill=(148, 163, 184, 255))

        elif preset_id == "stat_callout_neon":
            metric = params.get("metric", "+350%")
            explanation = params.get("explanation", "Velocidad de producción")
            badge = params.get("badge", "IMPACTO").upper()

            # Glass card
            draw.rounded_rectangle([60, 1260, 1020, 1600], radius=32, fill=(11, 19, 43, 230), outline=accent_rgb, width=3)
            # Badge
            draw.rounded_rectangle([108, 1296, 300, 1334], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((130, 1304), badge, font=f_badge, fill=accent_rgb)
            # Metric
            draw.text((108, 1350), metric, font=f_metric, fill=accent_rgb)
            # Explanation
            draw.text((108, 1455), explanation, font=f_title, fill=(255, 255, 255, 255))
            draw.text((108, 1520), "100% LOCAL & AUTONOMO", font=f_subtitle, fill=(100, 116, 139, 255))

        elif preset_id == "viral_hook":
            headline = params.get("headline", "NO COMETAS ESTE ERROR").upper()
            subheadline = params.get("subheadline", "Mira esto antes de publicar")
            badge = params.get("badge", "ATENCION").upper()

            draw.rounded_rectangle([60, 720, 1020, 1100], radius=36, fill=(24, 24, 27, 240), outline=accent_rgb, width=4)
            # Badge
            draw.rounded_rectangle([430, 760, 650, 804], radius=21, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((470, 770), badge, font=f_badge, fill=accent_rgb)
            # Headline
            draw.text((120, 840), headline, font=f_title, fill=(255, 255, 255, 255))
            # Subheadline
            draw.text((120, 930), subheadline, font=f_subtitle, fill=(228, 228, 231, 255))

        elif preset_id == "cta_badge":
            cta_text = params.get("cta_text", "Sigueme para mas contenido")
            subtext = params.get("subtext", "Comenta abajo tu opinion")

            draw.rounded_rectangle([100, 1500, 980, 1680], radius=30, fill=(30, 27, 75, 235), outline=accent_rgb, width=3)
            draw.text((180, 1540), cta_text, font=f_title, fill=(255, 255, 255, 255))
            draw.text((220, 1610), subtext, font=f_subtitle, fill=accent_rgb)

        elif preset_id == "attention_arrow":
            label = params.get("label", "¡OJO CON ESTO!").upper()
            sublabel = params.get("sublabel", "Detalle clave que no viste")
            draw.rounded_rectangle([120, 800, 960, 1030], radius=30, fill=(24, 24, 27, 240), outline=accent_rgb, width=4)
            draw.ellipse([180, 880, 240, 940], fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((270, 860), label, font=f_title, fill=(255, 255, 255, 255))
            draw.text((270, 935), sublabel, font=f_subtitle, fill=accent_rgb)

        elif preset_id == "social_handle":
            handle = params.get("handle", "@creador_digital")
            platform = params.get("platform", "TikTok / Instagram")
            draw.rounded_rectangle([60, 120, 560, 230], radius=48, fill=(9, 9, 11, 235), outline=accent_rgb, width=3)
            draw.ellipse([80, 140, 140, 200], fill=accent_dim)
            draw.text((160, 140), handle, font=f_title, fill=(255, 255, 255, 255))
            draw.text((160, 185), platform, font=f_subtitle, fill=accent_rgb)

        elif preset_id == "quote_card":
            quote = params.get("quote", "La clave no es la suerte, es la retencion.")
            author = params.get("author", "REGLA DE ORO").upper()
            draw.rounded_rectangle([60, 750, 1020, 1100], radius=32, fill=(15, 23, 42, 240), outline=accent_rgb, width=3)
            draw.text((100, 800), f'"{quote[:45]}"', font=f_quote, fill=(255, 255, 255, 255))
            if len(quote) > 45:
                draw.text((100, 860), f'{quote[45:90]}', font=f_quote, fill=(226, 232, 240, 255))
            draw.rounded_rectangle([100, 980, 360, 1030], radius=16, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((130, 992), f"— {author}", font=f_badge, fill=accent_rgb)

        elif preset_id == "number_counter":
            number_val = params.get("number_val", "+150,000")
            label = params.get("label", "Nuevas Reproducciones")
            badge = params.get("badge", "METRICA REAL").upper()
            draw.rounded_rectangle([60, 1260, 1020, 1590], radius=32, fill=(8, 47, 73, 240), outline=accent_rgb, width=3)
            draw.rounded_rectangle([110, 1296, 340, 1334], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((130, 1304), badge, font=f_badge, fill=accent_rgb)
            draw.text((110, 1360), number_val, font=f_metric, fill=accent_rgb)
            draw.text((110, 1475), label, font=f_title, fill=(255, 255, 255, 255))

        elif preset_id == "warning_alert":
            w_title = params.get("warning_title", "¡DETENTE AQUI!").upper()
            w_desc = params.get("warning_desc", "Error que destruye tu retencion")
            draw.rounded_rectangle([60, 750, 1020, 1050], radius=28, fill=(28, 25, 23, 245), outline=accent_rgb, width=4)
            draw.rectangle([60, 750, 1020, 768], fill=accent_rgb)
            draw.text((160, 830), f"AVISO: {w_title}", font=f_title, fill=accent_rgb)
            draw.text((160, 930), w_desc, font=f_subtitle, fill=(245, 245, 244, 255))

        elif preset_id in ["split_chars_stagger", "split_words_pop", "split_lines_mask", "scramble_matrix", "typewriter_cursor", "kinetic_typography_scale"]:
            h_text = params.get("headline") or params.get("title") or "TIPOGRAFIA CINETICA"
            s_text = params.get("subheadline") or params.get("subtitle") or "Efecto de Alta Retencion"
            badge = params.get("badge", "MOTION").upper()
            draw.rounded_rectangle([60, 700, 1020, 1060], radius=32, fill=(10, 10, 12, 240), outline=accent_rgb, width=4)
            draw.rounded_rectangle([420, 736, 660, 778], radius=21, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((450, 746), badge, font=f_badge, fill=accent_rgb)
            draw.text((120, 820), str(h_text)[:30], font=f_metric, fill=(255, 255, 255, 255))
            draw.text((120, 930), str(s_text)[:48], font=f_subtitle, fill=(203, 213, 225, 255))

        elif preset_id in ["lower_third_neon_edge", "lower_third_magazine"]:
            title = params.get("title", "PRESENTADOR").upper()
            subtitle = params.get("subtitle", "Especialista")
            badge = params.get("badge", "DESTACADO").upper()
            draw.rounded_rectangle([60, 1420, 1020, 1640], radius=20, fill=(3, 7, 18, 240), outline=accent_rgb, width=3)
            draw.rounded_rectangle([96, 1450, 104, 1610], radius=4, fill=accent_rgb)
            draw.text((130, 1454), badge, font=f_badge, fill=accent_rgb)
            draw.text((130, 1500), title, font=f_title, fill=(255, 255, 255, 255))
            draw.text((130, 1560), subtitle, font=f_subtitle, fill=(148, 163, 184, 255))

        elif preset_id == "news_ticker_breaking":
            h_text = params.get("headline", "ULTIMA HORA").upper()
            s_text = params.get("subheadline", "Noticia urgente de impacto")
            draw.rectangle([0, ref_h - 180, ref_w, ref_h], fill=(24, 24, 27, 245), outline=(220, 38, 38, 255), width=4)
            draw.rectangle([0, ref_h - 180, 300, ref_h - 120], fill=(220, 38, 38, 255))
            draw.text((40, ref_h - 165), "ULTIMA HORA", font=f_badge, fill=(255, 255, 255, 255))
            draw.text((330, ref_h - 165), str(h_text)[:40], font=f_subtitle, fill=(255, 255, 255, 255))
            draw.text((40, ref_h - 105), str(s_text)[:60], font=f_subtitle, fill=(228, 228, 231, 255))

        elif preset_id in ["crypto_stock_badge", "percentage_circle_gauge", "bar_chart_grow"]:
            h_text = params.get("headline") or params.get("metric") or "+88% CRECIMIENTO"
            s_text = params.get("subheadline") or params.get("explanation") or "Rendimiento y conversion"
            badge = params.get("badge", "FINANZAS").upper()
            draw.rounded_rectangle([60, 1260, 1020, 1580], radius=30, fill=(2, 44, 34, 240), outline=accent_rgb, width=3)
            draw.rounded_rectangle([110, 1296, 320, 1334], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((130, 1304), badge, font=f_badge, fill=accent_rgb)
            draw.text((110, 1360), str(h_text)[:25], font=f_metric, fill=accent_rgb)
            draw.text((110, 1475), str(s_text)[:45], font=f_title, fill=(255, 255, 255, 255))

        elif preset_id in ["cta_link_in_bio", "save_share_reminder", "discount_code_badge"]:
            h_text = params.get("headline") or params.get("cta_text") or "ENLACE EN LA BIO"
            s_text = params.get("subheadline") or params.get("subtext") or "Haz clic para acceder gratis"
            draw.rounded_rectangle([80, 1480, 1000, 1670], radius=28, fill=(30, 27, 75, 240), outline=accent_rgb, width=3)
            draw.text((140, 1520), str(h_text)[:35], font=f_title, fill=(255, 255, 255, 255))
            draw.text((140, 1590), str(s_text)[:45], font=f_subtitle, fill=accent_rgb)

        elif preset_id in ["highlighter_marker_draw", "retention_timer_countdown", "creator_profile_pill"]:
            h_text = params.get("headline") or params.get("title") or "ELEMENTO CLAVE"
            s_text = params.get("subheadline") or params.get("subtitle") or "Detalle relevante"
            draw.rounded_rectangle([100, 780, 980, 980], radius=24, fill=(15, 23, 42, 240), outline=accent_rgb, width=3)
            draw.text((160, 820), str(h_text)[:30], font=f_title, fill=accent_rgb)
            draw.text((160, 890), str(s_text)[:45], font=f_subtitle, fill=(255, 255, 255, 255))

        elif preset_id in ["manim_math_formula", "manim_coordinate_plot", "manim_geometry_vector"]:
            h_text = params.get("headline") or params.get("title") or "E = mc² (MANIM)"
            s_text = params.get("subheadline") or params.get("subtitle") or "Animación Matemática 3Blue1Brown"
            badge = params.get("badge", "MANIM").upper()
            draw.rounded_rectangle([60, 720, 1020, 1060], radius=28, fill=(3, 7, 18, 245), outline=accent_rgb, width=4)
            draw.rounded_rectangle([100, 750, 320, 788], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((120, 758), badge, font=f_badge, fill=accent_rgb)
            draw.text((100, 820), str(h_text)[:35], font=f_title, fill=(255, 255, 255, 255))
            draw.text((100, 920), str(s_text)[:50], font=f_subtitle, fill=(148, 163, 184, 255))

        elif preset_id in ["code_walkthrough_terminal", "flowchart_nodes_diagram", "tech_stack_pill_orbit"]:
            h_text = params.get("headline") or params.get("title") or "const short = await render();"
            s_text = params.get("subheadline") or params.get("subtitle") or "Motion Canvas Procedural Engine"
            badge = params.get("badge", "MOTION CANVAS").upper()
            draw.rounded_rectangle([60, 720, 1020, 1080], radius=24, fill=(13, 17, 23, 248), outline=accent_rgb, width=3)
            # macOS traffic dots
            draw.ellipse([80, 745, 96, 761], fill=(239, 68, 68, 255))
            draw.ellipse([108, 745, 124, 761], fill=(245, 158, 11, 255))
            draw.ellipse([136, 745, 152, 761], fill=(16, 185, 129, 255))
            draw.text((180, 743), badge, font=f_badge, fill=(110, 118, 129, 255))
            draw.line([60, 780, 1020, 780], fill=(48, 54, 61, 255), width=2)
            draw.text((90, 820), str(h_text)[:35], font=f_title, fill=accent_rgb)
            draw.text((90, 910), f"// {str(s_text)[:45]}", font=f_subtitle, fill=(139, 148, 158, 255))

        elif preset_id in ["flip_card_stack", "proximity_scale_grid", "velocity_skew", "scrubbed_bento_gallery", "directional_marquee", "cursor_tilt_3d", "physics_confetti_burst"]:
            h_text = params.get("headline") or params.get("title") or "EFECTO CINÉTICO"
            s_text = params.get("subheadline") or params.get("subtitle") or "1. Hook • 2. Retención • 3. CTA"
            badge = params.get("badge", "MOTION FX").upper()

            if preset_id == "directional_marquee":
                draw.rectangle([0, 800, 1080, 870], fill=accent_rgb)
                draw.text((60, 815), str(h_text)[:40].upper(), font=f_title, fill=(0, 0, 0, 255))
                draw.rectangle([0, 880, 1080, 950], fill=(3, 7, 18, 240), outline=accent_rgb, width=3)
                draw.text((60, 895), str(s_text)[:45].upper(), font=f_title, fill=(255, 255, 255, 255))
            elif preset_id == "scrubbed_bento_gallery":
                draw.rounded_rectangle([60, 700, 620, 1060], radius=28, fill=(3, 7, 18, 245), outline=accent_rgb, width=3)
                draw.rounded_rectangle([95, 730, 295, 768], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
                draw.text((115, 738), badge, font=f_badge, fill=accent_rgb)
                draw.text((95, 800), str(h_text)[:28], font=f_title, fill=(255, 255, 255, 255))
                draw.text((95, 880), str(s_text)[:35], font=f_subtitle, fill=accent_rgb)
                draw.rounded_rectangle([645, 700, 1020, 870], radius=24, fill=(11, 19, 43, 230), outline=(51, 65, 85, 255), width=2)
                draw.text((670, 740), "⚡ 10x MÁS RÁPIDO", font=f_badge, fill=accent_rgb)
                draw.rounded_rectangle([645, 890, 1020, 1060], radius=24, fill=(15, 23, 42, 230), outline=(51, 65, 85, 255), width=2)
                draw.text((670, 930), "🔒 PRIVACIDAD 100%", font=f_badge, fill=(16, 185, 129, 255))
            elif preset_id == "proximity_scale_grid":
                draw.rounded_rectangle([60, 680, 1020, 1160], radius=32, fill=(3, 7, 18, 245), outline=accent_rgb, width=3)
                draw.rounded_rectangle([100, 712, 330, 748], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
                draw.text((120, 720), badge, font=f_badge, fill=accent_rgb)
                draw.rounded_rectangle([385, 785, 695, 935], radius=22, fill=(30, 41, 59, 250), outline=accent_rgb, width=4)
                draw.text((410, 825), str(h_text)[:22], font=f_badge, fill=accent_rgb)
                draw.text((410, 870), str(s_text)[:30], font=f_subtitle, fill=(255, 255, 255, 255))
            else:
                draw.rounded_rectangle([120, 760, 960, 1020], radius=24, fill=(11, 19, 43, 160), outline=(30, 41, 59, 255), width=2)
                draw.rounded_rectangle([90, 740, 990, 1000], radius=26, fill=(15, 23, 42, 210), outline=(51, 65, 85, 255), width=2)
                draw.rounded_rectangle([60, 720, 1020, 980], radius=28, fill=(3, 7, 18, 245), outline=accent_rgb, width=3)
                draw.rounded_rectangle([100, 750, 300, 788], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
                draw.text((120, 758), badge, font=f_badge, fill=accent_rgb)
                draw.text((100, 815), str(h_text)[:35], font=f_title, fill=(255, 255, 255, 255))
                draw.text((100, 895), str(s_text)[:50], font=f_subtitle, fill=accent_rgb)

        elif preset_id in ["remotion_audio_waveform", "remotion_device_mockup", "remotion_push_notification", "remotion_split_screen_duet"]:
            h_text = params.get("headline") or params.get("title") or "REMOTION VIDEO PROGRAMATICO"
            s_text = params.get("subheadline") or params.get("subtitle") or "React Composition & Audio Spectrum"
            badge = params.get("badge", "REMOTION").upper()
            draw.rounded_rectangle([60, 1380, 1020, 1640], radius=28, fill=(11, 15, 25, 245), outline=accent_rgb, width=3)
            draw.rounded_rectangle([100, 1410, 320, 1448], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((120, 1418), badge, font=f_badge, fill=accent_rgb)
            draw.text((100, 1480), str(h_text)[:35], font=f_title, fill=(255, 255, 255, 255))
            draw.text((100, 1560), str(s_text)[:50], font=f_subtitle, fill=accent_rgb)

        elif preset_id == "retention_bar":
            bar_h = max(2, min(200, int(params.get("height_px", 14))))
            draw.rectangle([0, ref_h - bar_h, ref_w, ref_h], fill=accent_rgb)

        elif preset_id.startswith("transition_"):
            h_text = params.get("headline") or params.get("title") or "TRANSICIÓN CINEMÁTICA"
            s_text = params.get("subheadline") or params.get("subtitle") or "Corte Dinámico de Escena 60 FPS"
            badge = params.get("badge") or "TRANSICIÓN"
            badge = str(badge).upper()

            # Full-height cinematic transition backdrop
            draw.rectangle([0, 0, ref_w, ref_h], fill=(3, 7, 18, 220))
            # Diagonal accent slash / beam
            draw.line([(0, ref_h - 100), (ref_w, 100)], fill=accent_rgb, width=12)
            draw.line([(0, ref_h - 100), (ref_w, 100)], fill=(255, 255, 255, 255), width=4)
            # Centered impact card
            card_top = (ref_h - 320) // 2
            draw.rounded_rectangle([80, card_top, ref_w - 80, card_top + 320], radius=32, fill=(11, 19, 43, 245), outline=accent_rgb, width=4)
            draw.rounded_rectangle([130, card_top + 35, 420, card_top + 78], radius=21, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((150, card_top + 45), f"🎬 {badge}", font=f_badge, fill=accent_rgb)
            draw.text((130, card_top + 105), str(h_text)[:32], font=f_metric, fill=(255, 255, 255, 255))
            draw.text((130, card_top + 215), str(s_text)[:48], font=f_subtitle, fill=accent_rgb)

        else:  # Custom or generic preset fallback card
            h_text = params.get("headline") or params.get("title") or "EFECTO CINÉTICO"
            s_text = params.get("subheadline") or params.get("subtitle") or "Animación fluida acelerada por hardware"
            badge = params.get("badge") or "MOTION FX"
            badge = str(badge).upper()
            pos = params.get("position", "center")
            if pos in ["bottom", "bottom_card"]:
                top_y = ref_h - 450
            elif pos in ["top", "top_card"]:
                top_y = 120
            else:
                top_y = (ref_h - 300) // 2

            card_w = min(ref_w - 120, 880)
            left_x = (ref_w - card_w) // 2
            right_x = left_x + card_w
            bot_y = top_y + 280

            # Glass card container
            draw.rounded_rectangle([left_x, top_y, right_x, bot_y], radius=30, fill=(11, 15, 25, 235), outline=accent_rgb, width=3)
            # Badge pill
            badge_w = max(180, len(badge) * 11 + 36)
            draw.rounded_rectangle([left_x + 36, top_y + 30, left_x + 36 + badge_w, top_y + 68], radius=18, fill=accent_dim, outline=accent_rgb, width=2)
            draw.text((left_x + 50, top_y + 38), badge[:22], font=f_badge, fill=accent_rgb)
            # Title / Headline
            draw.text((left_x + 36, top_y + 90), str(h_text)[:35], font=f_title, fill=(255, 255, 255, 255))
            # Subtitle
            draw.text((left_x + 36, top_y + 165), str(s_text)[:50], font=f_subtitle, fill=accent_rgb)
            # Accent bottom bar
            draw.rounded_rectangle([left_x + 36, bot_y - 25, right_x - 36, bot_y - 20], radius=3, fill=accent_dim)

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
        # Colour values are interpolated into FFmpeg filter graphs: only hex is allowed.
        params = {k: (sanitize_hex_color(v) if "color" in k else v) for k, v in (params or {}).items()}
        meta = self.probe_video(video_path)
        vid_w = meta["width"]
        vid_h = meta["height"]
        vid_dur = meta["duration"]

        # Check if pinned to full video (fijar a todo el video)
        pin_to_video = bool(params.get("pin_to_video", False) or params.get("is_pinned", False))
        if pin_to_video:
            start_time = 0.0
            duration = vid_dur
        else:
            start_time = float(params.get("start_time", 1.0))
            requested_duration = float(params.get("duration", 5.0))
            if requested_duration <= 0.0 or (start_time + requested_duration) > vid_dur:
                duration = max(1.0, vid_dur - start_time)
            else:
                duration = requested_duration

        end_time = min(vid_dur, start_time + duration)
        fade_time = 0.3

        if not output_path:
            out_filename = f"mg_{safe_filename(Path(video_path).stem)}_{safe_filename(preset_id)}_{str(uuid.uuid4())[:6]}.mp4"
            out_p = settings.OUTPUTS_DIR / out_filename
        else:
            out_p = Path(output_path).resolve()

        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Dynamic Native Animated Retention Bar with FFmpeg
        if preset_id == "retention_bar":
            bar_h = max(2, min(200, int(params.get("height_px", 14))))
            color_hex = params.get("accent_color") or params.get("bar_color") or "#38BDF8"
            color_hex = color_hex.lstrip("#")
            bg_color = "black@0.45"
            fg_color = f"0x{color_hex}@1.0"
            eff_dur = vid_dur if duration <= 0.0 or duration >= vid_dur else duration

            filter_complex = (
                f"[0:v]drawbox=x=0:y=ih-{bar_h}:w=iw:h={bar_h}:color={bg_color}:t=fill,"
                f"drawbox=x=0:y=ih-{bar_h}:w='min(iw, max(1, iw*((t-{start_time})/{eff_dur})))':h={bar_h}:color={fg_color}:t=fill:enable='between(t,{start_time},{start_time + eff_dur})'[v_out]"
            )
            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", str(Path(video_path).resolve()),
                "-filter_complex", filter_complex,
                "-map", "[v_out]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                str(out_p)
            ]
            logger.info("Running dynamic animated retention bar compositing with FFmpeg...")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                logger.error(f"FFmpeg dynamic retention bar failed:\n{res.stderr}")
                raise RuntimeError(f"FFmpeg dynamic retention bar error: {res.stderr[:300]}")
            return str(out_p)

        # Always generate on reference standard dimensions (1080x1920 or 1920x1080)
        ref_w = 1920 if vid_w > vid_h else 1080
        ref_h = 1080 if vid_w > vid_h else 1920
        overlay_png = self.generate_overlay_png(preset_id, params, width=ref_w, height=ref_h)

        # Scale overlay to match video dimensions and apply smooth alpha fade
        pos_x = int(params.get("pos_x", 0) or params.get("offset_x", 0))
        pos_y = int(params.get("pos_y", 0) or params.get("offset_y", 0))

        filter_complex = (
            f"[1:v]scale={vid_w}:{vid_h},format=yuva420p,"
            f"fade=t=in:st=0:d={fade_time}:alpha=1,"
            f"fade=t=out:st={max(0.1, duration - fade_time)}:d={fade_time}:alpha=1,"
            f"setpts=PTS-STARTPTS+{start_time}/TB[over];"
            f"[0:v][over]overlay={pos_x}:{pos_y}:enable='between(t,{start_time},{end_time})'[v_out]"
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

