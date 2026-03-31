---
name: next-issue
description: Pick the next issue to work on from the BAKY roadmap. Reads the pinned roadmap issue, finds the first unblocked task, and sets up the branch.
user-invokable: true
argument-hint: "[optional: specific issue number to work on]"
---

# Pick and Start the Next Issue

## Step 1: Check Current State

```bash
# Check if we're already on a feature branch with uncommitted work
git status
git branch --show-current
```

If there's uncommitted work on a feature branch, warn the user and ask whether to continue that work or stash/commit first.

## Step 2: Read the Roadmap

```bash
gh issue view 44 -R robert197/baky
```

If `$ARGUMENTS` contains an issue number, use that directly. Otherwise, parse the roadmap:

1. Find all unchecked items (`- [ ]`)
2. For each, check if its dependencies (issues listed after `←`) are closed:
   ```bash
   gh issue view <dep_number> -R robert197/baky --json state -q .state
   ```
3. The first unchecked item with ALL dependencies closed is the next task

## Step 3: Read the Issue

```bash
gh issue view <issue_number> -R robert197/baky
```

Read the full issue body. Understand requirements and acceptance criteria.

## Step 4: Set Up the Branch

```bash
git checkout main
git pull origin main
git checkout -b feat/<issue_number>-<short-description>
```

Use a descriptive branch name based on the issue title (lowercase, hyphens, max 50 chars).

## Step 5: Present the Plan

Tell the user:
1. Which issue you're starting and why (dependencies satisfied)
2. Brief summary of what needs to be built
3. Suggest: "Should I run `/ce:plan` for this issue, or is it straightforward enough to start coding?"

For complex issues (data models, multi-step flows, integrations), recommend `/ce:plan`.
For simple issues (config, fixtures, single-file changes), suggest starting directly.
