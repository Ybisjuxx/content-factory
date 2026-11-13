# Auditoría técnica: Content Factory

**Fecha:** 13-11-2026 · **Alcance:** backend FastAPI (`app/`), interfaz (`web/index.html`), pruebas (`tests/`) y empaquetado.
**Método:** lectura del código, ejecución de la suite, pruebas de explotación contra el servidor en marcha, medición de vídeo con FFmpeg/ffprobe y capturas con Chromium (escritorio 1440 px y móvil 390 px).

---

## 1. Resumen ejecutivo

El proyecto funciona como prototipo, pero **no cumple varias afirmaciones de `AUDIT_SECURITY_OVERVIEW.md`**:

| Afirmación del dossier | Realidad comprobada |
|---|---|
| "Protección contra path traversal" | `POST /jobs` aceptaba `/etc/passwd` como entrada y cualquier ruta del disco como salida. |
| "Servidor solo en loopback, sin exposición" | CORS `*` **con credenciales**: cualquier web que visites podía manejar la API. Además `/storage` exponía la base de datos SQLite. |
| "Cero llamadas externas / 100 % local" | Trends consulta Google News, Google Trends y Reddit; la UI cargaba Tailwind CDN y Google Fonts. **Sin internet la interfaz se veía sin estilos**. |
| "100 % de cobertura, todo pasa" | Con un entorno limpio, 2 tests fallaban (dependen de Whisper real) y la suite escribía en el `storage/` real. |
| Python ≥ 3.11 | `app/database.py` daba `SyntaxError` en 3.11: la app no arrancaba. |

Además había **dos defectos funcionales que afectaban a cada vídeo renderizado** (desfase de audio y texto que faltaba en las tarjetas). Ambos están corregidos y verificados.

**Estado tras la intervención:** 49 tests pasan y 2 se omiten porque Whisper no está instalado. Antes había 32 tests que pasaban y 2 que fallaban. Se corrigieron todos los hallazgos críticos y altos. El diff ocupa 23 archivos (+667/−345).

---

## 2. Hallazgos y estado

Severidad: 🔴 Crítico · 🟠 Alto · 🟡 Medio · ⚪ Bajo

### Seguridad

| # | Sev. | Hallazgo | Evidencia | Estado |
|---|---|---|---|---|
| S1 | 🔴 | **CORS `allow_origins=["*"]` + `allow_credentials=True`**: cualquier página web podía crear jobs, borrar vídeos o publicar | Preflight desde `https://evil.example` devolvía `access-control-allow-origin: https://evil.example` | ✅ Lista de orígenes configurable (`CORS_ORIGINS`), sin credenciales. Se añadió `TrustedHostMiddleware` contra DNS rebinding |
| S2 | 🔴 | **`/storage` montado completo**: se descargaban `content_factory.db`, `video_workflow.json` y `server.log` | `GET /storage/content_factory.db` → 200 | ✅ Solo se montan `uploads/`, `outputs/` y `cache/subtitles/`, con CSP `sandbox` |
| S3 | 🔴 | **Lectura y escritura de rutas arbitrarias** en `/jobs`, `/editor/*`, `/motion-graphics/apply` y `/distribution/publish` | Job con `input=/etc/passwd`, `output=/tmp/...` aceptado (202) | ✅ `app/security.py::resolve_media_path`: solo `storage/` y `ALLOWED_MEDIA_DIRS`, con symlinks resueltos |
| S4 | 🔴 | **XSS en el dashboard** a partir de títulos de Google News/Reddit, ideas del LLM, presets y notas (`innerHTML` sin escapar, `href` que admitía `javascript:`) | Payload en un título: el original ejecuta JS (`pwned: true`); la versión corregida no | ✅ `esc()`, `safeUrl()` y `jsArg()`; los botones usan `data-*` en lugar de JS inline |
| S5 | 🟠 | **XSS almacenado en SVG** (`/assets/svg/generate`, previews de motion graphics) servido desde el mismo origen | `<script>` presente en el `.svg` generado | ✅ Escapado XML de todos los parámetros |
| S6 | 🟠 | **Inyección en filtros FFmpeg** mediante `accent_color` (se interpola en `drawbox=color=…`) | `#fff:t=fill[x];movie=…` llegaba al grafo | ✅ `sanitize_hex_color()`: solo se acepta hexadecimal |
| S7 | 🟠 | **SSRF**: `n8n_webhook_url` / `custom_webhook_url` hacia cualquier host (por ejemplo, metadatos de la nube) | — | ✅ `WEBHOOK_ALLOWED_HOSTS` (loopback por defecto) |
| S8 | 🟡 | Subidas sin límite de tamaño y con nombre de archivo poco saneado (`'`, `;` y `,` rompen filtros) | — | ✅ `app/api/uploads.py`: streaming, `MAX_UPLOAD_MB`, `safe_filename()`. Además se eliminó la lógica duplicada |
| S9 | 🟡 | Catálogo de "noticias de hoy" escrito a mano, con una condena penal atribuida a una persona real con nombre propio | `routes_trends.py` | ✅ Se eliminó esa entrada; el resto lleva la marca "Ejemplo (sin verificar)" |
| S10 | ⚪ | RSS parseado con `xml.etree` | — | ⏳ Recomendado: `defusedxml` |

