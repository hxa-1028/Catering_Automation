"""Fixed, read-only intake and catalog-resolution pipeline."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from catering_agent.catalog.resolution import (
    CatalogLookup,
    CatalogResolution,
    CatalogSnapshot,
    resolve_catalog,
)
from catering_agent.domain.models import EventBrief, NeedInput
from catering_agent.intake.clarification import assess_event_brief
from catering_agent.intake.extraction import (
    BriefExtractionError,
    BriefExtractionResult,
    ExtractionContext,
    extract_event_brief,
)
from catering_agent.llm.providers.base import BriefExtractionProvider, LLMProviderError


class PipelineRequest(BaseModel):
    """The bounded input accepted by the internal proposal pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    brief_text: str
    context: ExtractionContext
    reference_date: date | None = None


class PipelineResult(BaseModel):
    """A clarification request or source-backed catalog resolution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["NEEDS_CLARIFICATION", "SOURCES_RESOLVED"]
    brief: EventBrief
    extraction: BriefExtractionResult | None = None
    catalog_resolution: CatalogResolution | None = None
    needs_input: tuple[NeedInput, ...] = ()


def run_pipeline(
    provider: BriefExtractionProvider,
    snapshot: CatalogSnapshot,
    request: PipelineRequest,
) -> PipelineResult:
    """Run one extraction, clarification, and deterministic catalog lookup."""

    try:
        extraction = extract_event_brief(provider, request.brief_text, request.context)
    except (BriefExtractionError, LLMProviderError):
        return PipelineResult(
            status="NEEDS_CLARIFICATION",
            brief=_context_brief(request.context),
            needs_input=(NeedInput(field="event_brief", reason="extraction_failed"),),
        )

    assessment = assess_event_brief(
        extraction.brief,
        reference_date=request.reference_date,
        require_venue_id=False,
    )
    if assessment.status == "NEEDS_CLARIFICATION":
        return PipelineResult(
            status="NEEDS_CLARIFICATION",
            brief=assessment.brief,
            extraction=extraction,
            needs_input=assessment.needs_input,
        )
    if extraction.venue_query is None or not extraction.venue_query.strip():
        return PipelineResult(
            status="NEEDS_CLARIFICATION",
            brief=assessment.brief,
            extraction=extraction,
            needs_input=(NeedInput(field="venue", reason="missing"),),
        )

    lookup = CatalogLookup.model_validate(
        {
            "region_spec_id": request.context.region_spec_id,
            "region_spec_version": request.context.region_spec_version,
            "venue_query": extraction.venue_query,
            "event_date": assessment.brief.event_date,
            "event_type": assessment.brief.event_type,
            "service_styles": assessment.brief.service_styles,
            "language": request.context.preferred_language,
        }
    )
    catalog_resolution = resolve_catalog(snapshot, lookup)
    if catalog_resolution.status == "NEEDS_CLARIFICATION":
        return PipelineResult(
            status="NEEDS_CLARIFICATION",
            brief=assessment.brief,
            extraction=extraction,
            catalog_resolution=catalog_resolution,
            needs_input=catalog_resolution.needs_input,
        )

    if catalog_resolution.venue is None:
        return PipelineResult(
            status="NEEDS_CLARIFICATION",
            brief=assessment.brief,
            extraction=extraction,
            catalog_resolution=catalog_resolution,
            needs_input=(NeedInput(field="venue", reason="unresolved"),),
        )
    return PipelineResult(
        status="SOURCES_RESOLVED",
        brief=assessment.brief.model_copy(
            update={"venue_id": catalog_resolution.venue.venue_id}
        ),
        extraction=extraction,
        catalog_resolution=catalog_resolution,
    )


def _context_brief(context: ExtractionContext) -> EventBrief:
    return EventBrief(
        region_spec_id=context.region_spec_id,
        region_spec_version=context.region_spec_version,
        preferred_language=context.preferred_language,
    )
