# Outstanding Product Decisions

Decisions not yet made or explicitly unresolved in the current implementation. Answer these before a real launch.

---

## Session Lifecycle

**When does a session expire?**
The `expired` status exists but nothing sets it. Options: round date passes, N days idle, lead explicitly closes it.
- Decision needed: trigger condition + what happens to players when it fires

**When does a session close?**
The `closed` status exists but nothing sets it.
- Decision needed: is this manual (lead closes) or automatic (post-confirmation after N hours)?

**What happens after confirmed?**
Session locks, lead gets a booking URL, players get a broadcast. Then nothing. No follow-up.
- Decision needed: does the agent check if the lead completed the booking? Day-before reminder to players? Or does the agent's job end at handoff?

**The `searching` status is never set.**
It exists in `ACTIVE_SESSION_STATUSES` and the schema but no code path writes it. Either remove it or decide what transition triggers it (e.g., between policy met and proposals returned).

---

## No-Overlap and No-Results Handling

**When there's no course or time overlap, the agent is vague.**
Current reply: "I see a conflict in course/time overlap right now. I flagged this for the lead."
- Decision needed: should the agent name the specific conflict? (e.g., "Dave only approved Bethpage but everyone else approved Marine Park") Should it suggest specific resolutions to the lead?

**When tee-time search returns empty, nothing happens.**
The agent replies "couldn't find matching tee times yet" to the player who triggered the search. The lead is not notified. No retry, no alternatives suggested.
- Decision needed: should the lead get a notification? Should the agent suggest trying a different date, time window, or courses?

---

## Player Re-Engagement

**Can a declined player change their mind?**
No explicit flow. If they text preferences after declining it may update them but there's no clean re-engagement path or confirmation back to the lead.
- Decision needed: yes or no, and if yes, what does the re-engagement flow look like?

**Can a confirmed player's preference change kill the overlap?**
If a confirmed player texts "actually I can't do late morning" after proposals are already generated, the policy re-runs. But there's no explicit "overlap lost" alert to the lead, and the proposals may now be invalid.
- Decision needed: what does the lead notification look like when a previously valid overlap breaks?

---

## Lead Trigger

**Session creation is API-only, not SMS.**
The spec envisioned the lead texting natural language to start a session. The current implementation requires an API call with a structured payload.
- Decision needed: is API-only acceptable permanently (e.g., triggered by a CRM or web form), or does SMS-based session creation need to be built?

---

## Proposals

**Can the lead request fresh proposals without changing anything?**
Currently proposals only regenerate when player responses change. There's no "show me other options" command.
- Decision needed: should there be a refresh command? What would it say?

**Can the lead see more than 3 options?**
Max results is hardcoded to 3. No command to request more.
- Decision needed: is 3 the right number? Should it be configurable per session?

---

## Notifications

**Is the lead notified when all players have responded, even before an overlap exists?**
Currently the lead only hears something when proposals are generated or a player declines. No "everyone's in, here's the overlap" message if the policy fires automatically.
- Decision needed: should the lead get a status update when the last outstanding response arrives?

**What do non-responding invited players receive when the session locks?**
Players with status `invited` (never responded) get the confirmation broadcast. Is that the right behavior or should they get a different message?
- Decision needed: different message for non-responders, or same broadcast as everyone else?

---

## Real Booking Provider

**GolfNow adapter always returns empty.**
`golfnow_adapter.py` is a placeholder — it logs and returns `[]`, so the mock always runs.
- Decision needed: what is the real provider strategy and timeline? Is mock acceptable for v1 launch?

---

## Confirmation Gate Inconsistency

**Date and course changes execute immediately despite the spec saying they require confirmation.**
The spec lists "changing the session date or course list" as actions requiring lead confirmation. The code executes them immediately with no second step (unlike tee-time selection which has the two-step CONFIRM gate).
- Decision needed: add a CONFIRM gate to date/course changes, or accept immediate execution as the intended behavior and update the spec?
