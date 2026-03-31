# Ralph Autopilot Setup for BAKY

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Configure Ralph Loop to autonomously build the entire BAKY MVP by picking issues from the roadmap, implementing them with TDD, running e2e validation, and auto-merging to main.

**Architecture:** Two-phase approach. Phase 0 (Bootstrap) manually builds the foundation that Ralph needs: Django project, Docker, test infrastructure, seed framework, and e2e validation. Phase 1 (Autopilot) is Ralph Loop iterating through the roadmap issues autonomously with full validation between each feature.

**Tech Stack:** Ralph CLI + Claude Code, Django 5.x, Docker, pytest-django, pytest-playwright (e2e), factory_boy

---

## Task 1: Create Ralph Project Configuration

**Files:**
- Create: `.ralphrc`
- Create: `.ralph/AGENT.md`

**Step 1: Create `.ralphrc`**

```bash
cat > .ralphrc << 'RALPHRC'
# BAKY Ralph Configuration
PROJECT_NAME="baky"
PROJECT_TYPE="python"

# Claude Code
CLAUDE_CODE_CMD="claude"
CLAUDE_TIMEOUT_MINUTES=30
CLAUDE_OUTPUT_FORMAT="json"

# Rate limiting — conservative to avoid API limits
MAX_CALLS_PER_HOUR=60
MAX_TOKENS_PER_HOUR=0

# Tool permissions — Docker-first + GitHub CLI
ALLOWED_TOOLS="Write,Read,Edit,Bash(make *),Bash(docker compose *),Bash(git add *),Bash(git commit *),Bash(git diff *),Bash(git log *),Bash(git status),Bash(git status *),Bash(git push *),Bash(git pull *),Bash(git fetch *),Bash(git checkout *),Bash(git branch *),Bash(git stash *),Bash(git merge *),Bash(git tag *),Bash(gh issue *),Bash(gh pr *),Bash(gh api *),Bash(python manage.py *),Bash(pytest *),Bash(ls *),Bash(mkdir *),Bash(cat *)"

# Session management
SESSION_CONTINUITY=true
SESSION_EXPIRY_HOURS=48

# Circuit breaker — slightly generous for large features
CB_NO_PROGRESS_THRESHOLD=5
CB_SAME_ERROR_THRESHOLD=5
CB_OUTPUT_DECLINE_THRESHOLD=70
CB_PERMISSION_DENIAL_THRESHOLD=2
CB_COOLDOWN_MINUTES=15
CB_AUTO_RESET=false
RALPHRC
```

**Step 2: Create `.ralph/AGENT.md`**

```bash
cat > .ralph/AGENT.md << 'AGENTMD'
# BAKY Build & Test Commands

## Development (all via Docker)
- Start services: `make up`
- Stop services: `make down`
- Django migrations: `make migrate`
- Create migrations: `make makemigrations`
- Django shell: `make shell`
- Run any manage.py: `make manage CMD="<command>"`

## Testing
- Full test suite: `make test`
- Specific test: `make test ARGS="-k test_name"`
- E2E tests: `make e2e`
- Validation suite: `make validate`
- Lint: `make lint`

## Git & GitHub
- View roadmap: `gh issue view 44 -R robert197/baky`
- View issue: `gh issue view <N> -R robert197/baky`
- Close issue: `gh issue close <N> -R robert197/baky`
- Check issue state: `gh issue view <N> -R robert197/baky --json state -q .state`
AGENTMD
```

**Step 3: Verify files created**

```bash
cat .ralphrc
cat .ralph/AGENT.md
```

**Step 4: Commit**

```bash
git add .ralphrc .ralph/AGENT.md
git commit -m "chore: add Ralph configuration for autopilot development"
```

---

## Task 2: Create the Ralph PROMPT.md (Autopilot Brain)

**Files:**
- Create: `.ralph/PROMPT.md`

