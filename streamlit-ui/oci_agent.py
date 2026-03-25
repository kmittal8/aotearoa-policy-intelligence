"""
Anthropic Claude inference wrapper with function-calling loop.
Talks directly to Claude via the Anthropic API.
Tools are executed against the FastAPI service running on localhost:8000.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import urllib3
urllib3.disable_warnings()
import requests
import anthropic

# ── Config (read lazily so load_dotenv() in app.py runs first) ─────────────
def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

MODEL_ID = "claude-haiku-4-5"
MAX_ROUNDS = 15

_SYSTEM = (
    "You are the Aotearoa Policy Intelligence assistant with live access to Stats NZ data.\n\n"
    "TOOLS: search_dataflows, get_dimensions, get_data, compare_periods.\n\n"
    "SPEED RULES:\n"
    "1. Call tools immediately — never describe what you will do first.\n"
    "2. Call search_dataflows ONCE per question. Never repeat the same search.\n"
    "3. If you already know the dataflow ID and dimension codes (see below), skip "
    "search_dataflows and get_dimensions — call get_data directly.\n"
    "4. You may call MULTIPLE tools in a single round when they are independent.\n"
    "5. Answer with specific numbers as soon as you have data.\n\n"
    "KNOWN DATAFLOWS (use these directly — no search needed):\n"
    "- Population by census year and region: dataflow=CEN23_POP_006 "
    "dims: CEN23_YEAR_001 (2013/2018/2023), CEN23_GEO_002 (02=Auckland, 09=Wellington, 9999=NZ total), "
    "CEN23_ETH_002 (999=Total, 1=European, 2=Māori, 3=Pacific), "
    "CEN23_AGE_001 (99=Total), CEN23_SAB_002 (999=Total, 11=Male, 22=Female)\n"
    "- Total personal income by ethnicity/age (2013/2018/2023): dataflow=CEN23_ECI_014 "
    "dims: CEN23_YEAR_001 (2013/2018/2023), CEN23_GEO_008 (9999=NZ total, 02=Auckland Region, 09=Wellington Region), "
    "CEN23_TOI_002 (999=Total, Median=Median income, 13=$1-$10k, 21=$40,001-$50k, 777=Total stated), "
    "CEN23_ETH_003 (9999=Total, 1=European, 2=Māori, 3=Pacific Peoples, 4=Asian), "
    "CEN23_AGE_008 (99=Total, 2=15-29 years, 3=30-64 years, 4=65+ years)\n"
    "- Sources of personal income by ethnicity/gender/age (2013/2018/2023): dataflow=CEN23_ECI_013 "
    "dims: CEN23_YEAR_001 (2013/2018/2023), CEN23_GEO_008 (9999=NZ total, 02=Auckland Region, 09=Wellington Region), "
    "CEN23_SOI_002 (999=Total, 01=Wages/salary, 02=Self-employment, 07=Jobseeker Support, 08=Sole Parent Support, 09=Supported Living), "
    "CEN23_ETH_003 (9999=Total, 1=European, 2=Māori, 3=Pacific Peoples, 4=Asian), "
    "CEN23_AGE_008 (99=Total, 2=15-29 years, 3=30-64 years, 4=65+ years), "
    "CEN23_GEN_002 (99=Total, 1=Male/Tāne, 2=Female/Wahine, 3=Another gender)\n"
    "- Median personal income by ethnicity/sex/area (2013+2018 only): dataflow=CEN18_WRK_015 "
    "dims: YEAR_CEN18_WRK_015, AREA_CEN18_WRK_015 (09=Wellington Region, 02=Auckland Region), "
    "ETHNIC_CEN18_WRK_015 (2=Maori, 1=European), SEX_CEN18_WRK_015 (2=Female, 1=Male), "
    "INCOME_CEN18_WRK_015 (888=Median income), AGE_CEN18_WRK_015 (2=15-29yrs, 3=30-64yrs, 999999=Total)\n"
    "- Home ownership/tenure by ethnicity (2013/2018/2023): dataflow=CEN23_FHH_020 "
    "dims: CEN23_YEAR_001 (2013/2018/2023), CEN23_GEO_002 (02=Auckland, 9999=NZ total), "
    "CEN23_ETH_002 (1=European, 2=Māori, 999=Total), "
    "CEN23_THD_001 (001=Owned, 002=Not owned, 9999=Total), CEN23_AGE_004 (99=Total)\n"
    "- Enterprises by industry: dataflow=BDS_BDS_004 "
    "dims: ANZSIC06_BDS_BDS_004 (A=Agriculture, C=Manufacturing, G=Retail, TOTAL=All), "
    "YEAR_BDS_BDS_004 (2000-2025), MEASURE_BDS_BDS_004 (ENT_COUNT=Enterprises)\n"
)

# ── Tool definitions ───────────────────────────────────────────────────────
_TOOLS = [
    {
        "name": "search_dataflows",
        "description": (
            "Search the 914 Stats NZ dataflows by keyword to find relevant dataset IDs. "
            "Pass space-separated keywords. Use this first before get_data or compare_periods."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "Space-separated keywords, e.g. 'agricultural businesses sector'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 10)",
                },
            },
            "required": ["keywords"],
        },
    },
    {
        "name": "get_dimensions",
        "description": (
            "Get available dimensions and valid filter codes for a Stats NZ dataflow. "
            "Call after search_dataflows to understand what filter values exist before get_data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataflow_id": {
                    "type": "string",
                    "description": "Stats NZ dataflow ID from search_dataflows, e.g. 'BD_ENT_UR'",
                },
                "dimension_id": {
                    "type": "string",
                    "description": "Specific dimension to inspect, e.g. 'INDUSTRY'. Omit to get all.",
                },
            },
            "required": ["dataflow_id"],
        },
    },
    {
        "name": "get_data",
        "description": (
            "Fetch actual observations from a Stats NZ dataflow. "
            "Use filters from get_dimensions to narrow results. "
            "Use start_period/end_period to restrict to specific years."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataflow_id": {
                    "type": "string",
                    "description": "Stats NZ dataflow ID",
                },
                "filters": {
                    "type": "string",
                    "description": (
                        'Dimension filters as JSON object, e.g. {"GEOGRAPHY": "AUK", "SEX": "1"}. '
                        "Values must be valid codes from get_dimensions."
                    ),
                },
                "start_period": {
                    "type": "string",
                    "description": "Start year, e.g. '2022'",
                },
                "end_period": {
                    "type": "string",
                    "description": "End year, e.g. '2022'",
                },
            },
            "required": ["dataflow_id"],
        },
    },
    {
        "name": "compare_periods",
        "description": (
            "Compare a metric across multiple census years by providing one dataflow ID per year. "
            "Use for trend questions like 'How has X changed across the three censuses?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataflow_ids": {
                    "type": "string",
                    "description": (
                        'JSON array of dataflow IDs, one per time period, '
                        'e.g. ["CEN_DP_2013_GEOG", "CEN_DP_2018_GEOG", "CEN_DP_2023_GEOG"]'
                    ),
                },
                "metric_label": {
                    "type": "string",
                    "description": "Human-readable label for what is compared, e.g. 'Auckland population'",
                },
                "filters": {
                    "type": "string",
                    "description": 'Shared dimension filters as JSON object, e.g. {"GEOGRAPHY": "AUK"}',
                },
            },
            "required": ["dataflow_ids", "metric_label"],
        },
    },
]


# ── Tool execution ─────────────────────────────────────────────────────────
def _execute_tool(name: str, parameters: dict) -> str:
    """Map model parameters to FastAPI request schema and call the endpoint."""
    base_url = _cfg("FASTAPI_BASE_URL", "https://localhost:8000")
    endpoints = {
        "search_dataflows": "/search-dataflows",
        "get_dimensions": "/get-dimensions",
        "get_data": "/get-data",
        "compare_periods": "/compare-periods",
    }
    endpoint = endpoints.get(name)
    if not endpoint:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        payload = _build_payload(name, parameters)
        resp = requests.post(
            f"{base_url}{endpoint}",
            json=payload,
            timeout=30,
            verify=False,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())
    except requests.exceptions.RequestException as exc:
        return json.dumps({"error": str(exc)})


def _build_payload(name: str, params: dict) -> dict:
    """Convert model-supplied parameters to the FastAPI request body schema."""
    def parse_json(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return v
        return v

    if name == "search_dataflows":
        keywords_raw = params.get("keywords", "")
        keywords = keywords_raw.split() if isinstance(keywords_raw, str) else keywords_raw
        payload = {"keywords": keywords}
        if "limit" in params:
            payload["limit"] = int(params["limit"])
        return payload

    if name == "get_dimensions":
        payload = {"dataflow_id": params["dataflow_id"]}
        if params.get("dimension_id"):
            payload["dimension_id"] = params["dimension_id"]
        return payload

    if name == "get_data":
        payload = {"dataflow_id": params["dataflow_id"]}
        if params.get("filters"):
            payload["filters"] = parse_json(params["filters"])
        if params.get("start_period"):
            payload["start_period"] = params["start_period"]
        if params.get("end_period"):
            payload["end_period"] = params["end_period"]
        return payload

    if name == "compare_periods":
        payload = {
            "dataflow_ids": parse_json(params.get("dataflow_ids", "[]")),
            "metric_label": params.get("metric_label", ""),
        }
        if params.get("filters"):
            payload["filters"] = parse_json(params["filters"])
        return payload

    return {k: parse_json(v) for k, v in params.items()}


# ── Anthropic client ───────────────────────────────────────────────────────
def _get_client(api_key: Optional[str] = None) -> anthropic.Anthropic:
    key = api_key or _cfg("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "No Anthropic API key found. "
            "Set ANTHROPIC_API_KEY in your environment or enter it in the sidebar."
        )
    return anthropic.Anthropic(api_key=key)


# ── Public API ─────────────────────────────────────────────────────────────
def chat(history: list, user_message: str, api_key: Optional[str] = None) -> tuple[str, list]:
    """
    Send a user message, run the function-calling loop, and return
    (answer_text, updated_history).

    history: list of completed prior turns as Anthropic message dicts.
    api_key: Anthropic API key (overrides ANTHROPIC_API_KEY env var if provided).
    """
    client = _get_client(api_key)
    # Keep only the last 6 messages (3 turns) to avoid 413 request_too_large.
    # Stats NZ tool responses can be large JSON; they balloon the history quickly.
    messages = list(history[-6:])
    messages.append({"role": "user", "content": user_message})

    for _ in range(MAX_ROUNDS):
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=4096,
            system=_SYSTEM,
            tools=_TOOLS,
            messages=messages,
        )

        # Append assistant response to history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            answer = next(
                (block.text for block in response.content if block.type == "text"),
                "(No response text)",
            )
            return answer, messages

        if response.stop_reason != "tool_use":
            answer = next(
                (block.text for block in response.content if block.type == "text"),
                f"(Unexpected stop reason: {response.stop_reason})",
            )
            return answer, messages

        # Extract tool_use blocks and execute in parallel
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        tool_results = [None] * len(tool_use_blocks)

        with ThreadPoolExecutor(max_workers=len(tool_use_blocks)) as pool:
            futures = {
                pool.submit(_execute_tool, tb.name, tb.input or {}): i
                for i, tb in enumerate(tool_use_blocks)
            }
            for future in as_completed(futures):
                i = futures[future]
                result_str = future.result()
                tool_results[i] = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_blocks[i].id,
                    "content": result_str,
                }

        messages.append({"role": "user", "content": tool_results})

    return "(Max tool-call rounds reached without a final answer.)", messages
