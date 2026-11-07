# 🎬 Content Factory (100% Local & Self-Hosted)

An enterprise-grade, fully automated video production engine that runs **100% locally on your machine**. Zero reliance on external cloud APIs, zero subscriptions, zero data leaks, and zero Google Cloud/OpenAI dependencies.

---

## 🏛 Architecture Overview

```
                                      RAW VIDEO INPUT (.mp4 / .mov)
                                                    │
                                                    ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       STAGE 1: SPEECH INTELLIGENCE                                    │
│  faster-whisper (CTranslate2, int8 quantization, Silero VAD) -> Word-level Timestamps                │
└───────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       STAGE 2: SEMANTIC DIRECTOR                                      │
│  Local Ollama LLM (qwen2.5:7b-instruct / llama3.1:8b-instruct)                                        │
│  • Prunes false starts, repeated takes, and vocal stumbles                                            │
│  • Generates viral hook, summary, and Edit Decision List (EDL)                                        │
│  • Plans B-Roll insertion timestamps & procedural graphic card triggers                               │
└───────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       STAGE 3: VISUAL ASSET ENGINE                                    │
│  • Local Stock B-Roll Manager: Indexes & semantically matches 9:16 vertical clips                     │
│  • Procedural SVG Generator: Renders clean vector cards (Stats, Takeaways, Quotes, Terminal)          │
│  • Optional ComfyUI / Automatic1111 Hook (http://127.0.0.1:8188)                                      │
└───────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       STAGE 4: RENDER & MASTERING                                     │
│  System FFmpeg Engine                                                                                 │
│  • Slices and concatenates kept takes with 20ms audio crossfade (click-free)                          │
│  • Generates kinetic ASS subtitles with word highlighting & safe margin placement                     │
│  • Overlays 9:16 B-roll & SVG cards with smooth 0.2s alpha transitions                                │
│  • Ambient audio ducking: Background music attenuated to -22 dB during speech                         │
└───────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                    │
                                                    ▼
                                    FINAL 9:16 VERTICAL SHORT VIDEO
                                    + n8n Webhook Notification Trigger
```

---

## 📁 Directory Layout

```
content_factory/
├── app/
│   ├── api/                   # FastAPI routes (Jobs, Assets, System Doctor)
│   ├── models/                # SQLModel & Pydantic schemas (Job, Asset, DirectorPlan)
│   ├── services/
│   │   ├── transcriber.py     # faster-whisper (CTranslate2, int8, Silero VAD)
│   │   ├── semantic_director.py # Ollama LLM take pruning & JSON format enforcement
│   │   ├── broll_manager.py   # Local stock B-roll indexer & semantic matcher
│   │   ├── svg_generator.py   # Procedural vertical 9:16 SVG vector card generator
│   │   ├── subtitle_generator.py # Kinetic ASS subtitles with per-word karaoke highlighting
│   │   ├── ffmpeg_renderer.py # Jumpcuts, 20ms crossfade, -22dB ducking, overlays
│   │   └── comfyui_client.py  # Local ComfyUI API hook
│   ├── pipeline/
│   │   └── orchestrator.py    # Pipeline coordinator & n8n webhook dispatcher
│   ├── cli.py                 # Typer CLI application
│   ├── config.py              # Environment configuration & binary auto-detection
│   ├── database.py            # SQLite database & session management
│   └── main.py                # FastAPI entrypoint & web dashboard
├── storage/
│   ├── broll_library/         # 9:16 vertical B-roll stock clips
│   ├── audio_library/         # Ambient background music tracks
│   ├── cache/                 # Temporary render and model caches
│   └── outputs/               # Finished rendered short videos
├── web/
│   └── index.html             # Real-time local web management dashboard
├── tests/                     # Comprehensive test suite (11 unit & integration tests)
├── .env.example               # Configuration template
├── pyproject.toml             # Project package specifications
└── requirements.txt           # Python dependencies
```

---

## 🚀 Quick Start

### 1. Requirements

