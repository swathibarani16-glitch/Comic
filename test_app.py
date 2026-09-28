"""
test_app.py
-----------
Quick sanity tests. Gemini calls are mocked so tests run without an API key
or network access — run with:  pytest -v
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from models import ComicStory, Panel


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.text == "OK"


@patch("routes.check_gemini_connection")
def test_health_gemini_endpoint(mock_check):
    mock_check.return_value = {"status": "ok", "gemini": "connected"}
    response = client.get("/api/health/gemini")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "gemini": "connected"}


def test_index_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "ComicCraft" in response.text


def test_generate_empty_story_idea_shows_error():
    response = client.post("/generate", data={"story_idea": "", "genre": "Adventure", "art_style": "Manga", "num_panels": 4})
    assert response.status_code == 200
    assert "enter a story idea" in response.text


@patch("routes.generate_comic")
def test_generate_success(mock_generate_comic):
    mock_generate_comic.return_value = ComicStory(
        title="Test Comic",
        panels=[
            Panel(panel_number=1, scene_description="A hero stands on a rooftop", dialogue="Let's go!", caption="Night falls."),
        ],
    )
    response = client.post(
        "/generate",
        data={"story_idea": "A hero's first night patrol", "genre": "Adventure", "art_style": "Manga", "num_panels": 1},
    )
    assert response.status_code == 200
    assert "Test Comic" in response.text
    assert "Let&#39;s go!" in response.text or "Let's go!" in response.text