This is the most critical file — it's what Ralph reads every iteration.

**Step 1: Create the prompt file**

```bash
cat > .ralph/PROMPT.md << 'PROMPTMD'
# BAKY Autopilot — Ralph Development Loop

You are building BAKY, an apartment inspection platform for short-term rentals in Vienna.
This prompt runs in a loop. Each iteration, you wake up, assess where you are, and continue building.

## CRITICAL: Read This Every Iteration

1. Read CLAUDE.md for project conventions
2. Check git status to understand current state
3. Read the roadmap to find your next task

## Step 1: Assess Current State

```bash
# Where am I?
git branch --show-current
git status
git log --oneline -5

# Is Docker running? If not, start it.
docker compose ps 2>/dev/null || make up

# Are there uncommitted changes from a previous iteration?
# If yes: finish that work first (run tests, commit, merge).
```

## Step 2: Check if Current Feature Branch Has Work

If you're on a feature branch (not `main`):
1. Check if the feature is complete (all acceptance criteria met)
2. Run `make test` and `make lint`
3. If tests pass: merge to main and close the issue
4. If tests fail: fix them first

```bash
# Merge completed feature to main
branch=$(git branch --show-current)
if [ "$branch" != "main" ]; then
  # Extract issue number from branch name: feat/7-core-models -> 7
  issue_num=$(echo "$branch" | grep -oE '[0-9]+' | head -1)

  make lint
  make test

  # If both pass, merge
  git checkout main
  git pull origin main
  git merge "$branch" --no-edit
  git push origin main
  git branch -d "$branch"

  # Close issue and update roadmap
  gh issue close "$issue_num" -R robert197/baky
  # Check off in roadmap (issue #44)
fi
```

## Step 3: Pick the Next Issue from Roadmap

```bash
# Read the roadmap
gh issue view 44 -R robert197/baky
```

Parse the roadmap body. Find the first `- [ ]` item where ALL dependencies (issues after `←`) are closed.

To check if a dependency is closed:
```bash
gh issue view <number> -R robert197/baky --json state -q .state
# Returns "CLOSED" or "OPEN"
```

The first unchecked item with all dependencies CLOSED is your next task.

## Step 4: Read the Issue and Plan

```bash
gh issue view <number> -R robert197/baky
```

Read the full issue. Understand:
- What needs to be built
- Acceptance criteria (the checkboxes)
- Dependencies on other code

Create a feature branch:
```bash
git checkout main
git pull origin main
git checkout -b feat/<number>-<short-description>
```

## Step 5: Implement with TDD

For each piece of functionality:
1. **Write a failing test** first
2. **Run it** to confirm it fails: `make test ARGS="-k test_name"`
3. **Write minimal code** to make it pass
4. **Run tests** to confirm green: `make test`
5. **Commit** with conventional message: `feat(<scope>): description`

Follow CLAUDE.md conventions:
- All commands via `make` (Docker)
- Django patterns: fat models, thin views
- Tailwind CSS for styling
- HTMX for dynamic content
- Mobile-first design

## Step 6: Run Full Validation

Before declaring a feature complete:

```bash
# 1. Full test suite
make test

# 2. Linting
make lint

# 3. E2E validation (if UI features)
make e2e

# 4. Check Django deployment readiness
make manage CMD="check"
```

ALL must pass. If any fail, fix and re-run.

## Step 7: Complete the Feature

```bash
# Ensure on feature branch
git add -A
git status
git diff --staged

# Commit with issue reference
git commit -m "feat(<scope>): <description>

Closes #<issue_number>

Co-Authored-By: Claude <noreply@anthropic.com>"

# Merge to main
git checkout main
git pull origin main
git merge feat/<number>-<short-description> --no-edit
git push origin main
git branch -d feat/<number>-<short-description>

# Close issue
gh issue close <number> -R robert197/baky

