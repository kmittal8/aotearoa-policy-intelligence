"""
Aotearoa Policy Intelligence — FastAPI Custom Tool
Wraps the Stats NZ ADE API for use as an OCI GenAI Agent custom tool.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from routers import dataflows, data
from services import dataflow_index

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the in-memory dataflow index on startup (background-safe)
    import asyncio
    asyncio.create_task(dataflow_index.build_index())
    yield


app = FastAPI(
    title="Aotearoa Policy Intelligence — Stats NZ Tool",
    description=(
        "Custom tool for OCI GenAI Agents. "
        "Provides live access to 914 Stats NZ ADE dataflows "
        "(Census, Business Demography, LEED, Iwi, Justice, etc.).\n\n"
        "**Usage flow for the agent:**\n"
        "1. `POST /search-dataflows` — find relevant datasets\n"
        "2. `POST /get-dimensions` — discover valid filter codes\n"
        "3. `POST /get-data` — fetch observations\n"
        "4. `POST /compare-periods` — trend comparison across census years"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(dataflows.router)
app.include_router(data.router)


@app.get("/health", tags=["Meta"])
async def health():
    """Health check — reports dataflow index status and cache stats."""
    from services.cache import stats as cache_stats
    count = dataflow_index.total_count()
    status = "ready" if count > 0 else "indexing"
    return JSONResponse({
        "status": status,
        "dataflows_indexed": count,
        "cache": cache_stats(),
    })


@app.get("/", tags=["Meta"])
async def root():
    return {
        "name": "Aotearoa Policy Intelligence",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
