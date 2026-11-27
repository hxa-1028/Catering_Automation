from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from docx import Document
from pydantic import ValidationError

from catering_agent.domain.models import (
    EventBrief,
    Money,
    Proposal,
    ProposalLineItem,
    ProposalStatus,
    SourceLocation,
    SourceRef,
    Venue,
)
from catering_agent.render.proposal import (
    ProposalRenderError,
    convert_docx_to_pdf,
    render_proposal,
)

ROOT = Path(__file__).parents[3]


def test_renders_every_priced_line_and_total_to_docx_and_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template_directory = tmp_path / "templates"
    _write_template(template_directory / "sample-harbor-template.docx")
    monkeypatch.setattr(
        "catering_agent.render.proposal.convert_docx_to_pdf", _write_pdf
    )

    rendered = render_proposal(
        _proposal(),
        _venue(),
        template_directory,
        tmp_path / "docstore",
        "http://docconv:3000",
    )

    assert rendered.status == ProposalStatus.RENDERED
    assert rendered.docx_path is not None
    assert rendered.pdf_path is not None
    assert Path(rendered.pdf_path).read_bytes().startswith(b"%PDF-")
    document_text = "\n".join(
        paragraph.text for paragraph in Document(rendered.docx_path).paragraphs
    )
    assert "sample-lunch-service" in document_text
    assert "sample-venue-fee" in document_text
    assert "1600.00" in document_text
    assert "USD" in document_text
    assert "Sample & Client" in document_text
    assert "{{" not in document_text
    assert "{%" not in document_text


def test_sanitized_sample_template_is_renderable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "catering_agent.render.proposal.convert_docx_to_pdf", _write_pdf
    )

    rendered = render_proposal(
        _proposal(),
        _venue(),
        ROOT / "data" / "samples" / "templates",
        tmp_path / "docstore",
        "http://docconv:3000",
    )

    assert rendered.status == ProposalStatus.RENDERED


def test_refuses_missing_or_mismatched_venue_template(tmp_path: Path) -> None:
    with pytest.raises(ProposalRenderError, match="approved venue template"):
        render_proposal(
            _proposal(),
            _venue(),
            tmp_path / "templates",
            tmp_path / "docstore",
            "http://docconv:3000",
        )

    wrong_venue = _venue().model_copy(update={"venue_id": "other-venue"})
    with pytest.raises(ProposalRenderError, match="venue does not match"):
        render_proposal(
            _proposal(),
            wrong_venue,
            tmp_path / "templates",
            tmp_path / "docstore",
            "http://docconv:3000",
        )

    unsafe_template = _venue().model_copy(update={"template_id": "../template"})
    with pytest.raises(ProposalRenderError, match="template ID is unsafe"):
        render_proposal(
            _proposal(),
            unsafe_template,
            tmp_path / "templates",
            tmp_path / "docstore",
            "http://docconv:3000",
        )


def test_refuses_template_syntax_that_survives_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template_directory = tmp_path / "templates"
    _write_template(
        template_directory / "sample-harbor-template.docx",
        extra_text="{% raw %}{{ intentionally_unrendered }}{% endraw %}",
    )
    monkeypatch.setattr(
        "catering_agent.render.proposal.convert_docx_to_pdf", _write_pdf
    )

    with pytest.raises(ProposalRenderError, match="proposal rendering failed"):
        render_proposal(
            _proposal(),
            _venue(),
            template_directory,
            tmp_path / "docstore",
            "http://docconv:3000",
        )

    assert not (tmp_path / "docstore" / "proposal-001").exists()


def test_converter_failure_removes_partial_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template_directory = tmp_path / "templates"
    _write_template(template_directory / "sample-harbor-template.docx")

    def fail_conversion(*_: object) -> None:
        raise ProposalRenderError("converter unavailable")

    monkeypatch.setattr(
        "catering_agent.render.proposal.convert_docx_to_pdf", fail_conversion
    )

    with pytest.raises(ProposalRenderError, match="proposal rendering failed"):
        render_proposal(
            _proposal(),
            _venue(),
            template_directory,
            tmp_path / "docstore",
            "http://docconv:3000",
        )

    assert not (tmp_path / "docstore" / "proposal-001").exists()