# Update roadmap checkbox
# Read roadmap body, replace - [ ] #<number> with - [x] #<number>, update issue
```

## Step 8: Check Completion

After closing the issue, check: are ALL MVP issues closed?

```bash
gh issue list -R robert197/baky --milestone "MVP (Weeks 1-4)" --state open --json number -q 'length'
```

If 0 open issues remain: the MVP is complete.

Output: <promise>MVP_COMPLETE</promise>

Otherwise: go back to Step 1 for the next iteration.

## Rules

1. **Never skip tests.** Every feature must have passing tests before merge.
2. **Never merge failing code.** If tests fail, fix them.
3. **One issue per iteration.** Don't try to do multiple issues at once.
4. **Follow the roadmap order.** Don't jump ahead — dependencies matter.
5. **Docker for everything.** Never install Python or Node locally.
6. **Commit often.** Small, focused commits within each feature branch.
7. **German for UI, English for code.** Public-facing text in German.

## Completion Promise

When ALL MVP issues are closed and all tests pass:
<promise>MVP_COMPLETE</promise>

Only output this when it is genuinely true. Do not lie to exit the loop.
PROMPTMD
```

**Step 2: Verify**

```bash
wc -l .ralph/PROMPT.md
head -5 .ralph/PROMPT.md
```

**Step 3: Commit**

```bash
git add .ralph/PROMPT.md
git commit -m "chore: add Ralph PROMPT.md for autonomous development loop"
```

---

## Task 3: Create the Ralph Fix Plan (Derived from Roadmap)

**Files:**
- Create: `.ralph/fix_plan.md`

Ralph uses this as a checklist. When all items are checked, it knows to stop.

**Step 1: Create fix_plan.md**

```bash
cat > .ralph/fix_plan.md << 'FIXPLAN'
# BAKY MVP Build Plan

## Phase 1: Foundation
- [ ] #1 Initialize Django 5.x project with recommended stack
- [ ] #29 Set up environment and secrets management
- [ ] #3 Set up Docker development environment (everything runs in Docker)
- [ ] #2 Update CLAUDE.md with actual project paths after scaffolding
- [ ] #4 Configure linting, formatting, and pre-commit hooks
- [ ] #5 Set up testing infrastructure with pytest-django
- [ ] #43 Responsive base template and design system
- [ ] E2E: Set up pytest-playwright for end-to-end validation

## Phase 2: Data Layer
- [ ] #7 Implement core data models (Owner, Apartment, Inspection, etc.)
- [ ] #8 Set up Django authentication with role-based access control
- [ ] #30 Load default checklist template as Django fixture
- [ ] #10 Implement checklist template system with JSON schema
- [ ] #9 Configure S3/R2 file storage for photo uploads
- [ ] #11 Set up background task processing with Django-Q2
- [ ] #25 Implement security: encrypted fields, signed URLs, HSTS
- [ ] #12 Customize Django Admin with django-unfold
- [ ] SEED: Create comprehensive seed data for all models

## Phase 3: Public Website
- [ ] #13 Build public landing page with value proposition
- [ ] #14 Build pricing page
- [ ] #28 Build legal pages: Impressum, Datenschutz, AGB
- [ ] #15 Build owner signup and onboarding flow
- [ ] #42 Google Maps address autocomplete integration
- [ ] E2E: Public website validation (pages load, signup works)

## Phase 4: Inspector App
- [ ] #27 Build inspection scheduling system
- [ ] #19 Build inspector daily schedule view (mobile-optimized)
- [ ] #20 Build checklist execution interface with OK/Flag/N.A.
- [ ] #21 Build in-app photo capture per checklist item
- [ ] #22 Build inspection submission and report trigger flow
- [ ] E2E: Inspector workflow validation (schedule → checklist → submit)

## Phase 5: Reports & Notifications
- [ ] #23 Build automated report generation from inspection data
- [ ] #24 Implement email delivery for inspection reports
- [ ] E2E: Report generation and email delivery validation

## Phase 6: Owner Dashboard
- [ ] #16 Build owner dashboard - apartment list and management
- [ ] #17 Build inspection timeline and report detail view
- [ ] #18 Build subscription management for owners (basic MVP)
- [ ] E2E: Owner dashboard validation (view apartments, reports, timeline)

## Phase 7: Compliance & Launch
- [ ] #26 Implement GDPR compliance for inspection data and photos
- [ ] #40 Seed data and demo environment
- [ ] #6 Configure CI/CD pipeline with GitHub Actions
- [ ] #41 Production deployment configuration
- [ ] FINAL: Full E2E regression suite passes
FIXPLAN
```

