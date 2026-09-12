"""
FastAPI application entrypoint for Outside Bubble Scraper Service.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from apps.scraper_service.config import settings
from apps.scraper_service.api.routes import router
from apps.scraper_service.providers.fetcher.browser import browser_fetcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure storage dir exists and optionally pre-warm browser
    Path(settings.local_storage_dir).mkdir(parents=True, exist_ok=True)
    if settings.browser_enabled:
        try:
            await browser_fetcher.start()
        except Exception as e:
            print(f"Warning: Browser pre-warm failed: {e}")
    yield
    # Shutdown: gracefully close browser
    if settings.browser_enabled:
        await browser_fetcher.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Generic, self-hosted web acquisition service providing structured content, media, and screenshots.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local storage directory for static access if local storage provider is active
storage_path = Path(settings.local_storage_dir)
storage_path.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(storage_path)), name="storage")

@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")

# Include main router
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.scraper_service.main:app", host=settings.host, port=settings.port, reload=True)
