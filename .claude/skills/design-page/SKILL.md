---
name: design-page
description: Design and implement a beautiful page using BAKY's design system with impeccable.style quality. Use for any user-facing page — landing, dashboard, inspector views.
user-invokable: true
argument-hint: "<page description or issue number>"
---

# Design and Build a Beautiful Page

This skill combines BAKY's design context with the impeccable.style frontend-design skill
and compound engineering's design iteration workflow.

## Step 1: Understand What to Build

Read `$ARGUMENTS`. If it's an issue number, fetch the issue:
```bash
gh issue view <number> -R robert197/baky
```

Identify:
- **Who** uses this page (Owner, Inspector, Public visitor)
- **What** they need to accomplish
- **Which** layout template to extend (public, dashboard, inspector)

## Step 2: Design Direction

Before writing any code, commit to a design direction based on CLAUDE.md Design Context:

**BAKY Design Language:**
- **Colors**: Deep slate primary, warm amber accent. NOT generic blue. NOT dark mode.
- **Typography**: Clean sans-serif, bold hierarchy. Large text for mobile.
- **Layout**: Generous whitespace, clear sections. Cards for grouped info, NOT cards-in-cards.
- **Status**: Emerald (OK), Amber (Attention), Rose (Urgent) — consistent everywhere.
- **Tone**: Professional warmth. Like a trusted property manager's report, not a SaaS dashboard.

**Per-view specifics:**
| View Type | Design Priority |
|-----------|----------------|
| Public pages | Trust, clarity, conversion. Hero + social proof + CTA. |
| Owner dashboard | Information density, scanability. Data-first, not decoration. |
| Inspector app | One-hand usability. Huge tap targets. Minimal scrolling. Bottom-anchored actions. |

## Step 3: Implement with Quality

Use the `frontend-design` skill principles:
- Choose **beautiful, unique fonts** (Google Fonts) — not Inter, not Roboto
- Use **Tailwind CSS** with the color tokens from CLAUDE.md
- **Mobile-first**: write mobile layout, then add `sm:`, `md:`, `lg:` breakpoints
- Use **HTMX** for dynamic interactions (no page reloads)
- Use **Alpine.js** for local state (modals, toggles, dropdowns)

**Avoid generic AI aesthetics:**
- No gradient text
- No glassmorphism
- No neon-on-dark
- No identical card grids
- No decorative sparklines

## Step 4: Refine with Design Iteration

After implementing, use the design iteration workflow:

1. **Take a screenshot** (use Playwright MCP or browser)
2. **Critique** the design yourself — check against BAKY design principles
3. **Fix** issues: alignment, spacing, color consistency, mobile layout
4. **Repeat** until the page feels polished

Key checkpoints:
- [ ] Mobile layout works at 375px
- [ ] Color tokens used consistently (no raw hex values)
- [ ] Status badges use correct colors (emerald/amber/rose)
- [ ] Interactive elements have hover/focus states
- [ ] HTMX loading indicators present
- [ ] Text hierarchy clear (one H1, proper heading levels)
- [ ] No orphaned text (short lines at end of paragraphs)
- [ ] CTAs are prominent and clear

## Step 5: Verify

```bash
make lint
make test
```

Check the page in browser at multiple sizes:
- Mobile: 375px (iPhone SE)
- Tablet: 768px (iPad)
- Desktop: 1280px