**Step 2: Commit**

```bash
git add .ralph/fix_plan.md
git commit -m "chore: add Ralph fix_plan.md derived from roadmap #44"
```

---

## Task 4: Create E2E Validation Framework Specification

**Files:**
- Create: `.claude/skills/validate.md`

This skill defines the validation layer Ralph uses after each feature.

**Step 1: Create the validation skill**

```bash
cat > .claude/skills/validate.md << 'VALIDATEMD'
---
name: validate
description: Run the full BAKY validation suite — unit tests, linting, e2e tests, and Django checks. Use after completing any feature to ensure everything works.
user-invokable: true
argument-hint: "[optional: --quick for fast validation, --full for everything including e2e]"
---

# BAKY Validation Suite

## Quick Validation (default, ~30 seconds)

Run after every code change:

```bash
make lint
make test
make manage CMD="check"
```

All three must pass. If any fail, stop and fix.

## Full Validation (--full, ~2 minutes)

Run before merging a feature branch:

```bash
# 1. Lint
make lint

# 2. Unit + integration tests
make test

# 3. Django system checks
make manage CMD="check"

# 4. Migration check (no unapplied migrations)
make manage CMD="showmigrations" | grep -E "^\[.\]" | grep -v "\[X\]"
# Should return nothing (all migrations applied)

# 5. E2E browser tests (if UI changed)
make e2e

# 6. Check no secrets in code
grep -r "password\|secret\|api_key" --include="*.py" -l | grep -v test | grep -v example | grep -v settings
# Should return nothing (no hardcoded secrets)
```

## E2E Test Structure

E2E tests use pytest-playwright and validate complete user flows:

```
tests/e2e/
├── conftest.py          # Playwright fixtures, live server setup
├── test_public.py       # Public pages load, links work, signup flow
├── test_owner.py        # Owner login, dashboard, apartment management
├── test_inspector.py    # Inspector login, schedule, checklist, submit
├── test_reports.py      # Report generated after inspection, email sent
└── test_auth.py         # Login, logout, role separation, 404 on unauthorized
```

## E2E Test Conventions

- Tests run against Django's LiveServerTestCase (real server, real database)
- Seed data loaded before e2e tests via fixture or management command
- Each test class gets a fresh database state
- Tests are independent — no ordering dependency
- Mobile viewport (375x812) for inspector tests
- Desktop viewport (1280x720) for owner/public tests

## Validation Gates for Ralph Autopilot

Ralph MUST run validation at these gates:

| Gate | When | What to Run |
|------|------|-------------|
| Pre-merge | Before merging feature to main | Full validation |
| Post-merge | After merging to main | Quick validation (smoke test) |
| Phase complete | After finishing a roadmap phase | Full validation + e2e |

## What to Do When Validation Fails

1. **Lint fails**: Fix formatting/style issues, re-run
2. **Unit test fails**: Read the error, fix the code or test, re-run
3. **E2E fails**: Check if seed data is correct, check if UI matches selectors, fix
4. **Migration check fails**: Run `make migrate`
5. **Django check fails**: Read the warning, fix the configuration

NEVER merge to main with failing validation. NEVER skip validation to "save time".
VALIDATEMD
```

**Step 2: Commit**

