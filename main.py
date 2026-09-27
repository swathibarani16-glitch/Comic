"""
main.py
-------
Application entrypoint. Run with:  uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes import router

app = FastAPI(
    title="ComicCraft",
    description="AI Comic Story Creator using Gemini Models",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
