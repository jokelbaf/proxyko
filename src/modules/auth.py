import pyotp


def verify_totp(secret: str, code: int | str) -> bool:
    """Verify a TOTP code against the given secret."""
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(str(code), valid_window=1)
    except Exception:
        return False
