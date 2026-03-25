"""
/get-data        — fetch observations from one dataflow
/compare-periods — compare the same metric across multiple census years
"""
from fastapi import APIRouter, HTTPException
from models.requests import GetDataRequest, ComparePeriodsRequest
from models.responses import (
    GetDataResponse, Observation,
    ComparePeriodsResponse, PeriodComparison,
)
from services.ade_client import get_data, get_datastructure
from services.sdmx_parser import parse_observations, parse_dimensions

router = APIRouter()


async def _build_sdmx_key(dataflow_id: str, filters: dict[str, str]) -> str:
    """
    Build a positional SDMX key from dimension filters.

    Stats NZ requires dimension values in the order they are defined in the DSD,
    dot-separated. Empty positions act as wildcards.  Falls back to 'all' if the
    DSD cannot be fetched or no filters are supplied.
    """
    if "__key__" in filters:
        return filters.pop("__key__")
    if not filters:
        return "all"
    try:
        dsd_xml = await get_datastructure(dataflow_id)
        dims = parse_dimensions(dsd_xml)       # ordered list of {id, ...}
        key_parts = [filters.pop(d["id"], "") for d in dims]
        key = ".".join(key_parts)
        return key if key.replace(".", "") else "all"
    except Exception:
        return "all"


@router.post("/get-data", response_model=GetDataResponse, tags=["Data"])
async def get_data_endpoint(req: GetDataRequest):
    """
    Fetch actual observations from a Stats NZ dataflow.

    Provide the dataflow_id from /search-dataflows and optional filters
    (dimension key/value pairs) from /get-dimensions.

    Returns observations with their period labels and dimension values.
    """
    filters = dict(req.filters)
    key = await _build_sdmx_key(req.dataflow_id, filters)

    try:
        xml = await get_data(
            dataflow_id=req.dataflow_id,
            key=key,
            start_period=req.start_period,
            end_period=req.end_period,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stats NZ API error: {exc}")

    raw_obs = parse_observations(xml)

    # Apply any remaining dimension filters client-side
    if filters:
        raw_obs = [
            obs for obs in raw_obs
            if all(
                obs["dimension_values"].get(k, "").lower() == v.lower()
                for k, v in filters.items()
            )
        ]

    observations = [
        Observation(
            period=o["period"],
            value=o["value"],
            dimension_values=o["dimension_values"],
        )
        for o in raw_obs
    ]

    # Build a brief text summary for the LLM
    if observations:
        first, last = observations[0], observations[-1]
        summary = (
            f"Found {len(observations)} observation(s) in '{req.dataflow_id}'. "
            f"Earliest: {first.period} = {first.value}. "
            f"Latest: {last.period} = {last.value}."
        )
    else:
        summary = f"No observations found in '{req.dataflow_id}' for the given filters."

    return GetDataResponse(
        dataflow_id=req.dataflow_id,
        filters_applied=req.filters,
        observation_count=len(observations),
        observations=observations,
        summary=summary,
    )


@router.post("/compare-periods", response_model=ComparePeriodsResponse, tags=["Data"])
async def compare_periods(req: ComparePeriodsRequest):
    """
    Compare the same metric across multiple census years (2013, 2018, 2023).

    Pass a list of dataflow_ids (one per census year) and shared filters.
    The agent will call this to answer trend questions like:
    "How has Māori home ownership changed across the three censuses?"
    """
    if len(req.dataflow_ids) < 2:
        raise HTTPException(status_code=422, detail="Provide at least 2 dataflow_ids to compare")

    comparisons: list[PeriodComparison] = []
    previous_value: float | None = None

    for dataflow_id in req.dataflow_ids:
        filters = dict(req.filters)
        key = await _build_sdmx_key(dataflow_id, filters)

        try:
            xml = await get_data(dataflow_id=dataflow_id, key=key)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Stats NZ API error for '{dataflow_id}': {exc}")

        raw_obs = parse_observations(xml)

        # Apply filters
        if filters:
            raw_obs = [
                obs for obs in raw_obs
                if all(
                    obs["dimension_values"].get(k, "").lower() == v.lower()
                    for k, v in filters.items()
                )
            ]

        # Aggregate: sum all matching observations for this dataflow
        total = sum(o["value"] for o in raw_obs if isinstance(o["value"], (int, float)))
        period = raw_obs[0]["period"].split("-")[0] if raw_obs else dataflow_id  # use year

        change_str: str | None = None
        if previous_value is not None and previous_value != 0:
            pct = (total - previous_value) / previous_value * 100
            direction = "increase" if pct >= 0 else "decrease"
            change_str = f"{abs(pct):.1f}% {direction} from previous period"

        comparisons.append(PeriodComparison(
            dataflow_id=dataflow_id,
            period=period,
            value=total,
            change_from_previous=change_str,
        ))
        previous_value = total

    # Plain-English trend summary for the LLM
    if len(comparisons) >= 2:
        start, end = comparisons[0], comparisons[-1]
        if isinstance(start.value, (int, float)) and isinstance(end.value, (int, float)) and start.value != 0:
            overall_pct = (end.value - start.value) / start.value * 100
            direction = "increased" if overall_pct >= 0 else "decreased"
            trend_summary = (
                f"{req.metric_label} {direction} by {abs(overall_pct):.1f}% "
                f"from {start.period} ({start.value:,}) to {end.period} ({end.value:,})."
            )
        else:
            trend_summary = f"Comparison complete for {req.metric_label} across {len(comparisons)} periods."
    else:
        trend_summary = "Insufficient data for trend analysis."

    return ComparePeriodsResponse(
        metric_label=req.metric_label,
        filters_applied=req.filters,
        comparisons=comparisons,
        trend_summary=trend_summary,
    )
