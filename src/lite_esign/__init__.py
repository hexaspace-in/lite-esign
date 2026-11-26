"""lite-esign: simple electronic acceptance (typed name + I agree + optional drawn signature) with a certificate PDF."""
from .core import (KINDS, SignatureError, certificate_pdf, check_code, clean_drawn, fingerprint, fingerprint_file,
                   link_status, make_record, new_link, readable, stamp_pdf)

__version__ = "0.1.0"
__all__ = ["KINDS", "SignatureError", "certificate_pdf", "check_code", "clean_drawn", "fingerprint", "fingerprint_file",
           "link_status", "make_record", "new_link", "readable", "stamp_pdf"]
