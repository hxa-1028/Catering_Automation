from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from catering_agent.agent.pipeline import PipelineRequest, PipelineResult, run_pipeline
from catering_agent.catalog.ingestion import parse_catalog_manifest
from catering_agent.catalog.resolution import CatalogSnapshot
from catering_agent.domain.models import Proposal, ProposalStatus
from catering_agent.intake.extraction import ExtractionContext
from catering_agent.integrations.local_source import SourceDocument
from catering_agent.proposal.assembly import ProposalAssemblyError, assemble_proposal
from catering_agent.proposal.persistence import (
    ProposalPersistenceError,
    _line_item_records,
    _proposal_record,
    _require_matching_priced_line_items,
    _require_matching_priced_record,
    persist_proposal,
    persist_rendered_proposal,
)

ROOT = Path(__file__).parents[3]
SAMPLE_CATALOG = ROOT / "data" / "samples" / "catalog.json"
GOLDEN_ROOT = ROOT / "evals" / "golden"


@dataclass(frozen=True)
class RecordedProvider:
    extraction_response: Mapping[str, object]
    selection_response: Mapping[str, object]
    provider_name: str = "recorded"
    model_id: str = "structured-eval"

    def extract(self, **_: object) -> Mapping[str, object]:
        return self.extraction_response

    def select_menu(self, **_: object) -> Mapping[str, object]:
        return self.selection_response


def test_assembles_a_reproducible_source_backed_priced_proposal() -> None:
    proposal = assemble_proposal(_priced_result(), "proposal-001", _brief_text())

    assert proposal.status == ProposalStatus.PRICED
    assert proposal.total is not None
    assert proposal.total.amount == 1600
    assert proposal.prompt_version == "extract_brief.v1|select_menu.v1"
    assert [line.line_item_id for line in proposal.line_items] == [
        "sample-lunch-service",
        "sample-venue-fee",
    ]
    assert len(proposal.source_refs) == 5
    assert proposal.catalog_version == "sample-2026-11-22"
    assert proposal.original_brief_text == _brief_text()


def test_only_a_priced_pipeline_result_can_be_assembled() -> None:
    result = _pipeline_result("golden-01-resolved-corporate")

    with pytest.raises(ProposalAssemblyError, match="only a priced"):
        assemble_proposal(result, "proposal-001", _brief_text())


def test_assembly_rejects_source_reference_from_another_catalog_version() -> None:
    result = _priced_result()
    assert result.menu_selection is not None
    stale_source = result.menu_selection.cited_source_refs[0].model_copy(
        update={"catalog_version": "other-catalog"}
    )
    selection = result.menu_selection.model_copy(
        update={
            "cited_source_refs": (
                stale_source,
                *result.menu_selection.cited_source_refs[1:],
            )
        }
    )

    with pytest.raises(ProposalAssemblyError, match="does not match context"):
        assemble_proposal(
            result.model_copy(update={"menu_selection": selection}),
            "p-1",
            _brief_text(),
        )


def test_priced_proposal_rejects_a_total_that_does_not_match_line_items() -> None:
    proposal = assemble_proposal(_priced_result(), "proposal-001", _brief_text())
    payload = proposal.model_dump(mode="json")
    payload["total"] = {"amount": "1.00", "currency": "USD"}

    with pytest.raises(ValidationError, match="total must equal"):
        Proposal.model_validate(payload)


def test_persistence_records_keep_total_sources_and_repeatable_line_skus() -> None:
    proposal = assemble_proposal(_priced_result(), "proposal-001", _brief_text())

    record = _proposal_record(proposal)
    line_records = _line_item_records(proposal)

    assert record.total_amount == proposal.total.amount
    assert record.source_ref_ids == [
        source.source_ref_id for source in proposal.source_refs
    ]
    assert [(line.proposal_id, line.line_item_id) for line in line_records] == [
        ("proposal-001", "sample-lunch-service"),
        ("proposal-001", "sample-venue-fee"),
    ]


