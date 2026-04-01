# BAKY Autopilot — Compound Engineering Development Loop

You are building BAKY, an apartment inspection platform for short-term rentals in Vienna.
This prompt runs in a loop. Each iteration, you wake up, assess where you are, and build
ONE issue using the Compound Engineering workflow strictly.

## CRITICAL: Read This Every Iteration

You are a FRESH Claude Code process. You have NO memory of previous iterations. All state is in files:
- Git history and branch state → what's been built
- Roadmap issue #44 → what's shipped (checked) and what's next (unchecked)
- `docs/plans/` → implementation plans from /ce:plan
- `docs/solutions/` → learnings from /ce:compound

Read CLAUDE.md first for project conventions and design context.

## Step 1: Assess and Recover

```bash
git branch --show-current
git status
git log --oneline -5
docker compose ps 2>/dev/null || make up
```

**Handle dirty state from a crashed previous iteration:**

```bash
branch=$(git branch --show-current)
status=$(git status --porcelain)

# On main with uncommitted changes → discard (leftover from crash)
if [ "$branch" = "main" ] && [ -n "$status" ]; then
  git checkout -- .
  git clean -fd
fi

# On feature branch with already-merged PR → return to main
if [ "$branch" != "main" ]; then
  issue_num=$(echo "$branch" | grep -oE '[0-9]+' | head -1)
  pr_state=$(gh pr list -R robert197/baky --head "$branch" --state merged --json number -q 'length' 2>/dev/null)
  if [ "$pr_state" = "1" ]; then
    git checkout main && git pull origin main && git branch -D "$branch" 2>/dev/null
  fi
  issue_state=$(gh issue view "$issue_num" -R robert197/baky --json state -q .state 2>/dev/null)
  if [ "$issue_state" = "CLOSED" ]; then
    git checkout main && git pull origin main && git branch -D "$branch" 2>/dev/null
  fi
fi
```

## Step 2: Resume In-Progress Feature Branch

If you're on a feature branch (not `main`) with an open issue:
- Run `make lint` and `make test`
- If passing → skip to **Step 6 (Review)**
- If failing → fix issues, then proceed to **Step 6 (Review)**

## Step 3: Pick the Next Issue from Roadmap

```bash
gh issue view 44 -R robert197/baky
```

Find the first `- [ ]` item where ALL dependencies (after `←`) are closed:
```bash
gh issue view <number> -R robert197/baky --json state -q .state
```

## Step 4: Plan with /ce:plan

Read the issue:
```bash
gh issue view <number> -R robert197/baky
```

Check for relevant past learnings:
```bash
ls docs/solutions/*/ 2>/dev/null | head -20
```

Create a feature branch:
```bash
git checkout main && git pull origin main
git checkout -b feat/<number>-<short-description>
```

**NOW invoke the Skill tool to create an implementation plan:**

```
Skill({ skill: "compound-engineering:ce-plan", args: "<paste the full issue body here>" })
```

This will:
- Research the codebase for existing patterns
- Ask clarifying questions (answer them yourself based on the issue and CLAUDE.md)
- Create a detailed plan in `docs/plans/` with bite-sized TDD tasks
- Each task has: exact files, test code, implementation code, verification commands

Wait for the plan to be written to `docs/plans/` before proceeding.

## Step 5: Execute with /ce:work

**Invoke the Skill tool to execute the plan:**

```
Skill({ skill: "compound-engineering:ce-work", args: "docs/plans/<the-plan-file-just-created>.md" })
```

This will:
- Read the plan
- Create a todo list from the plan's tasks
- Execute each task following TDD (failing test → implementation → green test)
- Run tests continuously after each change
- Make incremental commits with conventional messages
- Follow the System-Wide Test Check for callbacks, middleware, state persistence
- Track progress via TodoWrite

### Testing Requirements (enforced by /ce:work)

The plan from /ce:plan will include tests for each task. /ce:work executes them via TDD.
But additionally verify these minimums before proceeding:

| Feature Type | Minimum Tests |
|-------------|---------------|
| New model | 5+ (create, str, constraints, relationships, business logic) |
| New view | 5+ (success, auth, role, scope, form handling) |
| New form | 3+ (valid, required, validation) |
| New task | 3+ (happy path, bad input, idempotent) |
| Full feature | 15+ combined |

Rules:
- Use factories (OwnerFactory, ApartmentFactory, etc.), never hardcode test data
- Test permissions for every authenticated view (unauthenticated, wrong role, wrong user)
- Test edge cases (empty data, German umlauts ä/ö/ü/ß, boundary values)
- No mocking the database — tests hit real PostgreSQL
- `make test` after EVERY change

## Step 6: Review with /ce:review

**After /ce:work ships all tasks and validation passes, invoke the Skill tool for code review:**

```
Skill({ skill: "compound-engineering:ce-review", args: "--serial" })
```

