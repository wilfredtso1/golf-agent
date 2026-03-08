from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Post a fake inbound SMS to the local dev endpoint")
    parser.add_argument("--from-number", required=True, help="Sender phone number (any common format)")
    parser.add_argument("--body", default="", help="SMS body text")
    parser.add_argument("--url", default="http://127.0.0.1:8010/dev/simulate-sms", help="Dev endpoint URL")
    args = parser.parse_args()

    payload = {"from_number": args.from_number, "body": args.body}
    data = json.dumps(payload).encode("utf-8")
    req = Request(args.url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Request failed: HTTP {exc.code} {exc.reason}\n{body}") from exc
    except URLError as exc:
        raise SystemExit(f"Request failed: {exc}") from exc

    print(text)


if __name__ == "__main__":
    main()
