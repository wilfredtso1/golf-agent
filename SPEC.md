# Context Prompt: Golf Tee Time Coordination Agent

## Who I Am
I'm a product leader (PM/COO background, not a professional developer) learning to code. I'm building this project to develop hands-on technical skills with AI agent architecture. I'm comfortable with product and architecture thinking but need guidance on implementation. I'll be using Claude Code for planning and building, so I need clean architecture and clear module boundaries.

Help me plan, architect, and build this project. Start by helping me finalize architecture decisions before writing any code. Ask me questions if anything is ambiguous. Bias toward simple, working solutions over elegant abstractions — I'd rather ship something rough that works end-to-end than build a perfect module that never connects.

**This needs to be buildable in one weekend.** Flag anything that's over-scoped.

## What I'm Building
An AI agent that coordinates golf tee times for a group of friends via SMS. The agent uses a **hub-and-spoke model**: it sits at the center and communicates with each player individually via Twilio SMS. There is no programmatic group chat — the agent simulates group coordination by broadcasting relevant updates to all active players in a session.

### How It Works

**Step 1: Lead triggers a session.**
The lead texts the agent something like: "Set up a round this Saturday. Invite Dave, Mike, and Joe. Check Bethpage, Marine Park, and Dyker Beach."

For **returning players**, the agent resolves names via the LLM. On every trigger, the full player roster from Supabase is injected into the LLM context (e.g., "Known players: David Chen (555-1234), Mike Ross (555-5678), Joe Park (555-9012)"). The LLM resolves "Dave" → David Chen, "Mike" → Mike Ross, etc. If a name is ambiguous (two Davids), the agent asks the lead to clarify. No phone number needed after the first invite.

For **first-time players**, the lead must provide a phone number: "Also invite Tom, his number is 555-3333." The agent creates a new player record.

The agent parses this, creates a session in Supabase, and moves to outreach.

**Step 2: Agent sends each player a form link.**
Each invited player receives an individual SMS:
"Hey Dave, this is [Agent Name] — an AI assistant helping [Lead] set up a golf round this Saturday. Pick what works for you: [form link]"

Each session carries a short numeric session code (2-4 digits, currently 4 digits) included in invite/follow-up messages to disambiguate replies if a player is part of multiple active sessions.

The form is a simple web page (hosted as a static page, one per session) with:
- "Are you in?" (Yes / No)
- Checkboxes for the candidate courses the lead specified (e.g., Bethpage, Marine Park, Dyker Beach)
- Checkboxes for time slots: Early Morning (8–10 AM), Late Morning (10 AM–12 PM), Early Afternoon (12–2 PM)

If the player is new (first time interacting with the agent), the form also collects standing profile info: name, general availability patterns, courses they generally like. This profile persists across future sessions.

The form submits to backend endpoints (`/api/form-context`, `/api/form-response`) and the backend persists to Supabase. No NLP needed for the structured preference collection — the form handles it cleanly.

**Step 3: Agent intersects and proposes.**
As form responses come in, the agent runs the policy engine:
- Availability intersection: find time blocks where ALL confirmed players are available
- Course intersection: find courses ALL confirmed players approved
- If no overlap exists, the agent texts the lead with the conflict and options

Once there's a valid intersection (and minimum 2 confirmed players), the agent searches for available tee times and proposes options — texting the lead:
"Found 3 options that work for everyone:
1. Bethpage, Sat 10:20 AM — $72/player
2. Bethpage, Sat 10:50 AM — $72/player
3. Marine Park, Sat 11:00 AM — $45/player
Which one?"

**Step 4: Lead picks, agent broadcasts and hands off.**
Lead replies with their pick. Agent texts all confirmed players:
"Locked in: Marine Park, Saturday 11:00 AM. [Lead] is booking now."

Agent texts the lead the booking URL:
"Book here for 3 players: [link]"

The lead completes the purchase themselves. The agent handles all coordination; the human handles payment.

**Step 5: Session closes.**

### Post-Form Conversational Layer
After the form submission, players can continue texting the agent to adjust their responses, ask questions, or update preferences. The agent handles natural language from this point:
- "Actually, I can't do early morning anymore" → agent updates their session availability, re-runs intersection
- "Is Bethpage expensive?" → agent answers from session context
- "I'm out, something came up" → agent marks them as declined, re-runs intersection, notifies the group
- "Can you add my buddy Tom? His number is 555-3333" → agent texts the lead for approval (only the lead can add people), then invites Tom if approved

