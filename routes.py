"""
routes.py
---------
Main application logic (Epic 3): receives user input from the form,
calls the Gemini service, and renders the Jinja2 templates.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from gemini_service import generate_comic

router = APIRouter()
templates = Jinja2Templates(directory="templates")

MAX_PANELS = 10
MIN_PANELS = 1


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    story_idea: str = Form(...),
    genre: str = Form("Adventure"),
    art_style: str = Form("Manga"),
    num_panels: int = Form(6),
):
    error = None
    story = None

    if not story_idea.strip():
        error = "Please enter a story idea before generating your comic."
    else:
        num_panels = max(MIN_PANELS, min(num_panels, MAX_PANELS))
        try:
            story = generate_comic(story_idea, genre, art_style, num_panels)
        except Exception as exc:  # noqa: BLE001 - surface a friendly error to the UI
            error = f"Could not generate comic: {exc}"

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "story": story,
            "error": error,
            "form": {
                "story_idea": story_idea,
                "genre": genre,
                "art_style": art_style,
                "num_panels": num_panels,
            },
        },
    )


@router.get("/health", response_class=HTMLResponse)
async def health():
    return "OK"