### Arquitectura y corrección funcional

| # | Sev. | Hallazgo | Evidencia | Estado |
|---|---|---|---|---|
| A1 | 🔴 | **Desfase audio/vídeo acumulativo**: `acrossfade` solapa el audio 20 ms por corte, pero el vídeo no se recorta | 8 tomas: vídeo 8,000 s / audio 7,860 s (**140 ms**) | ✅ Fundido de entrada y salida por toma + `concat v=1:a=1`. Desfase: **0 ms**. Lo cubre un test de regresión |
| A2 | 🔴 | **El texto del cuerpo de las tarjetas SVG no aparecía en el vídeo**: `<foreignObject>` no lo renderiza librsvg (FFmpeg) | Render con FFmpeg: solo se ve el título | ✅ `<text>/<tspan>` con ajuste de línea y tamaño de titular adaptativo. Ver `docs/auditoria/tarjetas_svg_corregidas.png` |
| A3 | 🔴 | `SyntaxError` en Python 3.11 (`\\` dentro de una f-string en `database.py`) | `python3.11 -m py_compile` | ✅ `as_posix()`. Todos los módulos compilan en 3.11 |
| A4 | 🟠 | **Cancelar no detenía nada**: el pipeline sobrescribía el estado `cancelled` | — | ✅ Cancelación cooperativa entre etapas (`JobCancelled`). Responde 409 si el job ya terminó |
| A5 | 🟠 | El modelo Whisper se cargaba en **cada job** y había jobs concurrentes sin límite | — | ✅ `get_transcriber()` singleton con lock y `MAX_CONCURRENT_JOBS` (semáforo) |
| A6 | 🟠 | `subtitle_sync_mode` del formulario **nunca llegaba al pipeline** | `routes_jobs.py` no lo incluía en `options` | ✅ Corregido |
| A7 | 🟠 | El panel mostraba "faster-whisper Listo" y "n8n Conectado" **a fuego**; los jobs fallaban con "No module named faster_whisper" | Captura del estado original | ✅ Estado real (`find_spec`, `/distribution/channels`) |
| A8 | 🟡 | Jobs huérfanos que quedaban en "rendering" para siempre tras reiniciar | — | ✅ Se marcan como fallidos al arrancar |
| A9 | 🟡 | `atempo` con velocidad < 0,5 se ignoraba (desincronización) | — | ✅ Cadena `atempo` para 0,25–4× y validación de rangos |
| A10 | 🟡 | Colisión de WAV temporales (mismo nombre base) y archivos que nunca se borraban | — | ✅ Nombre único y borrado en `finally` |
| A11 | 🟡 | `video_workflow.json`: lectura, modificación y escritura sin lock ni escritura atómica | — | ✅ `RLock` + `os.replace` |
| A12 | 🟡 | Ruta fija `C:/Developer/...` para YouTube; YouTube y MoneyPrinter se mostraban como "publicado" o "en síntesis" sin hacer nada | — | ✅ `YOUTUBE_CLIENT_SECRET_PATH`; respuestas honestas (`script_only`) |
| A13 | 🟡 | Faltaban `Pillow` y `python-multipart` en las dependencias; `pytest` estaba en las de producción | — | ✅ `requirements.txt` + `requirements-dev.txt` |
| A14 | 🟡 | Los tests escribían en el `storage/` real y dependían de Whisper | — | ✅ `tests/conftest.py` con almacenamiento temporal y skip si falta Whisper; test e2e del pipeline offline |

### Interfaz y diseño

| # | Sev. | Hallazgo | Estado |
|---|---|---|---|
| U1 | 🔴 | Tailwind Play CDN (no apto para producción): **sin internet la UI no tiene estilos** y se muestran todas las pestañas a la vez (`.hidden` no existe) | ✅ CSS compilado en local (`web/vendor/tailwind.css`, 37 KB) + `npm run build:css`. Google Fonts y el fallback de CDN eliminados |
| U2 | 🟠 | Desbordamiento horizontal en móvil (458 px de ancho en un viewport de 390) | ✅ Pestañas desplazables con etiquetas cortas en móvil. Ahora 390 px |
| U3 | 🟠 | Pestañas sin semántica (`role=tab`, `aria-selected`) ni navegación con teclado | ✅ Patrón WAI-ARIA con flechas, Home y End; además, la pestaña activa se recuerda |
| U4 | 🟡 | Sin foco visible ni respeto a `prefers-reduced-motion` (la UI tiene muchas animaciones) | ✅ `:focus-visible` y reducción de movimiento |
| U5 | 🟡 | Monitor de renderizado "en tiempo real" que no se actualizaba solo; "Descargar MP4" visible en jobs fallidos; no había botón Cancelar | ✅ Polling mientras hay jobs activos, descarga solo si el job está completado, botón Cancelar y mensaje de error visible |
| U6 | 🟡 | El select "Modo" de subtítulos se salía de la tarjeta | ✅ |

