---
name: estimation-framework
description: Story point estimation using RICE scoring adapted for BAKY. Use when sizing issues, planning sprints, or prioritizing the roadmap.
user-invokable: true
argument-hint: "[issue_number or feature description]"
---

# Estimation Framework

Estimate effort and priority for BAKY issues using a simplified RICE framework adapted for solo/small-team development.

## Input

If `$ARGUMENTS` contains an issue number, fetch it:
```bash
gh issue view <number> -R robert197/baky
```

Otherwise, use the provided feature description.

## Step 1: Assess Complexity (Story Points)

Rate the implementation effort on a Fibonacci scale:

| Points | Meaning | BAKY Examples |
|--------|---------|---------------|
| 1 | Trivial — config change, copy update | Add env var, update CLAUDE.md |
| 2 | Small — single file, clear pattern | New admin registration, simple fixture |
| 3 | Medium — one model or view, tests | New model + factory + tests |
| 5 | Large — multi-file, new patterns | HTMX view + template + URL + tests |
| 8 | Complex — cross-app, new infrastructure | Auth system, file upload pipeline |
| 13 | Epic — multi-day, many moving parts | Full inspection execution flow |

**Factors that increase points:**
- New infrastructure (Docker, S3, background tasks): +2-3
- Cross-app dependencies: +1-2
- Complex UI (mobile-first, offline, real-time): +2-3
- Third-party integration (Resend, Stripe, Maps): +1-2
- Data migration on existing data: +2

## Step 2: RICE Score

Calculate priority using RICE:

| Factor | Scale | Question |
|--------|-------|----------|
| **R**each | 1-3 | How many users/features depend on this? (1=few, 3=everyone) |
| **I**mpact | 1-3 | How much does it improve the product? (1=minor, 3=critical) |
| **C**onfidence | 0.5-1.0 | How well-defined are the requirements? (0.5=vague, 1.0=crystal clear) |
| **E**ffort | Story points | From Step 1 |

**RICE Score** = (Reach x Impact x Confidence) / Effort

Higher = do first.

## Step 3: Output

Present a summary:

```
## Estimate: [Issue/Feature Title]

**Story Points**: X (reason)
**RICE Score**: X.X

| Factor | Value | Rationale |
|--------|-------|-----------|
| Reach | X | ... |
| Impact | X | ... |
| Confidence | X | ... |
| Effort | X pts | ... |

**Dependencies**: #N, #M (if any)
**Risk factors**: (anything that could increase effort)
**Recommendation**: [Do now / Queue next / Defer / Needs refinement]
```

## Guidelines

- Prefer underestimating confidence over overestimating it
- If requirements are vague (confidence < 0.7), recommend a brainstorm or spike first
- Foundation/infrastructure issues (Phase 1-2) get a reach boost since everything depends on them
- Compare against completed issues for calibration when possible