def test_persistence_refuses_an_incomplete_proposal_before_database_access() -> None:
    proposal = assemble_proposal(
        _priced_result(), "proposal-001", _brief_text()
    ).model_copy(update={"status": ProposalStatus.DRAFT_REQUESTED})

    with pytest.raises(ProposalPersistenceError, match="only complete priced"):
        persist_proposal(proposal, "postgresql+psycopg://invalid")


def test_persistence_revalidates_a_model_copy_before_database_access() -> None:
    proposal = assemble_proposal(
        _priced_result(), "proposal-001", _brief_text()
    ).model_copy(update={"original_brief_text": ""})

    with pytest.raises(ProposalPersistenceError, match="proposal validation"):
        persist_proposal(proposal, "postgresql+psycopg://invalid")


def test_rendered_persistence_requires_the_exact_stored_priced_snapshot() -> None:
    priced = assemble_proposal(_priced_result(), "proposal-001", _brief_text())
    record = _proposal_record(priced)
    rendered = _rendered(proposal=priced)

    _require_matching_priced_record(record, rendered)

    record.catalog_version = "other-catalog"
    with pytest.raises(ProposalPersistenceError, match="does not match"):
        _require_matching_priced_record(record, rendered)


def test_rendered_persistence_requires_the_exact_stored_priced_line_items() -> None:
    proposal = assemble_proposal(_priced_result(), "proposal-001", _brief_text())
    line_records = _line_item_records(proposal)
    session = _LineItemSession(line_records)

    _require_matching_priced_line_items(session, _rendered(proposal=proposal))

    line_records[0].quantity = line_records[0].quantity + 1
    with pytest.raises(ProposalPersistenceError, match="does not match"):
        _require_matching_priced_line_items(session, _rendered(proposal=proposal))


def test_rendered_persistence_refuses_incomplete_artifacts_before_database_access() -> (
    None
):
    rendered = _rendered(
        proposal=assemble_proposal(_priced_result(), "p-1", _brief_text())
    )
    invalid = rendered.model_copy(update={"pdf_path": None})

    with pytest.raises(ProposalPersistenceError, match="proposal validation"):
        persist_rendered_proposal(invalid, "postgresql+psycopg://invalid")


def _priced_result() -> PipelineResult:
    return _pipeline_result("golden-06-preferred-menu-selection")


def _brief_text() -> str:
    return (GOLDEN_ROOT / "golden-06-preferred-menu-selection" / "brief.txt").read_text(
        encoding="utf-8"
    )


def _rendered(proposal: Proposal) -> Proposal:
    payload = proposal.model_dump(mode="json")
    payload.update(
        {
            "status": ProposalStatus.RENDERED,
            "docx_path": "/data/docstore/proposal/proposal.docx",
            "pdf_path": "/data/docstore/proposal/proposal.pdf",
        }
    )
    return Proposal.model_validate(payload)


class _LineItemSession:
    def __init__(self, line_items: list[object]) -> None:
        self.line_items = line_items

    def scalars(self, _: object) -> list[object]:
        return self.line_items


def _pipeline_result(case_name: str) -> PipelineResult:
    case_root = GOLDEN_ROOT / case_name
    context_payload = _load_json(case_root / "context.json")
    reference_date = date.fromisoformat(str(context_payload.pop("reference_date")))
    request = PipelineRequest(
        brief_text=(case_root / "brief.txt").read_text(encoding="utf-8"),
        context=ExtractionContext.model_validate(context_payload),
        reference_date=reference_date,
    )
    return run_pipeline(
        RecordedProvider(
            _load_json(case_root / "extraction.json"),
            _load_json(case_root / "selection.json")
            if (case_root / "selection.json").is_file()
            else {},
        ),
        _snapshot(),
        request,
    )


def _snapshot() -> CatalogSnapshot:
    content = SAMPLE_CATALOG.read_bytes()
    return CatalogSnapshot.from_bundle(
        parse_catalog_manifest(
            SourceDocument(
                provider="local_filesystem",
                provider_source_id="catalog.json",
                content_hash=sha256(content).hexdigest(),
                content=content,
            )
        )
    )


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value
