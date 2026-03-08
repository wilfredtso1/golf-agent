# Golf Agent Form (Current Architecture)

## Source of Truth
- Frontend app: `form-design/src`
- App route: `/golf-form`
- Backend endpoints:
  - `GET /api/form-context?token=...`
  - `POST /api/form-response`

The legacy root file `form/index.html` is no longer used.

## Runtime Flow
1. A signed token is generated server-side (see `dev_generate_form_link.py`).
2. User opens `https://<frontend>/golf-form?token=<signed-token>`.
3. Frontend fetches `/api/form-context` to render invite/session data.
4. Frontend submits choices to `/api/form-response`.
5. Backend validates token and persists data in Postgres/Supabase.

## Local Development
From `form-design/`:

```bash
bun install
bun run dev
```

Set API base URL for frontend:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8010
```

Run backend separately:

```bash
python3 -m uvicorn main:app --host 127.0.0.1 --port 8010
```

Generate a test URL token from repo root:

```bash
python3 dev_generate_form_link.py --base-url http://127.0.0.1:5173/golf-form
```

## Key Files
- `src/components/GolfSessionForm.tsx`: token parsing, context fetch, submission.
- `src/App.tsx`: route wiring (`/golf-form`).
- `README.md`: frontend run/build commands.