Capturas tras los cambios: `docs/auditoria/`.

---

## 3. Recomendaciones pendientes (no implementadas)

Ordenadas por impacto/esfuerzo:

1. **Cola de trabajos persistente.** `BackgroundTasks` vive dentro del proceso web. Un worker separado (RQ/Arq, o una tabla `jobs` sondeada por un proceso `worker`) permitiría reintentos, progreso real de FFmpeg (`-progress pipe:1`) y reinicios sin perder trabajo.
2. **Partir los monolitos.**
   - `web/index.html` (6.500 líneas, 60+ `innerHTML`): migrar a módulos ES con Vite (Tailwind ya está preparado para build) y separar por pestaña. Usar plantillas con `textContent` o un micro-framework (Lit o Alpine) para eliminar el riesgo XSS de raíz.
   - `services/motion_graphics.py` (3.300 líneas de if/elif por preset): pasar los presets a **datos** (JSON/YAML + plantillas SVG) con un registro de renderizadores. Generar el PNG final desde el mismo SVG (resvg) en lugar de redibujarlo con PIL evita que la vista previa y el render diverjan.
3. **Estado en la base de datos.** El workflow editorial (JSON) y el historial de publicaciones (lista en memoria, se pierde al reiniciar) deberían ser tablas SQLModel con migraciones Alembic. `create_all` no migra columnas.
4. **Token de API opcional** (cabecera `X-API-Key`) para llamadas desde n8n, ya que CORS no protege contra clientes que no son navegadores en la LAN si alguien cambia `HOST=0.0.0.0`.
5. **Diseño visual:**
   - Sustituir los emojis usados como iconos (inconsistentes entre sistemas operativos y leídos por lectores de pantalla) por un set SVG (Lucide/Heroicons).
   - Reducir los gradientes y el *glow*: hoy compiten el botón primario, la pestaña activa y la cinta "Última hora".
   - Definir tokens de color y una escala tipográfica. Ahora conviven `text-[9px]`, `[10px]` y `[11px]`, que quedan por debajo del mínimo legible de 12 px.
   - Reescribir el copy de marketing ("Hollywood", "enterprise-grade", "100 % local" mientras Trends sale a internet). El distintivo debería decir "Procesamiento local".
6. **Documentación:** el README habla de "11 tests" y de "cero llamadas externas", y el dossier de seguridad repite afirmaciones que no se cumplían. Conviene reescribirlo con este informe como base.
7. Unificar `run_server.py`, `start_server.py` y el `.bat` (lógica duplicada, incluido el parche de asyncio para Windows), usar `defusedxml` para RSS y dejar de usar `-preset fast` para el render final si importa la calidad (usar `medium` + CRF).

---

## 4. Configuración nueva (`.env`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `STORAGE_DIR` | `./storage` | Raíz de todo el estado (los tests la redirigen) |
| `ALLOWED_MEDIA_DIRS` | `[]` | Carpetas extra de entrada, p. ej. `["C:/Recordings"]` (**necesario si n8n envía rutas absolutas fuera de storage**) |
| `CORS_ORIGINS` | dashboard + n8n local | Orígenes de navegador permitidos |
| `ALLOWED_HOSTS` | `127.0.0.1, localhost, [::1]` | Anti DNS rebinding |
| `WEBHOOK_ALLOWED_HOSTS` | loopback | Anti SSRF |
| `MAX_UPLOAD_MB` / `MAX_CONCURRENT_JOBS` | 2048 / 1 | Límites |
| `TRENDS_LIVE_FETCH_ENABLED` | `true` | `false` = modo 100 % offline real |
| `YOUTUBE_CLIENT_SECRET_PATH` | — | Sustituye la ruta fija `C:/Developer/...` |

**Cambio de comportamiento a comunicar:** las rutas de vídeo de entrada fuera de `storage/` ahora se rechazan (403) hasta que se añadan a `ALLOWED_MEDIA_DIRS`.

## 5. Verificación

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # 49 passed, 2 skipped (sin faster-whisper)
npm install && npm run build:css   # solo si se modifican clases Tailwind en index.html
```
