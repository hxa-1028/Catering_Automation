"""Transactional persistence for already validated proposal drafts."""

from __future__ import annotations

from datetime import UTC, datetime

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


def persist_rendered_proposal(proposal: Proposal, database_url: str) -> Proposal:
    """Record artifacts only for the exact priced proposal that produced them."""

    try:
        proposal = Proposal.model_validate(proposal.model_dump(mode="json"))
    except ValidationError as error:
        raise ProposalPersistenceError("proposal validation failed") from error
    if proposal.status != ProposalStatus.RENDERED or proposal.total is None:
        raise ProposalPersistenceError(
            "only a complete rendered proposal can be stored"
        )
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session, session.begin():
            record = session.get(ProposalRecord, proposal.proposal_id)
            if record is None:
                raise ProposalPersistenceError("priced proposal ID does not exist")
            _require_matching_priced_record(record, proposal)
            _require_matching_priced_line_items(session, proposal)
            record.status = ProposalStatus.RENDERED.value
            record.docx_path = proposal.docx_path
            record.pdf_path = proposal.pdf_path
            record.updated_at = datetime.now(UTC)
    except SQLAlchemyError as error:
        raise ProposalPersistenceError(
            "rendered proposal persistence failed"
        ) from error
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


def _require_matching_priced_record(record: ProposalRecord, proposal: Proposal) -> None:
    """Reject an artifact update that is not for this exact priced snapshot."""

    if proposal.total is None:
        raise ProposalPersistenceError("rendered proposal total is unavailable")
    expected_source_refs = [source.source_ref_id for source in proposal.source_refs]
    if (
        record.status != ProposalStatus.PRICED.value
        or record.docx_path is not None
        or record.pdf_path is not None
        or record.brief != proposal.brief.model_dump(mode="json")
        or record.region_spec_id != proposal.region_spec_id
        or record.region_spec_version != proposal.region_spec_version
        or record.regional_policy_version != proposal.regional_policy_version
        or record.catalog_version != proposal.catalog_version
        or record.rules_version != proposal.rules_version
        or record.prompt_version != proposal.prompt_version
        or record.llm_model != proposal.llm_model
        or record.locale != proposal.locale
        or record.currency != proposal.currency
        or record.timezone != proposal.timezone
        or record.original_brief_text != proposal.original_brief_text
        or record.total_amount != proposal.total.amount
        or record.source_ref_ids != expected_source_refs
        or record.warnings != list(proposal.warnings)
        or record.needs_input != [item.model_dump() for item in proposal.needs_input]
    ):
        raise ProposalPersistenceError("stored priced proposal does not match render")


def _require_matching_priced_line_items(session: Session, proposal: Proposal) -> None:
    expected = {
        line.line_item_id: (
            line.quantity,
            line.unit,
            line.unit_price.amount,
            line.total.amount,
            line.total.currency,
            line.source_ref.source_ref_id,
        )
        for line in proposal.line_items
    }
    stored = {
        line.line_item_id: (
            line.quantity,
            line.unit,
            line.unit_price,
            line.total,
            line.currency,
            line.source_ref_id,
        )
        for line in session.scalars(
            select(ProposalLineItemRecord).where(
                ProposalLineItemRecord.proposal_id == proposal.proposal_id
            )
        )
    }
    if stored != expected:
        raise ProposalPersistenceError("stored priced proposal does not match render")


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
