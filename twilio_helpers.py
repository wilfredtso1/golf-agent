from __future__ import annotations

import hashlib
import hmac
import re
from uuid import uuid4
from typing import Mapping

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from config import SETTINGS

_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


class InvalidPhoneNumber(ValueError):
    pass



def normalize_phone(raw_phone: str) -> str:
    digits = re.sub(r"\D", "", raw_phone)

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        normalized = f"+1{digits}"
    elif 8 <= len(digits) <= 15:
        normalized = f"+{digits}"
    else:
        raise InvalidPhoneNumber(f"Unsupported phone number: {raw_phone}")

    if not _E164_PATTERN.match(normalized):
        raise InvalidPhoneNumber(f"Phone number is not valid E.164: {raw_phone}")
    return normalized



def validate_twilio_signature(url: str, form_data: Mapping[str, str], signature: str | None) -> bool:
    if not signature:
        return False
    validator = RequestValidator(SETTINGS.twilio_auth_token)
    return validator.validate(url, dict(form_data), signature)



def constant_time_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))



def sha256_hexdigest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def send_sms(to_number: str, body: str) -> str:
    if not SETTINGS.sms_send_enabled:
        return f"dryrun-{uuid4().hex[:12]}"
    if not SETTINGS.twilio_account_sid:
        raise RuntimeError("TWILIO_ACCOUNT_SID is required to send SMS invites")
    client = Client(SETTINGS.twilio_account_sid, SETTINGS.twilio_auth_token)
    message = client.messages.create(
        from_=SETTINGS.twilio_phone_number,
        to=to_number,
        body=body,
    )
    return str(message.sid)
