from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest

from catering_agent.agent.draft_generation import DraftGenerationError, generate_draft
from catering_agent.agent.pipeline import PipelineRequest, PipelineResult, run_pipeline
from catering_agent.catalog.ingestion import parse_catalog_manifest
from catering_agent.catalog.resolution import CatalogSnapshot
from catering_agent.domain.models import Proposal, ProposalStatus
from catering_agent.intake.extraction import ExtractionContext
from catering_agent.integrations.local_source import SourceDocument
from catering_agent.proposal.persistence import ProposalPersistenceError

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


def test_generates_a_rendered_draft_in_the_required_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def persist_priced(proposal: Proposal, _: str) -> Proposal:
        calls.append(f"priced:{proposal.status}")
        return proposal

    def render(
        proposal: Proposal,
        _: object,
        __: Path,
        docstore_directory: Path,
        ___: str,
    ) -> Proposal:
        calls.append("render")
        artifact_directory = docstore_directory / proposal.proposal_id
        artifact_directory.mkdir(parents=True)
        docx_path = artifact_directory / "proposal.docx"
        pdf_path = artifact_directory / "proposal.pdf"
        docx_path.write_bytes(b"docx")
        pdf_path.write_bytes(b"%PDF-")
        payload = proposal.model_dump(mode="json")
        payload.update(
            {
                "status": ProposalStatus.RENDERED,
                "docx_path": str(docx_path),
                "pdf_path": str(pdf_path),
            }
        )
        return Proposal.model_validate(payload)

    def persist_rendered(proposal: Proposal, _: str) -> Proposal:
        calls.append(f"rendered:{proposal.status}")
        return proposal

    monkeypatch.setattr(
        "catering_agent.agent.draft_generation.persist_proposal", persist_priced
    )
    monkeypatch.setattr("catering_agent.agent.draft_generation.render_proposal", render)
    monkeypatch.setattr(
        "catering_agent.agent.draft_generation.persist_rendered_proposal",
        persist_rendered,
    )

    result = generate_draft(
        _provider("golden-06-preferred-menu-selection"),
        _snapshot(),
        _request("golden-06-preferred-menu-selection"),
        "proposal-001",
        "postgresql+psycopg://unused",
        ROOT / "data" / "samples" / "templates",
        tmp_path / "docstore",
        "http://docconv:3000",
    )

    assert result.pipeline_result.status == "PRICED"
    assert result.proposal is not None
    assert result.proposal.status == ProposalStatus.RENDERED
    assert calls == ["priced:PRICED", "render", "rendered:RENDERED"]


def test_clarification_result_does_not_persist_or_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected(*_: object) -> None:
        raise AssertionError("workflow must stop before persistence or rendering")

    monkeypatch.setattr(
        "catering_agent.agent.draft_generation.persist_proposal", unexpected
    )
    monkeypatch.setattr(
        "catering_agent.agent.draft_generation.render_proposal", unexpected
    )

    result = generate_draft(
        _provider("golden-03-incomplete-date"),
        _snapshot(),
        _request("golden-03-incomplete-date"),
        "proposal-001",
        "postgresql+psycopg://unused",
        ROOT / "data" / "samples" / "templates",
        tmp_path / "docstore",
        "http://docconv:3000",
    )

    assert result.pipeline_result.status == "NEEDS_CLARIFICATION"
    assert result.proposal is None


def test_priced_result_without_a_venue_does_not_persist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_venue = _pipeline_result_without_venue()

    def unexpected(*_: object) -> None:
        raise AssertionError("workflow must resolve the venue before persistence")

    monkeypatch.setattr(
        "catering_agent.agent.draft_generation.run_pipeline",
        lambda *_: missing_venue,
    )
    monkeypatch.setattr(
        "catering_agent.agent.draft_generation.persist_proposal", unexpected
    )

    with pytest.raises(DraftGenerationError, match="no resolved venue"):
        generate_draft(
            _provider("golden-06-preferred-menu-selection"),
            _snapshot(),
            _request("golden-06-preferred-menu-selection"),
            "proposal-001",
            "postgresql+psycopg://unused",
            ROOT / "data" / "samples" / "templates",
            tmp_path / "docstore",
            "http://docconv:3000",
        )


def test_rendered_persistence_failure_removes_created_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def render(
        proposal: Proposal,
        _: object,
        __: Path,
        docstore_directory: Path,
        ___: str,
    ) -> Proposal:
        artifact_directory = docstore_directory / proposal.proposal_id
        artifact_directory.mkdir(parents=True)
        docx_path = artifact_directory / "proposal.docx"
        pdf_path = artifact_directory / "proposal.pdf"
        docx_path.write_bytes(b"docx")
        pdf_path.write_bytes(b"%PDF-")
        payload = proposal.model_dump(mode="json")
        payload.update(
            {
                "status": ProposalStatus.RENDERED,
                "docx_path": str(docx_path),
                "pdf_path": str(pdf_path),
            }
        )
        return Proposal.model_validate(payload)

    def fail_rendered_persistence(_: Proposal, __: str) -> None:
        raise ProposalPersistenceError("database unavailable")

    monkeypatch.setattr(
        "catering_agent.agent.draft_generation.persist_proposal",
        lambda proposal, _: proposal,
    )
    monkeypatch.setattr("catering_agent.agent.draft_generation.render_proposal", render)
    monkeypatch.setattr(
        "catering_agent.agent.draft_generation.persist_rendered_proposal",
        fail_rendered_persistence,
    )

    with pytest.raises(DraftGenerationError, match="could not be recorded"):
        generate_draft(
            _provider("golden-06-preferred-menu-selection"),
            _snapshot(),
            _request("golden-06-preferred-menu-selection"),
            "proposal-001",
            "postgresql+psycopg://unused",
            ROOT / "data" / "samples" / "templates",
            tmp_path / "docstore",
            "http://docconv:3000",
        )

    assert not (tmp_path / "docstore" / "proposal-001").exists()


def _provider(case_name: str) -> RecordedProvider:
    case_root = GOLDEN_ROOT / case_name
    return RecordedProvider(
        _load_json(case_root / "extraction.json"),
        _load_json(case_root / "selection.json")
        if (case_root / "selection.json").is_file()
        else {},
    )


def _request(case_name: str) -> PipelineRequest:
    case_root = GOLDEN_ROOT / case_name
    context_payload = _load_json(case_root / "context.json")
    reference_date = date.fromisoformat(str(context_payload.pop("reference_date")))
    return PipelineRequest(
        brief_text=(case_root / "brief.txt").read_text(encoding="utf-8"),
        context=ExtractionContext.model_validate(context_payload),
        reference_date=reference_date,
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


def _pipeline_result_without_venue() -> PipelineResult:
    """Return a malformed internal result to protect against partial persistence."""

    result = run_pipeline(
        _provider("golden-06-preferred-menu-selection"),
        _snapshot(),
        _request("golden-06-preferred-menu-selection"),
    )
    return result.model_copy(update={"catalog_resolution": None})


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value
