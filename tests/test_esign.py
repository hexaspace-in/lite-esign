import base64
import io
from datetime import datetime, timedelta, timezone

import pytest

from lite_esign import (SignatureError, certificate_pdf, check_code, clean_drawn, fingerprint, link_status, make_record,
                        new_link, readable, stamp_pdf)

PNG = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                  "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")).decode()


def test_fingerprint_changes_with_content():
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
    assert fingerprint({"total": 100}) != fingerprint({"total": 101})


def test_drawn_validation():
    assert clean_drawn(PNG) == PNG
    with pytest.raises(SignatureError):
        clean_drawn("data:image/jpeg;base64,xxxx")


def _record():
    return make_record(kind="boq", title="BOQ v2", content={"total": 100}, name="Asha Patel", agreed=True, drawn=PNG,
                    summary=[["Total", "Rs 100"]], company={"company": "Example Interiors", "name": "R. Shah", "title": "Director"})


def test_record_rules():
    with pytest.raises(SignatureError):
        make_record(kind="boq", title="BOQ v2", content={}, name="Asha Patel", agreed=False)
    r = _record()
    assert r["kind_label"] == "BOQ approval" and r["fingerprint_of"] == "content"


def test_certificate_and_stamp():
    from pypdf import PdfReader
    r = _record()
    cert = certificate_pdf(r, brand="Example Interiors")
    assert readable(cert)
    signed = stamp_pdf(cert, cert, "Signed by Asha Patel")
    assert len(PdfReader(io.BytesIO(signed)).pages) == 2


def test_links():
    link = new_link("+91 90000 01234")
    assert link["phone_last4"] == "1234" and link_status(link) == "waiting"
    assert not check_code(link, "0000")
    assert check_code(link, "1234")
    link["tries"] = 5
    assert link_status(link) == "locked"
    old = dict(new_link("1234"), expires=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
    assert link_status(old) == "expired"
