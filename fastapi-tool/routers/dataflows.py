"""
/search-dataflows  — find which of the 914 datasets to query
/get-dimensions    — get valid filter codes for a dataset
"""
from fastapi import APIRouter, HTTPException
from models.requests import SearchDataflowsRequest, GetDimensionsRequest
from models.responses import (
    SearchDataflowsResponse, DataflowResult,
    GetDimensionsResponse, DimensionInfo, DimensionCode,
)
from services import dataflow_index
from services.ade_client import get_datastructure, get_codelist
from services.sdmx_parser import parse_dimensions, parse_codelist

router = APIRouter()


@router.post("/search-dataflows", response_model=SearchDataflowsResponse, tags=["Discovery"])
async def search_dataflows(req: SearchDataflowsRequest):
    """
    Search the 914 Stats NZ dataflows by keyword.

    Use this first to discover which dataflow IDs are relevant to the
    user's question before calling /get-data or /compare-periods.

    Example keywords: ["census", "Maori", "housing"] or ["business", "employment"]
    """
    await dataflow_index.ensure_index()
    results = dataflow_index.search(req.keywords, req.limit)

    return SearchDataflowsResponse(
        query_keywords=req.keywords,
        total_found=len(results),
        dataflows=[
            DataflowResult(
                id=df["id"],
                name=df["name"],
                description=df.get("description"),
                agency=df.get("agency", "STATSNZ"),
                version=df.get("version", "1.0"),
            )
            for df in results
        ],
    )


@router.post("/get-dimensions", response_model=GetDimensionsResponse, tags=["Discovery"])
async def get_dimensions(req: GetDimensionsRequest):
    """
    Get the dimensions and valid code values for a specific dataflow.

    Call this after /search-dataflows to find out what filters are available
    (e.g. which geography codes, ethnicity codes, age groups).

    Pass the dimension_id to get codes for just one dimension.
    """
    try:
        xml = await get_datastructure(req.dataflow_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stats NZ API error: {exc}")

    raw_dims = parse_dimensions(xml)
    if not raw_dims:
        raise HTTPException(status_code=404, detail=f"No dimensions found for dataflow '{req.dataflow_id}'")

    # Filter to requested dimension if specified
    if req.dimension_id:
        raw_dims = [d for d in raw_dims if d["id"].upper() == req.dimension_id.upper()]
        if not raw_dims:
            raise HTTPException(status_code=404, detail=f"Dimension '{req.dimension_id}' not found")

    dimensions: list[DimensionInfo] = []
    for dim in raw_dims:
        codes: list[DimensionCode] = []
        if dim.get("codelist_id"):
            try:
                cl_xml = await get_codelist("STATSNZ", dim["codelist_id"])
                raw_codes = parse_codelist(cl_xml)
                codes = [DimensionCode(id=c["id"], name=c["name"]) for c in raw_codes]
            except Exception:
                pass  # Return dim without codes rather than failing entirely

        dimensions.append(DimensionInfo(id=dim["id"], name=dim["name"], codes=codes))

    return GetDimensionsResponse(dataflow_id=req.dataflow_id, dimensions=dimensions)