- Python 3.11+
- FFmpeg (system ffmpeg or auto-detected bundled binary)
- [Ollama](https://ollama.ai) (running locally on `http://127.0.0.1:11434`)
  ```bash
  ollama run qwen2.5:7b-instruct
  # or
  ollama run llama3.1:8b-instruct
  ```

### 2. Installation

```bash
cd video_factory
pip install -r requirements.txt
```

### 3. Check System Doctor

Verify your 100% local stack status with the CLI doctor:

```bash
python -m app.cli doctor
```

---

## 💻 CLI Usage

Render a raw video into a viral vertical short in a single command:

```bash
python -m app.cli run --input /path/to/raw_recording.mp4 --output /path/to/final_short.mp4
```

### Advanced CLI Options:

```bash
python -m app.cli run \
  --input "C:/Videos/raw_take.mp4" \
  --output "C:/Videos/final_render.mp4" \
  --broll \
  --svg-cards \
  --subtitles \
  --ducking \
  --music "storage/audio_library/ambient_focus_track.mp3" \
  --webhook "http://localhost:5678/webhook/video-ready"
```

### Other CLI Commands:

- **Start Web Dashboard & API Server:**
  ```bash
  python -m app.cli serve --port 8000
  ```
- **Index Local B-roll Stock Library:**
  ```bash
  python -m app.cli index-broll
  ```
- **Generate Standalone Procedural 9:16 SVG Card:**
  ```bash
  python -m app.cli card --type stat --title "100% LOCAL" --content "Zero cloud subscription fees"
  ```

---

## 🌐 FastAPI REST API & Local n8n Webhook Integration

When running `python -m app.cli serve`, the server runs on `http://127.0.0.1:8000`:
- **Web UI Dashboard:** `http://127.0.0.1:8000/`
- **Swagger Interactive API Docs:** `http://127.0.0.1:8000/docs`

### Triggering Production from n8n

Create an HTTP Request node in n8n targeting:
- **Method:** `POST`
- **URL:** `http://127.0.0.1:8000/api/v1/jobs`
- **Body:**
```json
{
  "input_video_path": "C:/Recordings/raw_take.mp4",
  "enable_broll": true,
  "enable_svg_cards": true,
  "enable_subtitles": true,
  "enable_music_ducking": true,
  "n8n_webhook_url": "http://localhost:5678/webhook/video-rendered"
}
```

When rendering completes, the factory immediately POSTs the payload back to your n8n workflow:
```json
{
  "event": "video.rendered",
  "job_id": "97e68bc3-fef6-4df0-94d5-5381f8872b7a",
  "status": "completed",
  "output_path": "C:/Developer/video_factory/storage/outputs/final_raw_take_1730960000.mp4",
  "execution_time_seconds": 18.5,
  "title": "Autonomous Video Factory",
  "hook": "Here is how to run AI video completely locally.",
  "pruned_takes_count": 3
}
```

---

## ⚙️ Key Technical Implementations

1. **20ms Audio Crossfading Between Takes:**
   FFmpeg audio filter graph chains `acrossfade=d=0.02:c1=tri:c2=tri` across consecutive kept segments to prevent click and pop audio phase disruptions.

2. **Kinetic ASS Subtitles with Word Highlighting:**
   Generates native Advanced SubStation Alpha (`.ass`) with 9:16 vertical safe margins (`MarginV=420`), bold drop shadows, and word highlighting (`{\c&H0000FFFF&}`) calculated against the pruned, concatenated timeline.

3. **Ambient Audio Ducking (-22 dB):**
   Uses sidechain compression (`sidechaincompress=threshold=0.08:ratio=12:attack=20:release=300`) to dynamically attenuate background music under human voice activity to -22 dB.

4. **Graceful Heuristic Fallback:**
   If Ollama is offline or model is not yet loaded, the engine automatically switches to a built-in algorithmic take pruner that detects phrase repetitions, vocal fillers, and awkward silences, ensuring zero pipeline crashes.

---

## 🧪 Testing

Run all 11 unit and integration tests:

```bash
pytest tests
```
