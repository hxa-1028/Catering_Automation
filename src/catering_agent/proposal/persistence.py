"""Transactional persistence for already validated proposal drafts."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from catering_agent.db.models import (
    ProposalLineItemRecord,
    ProposalRecord,
    SourceReferenceRecord,
)
from catering_agent.domain.models import Proposal, ProposalStatus


class ProposalPersistenceError(RuntimeError):
    """A validated proposal could not be written without risking its integrity."""


def persist_proposal(proposal: Proposal, database_url: str) -> Proposal:
    """Persist a complete proposal and its lines in one transaction."""

    try:
        proposal = Proposal.model_validate(proposal.model_dump(mode="json"))
    except ValidationError as error:
        raise ProposalPersistenceError("proposal validation failed") from error
    if proposal.status != ProposalStatus.PRICED or proposal.total is None:
        raise ProposalPersistenceError(
            "only complete priced proposals can be persisted"
        )
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session, session.begin():
            if session.get(ProposalRecord, proposal.proposal_id) is not None:
                raise ProposalPersistenceError("proposal ID already exists")
            _require_source_references(session, proposal)
            session.add(_proposal_record(proposal))
            session.add_all(_line_item_records(proposal))
    except SQLAlchemyError as error:
        raise ProposalPersistenceError("proposal persistence failed") from error
    finally:
        engine.dispose()
    return proposal


def _require_source_references(session: Session, proposal: Proposal) -> None:
    expected = {source.source_ref_id for source in proposal.source_refs}
    available = set(
        session.scalars(
            select(SourceReferenceRecord.source_ref_id).where(
                SourceReferenceRecord.source_ref_id.in_(expected)
            )
        )
    )
    if available != expected:
        raise ProposalPersistenceError("proposal references unavailable source data")


def _proposal_record(proposal: Proposal) -> ProposalRecord:
    return ProposalRecord(
        proposal_id=proposal.proposal_id,
        status=proposal.status.value,
        brief=proposal.brief.model_dump(mode="json"),
        region_spec_id=proposal.region_spec_id,
        region_spec_version=proposal.region_spec_version,
        regional_policy_version=proposal.regional_policy_version,
        catalog_version=proposal.catalog_version,
        rules_version=proposal.rules_version,
        prompt_version=proposal.prompt_version,
        llm_model=proposal.llm_model,
        locale=proposal.locale,
        currency=proposal.currency,
        timezone=proposal.timezone,
        original_brief_text=proposal.original_brief_text,
        total_amount=None if proposal.total is None else proposal.total.amount,
        source_ref_ids=[source.source_ref_id for source in proposal.source_refs],
        warnings=list(proposal.warnings),
        needs_input=[item.model_dump() for item in proposal.needs_input],
        docx_path=proposal.docx_path,
        pdf_path=proposal.pdf_path,
    )


def _line_item_records(proposal: Proposal) -> list[ProposalLineItemRecord]:
    return [
        ProposalLineItemRecord(
            line_item_id=line.line_item_id,
            proposal_id=proposal.proposal_id,
            quantity=line.quantity,
            unit=line.unit,
            unit_price=line.unit_price.amount,
            total=line.total.amount,
            currency=line.total.currency,
            source_ref_id=line.source_ref.source_ref_id,
        )
        for line in proposal.line_items
    ]
