# lite-esign

Simple electronic acceptance for Python apps. Use it for quotes, proposals, BOQs, change orders, stage sign-offs and site forms, where you need a clear, provable "yes" from a client and don't need a paid e-sign service.

- **Signing record**: typed full name, an "I agree" tick, and an optional drawn signature (PNG from any signature pad). It also stores time, IP and browser
- **Fingerprint** (SHA-256) of exactly what was signed, either the content (sorted JSON) or the original PDF file. If one word changes, the fingerprint changes
- **Signature certificate PDF** with your brand name and colour, including the company's authorised signatory if you set one
- **Signed copy of a PDF**: original pages with a small "signed" note on every page, plus the certificate as the last page
- **Private signing links** that expire after 15 days by default, with an identity check on the last 4 digits of the signer's phone; the link locks after 5 wrong tries
- Readable error messages you can show to signers

Built from the signing flow Hexaspace uses with clients on real projects.

**Important:** this is a simple electronic acceptance, not an Aadhaar eSign or a digital signature certificate (DSC). Check what level of signature your documents legally need.

## Install

```bash
pip install lite-esign
```

## Example

```python
from lite_esign import make_record, certificate_pdf, stamp_pdf

record = make_record(kind="boq", title="Kitchen BOQ v2", content=boq_dict,
                     name="Asha Patel", agreed=True, drawn=png_data_url,
                     ip=request_ip, user_agent=ua, summary=[["Total", "Rs 4,85,000"]])
save(record)                                              # your database

cert = certificate_pdf(record, brand="Your Company")      # bytes
signed = stamp_pdf(original_pdf, cert, f"Signed by {record['signer']['name']}")
```

## Licence

MIT. Maintained by [Hexaspace](https://hexaspace.in).
