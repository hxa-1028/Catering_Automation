"""Assemble one reproducible proposal from a validated priced pipeline result."""

from __future__ import annotations

from catering_agent.agent.pipeline import PipelineResult
from catering_agent.domain.models import Proposal, ProposalStatus, SourceRef


class ProposalAssemblyError(ValueError):
    """The pipeline result cannot safely become a proposal draft."""


def assemble_proposal(
    result: PipelineResult, proposal_id: str, original_brief_text: str
) -> Proposal:
    """Create a priced proposal without supplying business data or defaults."""

    if result.status != "PRICED":
        raise ProposalAssemblyError("only a priced pipeline result can be assembled")
    if not original_brief_text.strip():
        raise ProposalAssemblyError("original brief text is required")
    if (
        result.extraction is None
        or result.catalog_resolution is None
        or result.catalog_resolution.regional_specification is None
        or result.menu_selection is None
        or result.pricing is None
    ):
        raise ProposalAssemblyError(
            "priced result is missing required source-backed data"
        )

    regional_specification = result.catalog_resolution.regional_specification
    source_refs = _unique_source_refs(
        (*result.menu_selection.cited_source_refs, *result.pricing.cited_source_refs)
    )
    if any(
        source.catalog_version != result.catalog_resolution.catalog_version
        or source.region_spec_id != regional_specification.region_spec_id
        or source.region_spec_version != regional_specification.version
        for source in source_refs
    ):
        raise ProposalAssemblyError("proposal source reference does not match context")

    return Proposal(
        proposal_id=proposal_id,
        status=ProposalStatus.PRICED,
        brief=result.brief,
        region_spec_id=regional_specification.region_spec_id,
        region_spec_version=regional_specification.version,
        regional_policy_version=regional_specification.regional_policy_version,
        catalog_version=result.catalog_resolution.catalog_version,
        rules_version=regional_specification.rules_version,
        prompt_version=(
            f"{result.extraction.prompt_version}|{result.menu_selection.prompt_version}"
        ),
        llm_model=result.extraction.model,
        locale=regional_specification.locale,
        currency=regional_specification.currency,
        timezone=regional_specification.timezone,
        original_brief_text=original_brief_text,
        line_items=result.pricing.line_items,
        total=result.pricing.total,
        source_refs=source_refs,
    )


def _unique_source_refs(source_refs: tuple[SourceRef, ...]) -> tuple[SourceRef, ...]:
    unique: dict[str, SourceRef] = {}
    for source in source_refs:
        existing = unique.get(source.source_ref_id)
        if existing is not None and existing != source:
            raise ProposalAssemblyError("source reference ID has conflicting values")
        unique[source.source_ref_id] = source
    return tuple(unique.values())
