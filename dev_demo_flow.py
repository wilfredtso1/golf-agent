from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta

from courses import SEED_GOLF_COURSES
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _random_us_phone(prefix: str) -> str:
    return f"+1{prefix}{random.randint(1000000, 9999999)}"


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"POST {url} failed: HTTP {exc.code} {exc.reason}\n{body}") from exc
    except URLError as exc:
        raise SystemExit(f"POST {url} failed: {exc}") from exc


def _get_json(url: str, params: dict[str, str]) -> dict[str, object]:
    full_url = f"{url}?{urlencode(params)}"
    req = Request(full_url, method="GET")
    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GET {full_url} failed: HTTP {exc.code} {exc.reason}\n{body}") from exc
    except URLError as exc:
        raise SystemExit(f"GET {full_url} failed: {exc}") from exc


def run_demo(base_url: str, target_date: str | None, courses_csv: str) -> None:
    lead_phone = _random_us_phone("917")
    invite_phone = _random_us_phone("929")
    parsed_courses = [c.strip() for c in courses_csv.split(",") if c.strip()]
    if not parsed_courses:
        raise SystemExit("At least one course is required")

    demo_date = target_date or (date.today() + timedelta(days=7)).isoformat()

    lead_trigger_payload = {
        "lead_phone": lead_phone,
        "lead_name": "Demo Lead",
        "target_date": demo_date,
        "candidate_courses": parsed_courses,
        "invitees": [{"name": "Demo Dave", "phone": invite_phone}],
        "send_invites": False,
    }

    created = _post_json(f"{base_url}/api/lead-trigger", lead_trigger_payload)
    session_id = str(created["session_id"])

    invite_reply = _post_json(
        f"{base_url}/dev/simulate-sms",
        {"from_number": invite_phone, "body": f"late morning works, {parsed_courses[0].lower()}"},
    )

    mid_status = _get_json(f"{base_url}/api/session-status", {"session_id": session_id})

    lead_pick_reply = _post_json(
        f"{base_url}/dev/simulate-sms",
        {"from_number": lead_phone, "body": "1"},
    )

    lead_confirm_reply = _post_json(
        f"{base_url}/dev/simulate-sms",
        {"from_number": lead_phone, "body": "CONFIRM 1"},
    )

    final_status = _get_json(f"{base_url}/api/session-status", {"session_id": session_id})

    print("DEMO_FLOW_OK")
    print(f"base_url={base_url}")
    print(f"session_id={session_id}")
    print(f"lead_phone={lead_phone}")
    print(f"invite_phone={invite_phone}")
    print(f"invite_reply={invite_reply.get('reply_text')}")
    print(f"lead_pick_reply={lead_pick_reply.get('reply_text')}")
    print(f"lead_confirm_reply={lead_confirm_reply.get('reply_text')}")
    print(f"mid_session_status={mid_status.get('session', {}).get('status')}")
    print(f"final_session_status={final_status.get('session', {}).get('status')}")
    print(f"proposal_count={len(mid_status.get('proposals', []))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a full demo flow against the backend")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="Backend base URL")
    parser.add_argument("--target-date", default=None, help="YYYY-MM-DD (default: today+7)")
    parser.add_argument(
        "--courses",
        default=",".join(SEED_GOLF_COURSES),
        help="Comma-separated candidate courses",
    )
    args = parser.parse_args()

    run_demo(base_url=args.base_url.rstrip("/"), target_date=args.target_date, courses_csv=args.courses)
