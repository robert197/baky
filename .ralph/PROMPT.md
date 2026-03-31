# BAKY Autopilot — Ralph Development Loop

You are building BAKY, an apartment inspection platform for short-term rentals in Vienna.
This prompt runs in a loop. Each iteration, you wake up, assess where you are, and continue building.

## CRITICAL: Read This Every Iteration

You are running inside Ralph CLI. Each iteration is a FRESH Claude Code process with a clean
context window. You have NO memory of previous iterations. All state is in files:
- Git history and branch state → what's been built
- Roadmap issue #44 → what's done (checked) and what's next (unchecked)
- `.ralph/fix_plan.md` → local progress tracker

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
3. If tests pass: create PR and merge
4. If tests fail: fix them first

```bash
branch=$(git branch --show-current)
if [ "$branch" != "main" ]; then
  issue_num=$(echo "$branch" | grep -oE '[0-9]+' | head -1)

  make lint
  make test

  # If both pass, push and create PR
  git push -u origin "$branch"

  gh pr create --title "feat: $(gh issue view $issue_num -R robert197/baky --json title -q .title)" \
    --body "$(cat <<PRBODY
## Summary
Implements #$issue_num

## Validation
- [x] \`make lint\` passes
- [x] \`make test\` passes
- [x] \`make manage CMD="check"\` passes

Co-Authored-By: Claude <noreply@anthropic.com>
PRBODY
)"

  # Merge the PR (closes the linked issue automatically via "Implements #N")
  gh pr merge --merge --delete-branch
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
- Dependencies on other code already in the codebase

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
following the seed strategy in `.claude/skills/seed-strategy.md`.

## Step 6: Run Full Validation

Before declaring a feature complete:

```bash
# 1. Full test suite
make test

# 2. Linting
make lint

# 3. Django system checks
make manage CMD="check"

# 4. E2E validation (if UI features exist)
make e2e 2>/dev/null || echo "E2E tests not yet set up"
```

ALL must pass. If any fail, fix and re-run.

## Step 7: Complete the Feature

```bash
# Stage and review changes
git add -A
git status
git diff --staged | head -200

# Commit with issue reference
git commit -m "$(cat <<'EOF'
feat(<scope>): <description>

Closes #<issue_number>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Push the feature branch
git push -u origin feat/<number>-<short-description>

# Create a Pull Request
gh pr create \
  --title "feat(<scope>): <short description>" \
  --body "$(cat <<'PRBODY'
## Summary
<What was built and why>

Closes #<issue_number>

## Validation
- [x] `make lint` passes
- [x] `make test` passes
- [x] `make manage CMD="check"` passes

Co-Authored-By: Claude <noreply@anthropic.com>
PRBODY
)"

# Merge the PR and delete the branch
gh pr merge --merge --delete-branch

# Pull main to stay up to date
git checkout main
git pull origin main
```

After merging, also update the `.ralph/fix_plan.md` — mark the corresponding item `[x]`.

## Step 8: Update Fix Plan

After merging and closing the issue, mark it done in `.ralph/fix_plan.md`:
- Change `- [ ] #<number>` to `- [x] #<number>` using the Edit tool.

## Step 9: Exit Cleanly

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
NEXT: #<next_issue> - <title>
EXIT_SIGNAL: false
```

**IMPORTANT**: Do NOT try to start the next issue in the same iteration.
Exit after completing one issue. Ralph CLI will start a fresh process for the next one.
This keeps context clean and prevents compaction.

## Rules

1. **Never skip tests.** Every feature must have passing tests before merge.
2. **Never merge failing code.** If tests fail, fix them.
3. **One issue per iteration.** Focus on completing one issue fully.
4. **Follow the roadmap order.** Don't jump ahead — dependencies matter.
5. **Docker for everything.** All commands via `make`, never install locally.
6. **Commit often.** Small, focused commits within each feature branch.
7. **German for UI, English for code.** Public-facing text in German.
8. **Add seeds incrementally.** Each feature adds the seed data it needs.
9. **Mobile-first.** Design for 375px first, scale up.
10. **Use the design system.** Colors, typography, spacing from CLAUDE.md.

## Completion Promise

When ALL MVP issues are closed and all tests pass:
<promise>MVP_COMPLETE</promise>

Only output this when it is genuinely true. Do not lie to exit the loop.