```bash
git add .claude/skills/validate.md
git commit -m "feat: add validation skill for Ralph autopilot quality gates"
```

---

## Task 5: Create Seed Data Infrastructure Specification

**Files:**
- Create: `.claude/skills/seed-strategy.md`

**Step 1: Create seed strategy skill**

This defines how seed data evolves as features are built — critical for e2e tests.

```bash
cat > .claude/skills/seed-strategy.md << 'SEEDMD'
---
name: seed-strategy
description: Reference for BAKY's seed data strategy. Seed data grows incrementally as features are built, enabling e2e validation at every stage.
user-invokable: true
---

# BAKY Seed Data Strategy

## Principle: Seeds Grow With Features

Seed data is NOT a one-time dump at the end. Each feature adds the seeds it needs, and ALL previous seeds remain valid. This ensures e2e tests work at every stage.

## Seed Layers

Seeds are organized in layers that build on each other:

### Layer 0: Users & Auth (added with #8)
```python
# management/commands/seed_users.py
SEED_USERS = {
    "admin": {"email": "admin@baky.at", "password": "admin1234", "role": "admin"},
    "owner_anna": {"email": "anna@example.at", "password": "demo1234", "role": "owner", "name": "Anna Müller"},
    "owner_markus": {"email": "markus@example.at", "password": "demo1234", "role": "owner", "name": "Markus Weber"},
    "inspector_lisa": {"email": "lisa@baky.at", "password": "demo1234", "role": "inspector", "name": "Lisa Berger"},
}
```

### Layer 1: Apartments (added with #7)
```python
# management/commands/seed_apartments.py
SEED_APARTMENTS = [
    {"owner": "owner_anna", "address": "Mariahilfer Straße 45/12, 1060 Wien", "access": "lockbox", "access_code": "4521", "status": "active"},
    {"owner": "owner_anna", "address": "Praterstraße 78/3, 1020 Wien", "access": "smart_lock", "access_code": "APP-CODE-789", "status": "active"},
    {"owner": "owner_markus", "address": "Kärntner Ring 15/8, 1010 Wien", "access": "key_handover", "status": "active"},
    {"owner": "owner_markus", "address": "Wiedner Hauptstraße 90/5, 1050 Wien", "access": "lockbox", "access_code": "9012", "status": "active"},
    {"owner": "owner_markus", "address": "Landstraßer Hauptstraße 33/7, 1030 Wien", "access": "lockbox", "access_code": "3345", "status": "paused"},
]
```

### Layer 2: Checklists (added with #10, #30)
- Default checklist fixture loaded per apartment
- Customized versions for each apartment (some items toggled off)

### Layer 3: Inspections (added with #27)
```python
SEED_INSPECTIONS = [
    # Completed inspections (for report testing)
    {"apartment": 0, "inspector": "inspector_lisa", "status": "completed", "rating": "ok", "days_ago": 14},
    {"apartment": 0, "inspector": "inspector_lisa", "status": "completed", "rating": "attention", "days_ago": 7},
    {"apartment": 1, "inspector": "inspector_lisa", "status": "completed", "rating": "ok", "days_ago": 10},
    {"apartment": 2, "inspector": "inspector_lisa", "status": "completed", "rating": "urgent", "days_ago": 3},
    # Scheduled inspections (for inspector app testing)
    {"apartment": 0, "inspector": "inspector_lisa", "status": "scheduled", "days_from_now": 0},  # Today!
    {"apartment": 3, "inspector": "inspector_lisa", "status": "scheduled", "days_from_now": 1},
    {"apartment": 1, "inspector": "inspector_lisa", "status": "scheduled", "days_from_now": 3},
]
```

### Layer 4: Inspection Results (added with #20, #22)
- InspectionItems for completed inspections (mix of OK/Flag/N.A.)
- Photos (placeholder images) for flagged items
- General notes

### Layer 5: Reports (added with #23)
- Generated reports for completed inspections

### Layer 6: Subscriptions (added with #18)
- Anna: Basis plan, active
- Markus: Extra plan, active

## Master Seed Command

```bash
make seed
# Runs: python manage.py seed_all
```

`seed_all` calls each layer's seed command in order. Each is idempotent (safe to re-run).

```python
# management/commands/seed_all.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        call_command("seed_users")
        call_command("seed_apartments")
        call_command("loaddata", "default_checklist")
        call_command("seed_inspections")
        call_command("seed_inspection_results")
        call_command("seed_reports")
        call_command("seed_subscriptions")
        self.stdout.write(self.style.SUCCESS("All seed data loaded."))
