from pydantic import BaseModel
from typing import Any, Optional


class DataflowResult(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    agency: str
    version: str


class SearchDataflowsResponse(BaseModel):
    query_keywords: list[str]
    total_found: int
    dataflows: list[DataflowResult]


class DimensionCode(BaseModel):
    id: str
    name: str


class DimensionInfo(BaseModel):
    id: str
    name: str
    codes: list[DimensionCode]


class GetDimensionsResponse(BaseModel):
    dataflow_id: str
    dimensions: list[DimensionInfo]


class Observation(BaseModel):
    period: str
    value: Any
    dimension_values: dict[str, str]


class GetDataResponse(BaseModel):
    dataflow_id: str
    filters_applied: dict[str, str]
    observation_count: int
    observations: list[Observation]
    summary: str


class PeriodComparison(BaseModel):
    dataflow_id: str
    period: str
    value: Any
    change_from_previous: Optional[str] = None


class ComparePeriodsResponse(BaseModel):
    metric_label: str
    filters_applied: dict[str, str]
    comparisons: list[PeriodComparison]
    trend_summary: str
