from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas


def _money_str(val: Decimal) -> str:
    q = val.quantize(Decimal("0.01"))
    return f"{q:.2f}"


@dataclass(frozen=True)
class _Pos:
    x: float
    y: float


# NOTE:
# These coordinates are starter values for the bundled 1099-NEC.pdf.
# If you want perfect alignment, we’ll tweak these after you visually review one output.
_COPY_B_POSITIONS: dict[str, _Pos] = {
    "payer_name": _Pos(45, 708),
    "payer_addr": _Pos(45, 692),
    "payer_city_state_zip": _Pos(45, 676),
    "recipient_name": _Pos(45, 642),
    "recipient_addr": _Pos(45, 626),
    "recipient_city_state_zip": _Pos(45, 610),
    "recipient_tin_last4": _Pos(300, 610),
    "amount_1": _Pos(450, 642),  # Nonemployee compensation
}


def _pick_template() -> Path:
    # Prefer Copy B if present, else fall back to Copy 1 template
    base = Path(settings.BASE_DIR) / "static" / "images"
    b = base / "1099-NEC_B.pdf"
    if b.exists():
        return b
    return base / "1099-NEC.pdf"


def _make_overlay(page_w: float, page_h: float, values: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setFont("Helvetica", 9)

    for k, pos in _COPY_B_POSITIONS.items():
        v = values.get(k, "")
        if not v:
            continue
        c.drawString(pos.x, pos.y, v)

    c.showPage()
    c.save()
    return buf.getvalue()


def render_1099nec_pdf_response(
    *,
    request: HttpRequest,
    business: Any,
    contractor: Any,
    year: int,
    nonemployee_comp: Decimal,
) -> HttpResponse:
    template_path = _pick_template()
    reader = PdfReader(str(template_path))
    writer = PdfWriter()

    # Copy B is typically a single page in the provided file.
    page0 = reader.pages[0]
    w = float(page0.mediabox.width)
    h = float(page0.mediabox.height)

    payer_name = getattr(business, "name", "") or getattr(business, "business_name", "")
    payer_city = getattr(business, "city", "")
    payer_state = getattr(business, "state", "")
    payer_zip = getattr(business, "zip_code", "")
    payer_csz = " ".join([p for p in [payer_city, payer_state, payer_zip] if p])

    rec_name = getattr(contractor, "display_name", "") or getattr(contractor, "legal_name", "")
    rec_city = getattr(contractor, "city", "")
    rec_state = getattr(contractor, "state", "")
    rec_zip = getattr(contractor, "zip_code", "")
    rec_csz = " ".join([p for p in [rec_city, rec_state, rec_zip] if p])

    tax_profile = getattr(contractor, "tax_profile", None)
    tin_last4 = getattr(tax_profile, "tin_last4", "") if tax_profile else ""

    values = {
        "payer_name": payer_name,
        "payer_addr": getattr(business, "address1", "") or getattr(business, "address", ""),
        "payer_city_state_zip": payer_csz,
        "recipient_name": rec_name,
        "recipient_addr": getattr(contractor, "address1", ""),
        "recipient_city_state_zip": rec_csz,
        "recipient_tin_last4": tin_last4,
        "amount_1": _money_str(nonemployee_comp),
    }

    overlay_pdf = _make_overlay(w, h, values)
    overlay_reader = PdfReader(io.BytesIO(overlay_pdf))

    # Merge overlay onto first page only
    base_page = page0
    base_page.merge_page(overlay_reader.pages[0])
    writer.add_page(base_page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)

    filename = f"1099-NEC_{year}_{getattr(contractor, 'id', 'contractor')}.pdf"
    resp = HttpResponse(out.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
