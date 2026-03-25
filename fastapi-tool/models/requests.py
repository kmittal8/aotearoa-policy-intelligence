from pydantic import BaseModel, Field
from typing import Optional


class SearchDataflowsRequest(BaseModel):
    keywords: list[str] = Field(..., description="Keywords to search for in dataflow names/descriptions")
    limit: int = Field(10, ge=1, le=50, description="Max number of results to return")


class GetDimensionsRequest(BaseModel):
    dataflow_id: str = Field(..., description="Stats NZ dataflow ID, e.g. 'NZ_CENSUS_2023'")
    dimension_id: Optional[str] = Field(None, description="Specific dimension to get codes for, e.g. 'GEOGRAPHY'")


class GetDataRequest(BaseModel):
    dataflow_id: str = Field(..., description="Stats NZ dataflow ID")
    filters: dict[str, str] = Field(
        default_factory=dict,
        description="Dimension filters as key/value pairs, e.g. {'GEOGRAPHY': 'Auckland', 'ETHNICITY': 'Maori'}"
    )
    start_period: Optional[str] = Field(None, description="Start period, e.g. '2023'")
    end_period: Optional[str] = Field(None, description="End period, e.g. '2023'")


class ComparePeriodsRequest(BaseModel):
    dataflow_ids: list[str] = Field(..., description="List of dataflow IDs to compare (one per time period)")
    filters: dict[str, str] = Field(
        default_factory=dict,
        description="Shared dimension filters applied to all dataflows"
    )
    metric_label: str = Field(..., description="Human-readable label for what is being compared, e.g. 'Māori home ownership rate'")
