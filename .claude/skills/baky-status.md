---
name: baky-status
description: Quick project status overview — roadmap progress, open issues, recent commits, and what's next.
user-invokable: true
---

# BAKY Project Status

## Step 1: Gather Status

Run these in parallel:

```bash
# Roadmap progress
gh issue view 44 -R robert197/baky

# Open issues count by milestone
gh issue list -R robert197/baky --state open --json milestone,number,title -q 'group_by(.milestone.title)'

# Recent commits
git log --oneline -10

# Current branch and working state
git status
git branch --show-current
```

## Step 2: Report

Present a concise status report:

```
## BAKY Status

### Roadmap Progress
Phase 1 (Foundation): X/Y complete
Phase 2 (Data Layer): X/Y complete
Phase 3 (Public Website): X/Y complete
Phase 4 (Inspector App): X/Y complete
Phase 5 (Reports): X/Y complete
Phase 6 (Owner Dashboard): X/Y complete
Phase 7 (Launch): X/Y complete

### Milestones
MVP: X open / Y closed
v1.1: X open
v2.0: X open

### Current Work
Branch: <current branch>
Status: <clean / uncommitted changes>

### Next Up
<First unblocked issue from roadmap>
```

## Step 3: Suggest Next Action

Based on the status:
- If on a feature branch with work: "Continue working on current feature"
- If clean on main: "Run `/next-issue` to pick up the next task"
- If tests failing: "Fix failing tests before proceeding"
