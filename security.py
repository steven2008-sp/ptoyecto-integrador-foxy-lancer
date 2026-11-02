import hashlib
import hmac
import os
import re

_ITERATIONS = 310_000

_PASSWORD_STRENGTH_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,128}$")


def validar_fortaleza_password(password: str) -> str:
    """Valida que la contraseña tenga al menos 8 caracteres, una mayúscula, una minúscula y un número."""
    if not _PASSWORD_STRENGTH_RE.match(password or ""):
        raise ValueError("La contraseña debe tener al menos 8 caracteres, incluyendo una mayúscula, una minúscula y un número.")
    return password


def hash_password(password):
    password = validar_fortaleza_password(password)
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"

def verify_password(password, stored):
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
        return hmac.compare_digest(actual, digest_hex)
    except (ValueError, TypeError):
        return False