The lead can also text adjustments:
- "Add Tom (555-3333)" → agent invites Tom, sends him the form
- "Drop Bethpage, add Dyker Beach" → agent updates candidate courses, may need to re-poll if someone only approved Bethpage
- "Let's move to Sunday instead" → agent resets the session date, re-polls everyone

The agent broadcasts relevant changes to all active players: "Heads up — the date moved to Sunday. Does your availability still work? Reply here or update the form: [link]"

## Architecture Principles
I'm designing this agent to showcase specific patterns from enterprise AI agent architecture. These matter as much as the feature set.

### Deterministic Action Gates
The agent can reason, suggest, and coordinate freely. The irreversible commitment is booking selection, which requires explicit lead confirmation in code (`CONFIRM <n>`). The LLM cannot bypass this gate.

Session-management commands (add/remove player, date/course updates) are lead-authorized but execute immediately to reduce coordination friction.

### Policy Enforcement in Code
Hard rules enforced deterministically, not via prompt instructions:

| Policy | Rule | Enforcement |
|--------|------|-------------|
| Minimum group size | At least 2 confirmed players to proceed to search | Code checks before search step |
| Course intersection | Only propose courses ALL confirmed players approved | SQL intersection on session_players.approved_courses |
| Availability intersection | Only propose slots where ALL confirmed players are available | SQL intersection on session_players.available_time_blocks |
| Response deadline | Remind at 4 hours, escalate to lead at 8 hours | Background cron job |
| Lead approval for adds | Only the lead can add/remove players | Code checks lead_player_id before executing |
| No autonomous booking | Agent sends booking URL to lead, never books directly | Booking tool returns URL only |

These rules live in a policy engine module, not in the system prompt. The LLM is told the policies exist but the code enforces them.

### Tool Call Architecture
The agent interacts with external systems through well-defined tool interfaces:

```
search_tee_times(date, time_window, courses, group_size)
  → returns available slots with booking_url for each

get_player_profile(player_id)
  → retrieves standing preferences and profile

update_player_profile(player_id, updates)
  → updates standing preferences

get_session_state(session_id)
  → returns full session context: players, responses, intersection results, status

update_session_player(session_id, player_id, updates)
  → updates a player's session-specific responses (availability, courses, status)

add_player_to_session(session_id, phone, name)
  → lead-authorized session update; invites new player immediately

broadcast_message(session_id, message)
  → sends a message to all active players in the session

send_message(player_id, message)
  → sends a message to a specific player
```

The LLM decides WHEN to call these tools. The tools themselves are deterministic.

### Escalation Logic
When the agent can't resolve something autonomously, it escalates clearly:
- **No overlap in preferences** → texts the lead with the specific conflict and options
- **Unresponsive player** → reminder at 4 hours (clearly from AI, not the lead), escalation to lead at 8 hours with `PROCEED WITHOUT THEM` option
- **No available tee times** → tells the lead, suggests alternatives (different date, time, courses)
- **Ambiguous text messages** → asks for clarification rather than guessing
- **Multiple active sessions for same phone** → asks user to route with session code (e.g., `0421: late morning works`) and accepts a code-only message (e.g., `0421`) to set active routing context for follow-up replies while that session stays active
- **Player requests something outside scope** → "I can help with coordinating tee times — for anything else you'd want to text [Lead] directly"

## Memory and State Architecture
All state is structured data in Supabase. This is NOT RAG — we query by player_id and session_id, not by semantic similarity. Context is injected into each LLM call via structured database queries.

Each LLM call includes:
- **System prompt** (static): personality, tool definitions, policy awareness
- **Session context** (dynamic): current session state, all player responses so far, intersection results
- **Player context** (dynamic): this specific player's profile and session responses
- **Recent messages** (dynamic): last 10 messages in this player's conversation for multi-turn coherence
- **Current inbound message**

## Tech Stack

### Messaging: Twilio SMS
Individual SMS channels between the agent and each player. Hub-and-spoke: agent is the center, broadcasts group-relevant updates to all active players. Players text the agent individually.

