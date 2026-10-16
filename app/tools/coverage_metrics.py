"""Shared coverage checks for PRD feature to technical design mapping."""

from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any


def score_prd_tech_coverage(
    prd: dict[str, Any] | None,
    design: dict[str, Any] | None,
) -> float:
    """Estimate whether technical design covers PRD feature modules."""
    prd = prd or {}
    design = design or {}
    features = collect_feature_terms(prd)
    if not features:
        return 0.0

    design_text = normalize_text(json.dumps(design, ensure_ascii=False))
    covered = 0
    for feature in features:
        if terms_match(feature["terms"], design_text):
            covered += 1
    return covered / len(features)


def score_api_feature_coverage(
    prd: dict[str, Any] | None,
    design: dict[str, Any] | None,
) -> float:
    """Estimate whether PRD feature modules are represented in API design."""
    api_endpoints = (design or {}).get("api_endpoints") or []
    api_text = normalize_text(json.dumps(api_endpoints, ensure_ascii=False))
    return score_feature_coverage(prd, api_text)


def score_db_feature_coverage(
    prd: dict[str, Any] | None,
    design: dict[str, Any] | None,
) -> float:
    """Estimate whether PRD feature modules are represented in DB schema."""
    db_schema = (design or {}).get("db_schema") or {}
    db_text = normalize_text(json.dumps(db_schema, ensure_ascii=False))
    return score_feature_coverage(prd, db_text)


def missing_feature_mappings(
    prd: dict[str, Any] | None,
    design: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """Return feature module names missing API and/or DB representation."""
    features = collect_feature_terms(prd or {})
    api_text = normalize_text(json.dumps((design or {}).get("api_endpoints") or [], ensure_ascii=False))
    db_text = normalize_text(json.dumps((design or {}).get("db_schema") or {}, ensure_ascii=False))

    missing_api = []
    missing_db = []
    for feature in features:
        if not terms_match(feature["terms"], api_text):
            missing_api.append(feature["name"])
        if not terms_match(feature["terms"], db_text):
            missing_db.append(feature["name"])
    return {"api": missing_api, "db": missing_db}


def repair_feature_mappings(
    prd: dict[str, Any] | None,
    design: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Append explicit API/DB mappings for PRD features missing traceability."""
    repaired = deepcopy(design or {})
    repaired.setdefault("api_endpoints", [])
    repaired.setdefault("db_schema", {})
    repaired["db_schema"].setdefault("database_type", "PostgreSQL")
    repaired["db_schema"].setdefault("tables", [])
    repaired["db_schema"].setdefault("relationships", [])

    missing = missing_feature_mappings(prd, repaired)
    features_by_name = {item["name"]: item for item in collect_feature_terms(prd or {})}
    added = {"api": [], "db": []}

    for feature_name in missing["api"]:
        feature = features_by_name.get(feature_name) or {"name": feature_name, "terms": [feature_name]}
        repaired["api_endpoints"].append(
            _make_feature_api(feature, len(repaired["api_endpoints"]) + 1)
        )
        added["api"].append(feature_name)

    for feature_name in missing["db"]:
        feature = features_by_name.get(feature_name) or {"name": feature_name, "terms": [feature_name]}
        repaired["db_schema"]["tables"].append(
            _make_feature_table(feature, len(repaired["db_schema"]["tables"]) + 1)
        )
        added["db"].append(feature_name)

    return repaired, added


def score_feature_coverage(prd: dict[str, Any] | None, target_text: str) -> float:
    features = collect_feature_terms(prd or {})
    if not features:
        return 0.0
    covered = 0
    for feature in features:
        if terms_match(feature["terms"], target_text):
            covered += 1
    return covered / len(features)


def collect_feature_terms(prd: dict[str, Any]) -> list[dict[str, Any]]:
    features = []
    for index, module in enumerate(prd.get("feature_modules") or [], start=1):
        if not isinstance(module, dict):
            continue
        name = str(module.get("name") or f"feature_{index}").strip()
        terms = []
        if module.get("name"):
            terms.append(str(module["name"]))
        if module.get("description"):
            terms.append(str(module["description"]))
        terms.extend(str(item) for item in module.get("sub_features") or [] if item)
        compact_terms = [term for term in terms if normalize_text(term)]
        if compact_terms:
            features.append({"name": name, "terms": compact_terms})
    return features


def terms_match(terms: list[str], text: str) -> bool:
    return any(term_appears(term, text) for term in terms)


def term_appears(term: str, text: str) -> bool:
    normalized = normalize_text(term)
    if not normalized:
        return False
    if normalized in text:
        return True
    tokens = [token for token in re.split(r"\s+", normalized) if len(token) >= 3]
    return bool(tokens) and any(token in text for token in tokens)


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[_\-_/|:;,.!?()\[\]{}\"']", " ", value)
    value = re.sub(r"[，。！？、；：）（【】《》“”‘’]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _make_feature_api(feature: dict[str, Any], index: int) -> dict[str, Any]:
    feature_name = str(feature.get("name") or f"feature_{index}")
    feature_terms = _feature_term_text(feature)
    slug = _slugify(feature_name, index)
    return {
        "method": "POST",
        "path": f"/feature-modules/{slug}/actions",
        "description": (
            f"Covers PRD feature module: {feature_name}. "
            f"Supports workflow operations for {feature_terms}."
        ),
        "request_body": f"{feature_name} request payload and actor context.",
        "response_body": f"{feature_name} operation result.",
        "auth_required": True,
        "related_features": [feature_name],
    }


def _make_feature_table(feature: dict[str, Any], index: int) -> dict[str, Any]:
    feature_name = str(feature.get("name") or f"feature_{index}")
    feature_terms = _feature_term_text(feature)
    slug = _slugify(feature_name, index).replace("-", "_")
    return {
        "table_name": f"feature_{slug}_records",
        "description": (
            f"Persists PRD feature module: {feature_name}. "
            f"Stores workflow data and audit state for {feature_terms}."
        ),
        "columns": [
            {
                "name": "id",
                "type": "uuid",
                "nullable": False,
                "description": f"Primary key for {feature_name} records.",
            },
            {
                "name": "feature_payload",
                "type": "jsonb",
                "nullable": False,
                "description": f"Business payload for {feature_name}.",
            },
            {
                "name": "status",
                "type": "varchar(32)",
                "nullable": False,
                "description": f"Processing status for {feature_name}.",
            },
            {
                "name": "created_at",
                "type": "timestamp",
                "nullable": False,
                "description": f"Creation time for {feature_name}.",
            },
        ],
        "indexes": [f"idx_feature_{slug}_status", f"idx_feature_{slug}_created_at"],
        "related_features": [feature_name],
    }


def _feature_term_text(feature: dict[str, Any]) -> str:
    terms = [str(term) for term in feature.get("terms") or [] if str(term).strip()]
    return ", ".join(terms[:4]) or str(feature.get("name") or "this feature")


def _slugify(value: str, index: int) -> str:
    slug = normalize_text(value)
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", slug).strip("-")
    return slug[:48] or f"feature-{index:02d}"
