# Reusable Codex Prompts

Use these to start sessions quickly while enforcing project standards.

## 1) Autonomous Progress (Default)
```text
Use golf-agent-production-shipping.
Work autonomously on /Users/wilfredtso/golf-agent for the next 2 hours.
Prioritize highest-impact TODOs toward demo readiness.
After each meaningful change:
- run appropriate tests,
- update project.md and todo.md,
- commit to main with clear messages,
- push to GitHub.
Do not wait for approval unless blocked by missing credentials, destructive actions, or ambiguous product decisions.
At the end, provide a concise handoff with what changed, test results, deploy impact, and next 3 tasks.
```

## 2) One-Hour Demo Sprint
```text
Use golf-agent-production-shipping.
You have 1 hour to maximize demo readiness in /Users/wilfredtso/golf-agent.
Goal: produce a repeatable backend demo flow with clear commands and expected outputs.
Requirements:
- verify backend health and key endpoints,
- run demo flow script(s),
- ensure tests for changed areas pass,
- update project.md and todo.md with exact status,
- commit and push.
End with a demo runbook I can execute in 5 minutes.
```

## 3) Docs + Cleanup Only
```text
Use golf-agent-production-shipping.
Perform docs/cleanup only in /Users/wilfredtso/golf-agent.
Find and fix documentation drift after recent code/file/path changes.
Requirements:
- search for stale references with rg,
- realign docs to runtime architecture,
- verify deleted files are not referenced by runtime/tests,
- run minimal validation checks,
- update project.md and todo.md.
Mark runtime impact clearly as: none.
Commit and push with subject: Docs cleanup: <what was realigned>.
```

## 4) Pre-Deploy Hardening Pass
```text
Use golf-agent-production-shipping.
Prepare /Users/wilfredtso/golf-agent for deploy.
Run risk-based test gates, verify env/schema assumptions, and confirm health checks.
If you find issues, fix them and re-run checks.
Update project.md and todo.md, then commit and push.
Finish with:
1) deploy-ready yes/no,
2) blocking risks,
3) exact deploy/verify commands.
```
