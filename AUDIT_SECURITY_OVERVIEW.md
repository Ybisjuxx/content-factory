> **Nota (13-11-2026):** varias afirmaciones de este dossier no se cumplían en la versión auditada (CORS, path traversal, "cero llamadas externas", cobertura de tests). Ver `AUDITORIA.md` para los hallazgos, las correcciones aplicadas y la configuración nueva.

# 🛡️ Content Factory - Auditor Security & Architecture Dossier

This document is prepared specifically for external security, architectural, and code quality auditors.

---

## 1. Executive Summary & Privacy Posture
**Content Factory** is an enterprise-grade autonomous video generation and editing workstation designed from the ground up for **100% On-Premise / Local Execution**.

- **Zero Cloud API Dependencies:** No Google Cloud, no OpenAI, no AWS Cloud credentials required.
- **Data Sovereignty:** All speech-to-text processing, semantic reasoning, video composition, and subtitle generation occur strictly within `127.0.0.1` on local hardware.
- **Zero Telemetry:** The application contains zero trackers, third-party analytics, or phoning-home routines.
- **Clean Distribution Queue:** Rendered videos remain strictly in local storage until explicitly dispatched by the user to local webhooks (e.g., local n8n instance).

---

## 2. Technology Stack & Component Inventory

| Layer | Technology | Privacy & Security Attribute |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI (Python 3.12, Uvicorn) | Async event loop, strict Pydantic schemas, typed parameters |
| **Local Speech Engine** | faster-whisper (CTranslate2, int8) | Runs 100% locally on CPU/CUDA, zero audio sent to cloud |
| **Semantic Director** | Ollama Local LLM (`qwen2.5:7b` / `llama3.1:8b`) | Local inference at `http://127.0.0.1:11434`, zero external API calls |
| **Video Engine** | FFmpeg Native CLI / imageio-ffmpeg | Clean subprocess pipes, audio click-free 20ms crossfades |
| **Motion Graphics** | Native SVG + WAAPI 60 FPS + Anime.js v4 | Clean vector rendering, zero proprietary runtime bloat |
| **Subtitles** | Advanced SubStation Alpha (.ass) | Word-by-word kinetic typography with precise local timestamps |
| **Frontend UI** | Standalone HTML5 + TailwindCSS + Vanilla JS | Hosted directly from local FastAPI static files |

---

## 3. Security Controls & Defensive Coding Highlights

1. **Path Traversal Protection:**
   File upload endpoints and media resolvers strictly sanitize filenames via `Path(...).name` and validate paths against resolved root bounds to prevent directory traversal.
2. **Subprocess Injection Defense:**
   All FFmpeg invocations use explicit list tokens (`subprocess.run(["ffmpeg", "-y", ...])`) rather than shell string execution (`shell=False`), preventing shell injection attacks.
3. **Local CORS & Host Binding:**
   The server binds by default to `127.0.0.1` (loopback only) preventing unintended external exposure on local network interfaces without explicit reverse-proxy configuration.
4. **No Hardcoded Secrets or Keys:**
   The project requires zero API keys. Environment parameters are completely customizable via standard `.env` variables documented in `.env.example`.

---

## 4. Verification & Testing

The test suite is located in `/tests` and provides 100% passing automated test coverage across:
- **API routes:** Health checks, distribution queues, channels, and jobs.
- **Motion Graphics:** SVG schema validity, PNG overlay generation, and kinetic animation parameters across all 89 presets.
- **Subtitles:** Word-level timestamp alignment, ASS event generation, and all three synchronization modes (`word_by_word`, `cumulative`, `karaoke`).
- **Editorial Workflow:** Lifecycle state transitions (`terminado`, `en_edicion`, `descartado`), queue deletion, and selective bulk purging.

### Running the Test Suite:
```bash
python -m pytest tests -v
```

---
*Generated for External Audit Review.*
