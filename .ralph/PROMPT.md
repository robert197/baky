# BAKY Autopilot — Ralph Development Loop

You are building BAKY, an apartment inspection platform for short-term rentals in Vienna.
This prompt runs in a loop. Each iteration, you wake up, assess where you are, and continue building.

## CRITICAL: Read This Every Iteration

You are running inside Ralph CLI. Each iteration is a FRESH Claude Code process with a clean
context window. You have NO memory of previous iterations. All state is in files:
- Git history and branch state → what's been built
- Roadmap issue #44 → what's done (checked) and what's next (unchecked)
- `.ralph/fix_plan.md` → local progress tracker
- `docs/solutions/` → learnings from previous iterations (read before starting)

1. Read CLAUDE.md for project conventions and design context
2. Check git status to understand current state
3. Read the roadmap to find your next task
4. Check `docs/solutions/` for relevant past learnings

## Step 1: Assess and Recover

```bash
# Where am I?
git branch --show-current
git status
git log --oneline -5

# Is Docker running? If not, start it.
docker compose ps 2>/dev/null || make up
```

**Handle dirty state from a crashed previous iteration:**

```bash
branch=$(git branch --show-current)
status=$(git status --porcelain)

# Case A: On main with uncommitted changes → discard (leftover from crash)
if [ "$branch" = "main" ] && [ -n "$status" ]; then
  git checkout -- .
  git clean -fd
fi

# Case B: On a feature branch with a merged PR → the PR was merged but
# the iteration crashed before returning to main. Clean up.
if [ "$branch" != "main" ]; then
  issue_num=$(echo "$branch" | grep -oE '[0-9]+' | head -1)
  # Check if a PR for this branch was already merged
  pr_state=$(gh pr list -R robert197/baky --head "$branch" --state merged --json number -q 'length' 2>/dev/null)
  if [ "$pr_state" = "1" ]; then
    # PR already merged — just return to main
    git checkout main
    git pull origin main
    git branch -D "$branch" 2>/dev/null
    # Skip to Step 3 (pick next issue)
  fi
fi
```

Check for past learnings:
```bash
ls docs/solutions/*/ 2>/dev/null | head -20
```

## Step 2: Check if Current Feature Branch Has Work

If you're on a feature branch (not `main`) and the PR was NOT already merged:
1. Check if the feature is complete (all acceptance criteria met)
2. Run `make test` and `make lint`
3. If tests pass: go to Step 7 (Review) to finish shipping
4. If tests fail: fix them, then proceed to Step 7

```bash
branch=$(git branch --show-current)
if [ "$branch" != "main" ]; then
  issue_num=$(echo "$branch" | grep -oE '[0-9]+' | head -1)

  # Check if issue is already closed (previous iteration completed it)
  issue_state=$(gh issue view "$issue_num" -R robert197/baky --json state -q .state 2>/dev/null)
  if [ "$issue_state" = "CLOSED" ]; then
    git checkout main
    git pull origin main
    git branch -D "$branch" 2>/dev/null
    # Skip to Step 3
  else
    make lint
    make test
    # If passing → skip to Step 7 (Review)
    # If failing → fix issues, then proceed to Step 7
  fi
fi
```

## Step 3: Pick the Next Issue from Roadmap

```bash
gh issue view 44 -R robert197/baky
```

Parse the roadmap body. Find the first `- [ ]` item where ALL dependencies (issues after `←`) are closed.

To check if a dependency is closed:
```bash
gh issue view <number> -R robert197/baky --json state -q .state
```

The first unchecked item with all dependencies CLOSED is your next task.

## Step 4: Read the Issue, Check Learnings, and Plan

```bash
gh issue view <number> -R robert197/baky
```

Read the full issue. Understand:
- What needs to be built
- Acceptance criteria (the checkboxes)
- Dependencies on other code already in the codebase

**Check for relevant learnings** from previous iterations:
```bash
ls docs/solutions/ 2>/dev/null
# Read any solution docs that relate to the current issue's domain
# (e.g., if building models, check for database-issues/ or build-errors/)
```

Apply any relevant lessons — don't repeat mistakes that were already documented.

**For complex issues** (multi-model, multi-view, integrations): Use `/ce:plan` to create
a detailed implementation plan in `docs/plans/` before coding.

**For simple issues** (config, fixtures, single-file): Start coding directly.

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
- Tailwind CSS for styling (use color tokens from CLAUDE.md Design Context)
- HTMX for dynamic content
- Mobile-first design
- German for user-facing text, English for code

When implementing seed data for a new feature, add it as an idempotent management command
following the seed strategy in `.claude/skills/seed-strategy/SKILL.md`.

## Step 6: Validate

Before moving to review, run the full validation suite:

```bash
# 1. Linting
make lint

# 2. Full test suite
make test

# 3. Django system checks
make manage CMD="check"

# 4. E2E validation (if UI features exist)
make e2e 2>/dev/null || echo "E2E tests not yet set up"
```

ALL must pass. If any fail, fix and re-run. Do NOT proceed to review with failing tests.

## Step 7: Review (Compound Engineering)

**After validation passes**, run a code review using the `superpowers:requesting-code-review` pattern.

Dispatch the `code-reviewer` agent to review the changes:

```bash
# Get the diff range
BASE_SHA=$(git merge-base main HEAD)
HEAD_SHA=$(git rev-parse HEAD)
```

