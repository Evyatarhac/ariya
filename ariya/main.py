from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ariya.api.routes import router
from ariya.config import settings
from ariya.orchestrator import brain

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

DASH_DIR = Path(__file__).parent / "dashboard"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await brain.boot()
    yield


app = FastAPI(title="ARIYA", version="0.1.0", lifespan=lifespan)
app.include_router(router, prefix="/api")

if DASH_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DASH_DIR)), name="static")

    @app.get("/")
    def root():
        return FileResponse(DASH_DIR / "index.html")


def main():
    uvicorn.run("ariya.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
