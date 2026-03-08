from __future__ import annotations

import argparse
from uuid import UUID

from db import get_conn
from token_utils import generate_form_token


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a signed form URL for local testing.")
    parser.add_argument("--session-id", help="Session UUID")
    parser.add_argument("--player-id", help="Player UUID")
    parser.add_argument("--base-url", default="http://127.0.0.1:5173/golf-form", help="Frontend form URL")
    args = parser.parse_args()

    if args.session_id and args.player_id:
        session_id = UUID(args.session_id)
        player_id = UUID(args.player_id)
    else:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT session_id, player_id
                    FROM session_players
                    ORDER BY invited_at DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
        if not row:
            raise SystemExit("No rows found in session_players. Create a session and invite first.")
        session_id = row["session_id"]
        player_id = row["player_id"]

    token = generate_form_token(str(session_id), str(player_id))
    print(f"token={token}")
    print(f"form_url={args.base_url}?token={token}")


if __name__ == "__main__":
    main()
