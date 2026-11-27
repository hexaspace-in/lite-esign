"""Signing records, signature certificate PDF, and signed copies of PDFs."""
import base64
import hashlib
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

MAX_DRAWN = 250_000          # characters of the data URL (~180 KB image)
KINDS = {"proposal": "Proposal acceptance", "stage": "Stage approval", "boq": "BOQ approval", "change": "Change order approval",
         "document": "Document signature", "form": "Site form sign-off"}


class SignatureError(ValueError):
    """Raised with a message you can show to the signer."""


def fingerprint(content) -> str:
    """SHA-256 of what was signed (sorted JSON). One changed word or number gives a different fingerprint."""
    raw = json.dumps(content, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def fingerprint_file(data: bytes) -> str:
    """SHA-256 of a file (e.g. the original PDF the signer read)."""
    return hashlib.sha256(data).hexdigest()


def clean_drawn(drawn: Optional[str]) -> Optional[str]:
    """Validate an optional drawn signature: a PNG data URL from a signature pad, or None."""
    if not drawn:
        return None
    if len(drawn) > MAX_DRAWN or not drawn.startswith("data:image/png;base64,"):
        raise SignatureError("The drawn signature could not be read. Clear it and draw again, or sign with your typed name only.")
    try:
        png = base64.b64decode(drawn.split(",", 1)[1], validate=True)
    except Exception:
        raise SignatureError("The drawn signature could not be read. Clear it and draw again.")
    if not png.startswith(b"\x89PNG"):
        raise SignatureError("The drawn signature could not be read. Clear it and draw again.")
    return drawn


def make_record(*, kind: str, title: str, content=None, file_bytes: Optional[bytes] = None, name: str,
                agreed: bool, drawn: Optional[str] = None, email: str = "", account_name: str = "", ip: str = "",
                user_agent: str = "", channel: str = "portal", identity: str = "", summary: Optional[list] = None,
                company: Optional[dict] = None) -> dict:
    """Build a signing record. Store it in your database; pass it to certificate_pdf().

    channel: "portal" (signed in), "link" (private link + identity check) or "in_person" (staff device).
    Fingerprint is of file_bytes when given (a PDF), else of content.
    """
    if not agreed:
        raise SignatureError("Tick 'I agree' to sign")
    if len((name or "").strip()) < 2:
        raise SignatureError("Type your full name to sign")
    return {"id": f"sig_{uuid.uuid4().hex[:12]}", "kind": kind, "kind_label": KINDS.get(kind, kind.title()), "title": title,
            "summary": summary or [], "signer": {"name": name.strip(), "email": email, "account_name": account_name},
            "method": "Typed name and 'I agree'" + (" with a drawn signature" if drawn else ""),
            "drawn": clean_drawn(drawn), "at": datetime.now(timezone.utc).isoformat(), "ip": ip, "user_agent": user_agent[:300],
            "channel": channel, "identity": identity, "company": company or {},
            "fingerprint": fingerprint_file(file_bytes) if file_bytes is not None else fingerprint(content),
            "fingerprint_of": "file" if file_bytes is not None else "content"}


def _local(iso: str, tz: str) -> str:
    from zoneinfo import ZoneInfo
    try:
        return datetime.fromisoformat(iso).astimezone(ZoneInfo(tz)).strftime("%d %b %Y, %I:%M:%S %p %Z")
    except Exception:
        return iso


def certificate_pdf(rec: dict, brand: str = "", accent: str = "#C8102E", tz: str = "Asia/Kolkata") -> bytes:
    """One-page signature certificate PDF for a signing record (see make_record)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    red, ink, grey = HexColor(accent), HexColor("#1A1A1A"), HexColor("#6B6B6B")
    x, y = 20 * mm, h - 22 * mm
    c.setFillColor(red)
    c.rect(0, h - 8 * mm, w, 8 * mm, stroke=0, fill=1)
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, brand.upper())
    y -= 12 * mm
    c.setFont("Helvetica-Bold", 20)
    c.drawString(x, y, "Signature certificate")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(grey)
    c.drawString(x, y, f"{rec['kind_label']}  ·  Record {rec['id']}" + ("  ·  SAMPLE DATA" if rec.get("is_sample") else ""))
    y -= 12 * mm

    def row(label, value, bold=False):
        nonlocal y
        c.setFillColor(grey)
        c.setFont("Helvetica", 9)
        c.drawString(x, y, label)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10.5)
        text, lines = str(value or "-"), []
        while len(text) > 78:
            cut = text.rfind(" ", 0, 78)
            cut = cut if cut > 30 else 78
            lines.append(text[:cut])
            text = text[cut:].lstrip()
        lines.append(text)
        for ln in lines:
            c.drawString(x + 45 * mm, y, ln)
            y -= 5.2 * mm
        y -= 1.8 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "What was signed")
    y -= 7 * mm
    row("Document", rec["title"], True)
    for a, b in rec.get("summary") or []:
        row(a, b)
    y -= 3 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Who signed and how")
    y -= 7 * mm
    s = rec["signer"]
    row("Signed by (typed name)", s.get("name"), True)
    if rec.get("identity"):
        row("Identity check", rec["identity"])
    else:
        row("Signed-in account", " · ".join(v for v in (s.get("account_name"), s.get("email")) if v))
    row("Date and time", _local(rec["at"], tz))
    ch = rec.get("channel") or ("link" if rec.get("identity") else "portal")
    row("Method", rec["method"] + {"link": ", on a private signing link", "in_person": ", in person on a staff device"}.get(ch, ", while signed in to their account"))
    row("IP address", rec.get("ip"))
    row("Browser", rec.get("user_agent"))
    if rec.get("drawn"):
        try:
            img = ImageReader(io.BytesIO(base64.b64decode(rec["drawn"].split(",", 1)[1])))
            c.setFillColor(grey)
            c.setFont("Helvetica", 9)
            c.drawString(x, y, "Drawn signature")
            iw, ih = img.getSize()
            bw = 70 * mm
            bh = min(28 * mm, bw * ih / max(iw, 1))
            c.drawImage(img, x + 45 * mm, y - bh + 3 * mm, width=bw, height=bh, mask="auto", preserveAspectRatio=True)
            c.setStrokeColor(grey)
            c.line(x + 45 * mm, y - bh + 2 * mm, x + 115 * mm, y - bh + 2 * mm)
            y -= bh + 6 * mm
        except Exception:
            row("Drawn signature", "(saved, could not be shown)")
    co = rec.get("company") or {}
    if co.get("name"):
        y -= 2 * mm
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(ink)
        c.drawString(x, y, f"For {co.get('company') or brand or 'the company'}")
        y -= 7 * mm
        row("Authorised signatory", ", ".join(v for v in (co.get("name"), co.get("title")) if v), True)
        row("Added", "Automatically when the client signed, as set in the document rules")
        if co.get("image"):
            try:
                img = ImageReader(io.BytesIO(base64.b64decode(co["image"].split(",", 1)[1])))
                iw, ih = img.getSize()
                bw = 55 * mm
                bh = min(22 * mm, bw * ih / max(iw, 1))
                c.drawImage(img, x + 45 * mm, y - bh + 3 * mm, width=bw, height=bh, mask="auto", preserveAspectRatio=True)
                y -= bh + 4 * mm
            except Exception:
                pass
    y -= 3 * mm
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(ink)
    c.drawString(x, y, "Fingerprint of the original PDF (SHA-256)" if rec.get("fingerprint_of") == "file" else "Fingerprint of what was signed (SHA-256)")
    y -= 6 * mm
    c.setFont("Courier", 9)
    c.drawString(x, y, rec["fingerprint"])
    y -= 10 * mm
    c.setFont("Helvetica", 8.5)
    c.setFillColor(grey)
    doc_note = ("The fingerprint is the SHA-256 of the original PDF the signer read (the pages before this certificate, without the",
                "signed note in the footer). Anyone can recalculate it from that file; if one byte changes, the fingerprint changes.")
    content_note = ("The fingerprint is calculated from the exact content the signer approved. If even one word or number of that",
                    "content changes, the fingerprint changes, so this record shows what was agreed and that it has not been altered.")
    for ln in (doc_note if rec.get("fingerprint_of") == "file" else content_note) + (
               "This is an electronic acceptance (typed name and tick box, with an optional drawn signature) made by the signer",
               {"link": "on a private signing link after the phone check above.", "in_person": "in person, on the staff device named above."}.get(
                   rec.get("channel") or ("link" if rec.get("identity") else "portal"), "while signed in to their own account.")
               + " It is not an Aadhaar eSign or a digital signature certificate."):
        c.drawString(x, y, ln)
        y -= 4.4 * mm
    c.showPage()
    c.save()
    return buf.getvalue()


def readable(pdf: bytes) -> bool:
    """Can the signed copy be made from this PDF? Checked when a document is sent, so signing never fails half-way."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(io.BytesIO(pdf), strict=False).pages) > 0
    except Exception:
        return False


def stamp_pdf(original: bytes, cert: bytes, note: str) -> bytes:
    """Original pages + a small signed note at the foot of every page, then the certificate page."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    src, cert_r, out = PdfReader(io.BytesIO(original), strict=False), PdfReader(io.BytesIO(cert)), PdfWriter()
    for src_page in src.pages:
        page = out.add_page(src_page)          # attach to the writer first (required by pypdf 7+)
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))
        c.setFont("Helvetica", 6.5)
        c.setFillColor(HexColor("#C8102E"))
        c.drawString(18, 9, note)
        c.save()
        page.merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])
    for page in cert_r.pages:
        out.add_page(page)
    b = io.BytesIO()
    out.write(b)
    return b.getvalue()


# ---------- signing links ----------

VALID_DAYS = 15
MAX_TRIES = 5


def new_link(phone: str, days: int = VALID_DAYS) -> dict:
    """A private signing link record: random token, expiry, and the phone whose last 4 digits the signer must enter."""
    import secrets
    return {"token": secrets.token_urlsafe(24), "expires": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
            "phone_last4": "".join(ch for ch in phone if ch.isdigit())[-4:], "tries": 0, "status": "waiting"}


def link_status(link: dict, now: Optional[datetime] = None) -> str:
    """waiting | signed | cancelled | expired | locked"""
    now = now or datetime.now(timezone.utc)
    if link["status"] == "waiting" and link.get("tries", 0) >= MAX_TRIES:
        return "locked"
    if link["status"] == "waiting" and datetime.fromisoformat(link["expires"]) < now:
        return "expired"
    return link["status"]


def check_code(link: dict, code: str) -> bool:
    """Check the last 4 phone digits. Counts wrong tries; after MAX_TRIES the link locks. Mutates link["tries"]."""
    if link_status(link) != "waiting":
        raise SignatureError("This link can no longer be used. Ask for a new one.")
    if "".join(ch for ch in code if ch.isdigit()) == link["phone_last4"]:
        return True
    link["tries"] = link.get("tries", 0) + 1
    return False