### Form: Static Frontend App
One form page per session, hosted as a static frontend app. URL includes a signed `token` query param that encodes session/player identity and is verified server-side.

Tech: frontend app (`form-design`) calls backend endpoints (`/api/form-context`, `/api/form-response`). The server validates token + payload and writes to Supabase using the service role key. This keeps all database writes going through the server — no direct client-to-Supabase access, no RLS required for form writes, and consistent with the "policy enforcement in code" principle.

The form page shows:
- "Are you in for [date]?" — Yes / No
- Course options (checkboxes) — populated from the session's candidate_courses
- Time slots (checkboxes) — Early Morning / Late Morning / Early Afternoon
- For new players only: name field and general availability/course preferences for their standing profile
- Submit button

After submission, a simple confirmation: "You're locked in. [Lead] will get back to you once everyone responds. You can text [agent number] if anything changes."

### Booking API: Mocked for v1
Mock API returns realistic tee time results with booking_url. This lets us build the full coordination flow without being blocked on API access.

### Database: Supabase (Postgres)

```sql
-- Players: standing profiles that persist across sessions
CREATE TABLE players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  phone TEXT UNIQUE NOT NULL,
  general_availability JSONB DEFAULT '[]',  -- e.g., ["early_morning", "late_morning"]
  course_preferences JSONB DEFAULT '[]',    -- standing course list
  standing_constraints TEXT,                 -- free text: "never on Sundays"
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Sessions: one per coordination round
CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_player_id UUID REFERENCES players(id),
  target_date DATE NOT NULL,
  candidate_courses JSONB NOT NULL,         -- ["Bethpage", "Marine Park"]
  session_code TEXT,                         -- short code for multi-session SMS routing
  status TEXT DEFAULT 'collecting',         -- collecting | searching | proposing | confirmed | closed | expired
  form_url TEXT,                            -- URL to the form for this session
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Session players: per-player responses within a session
CREATE TABLE session_players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES sessions(id),
  player_id UUID REFERENCES players(id),
  status TEXT DEFAULT 'invited',            -- invited | confirmed | declined | unresponsive
  available_time_blocks JSONB DEFAULT '[]', -- ["early_morning", "late_morning"]
  approved_courses JSONB DEFAULT '[]',      -- ["Bethpage", "Marine Park"]
  invited_at TIMESTAMPTZ DEFAULT now(),
  responded_at TIMESTAMPTZ,
  reminder_sent_at TIMESTAMPTZ,
  UNIQUE(session_id, player_id)
);

-- Tee time proposals: options found and proposed to lead
CREATE TABLE tee_time_proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES sessions(id),
  course TEXT NOT NULL,
  tee_time TIMESTAMPTZ NOT NULL,
  price_per_player NUMERIC,
  booking_url TEXT,
  status TEXT DEFAULT 'proposed',           -- proposed | selected | expired
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Messages: conversation log per player per session
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES sessions(id),
  player_id UUID REFERENCES players(id),
  direction TEXT NOT NULL,                  -- inbound | outbound
  body TEXT NOT NULL,
  provider_message_sid TEXT,                -- Twilio SID for idempotency
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Protect against active session-code collisions:
-- enforce uniqueness only while sessions are active.
CREATE UNIQUE INDEX uq_sessions_active_session_code
  ON sessions(session_code)
  WHERE session_code IS NOT NULL
    AND status IN ('collecting', 'searching', 'proposing');
```

### LLM: OpenAI (GPT-4o) via API
System prompt defines personality, tool interfaces, and policy awareness. Policies are referenced but enforced in code.

### Deployment: Railway
Simplest option for a webhook server + cron job. FastAPI app deployed via Dockerfile or Nixpack. Supabase is external (managed). Environment variables for all API keys.

### Language: Python (FastAPI)
Keep it straightforward. Clear functions, clear flow. No complex abstractions. I'm learning Python.

## Project Structure

