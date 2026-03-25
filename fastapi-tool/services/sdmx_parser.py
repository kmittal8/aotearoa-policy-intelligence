"""
SDMX XML → Python dict parser.

Stats NZ returns SDMX 2.1 XML. This module flattens the nested structure
into clean Python dicts that the routers can serialise to JSON.
"""
import xmltodict
from typing import Any


def _force_list(val: Any) -> list:
    """xmltodict returns a dict for single items; always return a list."""
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def parse_dataflows(xml: str) -> list[dict]:
    """
    Parse SDMX Structure message containing Dataflow elements.
    Returns list of {id, name, description, agency, version}.
    """
    doc = xmltodict.parse(xml)
    # Navigate SDMX envelope: Structure > Structures > Dataflows > Dataflow
    # Stats NZ uses message:/structure:/common: namespace prefixes
    try:
        structures = doc["message:Structure"]["message:Structures"]
        dataflows_raw = structures["structure:Dataflows"]["structure:Dataflow"]
    except (KeyError, TypeError):
        return []

    results = []
    for df in _force_list(dataflows_raw):
        attrs = df.get("@id", ""), df.get("@agencyID", "STATSNZ"), df.get("@version", "1.0")
        # Name is {"@xml:lang": "en", "#text": "..."}
        name_raw = df.get("common:Name", "")
        name = name_raw if isinstance(name_raw, str) else name_raw.get("#text", "")
        desc_raw = df.get("common:Description", "")
        desc = desc_raw if isinstance(desc_raw, str) else desc_raw.get("#text", "") if desc_raw else None

        results.append({
            "id": attrs[0],
            "agency": attrs[1],
            "version": attrs[2],
            "name": name,
            "description": desc,
        })
    return results


def parse_dimensions(xml: str) -> list[dict]:
    """
    Parse a DataStructureDefinition message.
    Returns list of {id, name, codes: [{id, name}]}.
    """
    doc = xmltodict.parse(xml)
    try:
        structures = doc["message:Structure"]["message:Structures"]
        dsd = structures["structure:DataStructures"]["structure:DataStructure"]
        components = dsd["structure:DataStructureComponents"]
        dim_list = components["structure:DimensionList"]["structure:Dimension"]
    except (KeyError, TypeError):
        return []

    dimensions = []
    for dim in _force_list(dim_list):
        dim_id = dim.get("@id", "")
        # Concept reference gives the human name
        concept_ref = dim.get("structure:ConceptIdentity", {}).get("Ref", {})
        dim_name = concept_ref.get("@id", dim_id)

        # Local representation gives the codelist
        local_rep = dim.get("structure:LocalRepresentation", {})
        enum_ref = local_rep.get("structure:Enumeration", {}).get("Ref", {})
        codelist_id = enum_ref.get("@id", "")

        dimensions.append({
            "id": dim_id,
            "name": dim_name,
            "codelist_id": codelist_id,
            "codes": [],  # populated separately via parse_codelist
        })
    return dimensions


def parse_codelist(xml: str) -> list[dict]:
    """
    Parse a Codelist message.
    Returns list of {id, name}.
    """
    doc = xmltodict.parse(xml)
    try:
        structures = doc["message:Structure"]["message:Structures"]
        codelist = structures["structure:Codelists"]["structure:Codelist"]
        codes_raw = codelist["structure:Code"]
    except (KeyError, TypeError):
        return []

    codes = []
    for code in _force_list(codes_raw):
        code_id = code.get("@id", "")
        name_raw = code.get("common:Name", code_id)
        name = name_raw if isinstance(name_raw, str) else name_raw.get("#text", code_id)
        codes.append({"id": code_id, "name": name})
    return codes


def parse_observations(xml: str) -> list[dict]:
    """
    Parse a GenericData SDMX message (flat obs format used by Stats NZ).
    Returns list of {period, value, dimension_values: dict}.
    """
    doc = xmltodict.parse(xml)

    try:
        dataset = doc["message:GenericData"]["message:DataSet"]
    except (KeyError, TypeError):
        return []

    # Stats NZ returns flat observations (not series-grouped)
    obs_list = _force_list(dataset.get("generic:Obs", []))

    observations = []
    for obs in obs_list:
        # All dimension values including time are in ObsKey
        key_values = _force_list(
            obs.get("generic:ObsKey", {}).get("generic:Value", [])
        )
        dim_vals: dict[str, str] = {}
        period = ""
        for kv in key_values:
            k, v = kv.get("@id", ""), kv.get("@value", "")
            dim_vals[k] = v
            # Heuristic: the time/period dimension typically contains YEAR or TIME
            if not period and any(t in k.upper() for t in ("YEAR", "TIME", "PERIOD")):
                period = v

        value_raw = obs.get("generic:ObsValue", {}).get("@value", None)
        try:
            value = float(value_raw) if value_raw is not None else None
            if value is not None and value == int(value):
                value = int(value)
        except (ValueError, TypeError):
            value = value_raw

        observations.append({
            "period": period,
            "value": value,
            "dimension_values": dim_vals,
        })

    return observations