```

Each command checks if data exists before creating (idempotent):
```python
user, created = User.objects.get_or_create(email=email, defaults={...})
if created:
    self.stdout.write(f"Created user: {email}")
else:
    self.stdout.write(f"User already exists: {email}")
```

## E2E Tests Use Seeds

E2E tests assume seed data exists. The test conftest loads seeds:

```python
# tests/e2e/conftest.py
@pytest.fixture(scope="session", autouse=True)
def seed_data(live_server):
    """Load seed data before all e2e tests."""
    call_command("seed_all")
```

## When Ralph Adds a New Feature

1. If the feature needs new seed data → add a new seed command
2. Register it in `seed_all`
3. Update this document
4. Existing e2e tests still pass (seeds are additive, never destructive)
SEEDMD
```

**Step 2: Commit**

```bash
git add .claude/skills/seed-strategy.md
git commit -m "feat: add seed data strategy skill for incremental test data"
```

---

## Task 6: Create the Autopilot Skill

**Files:**
- Create: `.claude/skills/autopilot.md`

**Step 1: Create the skill that starts Ralph**

```bash
cat > .claude/skills/autopilot.md << 'AUTOPILOTMD'
---
name: autopilot
description: Start Ralph Loop to autonomously build BAKY MVP. Reads roadmap, implements issues with TDD, validates with e2e tests, and merges automatically.
user-invokable: true
argument-hint: "[optional: --bootstrap to run Phase 0 first, --resume to continue, --status to check progress]"
---

# BAKY Autopilot

## Pre-Flight Checklist

Before starting Ralph, verify:

```bash
# 1. Docker is running
docker info > /dev/null 2>&1 && echo "Docker: OK" || echo "Docker: NOT RUNNING"

# 2. Ralph CLI is installed
which ralph && echo "Ralph: OK" || echo "Ralph: NOT FOUND"

# 3. GitHub CLI is authenticated
gh auth status 2>&1 | head -1

# 4. We're on main branch, clean state
git branch --show-current
git status --short
```

If anything fails, fix it before proceeding.

## Phase 0: Bootstrap (Manual)

The bootstrap must be done BEFORE Ralph can autopilot. It creates the test infrastructure
Ralph needs to validate its own work.

Check if bootstrap is complete:
```bash
# Bootstrap is complete if:
# 1. Docker services start: make up
# 2. Tests run: make test
# 3. Lint runs: make lint
# 4. E2E framework exists: tests/e2e/conftest.py
```

If bootstrap is NOT complete, tell the user:
"Bootstrap (Phase 0) is required before autopilot. This sets up Django, Docker, tests, and e2e validation.
Run `/ce:work docs/plans/2026-03-31-ralph-autopilot-setup.md` to execute the bootstrap, or implement issues #1, #29, #3, #5 manually."

## Phase 1: Start Autopilot

```bash
/ralph-loop "$(cat .ralph/PROMPT.md)" --max-iterations 100 --completion-promise "MVP_COMPLETE"
```

This starts the Ralph Loop which will:
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

# Or use tmux monitor
ralph --monitor
```

## Circuit Breaker