```
golf-agent/
├── main.py                  # FastAPI app, Twilio webhook + API endpoints
├── agent.py                 # Core agent loop and lead/player command handling
├── tools.py                 # DB/state tools and session transition helpers
├── booking_provider.py      # Tee-time provider selector (mock vs golfnow)
├── golfnow_adapter.py       # GolfNow adapter scaffold (shared-catalog mapped)
├── course_semantic.py       # Semantic course matching over shared catalog
├── policy_engine.py         # Deterministic policy checks (intersection, min group, deadlines)
├── context_builder.py       # Builds LLM context from DB state
├── llm.py                   # LLM parsing helper (JSON mode)
├── twilio_helpers.py        # Send SMS, parse inbound messages
├── reminders.py             # Background job for 4hr/8hr deadline checks
├── scripts/                 # Demo + deploy helper scripts
├── form-design/             # Frontend form app
├── tests/                   # Unit + DB-backed integration/eval coverage
├── schema.sql               # Postgres schema
└── requirements.txt
```

## Weekend Build Plan

### Saturday Morning: Foundation (4 hours)
1. Create Supabase project, run schema.sql
2. Set up Twilio account, get phone number, configure webhook URL (use ngrok for local dev)
3. Scaffold FastAPI app with Twilio webhook endpoint
4. Test: text the number, get an echo response back
5. Build the form page: static frontend with checkboxes, submits to backend form endpoints
6. Test: open form in browser, submit, verify data lands in Supabase

### Saturday Afternoon: Agent Loop (4 hours)
7. Build context_builder.py: given inbound message + player_id + session_id, query Supabase and assemble the LLM prompt
8. Build agent.py: system prompt + injected context + inbound message → OpenAI API call → parse response
9. Define tools in tools.py with mock implementations
10. Wire it up: inbound SMS → identify player and session → build context → call OpenAI → parse tool calls → execute → send response
11. Test: text the agent, have a basic back-and-forth conversation

### Saturday Evening: Session Flow (3 hours)
12. Implement lead trigger: parse intent from lead's first message, create session in Supabase, generate form URL
13. Implement player outreach: agent sends SMS with form link to each invited player
14. Implement form webhook/polling: when form responses arrive, update session_players
15. Implement policy engine: intersection logic for availability and courses
16. Test: trigger a session as lead, submit forms as players, verify intersection works

### Sunday Morning: Proposal and Handoff (4 hours)
17. Implement tee time search (mock API) triggered when policy engine finds valid intersection
18. Implement proposal flow: agent texts lead with options
19. Implement lead selection: lead picks, agent broadcasts confirmation to all players
20. Implement booking URL handoff to lead
21. Test: full end-to-end flow from trigger to booking handoff

### Sunday Afternoon: Edge Cases and Deploy (4 hours)
22. Implement conversational adjustments: player changes availability via text, agent re-runs intersection
23. Implement "add player" flow with lead authorization and immediate execution
24. Implement reminder cron job (4hr reminder, 8hr escalation to lead)
25. Handle: player declines, no overlap found, no tee times available
26. Deploy to Railway
27. Test end-to-end with real phones on deployed version

## Agent Personality and Tone
- Always identifies itself as an AI agent helping [Lead Name] coordinate — never pretends to be the lead
- Casual but efficient: "Found 3 options for Saturday — here's what fits everyone"
- Brief — these are text messages
- Proactive: flags conflicts and suggests alternatives without being asked
- Honest: "Couldn't find anything before noon at Bethpage — want me to check afternoon?"
- Reminders are clearly from the AI: "Hey, this is [Agent Name] again — [Lead] is trying to lock down Saturday and I need your availability. Takes 30 seconds: [form link]"

## Interview Framing
When I discuss this project in interviews, I want to be able to say:

"I built a multi-user coordination agent over SMS that manages golf tee times. The lead triggers a session, the agent reaches out to each player with a structured form for preferences, runs a policy engine to find the intersection of everyone's availability and course approvals, proposes options, and hands off a booking link once confirmed.

What's interesting architecturally is that the core design patterns are identical to enterprise customer support agents: deterministic high-risk action gating (booking confirmation), a policy engine enforced in code rather than prompt instructions, structured tool call interfaces for external system integration, a form-based intake for reliable structured data collection with conversational flexibility layered on top, escalation logic for unresolvable conflicts, and hub-and-spoke messaging that simulates group coordination through individual channels. The domain is fun, but the architecture is serious."
