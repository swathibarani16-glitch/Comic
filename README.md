# ComicCraft — AI Comic Story Creator using Gemini Models

Turn a one-line idea into a short comic: Gemini writes the panel-by-panel
script (scene, dialogue, caption), and the app renders it as a comic strip
in the browser. Optional: Gemini also illustrates each panel.

This README is organised by the same epics from the project board:

---

## Epic: Pre-requisites

- Python 3.10+
- A free Gemini API key from https://aistudio.google.com/apikey
- `pip` (or a virtualenv tool)

## Epic: Workflow

```
User fills form (idea, genre, art style, panel count)
        │
        ▼
POST /generate  (routes.py)
        │
        ▼
gemini_service.generate_comic()
        │
        ├── generate_comic_script() → Gemini text model → JSON panels
        │
        └── generate_panel_image()  → Gemini image model (optional) → PNG
        │
        ▼
result.html renders the comic strip
```

## Epic 1: Model selection & Architecture

- **Text model**: `gemini-2.5-flash` (fast, cheap, good enough for short
  comic scripts) — configurable via `GEMINI_TEXT_MODEL` in `.env`.
- **Image model**: `gemini-2.5-flash-image` — configurable via
  `GEMINI_IMAGE_MODEL`, off by default (`ENABLE_IMAGE_GEN=false`) since
  image-generation quota/access varies by API key. The app degrades
  gracefully to a text-description placeholder per panel if this is off
  or fails.
- **Architecture**: a thin FastAPI app (`main.py` + `routes.py`) calling a
  single service module (`gemini_service.py`) that owns all Gemini calls,
  rendering server-side with Jinja2 (`templates/`). No database — this is a
  stateless prototype (each request is generated fresh).

```
comiccraft/
├── main.py              # FastAPI app + static mount
├── routes.py            # GET / , POST /generate
├── gemini_service.py    # all Gemini API calls live here
├── models.py            # Pydantic schemas (ComicRequest, Panel, ComicStory)
├── templates/
│   ├── base.html
│   ├── index.html       # the input form
│   └── result.html      # the rendered comic
├── static/
│   ├── style.css
│   └── generated/       # panel images land here if ENABLE_IMAGE_GEN=true
├── test_app.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Epic 2: Core functionalities / FastAPI backend

- `gemini_service.generate_comic_script()` — prompts Gemini to return
  **strict JSON** (title + numbered panels with scene/dialogue/caption),
  and safely extracts JSON even if Gemini wraps it in ```` ```json ```` fences.
- `gemini_service.generate_panel_image()` — optional per-panel illustration.
- `routes.py` — validates input (empty idea, panel count clamped to 1–10),
  calls the service, and always renders a page (success or friendly error)
  instead of crashing.

## Epic 3: Main application logic (`routes.py`)

- `GET /` → renders the form (`index.html`)
- `POST /generate` → reads form fields, calls `generate_comic()`, renders
  `result.html` with either the comic or an error message
- `GET /health` → simple liveness check

## Epic 4: Frontend / Jinja2 templates

- `base.html` — shared layout, Bootstrap 5 + Google Fonts (Bangers for
  comic-style headings) via CDN, plus `static/style.css`
- `index.html` — the story-idea form (extends `base.html`)
- `result.html` — renders each panel as a comic-book-styled card with
  panel number, image (or placeholder text), caption and speech bubble

## Epic 5: Local deployment & testing

### 1. Set up the environment

```bash
git clone <your-repo-url>
cd comiccraft
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and paste your key:

```
GEMINI_API_KEY=your_actual_key_here
```

### 2. Run it

```bash
uvicorn main:app --reload
```

Visit **http://127.0.0.1:8000**, enter a story idea, and generate your comic.

### 3. Test it

Tests mock the Gemini calls, so they run with no API key or network needed:

```bash
pip install pytest httpx
pytest -v
```

### 4. Turn on image generation (optional)

Once you've confirmed your Gemini key/plan supports image generation, set
in `.env`:

```
ENABLE_IMAGE_GEN=true
```

---

## Pushing to GitHub

```bash
cd comiccraft
git init
git add .
git commit -m "ComicCraft prototype: FastAPI + Gemini comic generator"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

`.env` is already in `.gitignore` — your API key will **not** be pushed.
Anyone cloning the repo just needs their own key in `.env`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `RuntimeError: GEMINI_API_KEY not set` | Copy `.env.example` → `.env` and add your key |
| Comic panels look generic / off-topic | Rewrite your story idea to be more specific |
| Images never appear | `ENABLE_IMAGE_GEN` is `false` by default, or your key lacks image access — panels still show as styled text cards |
| `ModuleNotFoundError` | Activate your venv and re-run `pip install -r requirements.txt` |