This will:
- Read `compound-engineering.local.md` for configured review agents
- Launch review agents (architecture, patterns, performance, security, data-integrity)
- Run in serial mode (context-safe for autopilot iterations)
- Report findings with severity: Critical / Important / Minor

**Act on feedback:**

| Severity | Action |
|----------|--------|
| **Critical** | Fix immediately. Re-run `make test` and `make lint`. |
| **Important** | Fix before creating PR. |
| **Minor** | Note in PR description — do not delay shipping. |

After fixing Critical/Important issues, commit:
```bash
git add -A
git commit -m "fix(<scope>): address review feedback"
make test && make lint
```

## Step 7: Ship — Create PR and Merge

```bash
git add -A
if [ -n "$(git status --porcelain)" ]; then
  git commit -m "$(cat <<'EOF'
feat(<scope>): <description>

Closes #<issue_number>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
fi

branch=$(git branch --show-current)
git push -u origin "$branch"

# Check if PR already exists (crash recovery)
existing_pr=$(gh pr list -R robert197/baky --head "$branch" --state open --json number -q '.[0].number' 2>/dev/null)

if [ -z "$existing_pr" ]; then
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
- [x] Code review via /ce:review (Critical/Important resolved)

## Review Notes
<Any notable decisions, trade-offs, or follow-up from review agents>

Co-Authored-By: Claude <noreply@anthropic.com>
PRBODY
)"
fi

gh pr merge --merge
git checkout main && git pull origin main
git branch -D "$branch" 2>/dev/null
```

## Step 8: Compound Learnings with /ce:compound

**After merging, check if this iteration produced knowledge worth documenting.**

Invoke compound if ANY of these occurred:
- A non-obvious bug was found and fixed
- A pattern was discovered that future features should follow
- A configuration or setup issue took trial and error
- A workaround was needed for a library limitation
- A test approach was found that's worth reusing

**Invoke the Skill tool:**

```
Skill({ skill: "compound-engineering:ce-compound", args: "Shipped issue #<number>: <brief context of what was non-obvious>" })
```

This will:
- Analyze the conversation for the problem/solution
- Create a structured doc in `docs/solutions/<category>/`
- Include: problem, root cause, solution, prevention
- Future iterations read these in Step 4

**Skip compounding if the feature was straightforward with no surprises.**

## Step 9: Exit This Iteration

Check how many MVP issues remain:
```bash
remaining=$(gh issue list -R robert197/baky --milestone "MVP (Weeks 1-4)" --state open --json number -q 'length')
echo "Remaining MVP issues: $remaining"
```

**If 0 remaining** — ALL MVP issues are shipped:
<promise>MVP_COMPLETE</promise>

**If issues remain** — output EXACTLY this and exit:
```
RALPH_STATUS:
EXIT_SIGNAL: false
SHIPPED: #<issue_number>
REMAINING: <count>
PICKING_UP_NEXT: #<next_issue_number>
```

**Do NOT start the next issue.** Exit now. The loop starts a fresh process.

## The Strict Compound Engineering Flow

```
  Step 1: Assess/Recover
    ↓
  Step 2: Resume in-progress branch (if any)
    ↓
  Step 3: Pick next issue from roadmap #44
    ↓
  Step 4: /ce:plan → creates docs/plans/<plan>.md
    ↓
  Step 5: /ce:work → executes plan with TDD, tests, incremental commits
    ↓
  Step 6: /ce:review --serial → code review with 5 agents
    ↓
  Step 7: Ship → PR → merge
    ↓
  Step 8: /ce:compound → document learnings to docs/solutions/
    ↓
  Step 9: Exit → fresh iteration
```

**Every issue goes through: Plan → Work → Review → Ship → Compound.**
No shortcuts. No skipping steps. This is the Compound Engineering process.

## Rules

1. **Use /ce:plan for every issue.** No implementing without a plan.
2. **Use /ce:work to execute.** Follow the plan's TDD tasks exactly.
3. **Use /ce:review before every PR.** Run in --serial mode.
4. **Use /ce:compound after non-trivial issues.** Document what was learned.
5. **Never skip tests.** Minimum test counts enforced per feature type.
6. **Never merge failing code.** All validation must pass.
7. **One issue per iteration.** Ship one, then exit.
8. **Follow the roadmap order.** Dependencies matter.
9. **Docker for everything.** All commands via `make`.
10. **German for UI, English for code.**
11. **Mobile-first.** Design for 375px, scale up.
12. **Use the design system.** Colors, typography from CLAUDE.md.

## CRITICAL: Exit Signal Words

**NEVER use in final output** (unless ALL MVP issues are truly shipped):
"complete", "done", "finished", "ready", "all requirements met", "nothing left"

**Safe words:** "shipped", "remaining", "picking up next", "in progress"

## Completion Promise

When ALL MVP issues are closed and all tests pass — and ONLY then:
<promise>MVP_COMPLETE</promise>