def test_rendered_status_requires_both_artifact_paths() -> None:
    payload = _proposal().model_dump(mode="json")
    payload["status"] = ProposalStatus.RENDERED

    with pytest.raises(ValidationError, match="DOCX and PDF artifacts"):
        Proposal.model_validate(payload)


def test_gotenberg_converter_posts_docx_and_writes_its_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docx_path = tmp_path / "proposal.docx"
    pdf_path = tmp_path / "proposal.pdf"
    docx_path.write_bytes(b"synthetic docx")
    captured: dict[str, object] = {}

    class FakeResponse:
        status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b"%PDF-1.7\nconverted"

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("catering_agent.render.proposal.urlopen", fake_urlopen)

    convert_docx_to_pdf(docx_path, pdf_path, "http://docconv:3000")

    request = captured["request"]
    assert request.full_url == "http://docconv:3000/forms/libreoffice/convert"
    assert b"synthetic docx" in request.data
    assert pdf_path.read_bytes() == b"%PDF-1.7\nconverted"


def _write_template(path: Path, extra_text: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph("Proposal {{ proposal.proposal_id }}")
    document.add_paragraph("Client {{ proposal.client_name }}")
    document.add_paragraph("Venue {{ proposal.venue_name }}")
    document.add_paragraph(
        "{% for item in proposal.line_items %}{{ item.line_item_id }} "
        "{{ item.quantity }} {{ item.unit }} {{ item.unit_price }} "
        "{{ item.total }}{% endfor %}"
    )
    document.add_paragraph("Total {{ proposal.total }} {{ proposal.currency }}")
    if extra_text is not None:
        document.add_paragraph(extra_text)
    document.save(path)


def _write_pdf(_: Path, pdf_path: Path, __: str) -> None:
    pdf_path.write_bytes(b"%PDF-1.7\nsynthetic test output")


def _proposal() -> Proposal:
    source_ref = SourceRef(
        source_ref_id="sample-source-ref",
        provider="local_filesystem",
        provider_source_id="catalog.json",
        content_hash="a" * 64,
        location=SourceLocation(section="sample"),
        catalog_version="sample-2026-11-22",
        region_spec_id="sample-us-west",
        region_spec_version="1",
    )
    return Proposal(
        proposal_id="proposal-001",
        status=ProposalStatus.PRICED,
        brief=EventBrief(
            client_name="Sample & Client",
            event_date=date(2026, 6, 15),
            venue_id="sample-harbor-hall",
            guest_count=50,
            event_type="corporate",
            service_styles=("buffet",),
        ),
        region_spec_id="sample-us-west",
        region_spec_version="1",
        regional_policy_version="sample-policy-1",
        catalog_version="sample-2026-11-22",
        rules_version="sample-rules-1",
        prompt_version="extract_brief.v1|select_menu.v1",
        llm_model="structured-eval",
        locale="en-US",
        currency="USD",
        timezone="America/Los_Angeles",
        original_brief_text="A sample corporate event.",
        line_items=(
            ProposalLineItem(
                line_item_id="sample-lunch-service",
                quantity=Decimal("50"),
                unit="per_guest",
                unit_price=Money(amount=Decimal("30.00"), currency="USD"),
                total=Money(amount=Decimal("1500.00"), currency="USD"),
                source_ref=source_ref,
            ),
            ProposalLineItem(
                line_item_id="sample-venue-fee",
                quantity=Decimal("1"),
                unit="flat",
                unit_price=Money(amount=Decimal("100.00"), currency="USD"),
                total=Money(amount=Decimal("100.00"), currency="USD"),
                source_ref=source_ref,
            ),
        ),
        total=Money(amount=Decimal("1600.00"), currency="USD"),
        source_refs=(source_ref,),
    )


def _venue() -> Venue:
    return Venue(
        venue_id="sample-harbor-hall",
        region_spec_id="sample-us-west",
        region_spec_version="1",
        display_name="Sample Harbor Hall",
        location_jurisdiction_ids=("sample-city",),
        capacity_by_service_style={"buffet": 120},
        template_id="sample-harbor-template",
        source_ref=SourceRef(
            source_ref_id="sample-source-ref",
            provider="local_filesystem",
            provider_source_id="catalog.json",
            content_hash="a" * 64,
            location=SourceLocation(section="sample"),
            catalog_version="sample-2026-11-22",
            region_spec_id="sample-us-west",
            region_spec_version="1",
        ),
    )
