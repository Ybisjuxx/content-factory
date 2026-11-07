import json
import logging
import re
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.models.job import DirectorPlan, EditSegment, VisualCue

logger = logging.getLogger(__name__)


DIRECTOR_SYSTEM_PROMPT = """
You are an expert Hollywood video editor, creative director, and viral short-form content producer.
Your goal is to transform a raw, unedited, multi-take video transcript into a razor-sharp, engaging 9:16 vertical short.

Your tasks:
1. TAKE PRUNING:
   - Identify repeated takes, stumbles, false starts, and throat-clearing.
   - When the speaker restarts a sentence or says the same thought multiple times, KEEP ONLY THE BEST, MOST FLUENT TAKE and CUT all previous attempts!
   - Mark every original segment as either `keep: true` or `keep: false` with a concise reason.
   
2. HOOK & SUMMARY:
   - Create a punchy hook (first 3 seconds) that hooks the viewer instantly.
   - Provide a concise summary of the core value proposition.

3. VISUAL CUES & B-ROLL INSERTION:
   - Plan where to cut away to 9:16 vertical B-roll or procedural SVG graphic cards.
   - Suggest B-roll search keywords (e.g. "artificial intelligence", "coding matrix", "laptop coffee", "growth graph").
   - Suggest procedural SVG cards for numbers, statistics, or key bullet points (e.g. card_type: 'stat', card_title: '+350% Growth', card_content: 'Production speed increase').

STRICT REQUIREMENT: You MUST respond ONLY with a single valid JSON object following this exact structure:
{
  "title": "Short title",
  "hook": "Strong opening hook sentence",
  "summary": "Core topic summary",
  "edit_decision_list": [
    {
      "start": 0.0,
      "end": 2.5,
      "keep": false,
      "reason": "False start / repetition",
      "text": "..."
    },
    {
      "start": 2.5,
      "end": 5.8,
      "keep": true,
      "reason": "Clean final take",
      "text": "..."
    }
  ],
  "visual_cues": [
    {
      "timestamp_start": 3.0,
      "timestamp_end": 5.5,
      "asset_type": "broll",
      "query_or_topic": "technology computer code",
      "card_type": null,
      "card_title": null,
      "card_content": null
    },
    {
      "timestamp_start": 6.0,
      "timestamp_end": 8.5,
      "asset_type": "svg_card",
      "query_or_topic": "stat",
      "card_type": "stat",
      "card_title": "100% LOCAL",
      "card_content": "Zero cloud subscription fees"
    }
  ]
}
"""