Ralph will automatically pause if:
- 5 iterations with no file changes (stuck)
- 5 iterations with same error (loop)
- Output quality drops >70% (degrading)

When paused, review `.ralph/logs/` and either:
- Fix the issue manually and `ralph --reset-circuit`
- Cancel with `/cancel-ralph`

## Resume After Pause

If Ralph was paused (circuit breaker, manual cancel, API limit):
```bash
# Check status
ralph --circuit-status
cat .ralph/fix_plan.md | grep "- \[ \]" | head -5

# Reset and restart
ralph --reset-circuit
/ralph-loop "$(cat .ralph/PROMPT.md)" --max-iterations 100 --completion-promise "MVP_COMPLETE"
```
AUTOPILOTMD
```

**Step 2: Commit**

```bash
git add .claude/skills/autopilot.md
git commit -m "feat: add autopilot skill to start Ralph Loop for autonomous MVP development"
```

---

## Task 7: Update CLAUDE.md with Autopilot Workflow

**Files:**
- Modify: `CLAUDE.md` (add autopilot section)

**Step 1: Append autopilot section to CLAUDE.md**

Add before the last section (Design Context):

```markdown
## Autopilot Development (Ralph Loop)

BAKY can be built autonomously using Ralph Loop. The autopilot:

1. Reads the roadmap (#44) each iteration
2. Picks the first unblocked issue
3. Creates a feature branch
4. Implements with TDD (failing test → implementation → passing test)
5. Runs full validation (lint + tests + e2e)
6. Merges to main, closes the issue
7. Updates the roadmap checklist
8. Repeats until MVP is complete

### Commands
- `/autopilot` — Pre-flight check and start Ralph Loop
- `/autopilot --status` — Check autopilot progress
- `/validate` — Run validation suite manually
- `/baky-status` — Overall project status
- `/cancel-ralph` — Stop the autopilot

### Seed Data
Seeds grow incrementally with features. See `/seed-strategy` skill.
Each layer is added when its feature is built, and all previous seeds remain valid.
E2E tests rely on seed data being present.

### Validation Gates
| Gate | When | What Runs |
|------|------|-----------|
| Pre-merge | Before merging feature to main | `make lint` + `make test` + `make e2e` |
| Post-merge | After merge to main | `make test` (smoke) |
| Phase complete | After roadmap phase done | Full validation |
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add autopilot workflow section to CLAUDE.md"
```

---

## Task 8: Update Makefile Targets Specification

**Files:**
- Modify: `CLAUDE.md` (update make targets to include e2e and validate)

**Step 1: Update the make commands section in CLAUDE.md**

The Makefile (to be created in issue #3) must include these targets:

```makefile
# Add to Makefile when Docker is set up (issue #3):
e2e:
	docker compose exec web pytest tests/e2e/ -v --tb=short

validate:
	@echo "=== BAKY Validation Suite ==="
	@echo "1/4 Linting..."
	docker compose exec web ruff check .
	docker compose exec web djlint templates/ --check
	@echo "2/4 Unit tests..."
	docker compose exec web pytest tests/ --ignore=tests/e2e/ -v --tb=short
	@echo "3/4 Django checks..."
	docker compose exec web python manage.py check
	@echo "4/4 E2E tests..."
	docker compose exec web pytest tests/e2e/ -v --tb=short
	@echo "=== All validation passed ==="

seed:
	docker compose exec web python manage.py seed_all
```

Note: this is a specification. The actual Makefile will be created in issue #3 (Docker setup).

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: specify Makefile targets for e2e, validate, and seed"
```

---

## Task 9: Create E2E Test Scaffolding Specification

**Files:**
- Create: `tests/e2e/README.md`

**Step 1: Create E2E test specification**

This spec will be implemented when the test infrastructure is built (issue #5).

```bash
mkdir -p tests/e2e
cat > tests/e2e/README.md << 'E2EREADME'
# BAKY E2E Tests

End-to-end tests using pytest-playwright. These test complete user flows against a live Django server.

## Setup

E2E tests are part of the Docker test suite:

```bash
make e2e                    # Run all e2e tests
make test ARGS="tests/e2e/" # Same thing
```

## Test Files

| File | What It Tests |
|------|--------------|
| `test_public.py` | Landing page loads, pricing page, legal pages, navigation links |
| `test_auth.py` | Login, logout, role-based redirects, unauthorized access returns 404 |
| `test_signup.py` | Owner signup flow: form → email verification → apartment registration |
| `test_owner.py` | Owner dashboard: apartment list, inspection timeline, report view |
| `test_inspector.py` | Inspector app: schedule view, checklist execution, photo upload, submit |
| `test_reports.py` | Report generation triggered, email sent, report viewable in dashboard |

## Conventions

- Tests use seed data (loaded in conftest.py)
- Mobile viewport (375x812) for inspector tests
- Desktop viewport (1280x720) for owner/public tests
- Each test is independent (no ordering)
- Use `page.goto()` with relative paths
- Assert on visible text content, not CSS selectors when possible
- Screenshots saved on failure for debugging

## Adding New E2E Tests

When implementing a new feature that has a UI:
1. Write the e2e test AFTER unit tests pass
2. The test should verify the complete user flow
3. Use seed data — don't create test data in e2e tests
4. Run `make e2e` to verify

## Dependencies

In `requirements/local.txt`:
```
pytest-playwright
playwright
```

In `Dockerfile`:
```dockerfile
RUN playwright install chromium
```
E2EREADME
```

**Step 2: Commit**

```bash
git add tests/e2e/README.md
git commit -m "docs: add e2e test specification and conventions"
```

---

## Task 10: Update .gitignore and Push Everything

**Files:**
- Modify: `.gitignore`

**Step 1: Add Ralph and test artifacts to .gitignore**

```bash
# Append to .gitignore
cat >> .gitignore << 'GITIGNORE'

# Ralph Loop
.ralph/logs/
.ralph/.call_count
.ralph/.token_count
.ralph/.last_reset
.ralph/.circuit_breaker_state
.ralph/.circuit_breaker_history
.ralph/.ralph_session
.ralph/.ralph_session_history
.ralph/status.json
.ralph/live.log
.claude/ralph-loop.local.md

# E2E test artifacts
tests/e2e/screenshots/
tests/e2e/videos/
test-results/
GITIGNORE
```

**Step 2: Commit and push**

```bash
git add .gitignore
git commit -m "chore: add Ralph and e2e artifacts to .gitignore"
git push origin main
```

**Step 3: Verify final state**

```bash
git log --oneline
ls -la .ralph/
ls -la .claude/skills/
cat .ralph/fix_plan.md | grep -c "\- \[ \]"  # Should show total tasks
```

---

## Summary

After completing all tasks, the project has:

| Component | File | Purpose |
|-----------|------|---------|
| Ralph config | `.ralphrc` | Rate limits, circuit breaker, tool permissions |
| Ralph agent | `.ralph/AGENT.md` | Build/test commands reference |
| Autopilot brain | `.ralph/PROMPT.md` | The loop prompt — assess → pick → build → validate → merge |
| Fix plan | `.ralph/fix_plan.md` | All MVP tasks as checklist (Ralph tracks progress) |
| Validation skill | `.claude/skills/validate.md` | Quality gates for each feature |
| Seed strategy | `.claude/skills/seed-strategy.md` | Incremental seed data plan |
| Autopilot skill | `.claude/skills/autopilot.md` | Pre-flight + start Ralph |
| E2E spec | `tests/e2e/README.md` | E2E test conventions and structure |

**Next steps after this plan:**
1. Execute the bootstrap (issues #1, #29, #3, #5 + e2e framework)
2. Run `/autopilot` to start Ralph Loop
3. Monitor with `ralph --monitor`
