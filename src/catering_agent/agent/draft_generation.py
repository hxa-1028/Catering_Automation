"""Internal orchestration from a brief to a persisted rendered proposal draft."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from catering_agent.agent.pipeline import PipelineRequest, PipelineResult, run_pipeline
from catering_agent.catalog.resolution import CatalogSnapshot
from catering_agent.domain.models import Proposal, Venue
from catering_agent.llm.providers.base import BriefExtractionProvider
from catering_agent.proposal.assembly import ProposalAssemblyError, assemble_proposal
from catering_agent.proposal.persistence import (
    ProposalPersistenceError,
    persist_proposal,
    persist_rendered_proposal,
)
from catering_agent.render.proposal import ProposalRenderError, render_proposal

_SAFE_PROPOSAL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


class DraftGenerationError(RuntimeError):
    """The internal workflow could not safely complete a draft proposal."""


@dataclass(frozen=True)
class DraftGenerationResult:
    """Pipeline result plus the rendered proposal when one was safely created."""

    pipeline_result: PipelineResult
    proposal: Proposal | None = None


def generate_draft(
    provider: BriefExtractionProvider,
    snapshot: CatalogSnapshot,
    request: PipelineRequest,
    proposal_id: str,
    database_url: str,
    template_directory: Path,
    docstore_directory: Path,
    gotenberg_url: str,
) -> DraftGenerationResult:
    """Run the bounded pipeline and persist a rendered draft when it is priced."""

    pipeline_result = run_pipeline(provider, snapshot, request)
    if pipeline_result.status != "PRICED":
        return DraftGenerationResult(pipeline_result=pipeline_result)
    if _SAFE_PROPOSAL_ID.fullmatch(proposal_id) is None:
        raise DraftGenerationError("proposal ID is unsafe for draft generation")

    venue = _resolved_venue(pipeline_result)
    try:
        priced_proposal = assemble_proposal(
            pipeline_result, proposal_id, request.brief_text
        )
        persist_proposal(priced_proposal, database_url)
        rendered_proposal = render_proposal(
            priced_proposal,
            venue,
            template_directory,
            docstore_directory,
            gotenberg_url,
        )
    except (
        ProposalAssemblyError,
        ProposalPersistenceError,
        ProposalRenderError,
    ) as error:
        raise DraftGenerationError("draft generation failed") from error

    try:
        persist_rendered_proposal(rendered_proposal, database_url)
    except ProposalPersistenceError as error:
        _remove_created_artifacts(rendered_proposal, docstore_directory)
        raise DraftGenerationError("rendered draft could not be recorded") from error
    return DraftGenerationResult(
        pipeline_result=pipeline_result, proposal=rendered_proposal
    )


def _resolved_venue(pipeline_result: PipelineResult) -> Venue:
    catalog_resolution = pipeline_result.catalog_resolution
    if catalog_resolution is None or catalog_resolution.venue is None:
        raise DraftGenerationError("priced pipeline result has no resolved venue")
    return catalog_resolution.venue


def _remove_created_artifacts(proposal: Proposal, docstore_directory: Path) -> None:
    if proposal.docx_path is None:
        raise DraftGenerationError("rendered proposal has no DOCX artifact")
    docstore_root = docstore_directory.resolve()
    artifact_directory = Path(proposal.docx_path).resolve().parent
    if (
        artifact_directory.parent != docstore_root
        or artifact_directory.name != proposal.proposal_id
    ):
        raise DraftGenerationError("rendered artifact path is outside docstore")
    try:
        shutil.rmtree(artifact_directory)
    except OSError as error:
        raise DraftGenerationError("rendered artifacts could not be removed") from error
