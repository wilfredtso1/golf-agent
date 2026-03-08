from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from config import SETTINGS


class InvalidFormToken(ValueError):
    pass



def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")



def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)



def generate_form_token(session_id: str, player_id: str, ttl_seconds: int | None = None) -> str:
    now = int(time.time())
    exp = now + (ttl_seconds or SETTINGS.form_token_ttl_seconds)
    payload = {"session_id": session_id, "player_id": player_id, "exp": exp}
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = _b64url_encode(payload_json.encode("utf-8"))

    signature = hmac.new(
        SETTINGS.form_token_secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{payload_b64}.{signature_b64}"



def verify_form_token(token: str) -> dict[str, Any]:
    try:
        payload_b64, signature_b64 = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise InvalidFormToken("Token format is invalid") from exc

    expected_signature = hmac.new(
        SETTINGS.form_token_secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise InvalidFormToken("Token signature mismatch")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidFormToken("Token payload is invalid") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise InvalidFormToken("Token has expired")

    if not payload.get("session_id") or not payload.get("player_id"):
        raise InvalidFormToken("Token missing required fields")

    return payload
