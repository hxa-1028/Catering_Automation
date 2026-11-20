"""Run deterministic golden evaluations without a live LLM call."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path

from catering_agent.agent.pipeline import PipelineRequest, PipelineResult, run_pipeline
from catering_agent.catalog.ingestion import parse_catalog_manifest
from catering_agent.catalog.resolution import CatalogSnapshot
from catering_agent.intake.extraction import ExtractionContext
from catering_agent.integrations.local_source import SourceDocument

ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = ROOT / "evals" / "golden"
SAMPLE_CATALOG = ROOT / "data" / "samples" / "catalog.json"


class EvaluationFailure(AssertionError):
    """Raised when a golden result differs from its approved expectation."""


@dataclass(frozen=True)
class RecordedBriefProvider:
    """Return a scrubbed, recorded extraction instead of calling an LLM."""

    response: Mapping[str, object]
    provider_name: str = "recorded"
    model_id: str = "structured-eval"

    def extract(self, **_: object) -> Mapping[str, object]:
        return self.response


def run_golden_suite(case_root: Path = GOLDEN_ROOT) -> tuple[str, ...]:
    """Run every sanitized golden case against the prototype catalog."""

    snapshot = _sample_snapshot()
    failures: list[str] = []
    passed: list[str] = []
    for case_path in sorted(path for path in case_root.iterdir() if path.is_dir()):
        try:
            _run_case(case_path, snapshot)
        except EvaluationFailure as error:
            failures.append(f"{case_path.name}: {error}")
        else:
            passed.append(case_path.name)
    if failures:
        raise EvaluationFailure("\n".join(failures))
    return tuple(passed)


def main(argv: list[str] | None = None) -> int:
    """Run the supported offline evaluation suite."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("golden",), required=True)
    parser.add_argument("--mode", choices=("structured",), default="structured")
    parser.parse_args(argv)
    try:
        passed = run_golden_suite()
    except EvaluationFailure as error:
        print(error)
        return 1
    print(f"golden: {len(passed)} passed")
    return 0


def _run_case(case_path: Path, snapshot: CatalogSnapshot) -> None:
    context_payload = _load_json(case_path / "context.json")
    reference_date = date.fromisoformat(str(context_payload.pop("reference_date")))
    request = PipelineRequest(
        brief_text=(case_path / "brief.txt").read_text(encoding="utf-8"),
        context=ExtractionContext.model_validate(context_payload),
        reference_date=reference_date,
    )
    result = run_pipeline(
        RecordedBriefProvider(_load_json(case_path / "extraction.json")),
        snapshot,
        request,
    )
    expected = _load_json(case_path / "expected.json")
    actual = _result_projection(result)
    if actual != expected:
        raise EvaluationFailure(f"expected {expected}, got {actual}")
    _assert_source_backed(result)


def _result_projection(result: PipelineResult) -> dict[str, object]:
    catalog = result.catalog_resolution
    return {
        "status": result.status,
        "needs_input": [item.model_dump() for item in result.needs_input],
        "catalog_version": catalog.catalog_version if catalog is not None else None,
        "venue_id": result.brief.venue_id,
        "eligible_menu_ids": [menu.menu_id for menu in catalog.eligible_menus]
        if catalog is not None
        else [],
    }


def _assert_source_backed(result: PipelineResult) -> None:
    if result.status != "SOURCES_RESOLVED":
        return
    catalog = result.catalog_resolution
    if catalog is None or catalog.venue is None or not catalog.eligible_menus:
        raise EvaluationFailure("resolved result is missing catalog records")
    if not catalog.venue.source_ref.source_ref_id or any(
        not menu.source_ref.source_ref_id for menu in catalog.eligible_menus
    ):
        raise EvaluationFailure("resolved catalog record is missing source provenance")


def _sample_snapshot() -> CatalogSnapshot:
    content = SAMPLE_CATALOG.read_bytes()
    bundle = parse_catalog_manifest(
        SourceDocument(
            provider="local_filesystem",
            provider_source_id="catalog.json",
            content_hash=sha256(content).hexdigest(),
            content=content,
        )
    )
    return CatalogSnapshot.from_bundle(bundle)


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationFailure(f"{path} must contain a JSON object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
