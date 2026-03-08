from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen


def _health_check(base_url: str) -> tuple[bool, str]:
    url = f"{base_url}/health"
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
        ok = '"status":"ok"' in body.replace(" ", "")
        return ok, body
    except URLError as exc:
        return False, str(exc)


def _courses_check(base_url: str) -> tuple[bool, str]:
    url = f"{base_url}/api/courses?limit=5"
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        ok = bool(payload.get("ok")) and int(payload.get("count", 0)) >= 1
        return ok, f"count={payload.get('count', 0)}"
    except Exception as exc:
        return False, str(exc)


def _demo_flow_check(base_url: str) -> tuple[bool, str]:
    cmd = [sys.executable, "dev_demo_flow.py", "--base-url", base_url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    ok = proc.returncode == 0 and "DEMO_FLOW_OK" in output and "final_session_status=confirmed" in output
    return ok, output.strip()


def run_report(base_url: str) -> dict[str, object]:
    checks = []

    health_ok, health_detail = _health_check(base_url)
    checks.append({"name": "health", "ok": health_ok, "detail": health_detail})

    demo_ok, demo_detail = _demo_flow_check(base_url)
    checks.append({"name": "demo_flow", "ok": demo_ok, "detail": demo_detail})

    courses_ok, courses_detail = _courses_check(base_url)
    checks.append({"name": "courses", "ok": courses_ok, "detail": courses_detail})

    overall_ok = all(item["ok"] for item in checks)
    return {
        "ok": overall_ok,
        "base_url": base_url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a demo-readiness report against Golf Agent backend")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="Backend base URL")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    report = run_report(args.base_url.rstrip("/"))
    if args.pretty:
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
