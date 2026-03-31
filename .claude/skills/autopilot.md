---
name: autopilot
description: Start Ralph Loop to autonomously build BAKY MVP. Reads roadmap, implements issues with TDD, validates with e2e tests, and merges automatically.
user-invokable: true
argument-hint: "[optional: --bootstrap to check Phase 0, --resume to continue, --status to check progress]"
---

# BAKY Autopilot

## Pre-Flight Checklist

Before starting Ralph, verify:

```bash
# 1. Docker is running
docker info > /dev/null 2>&1 && echo "Docker: OK" || echo "Docker: NOT RUNNING - start Docker Desktop first"

# 2. Ralph CLI is installed
which ralph && echo "Ralph: OK" || echo "Ralph: NOT FOUND - install from github.com/frankbria/ralph-claude-code"

# 3. GitHub CLI is authenticated
gh auth status 2>&1 | head -3

# 4. We're on main branch, clean state
echo "Branch: $(git branch --show-current)"
echo "Status: $(git status --short | wc -l | tr -d ' ') uncommitted files"
```

If anything fails, fix it before proceeding.

## Phase 0: Bootstrap Check

The bootstrap must be done BEFORE Ralph can autopilot. It creates the test infrastructure
Ralph needs to validate its own work.

Check if bootstrap is complete:
```bash
# Bootstrap is complete when ALL of these work:
make up 2>/dev/null && echo "1. Docker: OK"
make test 2>/dev/null && echo "2. Tests: OK"
make lint 2>/dev/null && echo "3. Lint: OK"
test -f tests/e2e/conftest.py && echo "4. E2E framework: OK"
```

If bootstrap is NOT complete, tell the user:

"Bootstrap (Phase 0) is required before autopilot can run. This sets up Django, Docker, tests, and e2e validation. The following issues must be completed first:
- #1 Django project initialization
- #29 Environment and secrets management
- #3 Docker development environment
- #5 Testing infrastructure
- Plus: e2e framework setup (pytest-playwright)

You can build these manually or use `/ce:work` on each issue. Once `make test` and `make lint` pass inside Docker, autopilot is ready."

## Phase 1: Start Autopilot

Once bootstrap is confirmed:

```bash
/ralph-loop "$(cat .ralph/PROMPT.md)" --max-iterations 100 --completion-promise "MVP_COMPLETE"
```

This starts the Ralph Loop which will autonomously:
1. Assess current state (git branch, uncommitted work)
2. Complete any in-progress feature
3. Pick next unblocked issue from roadmap #44
4. Implement with TDD
5. Run full validation (tests + lint + e2e)
6. Merge to main, close issue, update roadmap
7. Repeat until all MVP issues are closed

## Monitoring

In a separate terminal:
```bash
# Watch Ralph's progress
ralph --status

# Live monitoring dashboard (tmux 3-pane)
ralph --monitor

# Tail logs
tail -f .ralph/logs/ralph.log
```

## Circuit Breaker

Ralph will automatically pause if:
- 5 iterations with no file changes (stuck)
- 5 iterations with same error (loop)
- Output quality drops >70% (degrading)

When paused:
1. Review logs: `ls -la .ralph/logs/`
2. Check circuit: `ralph --circuit-status`
3. Either fix the issue manually and restart: `ralph --reset-circuit`
4. Or cancel: `/cancel-ralph`

## Resume After Pause

```bash
# Check where we left off
cat .ralph/fix_plan.md | grep "- \[ \]" | head -5
ralph --circuit-status

# Reset and restart
ralph --reset-circuit
/ralph-loop "$(cat .ralph/PROMPT.md)" --max-iterations 100 --completion-promise "MVP_COMPLETE"
```

## Emergency Stop

```bash
/cancel-ralph
```
This removes the Ralph state file and stops the loop immediately.