Launch the code-reviewer agent with:
- **What was implemented**: Summary of the feature (from the issue)
- **Requirements**: The acceptance criteria from the issue
- **BASE_SHA / HEAD_SHA**: The commit range to review
- **Mode**: `--serial` (context-safe for Ralph iterations)

**Act on review feedback:**

| Severity | Action |
|----------|--------|
| **Critical** | Fix immediately. Re-run validation. |
| **Important** | Fix before proceeding to PR. |
| **Minor** | Note for later — do not delay shipping. |

After fixing Critical/Important issues:
```bash
git add -A
git commit -m "fix(<scope>): address review feedback"
make test
make lint
```

## Step 8: Ship — Create PR and Merge

```bash
# Stage any remaining changes (skip if nothing to commit)
git add -A
if [ -n "$(git status --porcelain)" ]; then
  git commit -m "$(cat <<'EOF'
feat(<scope>): <description>

Closes #<issue_number>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
fi

# Push feature branch
branch=$(git branch --show-current)
git push -u origin "$branch"

# Check if PR already exists for this branch (from a crashed previous attempt)
existing_pr=$(gh pr list -R robert197/baky --head "$branch" --state open --json number -q '.[0].number' 2>/dev/null)

if [ -z "$existing_pr" ]; then
  # Create new PR
  gh pr create \
    --title "feat(<scope>): <short description>" \
    --body "$(cat <<'PRBODY'
## Summary
<What was built and why>

Closes #<issue_number>

## Changes
- <Key change 1>
- <Key change 2>

## Validation
- [x] `make lint` passes
- [x] `make test` passes
- [x] `make manage CMD="check"` passes
- [x] Code review completed (Critical/Important issues resolved)

## Review Notes
<Any notable decisions, trade-offs, or follow-up items from review>

Co-Authored-By: Claude <noreply@anthropic.com>
PRBODY
)"
fi

# Merge the PR (auto-deletes branch via repo setting)
gh pr merge --merge

# Return to main
git checkout main
git pull origin main

# Clean up local branch if it still exists
git branch -D "$branch" 2>/dev/null
```

## Step 9: Compound — Document Learnings

**After merging**, check if this iteration produced knowledge worth compounding.

**Document a learning if ANY of these occurred:**
- A non-obvious bug was found and fixed
- A pattern was discovered that future features should follow
- A configuration or setup issue was resolved after trial and error
- A workaround was needed for a library or framework limitation
- A test approach was found that's worth reusing

**Run `/ce:compound` to document the learning.** This will use parallel subagents to create
a thorough solution doc in `docs/solutions/`.

**Skip compounding if** the feature was straightforward with no surprises.

Future iterations will read `docs/solutions/` in Step 4 to avoid repeating mistakes.

## Step 10: Update Fix Plan

After merging, mark the completed item in `.ralph/fix_plan.md`:
- Change `- [ ] #<number>` to `- [x] #<number>` using the Edit tool.

## Step 11: Exit Cleanly

After completing ONE issue, exit so Ralph CLI starts a fresh iteration with clean context.

First, check if the MVP is complete:
```bash
gh issue list -R robert197/baky --milestone "MVP (Weeks 1-4)" --state open --json number -q 'length'
```

If 0 open issues remain, output:
<promise>MVP_COMPLETE</promise>

Otherwise, output a status summary and exit:
```
RALPH_STATUS:
STATUS: IN_PROGRESS
COMPLETED: #<issue_number> - <title>
REVIEW: <passed/issues found and fixed>
COMPOUNDED: <yes — topic / no — straightforward>
NEXT: #<next_issue> - <title>
EXIT_SIGNAL: false
```

**IMPORTANT**: Do NOT try to start the next issue in the same iteration.
Exit after completing one issue. Ralph CLI will start a fresh process for the next one.
This keeps context clean and prevents compaction.

## The Full Iteration Flow

```
  Assess → Pick Issue → Check Learnings → Plan (if complex)
    ↓
  Implement (TDD) → Validate (lint + test + e2e)
    ↓
  Review (code-reviewer agent) → Fix Critical/Important
    ↓
  Ship (PR → merge) → Compound (document learnings)
    ↓
  Update fix_plan → Exit → Ralph starts fresh iteration
```

## Rules

1. **Never skip tests.** Every feature must have passing tests before merge.
2. **Never skip review.** Code-reviewer runs on every feature before PR.
3. **Never merge failing code.** If tests or review finds Critical issues, fix them.
4. **One issue per iteration.** Focus on completing one issue fully.
5. **Follow the roadmap order.** Don't jump ahead — dependencies matter.
6. **Docker for everything.** All commands via `make`, never install locally.
7. **Commit often.** Small, focused commits within each feature branch.
8. **German for UI, English for code.** Public-facing text in German.
9. **Add seeds incrementally.** Each feature adds the seed data it needs.
10. **Compound your learnings.** Document non-obvious solutions so future iterations benefit.
11. **Read before building.** Check `docs/solutions/` for relevant past learnings.
12. **Mobile-first.** Design for 375px first, scale up.
13. **Use the design system.** Colors, typography, spacing from CLAUDE.md.

## Completion Promise

When ALL MVP issues are closed and all tests pass:
<promise>MVP_COMPLETE</promise>

Only output this when it is genuinely true. Do not lie to exit the loop.
