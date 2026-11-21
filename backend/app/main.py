from __future__ import annotations

import asyncio
import hmac
import logging
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import database
from app.ai import TokenUsage, generate_listing
from app.ai_pricing import get_model_rates
from app.config import DEFAULT_MODEL, get_frontend_dir
from app.extractor import ExtractionError, extract_product, validate_aliexpress_url
from app.models import (
    ExtractionStartRequest,
    GenerateRequest,
    ListingContent,
    ProductData,
    RenderRequest,
    SaveListingRequest,
    SettingsUpdate,
)
from app.renderer import render_listing
from app.secrets import secrets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ExtractionJob:
    id: str
    status: str = "opening"
    message: str = "Opening the product page in Chromium..."
    product: ProductData | None = None
    error: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    continue_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None

    def update(self, status: str, message: str) -> None:
        self.status = status
        self.message = message
        self.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


extraction_jobs: dict[str, ExtractionJob] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize_database()
    yield
    tasks = [job.task for job in extraction_jobs.values() if job.task and not job.task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(
    title="PrimePick Goods Listing Generator",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def handle_invalid_request(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Some listing information is missing or too long. Review the title, description, and content fields, then try again."},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled request error for %s (%s)", request.url.path, type(error).__name__)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "PrimePick Goods Listing Generator"}


@app.get("/api/usage")
async def get_openai_usage() -> dict[str, int | float]:
    return database.get_openai_usage_summary()


async def _run_extraction(job: ExtractionJob, url: str) -> None:
    async def report(status: str, message: str) -> None:
        job.update(status, message)

    try:
        product = await extract_product(url, report, job.continue_event)
        job.product = product
        job.error = None
        job.update("completed", "Product information extracted. Review the details before generating copy.")
    except ExtractionError as error:
        job.error = str(error)
        job.update("failed", str(error))
    except asyncio.CancelledError:
        job.update("cancelled", "Extraction stopped.")
        raise
    except Exception as error:
        logger.exception("Extraction job %s failed (%s)", job.id, type(error).__name__)
        job.error = "We couldn't read this AliExpress page. Check the URL and try again."
        job.update("failed", job.error)


def _job_payload(job: ExtractionJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "message": job.message,
        "updated_at": job.updated_at,
        "product": job.product.model_dump(mode="json") if job.product else None,
        "error": job.error,
    }


@app.post("/api/extractions", status_code=202)
async def start_extraction(request: ExtractionStartRequest) -> dict[str, Any]:
    try:
        url = validate_aliexpress_url(request.url)
    except ExtractionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    job_id = str(uuid.uuid4())
    job = ExtractionJob(id=job_id)
    extraction_jobs[job_id] = job
    job.task = asyncio.create_task(_run_extraction(job, url), name=f"extract-{job_id}")
    return _job_payload(job)


@app.get("/api/extractions/{job_id}")
async def get_extraction(job_id: str) -> dict[str, Any]:
    job = extraction_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That extraction is no longer available. Please start again.")
    return _job_payload(job)


@app.post("/api/extractions/{job_id}/continue")
async def continue_extraction(job_id: str) -> dict[str, str]:
    job = extraction_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That extraction is no longer available.")
    if job.status != "verification_required":
        raise HTTPException(status_code=409, detail="The product page is not waiting for verification right now.")
    job.continue_event.set()
    return {"status": "continuing", "message": "Checking the page now..."}


@app.post("/api/extractions/{job_id}/cancel")
async def cancel_extraction(job_id: str) -> dict[str, str]:
    job = extraction_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That extraction is no longer available.")
    if job.task and not job.task.done():
        job.task.cancel()
    job.update("cancelled", "Extraction stopped.")
    return {"status": "cancelled", "message": job.message}


@app.post("/api/generate")
async def generate(request: GenerateRequest) -> dict[str, Any]:
    api_key = secrets.get()
    if not api_key:
        raise HTTPException(status_code=400, detail="Add your OpenAI API key in Settings before generating listing copy.")
    model = database.get_preference("openai_model", DEFAULT_MODEL)

    def record_usage(usage: TokenUsage) -> None:
        rates = get_model_rates(model)
        input_price, output_price = rates if rates else (None, None)
        database.record_openai_usage(
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            input_price_per_million=input_price,
            output_price_per_million=output_price,
        )

    try:
        content = await generate_listing(request.product, api_key, model, on_usage=record_usage)
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"content": content.model_dump(mode="json")}


@app.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    return {
        "api_key_configured": bool(secrets.get()),
        "model": database.get_preference("openai_model", DEFAULT_MODEL),
        "key_storage": "OS credential vault when available; encrypted local fallback otherwise",
    }


@app.put("/api/settings")
async def update_settings(request: SettingsUpdate) -> dict[str, Any]:
    if request.clear_api_key:
        secrets.clear()
    elif request.api_key is not None and request.api_key.strip():
        secrets.set(request.api_key.strip())
    if request.model is not None:
        database.set_preference("openai_model", request.model)
    return await get_settings()


@app.post("/api/render")
async def render(request: RenderRequest) -> dict[str, str]:
    try:
        html = render_listing(request.product, request.content)
    except Exception as error:
        logger.exception("HTML rendering failed (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="The listing preview could not be built. Check the content and try again.") from error
    return {"html": html}


@app.post("/api/listings", status_code=201)
async def create_listing(request: SaveListingRequest) -> dict[str, Any]:
    try:
        html = render_listing(request.product, request.content)
        return database.save_listing(request.product, request.content, html)
    except Exception as error:
        logger.exception("Could not save listing (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="The listing could not be saved. Please try again.") from error


@app.get("/api/listings")
async def get_listings() -> list[dict[str, Any]]:
    return database.list_listings()


@app.get("/api/listings/{listing_id}")
async def get_listing(listing_id: str) -> dict[str, Any]:
    item = database.get_listing(listing_id)
    if item is None:
        raise HTTPException(status_code=404, detail="This saved listing could not be found.")
    return item


@app.get("/api/listings/{listing_id}/download")
async def download_listing(listing_id: str) -> HTMLResponse:
    item = database.get_listing(listing_id)
    if item is None:
        raise HTTPException(status_code=404, detail="This saved listing could not be found.")
    safe_name = "".join(
        character for character in item["title"] if character.isascii() and (character.isalnum() or character in " -_")
    ).strip()[:60]
    safe_name = safe_name or "primepick-listing"
    return HTMLResponse(
        item["html"],
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.html"'},
    )


@app.post("/api/internal/shutdown")
async def request_shutdown(request: Request) -> dict[str, str]:
    expected = os.getenv("PRIMEPICK_SHUTDOWN_TOKEN", "")
    supplied = request.headers.get("x-primepick-shutdown-token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="Shutdown request is not authorized.")
    server = getattr(app.state, "uvicorn_server", None)
    if server is not None:
        asyncio.get_running_loop().call_later(0.15, setattr, server, "should_exit", True)
    return {"status": "shutting_down"}


frontend_dir = get_frontend_dir()
assets_dir = frontend_dir / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
async def frontend_index() -> FileResponse:
    index_file = frontend_dir / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="The desktop interface has not been built yet.")
    return FileResponse(index_file)


@app.get("/{frontend_path:path}", include_in_schema=False)
async def frontend_fallback(frontend_path: str) -> FileResponse:
    candidate = (frontend_dir / frontend_path).resolve()
    root = frontend_dir.resolve()
    if root in candidate.parents and candidate.is_file():
        return FileResponse(candidate)
    index_file = frontend_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Page not found.")
