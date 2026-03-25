"""
In-memory search index over the 914 Stats NZ dataflows.

On startup the index is populated by fetching the full dataflow list from
the ADE API.  Subsequent searches are pure in-memory keyword matching so
they're fast and don't cost API quota.
"""
import asyncio
import logging
from typing import Optional
from services.ade_client import get_all_dataflows
from services.sdmx_parser import parse_dataflows

logger = logging.getLogger(__name__)

# Module-level cache — shared across all requests
_dataflows: list[dict] = []
_index_ready = asyncio.Event()


async def build_index() -> None:
    """Fetch all dataflows from Stats NZ and populate the in-memory index."""
    global _dataflows
    logger.info("Building dataflow index from Stats NZ ADE API …")
    try:
        xml = await get_all_dataflows()
        _dataflows = parse_dataflows(xml)
        logger.info(f"Dataflow index ready — {len(_dataflows)} dataflows loaded")
    except Exception as exc:
        logger.error(f"Failed to build dataflow index: {exc}")
        # Don't crash startup; individual requests will surface the error
    finally:
        _index_ready.set()


async def ensure_index() -> None:
    """Wait until the index has been built (at most 60 s)."""
    await asyncio.wait_for(_index_ready.wait(), timeout=60.0)


def search(keywords: list[str], limit: int = 10) -> list[dict]:
    """
    Simple ranked keyword search over dataflow ids, names, and descriptions.
    Returns up to `limit` results ordered by match score (descending).
    """
    if not _dataflows:
        return []

    lower_kw = [kw.lower() for kw in keywords]
    scored: list[tuple[int, dict]] = []

    for df in _dataflows:
        haystack = " ".join(filter(None, [
            df.get("id", ""),
            df.get("name", ""),
            df.get("description", ""),
        ])).lower()

        score = sum(1 for kw in lower_kw if kw in haystack)
        if score > 0:
            scored.append((score, df))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [df for _, df in scored[:limit]]


def get_by_id(dataflow_id: str) -> Optional[dict]:
    """Return a single dataflow dict by exact ID match, or None."""
    for df in _dataflows:
        if df.get("id", "").upper() == dataflow_id.upper():
            return df
    return None


def total_count() -> int:
    return len(_dataflows)
