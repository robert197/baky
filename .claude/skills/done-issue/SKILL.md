---
name: done-issue
description: Complete the current issue — verify, commit, PR, close issue, update roadmap. Use after finishing implementation work.
user-invokable: true
argument-hint: "[optional: issue number if not on a feature branch]"
---

# Complete and Ship the Current Issue

## Step 1: Identify the Issue

Determine which issue we're completing:
- Parse from branch name: `feat/<number>-...` → issue number
- Or use `$ARGUMENTS` if provided
- Or ask the user

```bash
git branch --show-current
```

## Step 2: Verify Everything Works

Run the full verification suite inside Docker:

```bash
make lint
make test
```

If either fails, fix the issues before proceeding. Do NOT skip verification.

Check that all acceptance criteria from the issue are met:
```bash
gh issue view <issue_number> -R robert197/baky
```

Walk through each `- [ ]` acceptance criterion and verify it's satisfied.

## Step 3: Commit

```bash
git add <specific files>
git status
git diff --staged
```

Write a conventional commit message:
```bash
git commit -m "$(cat <<'EOF'
feat(<scope>): <what was built>

<Brief explanation of key decisions if needed>

Closes #<issue_number>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

## Step 4: Push and Create PR

```bash
git push -u origin $(git branch --show-current)

gh pr create --title "<short title>" --body "$(cat <<'EOF'
## Summary
- <What was built>
- <Key decisions>

## Issue
Closes #<issue_number>

## Testing
- <Tests added>
- <Manual verification performed>

## Acceptance Criteria
- [x] <criterion 1>
- [x] <criterion 2>
...

---
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

## Step 5: Close Issue and Update Roadmap

```bash
# Close the issue
gh issue close <issue_number> -R robert197/baky

# Update roadmap checkbox: change - [ ] #<number> to - [x] #<number>
# Read current roadmap body, edit it, update
```

Use `gh issue edit 44` to check off the completed item in the roadmap.

## Step 6: Report to User

Tell the user:
1. PR link
2. What was completed
3. What the next unblocked issue is (quick glance at roadmap)
4. Suggest: "Ready to pick up the next issue? Run `/next-issue`"
