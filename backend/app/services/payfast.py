"""PayFast hosted checkout helpers.

The application never handles card numbers. Payments are confirmed only after
signature validation and PayFast's server-to-server ITN validation response.
"""
import hashlib
import hmac
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def signature(fields: list[tuple[str, str]], passphrase: str = "") -> str:
    parts = [
        f"{key}={urlencode({'v': value.strip()})[2:]}"
        for key, value in fields
        if value is not None and str(value).strip() != "" and key != "signature"
    ]
    if passphrase:
        parts.append(f"passphrase={urlencode({'v': passphrase.strip()})[2:]}")
    return hashlib.md5("&".join(parts).encode("utf-8")).hexdigest()


def valid_signature(fields: list[tuple[str, str]], supplied: str, passphrase: str = "") -> bool:
    expected = signature(fields, passphrase)
    return bool(supplied) and hmac.compare_digest(expected, supplied.lower())


def validate_itn(fields: list[tuple[str, str]], *, sandbox: bool) -> bool:
    """Ask PayFast to validate the exact notification server-to-server."""
    endpoint = (
        "https://sandbox.payfast.co.za/eng/query/validate"
        if sandbox
        else "https://www.payfast.co.za/eng/query/validate"
    )
    body = urlencode(fields).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status == 200 and response.read(64).decode("utf-8").strip() == "VALID"
    except Exception:
        return False


def checkout_url(*, sandbox: bool) -> str:
    return (
        "https://sandbox.payfast.co.za/eng/process"
        if sandbox
        else "https://www.payfast.co.za/eng/process"
    )
