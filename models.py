from typing import List, Optional
from pydantic import BaseModel


class ComicRequest(BaseModel):
    """Input the user submits from the web form."""
    story_idea: str
    genre: str = "Adventure"
    art_style: str = "Manga"
    num_panels: int = 6


class Panel(BaseModel):
    """A single comic panel produced by Gemini."""
    panel_number: int
    scene_description: str
    dialogue: Optional[str] = ""
    caption: Optional[str] = ""
    image_path: Optional[str] = None  # relative path under /static, if image gen is enabled


class ComicStory(BaseModel):
    """The full generated comic."""
    title: str
    panels: List[Panel]