class SemanticDirector:
    """Local LLM Semantic Director using Ollama API with strict JSON schema enforcement."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

    def check_ollama_status(self) -> Dict[str, Any]:
        """Check if local Ollama daemon is reachable and list installed models."""
        import socket
        # Fast socket probe to prevent any HTTP connection hang
        port = 11434
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.base_url)
            port = parsed.port or 11434
            host = parsed.hostname or "127.0.0.1"
            with socket.create_connection((host, port), timeout=0.15):
                pass
        except Exception:
            return {
                "available": False,
                "url": self.base_url,
                "installed_models": [],
                "target_model": self.model_name,
                "target_model_present": False,
                "fallback_engine": "Heurístico Local Activo"
            }

        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    return {
                        "available": True,
                        "url": self.base_url,
                        "installed_models": models,
                        "target_model": self.model_name,
                        "target_model_present": any(self.model_name in m for m in models)
                    }
        except Exception:
            pass
        return {
            "available": False,
            "url": self.base_url,
            "installed_models": [],
            "target_model": self.model_name,
            "target_model_present": False,
            "fallback_engine": "Heurístico Local Activo"
        }

    def direct(self, transcript_data: Dict[str, Any]) -> DirectorPlan:
        """Analyzes transcript segments, prunes redundant takes, and generates edit plan."""
        segments = transcript_data.get("segments", [])
        duration = float(transcript_data.get("duration", 0.0) or 5.0)

        if not segments:
            logger.info("No speech segments detected in media. Retaining entire video as single take.")
            default_edl = [
                EditSegment(
                    start=0.0,
                    end=max(1.0, duration),
                    keep=True,
                    reason="No speech detected / ambient pass-through",
                    text=""
                )
            ]
            return DirectorPlan(
                title="Ambient Video",
                hook="Autonomous Video",
                summary="Full ambient pass-through",
                edit_decision_list=default_edl,
                visual_cues=[],
                removed_takes_count=0,
                estimated_duration=round(duration, 2)
            )

        prompt_payload = {
            "media_duration": transcript_data.get("duration", 0.0),
            "language": transcript_data.get("language", "auto"),
            "segments_to_evaluate": [
                {
                    "id": s["id"],
                    "start": s["start"],
                    "end": s["end"],
                    "text": s["text"]
                }
                for s in segments
            ]
        }

        user_content = (
            f"Here is the raw unedited transcript with exact timestamps:\n"
            f"{json.dumps(prompt_payload, indent=2)}\n\n"
            f"Analyze all takes, prune false starts and stumbles, plan visual cuts, and generate the JSON DirectorPlan."
        )

        ollama_status = self.check_ollama_status()
        if ollama_status["available"]:
            try:
                plan = self._call_ollama(user_content)
                if plan:
                    return self._reconcile_and_enrich_plan(plan, segments)
            except Exception as e:
                logger.error(f"Error executing Ollama semantic director: {e}. Falling back to rule-based engine.")

        # Heuristic fallback if Ollama is unavailable or failed
        logger.info("Using built-in heuristic take pruner & semantic director engine.")
        return self._heuristic_prune(segments, transcript_data)

    def _call_ollama(self, user_prompt: str) -> Optional[DirectorPlan]:
        """Query local Ollama with format='json' enforcement."""
        api_url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            }
        }

        logger.info(f"Querying Ollama model '{self.model_name}' at {api_url}...")
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(api_url, json=payload)
            if response.status_code != 200:
                logger.warning(f"Ollama returned HTTP {response.status_code}: {response.text}")
                return None

            data = response.json()
            message_content = data.get("message", {}).get("content", "")
            
            # Parse strict JSON output
            plan_dict = json.loads(message_content)
            return DirectorPlan(**plan_dict)

    def _heuristic_prune(self, segments: List[Dict[str, Any]], transcript_data: Dict[str, Any]) -> DirectorPlan:
        """Algorithmic take-pruner for instant offline execution and testing.

        Rules:
        - Consecutive repetitive phrases/stumbles: keep only the latest take.
        - Segments that are very short and consist only of filler sounds ('uh', 'um', 'ah', 'eh') are pruned.
        - Generates automatic visual cue insertions every 5-8 seconds.
        """
        fillers = {"um", "uh", "ah", "eh", "er", "like", "you know", "o sea", "este", "bueno"}
        edl: List[EditSegment] = []
        kept_count = 0
        pruned_count = 0

        for i, seg in enumerate(segments):
            text = seg["text"].strip().lower()
            clean_words = [w for w in re.sub(r"[^\w\s]", "", text).split() if w]
            
            is_keep = True
            reason = "Clean take"

            # Check for pure filler words
            if len(clean_words) <= 2 and all(w in fillers for w in clean_words):
                is_keep = False
                reason = "Vocal filler / pause"

            # Check if next segment is an immediate restart / repetition of this one
            if i < len(segments) - 1:
                next_text = segments[i + 1]["text"].strip().lower()
                next_words = [w for w in re.sub(r"[^\w\s]", "", next_text).split() if w]
                # If first 2+ words match next segment, current segment is a false start
                if len(clean_words) >= 2 and len(next_words) >= 2:
                    if clean_words[:2] == next_words[:2]:
                        is_keep = False
                        reason = "False start / superseded by following take"

            if is_keep:
                kept_count += 1
            else:
                pruned_count += 1

            edl.append(
                EditSegment(
                    start=seg["start"],
                    end=seg["end"],
                    keep=is_keep,
                    reason=reason,
                    text=seg["text"]
                )
            )

        # Generate intelligent visual cues over kept timeline
        visual_cues: List[VisualCue] = []
        cumulative_time = 0.0
        for seg in edl:
            duration = seg.end - seg.start
            if seg.keep and duration > 3.0:
                cue_start = cumulative_time + 0.5
                cue_end = min(cumulative_time + duration - 0.2, cue_start + 3.0)
                
                # Pick topic from words
                words = [w for w in re.sub(r"[^\w\s]", "", seg.text).split() if len(w) > 4]
                topic = words[0] if words else "technology"

                if len(visual_cues) % 2 == 0:
                    visual_cues.append(
                        VisualCue(
                            timestamp_start=round(cue_start, 2),
                            timestamp_end=round(cue_end, 2),
                            asset_type="broll",
                            query_or_topic=topic,
                        )
                    )
                else:
                    visual_cues.append(
                        VisualCue(
                            timestamp_start=round(cue_start, 2),
                            timestamp_end=round(cue_end, 2),
                            asset_type="svg_card",
                            query_or_topic="stat",
                            card_type="stat",
                            card_title="KEY HIGHLIGHT",
                            card_content=seg.text[:40] + ("..." if len(seg.text) > 40 else "")
                        )
                    )
            if seg.keep:
                cumulative_time += duration

        first_kept = next((s for s in edl if s.keep), None)
        hook_text = first_kept.text if first_kept else "Autonomous Local Video"

        return DirectorPlan(
            title="Local AI Video Production",
            hook=hook_text,
            summary=transcript_data.get("full_text", "")[:120],
            edit_decision_list=edl,
            visual_cues=visual_cues,
            removed_takes_count=pruned_count,
            estimated_duration=round(cumulative_time, 2)
        )

    def _reconcile_and_enrich_plan(
        self, plan: DirectorPlan, original_segments: List[Dict[str, Any]]
    ) -> DirectorPlan:
        """Ensures all segments from Whisper are mapped to the EDL with valid timestamps."""
        if not plan.edit_decision_list:
            return self._heuristic_prune(original_segments, {})

        # If LLM didn't include text or accurate timestamps, match with originals
        for i, edl_seg in enumerate(plan.edit_decision_list):
            if i < len(original_segments):
                orig = original_segments[i]
                if not edl_seg.text:
                    edl_seg.text = orig["text"]
                if edl_seg.start == 0.0 and edl_seg.end == 0.0:
                    edl_seg.start = orig["start"]
                    edl_seg.end = orig["end"]

        # Recalculate duration & removed count
        kept_duration = sum(s.end - s.start for s in plan.edit_decision_list if s.keep)
        plan.estimated_duration = round(kept_duration, 2)
        plan.removed_takes_count = sum(1 for s in plan.edit_decision_list if not s.keep)
        return plan
