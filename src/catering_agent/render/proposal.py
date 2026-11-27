"""Fail-closed rendering of a priced proposal through an approved DOCX template."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile

from docx import Document
from docxtpl import DocxTemplate  # type: ignore[import-untyped]
from jinja2 import TemplateError
from pydantic import ValidationError

from catering_agent.domain.models import Proposal, ProposalStatus, Venue

_SAFE_FILE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_GOTENBERG_TIMEOUT_SECONDS = 30


class ProposalRenderError(RuntimeError):
    """A priced proposal could not safely become a complete document set."""


def render_proposal(
    proposal: Proposal,
    venue: Venue,
    template_directory: Path,
    docstore_directory: Path,
    gotenberg_url: str,
) -> Proposal:
    """Render a priced proposal with its venue's exact approved template."""

    proposal = _validated_priced_proposal(proposal)
    _require_matching_venue(proposal, venue)
    template_path = _template_path(template_directory, venue.template_id)
    artifact_directory = _artifact_directory(docstore_directory, proposal.proposal_id)
    if artifact_directory.exists():
        raise ProposalRenderError("proposal artifacts already exist")

    try:
        artifact_directory.mkdir(parents=True)
        docx_path = artifact_directory / "proposal.docx"
        pdf_path = artifact_directory / "proposal.pdf"
        document = DocxTemplate(template_path)
        document.render(_template_context(proposal, venue), autoescape=True)
        document.save(docx_path)
        _validate_docx(docx_path, proposal)
        convert_docx_to_pdf(docx_path, pdf_path, gotenberg_url)
        _validate_pdf(pdf_path)
        payload = proposal.model_dump(mode="json")
        payload.update(
            {
                "status": ProposalStatus.RENDERED,
                "docx_path": str(docx_path),
                "pdf_path": str(pdf_path),
            }
        )
        return Proposal.model_validate(payload)
    except (
        BadZipFile,
        OSError,
        ProposalRenderError,
        TemplateError,
        ValidationError,
        ValueError,
    ) as error:
        shutil.rmtree(artifact_directory, ignore_errors=True)
        raise ProposalRenderError("proposal rendering failed") from error


def convert_docx_to_pdf(docx_path: Path, pdf_path: Path, gotenberg_url: str) -> None:
    """Use the internal Gotenberg service to convert one generated DOCX to PDF."""

    boundary = "catering-proposal-boundary"
    body = b"".join(
        (
            f"--{boundary}\r\n".encode(),
            (
                b'Content-Disposition: form-data; name="files"; '
                b'filename="proposal.docx"\r\n'
            ),
            (
                b"Content-Type: application/vnd.openxmlformats-officedocument."
                b"wordprocessingml.document\r\n\r\n"
            ),
            docx_path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        )
    )
    request = Request(
        f"{gotenberg_url.rstrip('/')}/forms/libreoffice/convert",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_GOTENBERG_TIMEOUT_SECONDS) as response:  # noqa: S310
            if response.status != 200:
                raise ProposalRenderError("document conversion returned an error")
            pdf_path.write_bytes(response.read())
    except (HTTPError, OSError, URLError) as error:
        raise ProposalRenderError("document conversion failed") from error


def _validated_priced_proposal(proposal: Proposal) -> Proposal:
    try:
        proposal = Proposal.model_validate(proposal.model_dump(mode="json"))
    except ValidationError as error:
        raise ProposalRenderError("proposal validation failed") from error
    if proposal.status != ProposalStatus.PRICED:
        raise ProposalRenderError("only a complete priced proposal can be rendered")
    return proposal


def _require_matching_venue(proposal: Proposal, venue: Venue) -> None:
    if (
        proposal.brief.venue_id != venue.venue_id
        or proposal.region_spec_id != venue.region_spec_id
        or proposal.region_spec_version != venue.region_spec_version
    ):
        raise ProposalRenderError("venue does not match proposal context")


def _template_path(template_directory: Path, template_id: str) -> Path:
    if _SAFE_FILE_ID.fullmatch(template_id) is None:
        raise ProposalRenderError("venue template ID is unsafe")
    template_root = template_directory.resolve()
    template_path = (template_root / f"{template_id}.docx").resolve()
    if template_path.parent != template_root or not template_path.is_file():
        raise ProposalRenderError("approved venue template is unavailable")
    return template_path


def _artifact_directory(docstore_directory: Path, proposal_id: str) -> Path:
    if _SAFE_FILE_ID.fullmatch(proposal_id) is None:
        raise ProposalRenderError("proposal ID is unsafe for artifact storage")
    docstore_root = docstore_directory.resolve()
    artifact_directory = (docstore_root / proposal_id).resolve()
    if artifact_directory.parent != docstore_root:
        raise ProposalRenderError("proposal artifact path is unsafe")
    return artifact_directory


def _template_context(proposal: Proposal, venue: Venue) -> dict[str, object]:
    assert proposal.total is not None
    return {
        "proposal": {
            "proposal_id": proposal.proposal_id,
            "client_name": proposal.brief.client_name or "",
            "client_contact": proposal.brief.client_contact or "",
            "event_date": (
                proposal.brief.event_date.isoformat()
                if proposal.brief.event_date is not None
                else ""
            ),
            "venue_name": venue.display_name,
            "guest_count": ""
            if proposal.brief.guest_count is None
            else str(proposal.brief.guest_count),
            "event_type": proposal.brief.event_type or "",
            "service_styles": ", ".join(proposal.brief.service_styles),
            "currency": proposal.currency,
            "line_items": [
                {
                    "line_item_id": line.line_item_id,
                    "quantity": str(line.quantity),
                    "unit": line.unit,
                    "unit_price": str(line.unit_price.amount),
                    "total": str(line.total.amount),
                }
                for line in proposal.line_items
            ],
            "total": str(proposal.total.amount),
        }
    }


def _validate_docx(docx_path: Path, proposal: Proposal) -> None:
    document_text = _document_text(Document(str(docx_path)))
    if "{{" in document_text or "{%" in document_text:
        raise ProposalRenderError("rendered document retains template syntax")
    required_values = [
        *(line.line_item_id for line in proposal.line_items),
        str(proposal.total.amount) if proposal.total is not None else "",
        proposal.currency,
    ]
    if any(value not in document_text for value in required_values):
        raise ProposalRenderError("rendered document is missing proposal values")


def _document_text(document: Any) -> str:
    paragraphs = list(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(cell.paragraphs)
    for section in document.sections:
        paragraphs.extend(section.header.paragraphs)
        paragraphs.extend(section.footer.paragraphs)
    return "\n".join(paragraph.text for paragraph in paragraphs)


def _validate_pdf(pdf_path: Path) -> None:
    if not pdf_path.is_file() or not pdf_path.read_bytes().startswith(b"%PDF-"):
        raise ProposalRenderError("document conversion did not produce a PDF")
