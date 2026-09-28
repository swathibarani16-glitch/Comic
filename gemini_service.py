"""
gemini_service.py
------------------
All calls to Google's Gemini models live here using the official google-genai SDK.

Responsibilities:
1. generate_comic_script()  -> uses Gemini to write the story in structured JSON.
2. generate_panel_image()   -> (optional) uses Gemini to illustrate each panel.
3. check_gemini_connection() -> health check endpoint logic for /api/health/gemini.
"""

import os
import re
import json
import time
import uuid
import base64
from pathlib import Path
from typing import Optional

from google import genai
from dotenv import load_dotenv

from models import Panel, ComicStory

load_dotenv(override=True)

GENERATED_DIR = Path(__file__).parent / "static" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def _mask_credentials(text: str) -> str:
    """Masks API keys and auth tokens from error strings to prevent leaking sensitive data."""
    if not text:
        return ""
    text = re.sub(r"AIzaSy[A-Za-z0-9_-]{33}", "AIzaSy***", text)
    text = re.sub(r"AQ\.[A-Za-z0-9_-]{50,}", "AQ.***", text)
    text = re.sub(r"key=[A-Za-z0-9._-]+", "key=***", text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer ***", text)
    return text


def _get_api_key() -> str:
    load_dotenv(override=True)
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key or key.strip() in ("", "YOUR_API_KEY", "your_gemini_api_key_here"):
        raise ValueError(
            "GEMINI_API_KEY is not set or is empty in .env. "
            "Please obtain a valid key from https://aistudio.google.com/apikey and update GEMINI_API_KEY in .env."
        )
    return key.strip()


def _get_client() -> genai.Client:
    key = _get_api_key()
    return genai.Client(api_key=key)


def _get_text_model() -> str:
    return os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")


def _get_image_model() -> str:
    return os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")


def _is_image_gen_enabled() -> bool:
    load_dotenv(override=True)
    return os.getenv("ENABLE_IMAGE_GEN", "false").lower() == "true"


def check_gemini_connection() -> dict:
    """Minimal health check request to verify Gemini authentication & API connectivity."""
    try:
        client = _get_client()
        res = client.models.generate_content(
            model=_get_text_model(),
            contents="Respond with 'connected' if online.",
        )
        if res and res.text:
            return {"status": "ok", "gemini": "connected"}
        return {"status": "error", "message": "Gemini returned an empty response."}
    except ValueError as val_err:
        return {"status": "error", "message": _mask_credentials(str(val_err))}
    except Exception as exc:
        err_msg = _mask_credentials(str(exc))
        if any(token in err_msg for token in ("401", "UNAUTHENTICATED", "INVALID_ARGUMENT", "ACCESS_TOKEN_TYPE_UNSUPPORTED", "API key not valid")):
            return {
                "status": "error",
                "message": (
                    "Gemini API authentication error (401 UNAUTHENTICATED): "
                    "The GEMINI_API_KEY in .env is invalid or unauthenticated. "
                    "Please get a valid API key from https://aistudio.google.com/apikey and update GEMINI_API_KEY in .env."
                ),
            }
        return {"status": "error", "message": f"Gemini service issue: {err_msg}"}


def _call_gemini(model: str, prompt: str, retries: int = 2) -> str:
    """Generates content via google-genai SDK with automatic fallbacks for capacity spikes."""
    client = _get_client()

    models_to_try = [model]
    for fallback in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_exc = None
    for target_model in models_to_try:
        for attempt in range(retries):
            try:
                response = client.models.generate_content(
                    model=target_model,
                    contents=prompt,
                )
                if response and response.text:
                    return response.text
                raise RuntimeError("Empty response received from Gemini API.")
            except Exception as exc:
                last_exc = exc
                err_str = str(exc)
                if any(token in err_str for token in ("401", "UNAUTHENTICATED", "INVALID_ARGUMENT", "ACCESS_TOKEN_TYPE_UNSUPPORTED", "API key not valid")):
                    raise RuntimeError(
                        "Gemini API error (401): Request had invalid authentication credentials. "
                        "Expected a valid Gemini API key from https://aistudio.google.com/apikey in .env. status: UNAUTHENTICATED"
                    ) from exc
                if attempt < retries - 1:
                    time.sleep(1.5 * (attempt + 1))

        if "image" in model:
            break

    safe_err = _mask_credentials(str(last_exc))
    raise RuntimeError(f"Gemini service temporary issue: {safe_err}") from last_exc


def _build_script_prompt(story_idea: str, genre: str, art_style: str, num_panels: int) -> str:
    return f"""You are a professional comic book writer.

Story idea: {story_idea}
Genre: {genre}
Art style reference: {art_style}
Number of panels required: {num_panels}

Return ONLY valid JSON, no markdown code fences, no commentary, in exactly
this shape:

{{
  "title": "Short punchy comic title",
  "panels": [
    {{
      "panel_number": 1,
      "scene_description": "Vivid visual description an illustrator could draw from",
      "dialogue": "Short comic-style dialogue, or empty string if none",
      "caption": "Narration caption, or empty string if none"
    }}
  ]
}}

Rules:
- Exactly {num_panels} panel objects, numbered 1..{num_panels} in order.
- scene_description must be specific (setting, characters, action, mood).
- Keep dialogue punchy and short, like real comic speech bubbles.
"""


def _extract_json(text: str) -> dict:
    """Gemini sometimes wraps JSON in ```json fences even when told not to."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("Gemini did not return parseable JSON for the comic script.")
    return json.loads(match.group(0))


def generate_comic_script(story_idea: str, genre: str, art_style: str, num_panels: int) -> ComicStory:
    prompt = _build_script_prompt(story_idea, genre, art_style, num_panels)
    text = _call_gemini(_get_text_model(), prompt)
    parsed = _extract_json(text)
    panels = [Panel(**p) for p in parsed["panels"]]
    return ComicStory(title=parsed.get("title", "Untitled Comic"), panels=panels)


def generate_panel_image(scene_description: str, art_style: str) -> Optional[str]:
    """Returns a path relative to /static (e.g. 'generated/xyz.png'), or None if image generation is disabled."""
    if not _is_image_gen_enabled():
        return None
    try:
        client = _get_client()
        prompt = (
            f"{art_style} style comic book panel illustration, single frame, "
            f"no text, no speech bubbles, no captions: {scene_description}"
        )
        data = client.models.generate_content(
            model=_get_image_model(),
            contents=prompt,
        )
        if data and data.candidates:
            parts = data.candidates[0].content.parts
            for part in parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_bytes = part.inline_data.data
                    if isinstance(image_bytes, str):
                        image_bytes = base64.b64decode(image_bytes)
                    filename = f"{uuid.uuid4().hex}.png"
                    (GENERATED_DIR / filename).write_bytes(image_bytes)
                    return f"generated/{filename}"
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on purpose
        print(f"[ComicCraft] Image generation skipped: {_mask_credentials(str(exc))}")
    return None


def generate_comic(story_idea: str, genre: str, art_style: str, num_panels: int) -> ComicStory:
    """Top-level entry point used by routes.py."""
    story = generate_comic_script(story_idea, genre, art_style, num_panels)
    for i, panel in enumerate(story.panels):
        if i > 0 and _is_image_gen_enabled():
            time.sleep(1.5)
        panel.image_path = generate_panel_image(panel.scene_description, art_style)
    return story