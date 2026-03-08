from __future__ import annotations

import json
from typing import Any

import httpx

from config import SETTINGS


class LLMError(RuntimeError):
    pass


def has_llm_config() -> bool:
    return bool(SETTINGS.openai_api_key and SETTINGS.openai_model)


def parse_intent_with_llm(context: dict[str, object], inbound_body: str) -> dict[str, Any] | None:
    if not has_llm_config():
        return None

    session = context.get("session") or {}
    player = context.get("player") or {}
    candidate_courses = session.get("candidate_courses") or []

    system_prompt = (
        "You extract SMS intent for a golf coordination agent. "
        "Return strict JSON with keys: type, available_time_blocks, approved_courses, option_number. "
        "type must be one of: preferences, decline, select_option, none. "
        "Use only time block enums: early_morning, late_morning, early_afternoon."
    )

    user_prompt = {
        "message": inbound_body,
        "player_name": player.get("name"),
        "is_lead": player.get("is_lead", False),
        "candidate_courses": candidate_courses,
    }

    payload = {
        "model": SETTINGS.openai_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt)},
        ],
    }

    try:
        with httpx.Client(timeout=12) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {SETTINGS.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - network/provider failures
        raise LLMError(f"Failed to call OpenAI: {exc}") from exc

    body = resp.json()
    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if not content:
        return None

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    parsed.setdefault("type", "none")
    parsed.setdefault("available_time_blocks", [])
    parsed.setdefault("approved_courses", [])
    parsed.setdefault("option_number", None)
    return parsed
