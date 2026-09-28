"""
routes.py
---------
Main application logic (Epic 3): receives user input from the form,
calls the Gemini service, and renders the Jinja2 templates.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from gemini_service import generate_comic, check_gemini_connection, _mask_credentials

router = APIRouter()
templates = Jinja2Templates(directory="templates")

MAX_PANELS = 10
MIN_PANELS = 1


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    story_idea: str = Form(""),
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
            safe_err = _mask_credentials(str(exc))
            error = f"Could not generate comic: {safe_err}"

    return templates.TemplateResponse(
        request,
        "result.html",
        {
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


@router.get("/api/health/gemini", response_class=JSONResponse)
async def health_gemini():
    result = check_gemini_connection()
    status_code = 200 if result.get("status") == "ok" else (401 if "authentication" in result.get("message", "").lower() else 500)
    return JSONResponse(content=result, status_code=status_code)

