"""
Stats NZ ADE API client.
Base URL:  https://apis.stats.govt.nz/ade-api/rest/v1/
Auth:      Ocp-Apim-Subscription-Key header
Returns:   SDMX XML (cached in-memory to avoid redundant API calls)
"""
import os
import httpx
from typing import Optional
from services.cache import get as cache_get, set as cache_set, TTL_DATAFLOWS, TTL_DATASTRUCTURE, TTL_OBSERVATIONS

BASE_URL = os.getenv("ADE_BASE_URL", "https://apis.stats.govt.nz/ade-api/rest/v1")
SUBSCRIPTION_KEY = os.getenv("ADE_SUBSCRIPTION_KEY", "a674b7952feb450c826d27a357dda711")
USER_AGENT = "AotearoaPI/1.0 (Language=Python/3.x)"

HEADERS = {
    "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    "user-agent": USER_AGENT,
    "Accept": "application/xml",
}

# Timeout: Stats NZ can be slow on large requests
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def get_all_dataflows() -> str:
    """Fetch all available dataflows as SDMX XML (cached 24 h)."""
    cached = cache_get("dataflows")
    if cached:
        return cached
    url = f"{BASE_URL}/dataflow/all/all/latest"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        xml = resp.text
    cache_set("dataflows", xml, TTL_DATAFLOWS)
    return xml


async def get_datastructure(dataflow_id: str, agency: str = "STATSNZ") -> str:
    """Fetch the DSD (dimensions, codes) for a specific dataflow (cached 6 h)."""
    cached = cache_get("dsd", id=dataflow_id, agency=agency)
    if cached:
        return cached
    url = f"{BASE_URL}/datastructure/{agency}/{dataflow_id}/latest"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        xml = resp.text
    cache_set("dsd", xml, TTL_DATASTRUCTURE, id=dataflow_id, agency=agency)
    return xml


async def get_codelist(agency: str, codelist_id: str) -> str:
    """Fetch a specific codelist (cached 6 h)."""
    cached = cache_get("codelist", agency=agency, id=codelist_id)
    if cached:
        return cached
    url = f"{BASE_URL}/codelist/{agency}/{codelist_id}/latest"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        xml = resp.text
    cache_set("codelist", xml, TTL_DATASTRUCTURE, agency=agency, id=codelist_id)
    return xml


async def get_data(
    dataflow_id: str,
    key: str = "all",
    start_period: Optional[str] = None,
    end_period: Optional[str] = None,
    agency: str = "STATSNZ",
) -> str:
    """
    Fetch data observations from a dataflow (cached 1 h).

    key: SDMX key string, e.g. "M.NZ...." or "all"
    """
    cached = cache_get("obs", id=dataflow_id, key=key, start=start_period, end=end_period)
    if cached:
        return cached
    url = f"{BASE_URL}/data/{agency},{dataflow_id}/key/{key}"
    params: dict = {}
    if start_period:
        params["startPeriod"] = start_period
    if end_period:
        params["endPeriod"] = end_period

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        xml = resp.text
    cache_set("obs", xml, TTL_OBSERVATIONS, id=dataflow_id, key=key, start=start_period, end=end_period)
    return xml
