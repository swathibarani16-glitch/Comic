"""
gemini_service.py
------------------
All calls to Google's Gemini models live here (Epic 1 & Epic 2:
Model selection/architecture + core functionalities).

This talks to Gemini directly over plain HTTPS (REST via `requests`),
instead of the grpc-based google-generativeai SDK. Some locked-down Windows
machines (corporate antivirus / Application Control policies) block grpc's
native DLLs, so REST keeps this prototype portable everywhere.

Two responsibilities:
1. generate_comic_script()  -> uses a Gemini text model to write the story,
                                broken into panels, as structured JSON.
2. generate_panel_image()   -> (optional) uses a Gemini image-capable model
                                to illustrate each panel.

Image generation is OFF by default (ENABLE_IMAGE_GEN=false in .env) so the
prototype works immediately with just a text-model API key/quota. Turn it on
once you've confirmed your Gemini key has image-generation access.
"""

import os
import re
import json
import uuid
import base64
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from models import Panel, ComicStory

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
ENABLE_IMAGE_GEN = os.getenv("ENABLE_IMAGE_GEN", "false").lower() == "true"

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not set. Copy .env.example to .env and paste a key "
        "from https://aistudio.google.com/apikey"
    )

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

GENERATED_DIR = Path(__file__).parent / "static" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def _call_gemini(model: str, prompt: str) -> dict:
    """POSTs a single-turn prompt to the Gemini REST API and returns the parsed JSON body."""
    url = f"{API_BASE}/{model}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, json=payload, timeout=60)
    if not response.ok:
        raise RuntimeError(f"Gemini API error ({response.status_code}): {response.text[:300]}")
    return response.json()


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
    data = _call_gemini(TEXT_MODEL, prompt)

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response shape: {data}") from exc

    parsed = _extract_json(text)
    panels = [Panel(**p) for p in parsed["panels"]]
    return ComicStory(title=parsed.get("title", "Untitled Comic"), panels=panels)


def generate_panel_image(scene_description: str, art_style: str) -> Optional[str]:
    """Returns a path relative to /static (e.g. 'generated/xyz.png'), or None
    if image generation is disabled or fails. The app must keep working with
    text-only panels either way."""
    if not ENABLE_IMAGE_GEN:
        return None
    try:
        prompt = (
            f"{art_style} style comic book panel illustration, single frame, "
            f"no text, no speech bubbles, no captions: {scene_description}"
        )
        data = _call_gemini(IMAGE_MODEL, prompt)
        parts = data["candidates"][0]["content"]["parts"]
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                image_bytes = base64.b64decode(inline["data"])
                filename = f"{uuid.uuid4().hex}.png"
                (GENERATED_DIR / filename).write_bytes(image_bytes)
                return f"generated/{filename}"
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on purpose
        print(f"[ComicCraft] Image generation skipped: {exc}")
    return None


def generate_comic(story_idea: str, genre: str, art_style: str, num_panels: int) -> ComicStory:
    """Top-level entry point used by routes.py."""
    story = generate_comic_script(story_idea, genre, art_style, num_panels)
    for panel in story.panels:
        panel.image_path = generate_panel_image(panel.scene_description, art_style)
    return story