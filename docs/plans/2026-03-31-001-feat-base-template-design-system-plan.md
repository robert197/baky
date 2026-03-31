---
title: "feat: Responsive base template and design system"
type: feat
status: completed
date: 2026-03-31
issue: "#43"
---

# Responsive Base Template and Design System

## Overview

Create the foundational template hierarchy and Tailwind-based design system that all BAKY pages will extend. This is the single biggest blocker on the roadmap — it gates Phase 3 (public website: #13, #14, #28, #15) and every layout-dependent feature after it.

The deliverable is three layout templates extending a shared `base.html`, a set of reusable components, a complete Tailwind theme, and proper HTMX/Alpine.js integration including CSRF and error handling.

## Problem Statement / Motivation

The current `base.html` is a skeleton: it loads HTMX and Alpine.js via CDN but doesn't link the compiled Tailwind CSS, has no CSRF config for HTMX, and defines only minimal blocks. There are no layout templates, no components, and the Tailwind config has only 2 of 9 color tokens. Nothing can be styled or built on top of this.

## Proposed Solution

### Template Hierarchy

```
templates/
├── base.html                    # HTML shell: Tailwind, HTMX, Alpine, CSRF, messages, error handling
├── public/
│   └── base_public.html         # Navbar + content + footer (extends base.html)
├── dashboard/
│   └── base_dashboard.html      # Sidebar + content area (extends base.html)
├── inspector/
│   └── base_inspector.html      # Mobile-first + bottom nav (extends base.html)
└── components/
    ├── _navbar.html             # Public site navigation
    ├── _footer.html             # Public site footer
    ├── _sidebar.html            # Dashboard sidebar navigation
    ├── _bottom_nav.html         # Inspector bottom navigation (renamed from _sidebar for clarity)
    ├── _alert.html              # Dismissible alert/notification (maps to Django messages)
    ├── _modal.html              # Alpine.js modal with focus trapping
    ├── _status_badge.html       # OK / Attention / Urgent badge
    ├── _loading.html            # HTMX loading indicator
    └── _card.html               # Content card wrapper
```

**Note:** `_photo_grid.html` is deferred to #21 (Photo capture) where the actual requirements are clearer.

### Block Contract

Each layout template exposes a consistent set of blocks:

| Block | Purpose | Available in |
|-------|---------|-------------|
| `title` | Page `<title>` | base.html |
| `meta_description` | SEO meta description | base.html |
| `extra_head` | Additional `<head>` content | base.html |
| `content` | Main page content | All layouts |
| `page_title` | H1 heading / breadcrumb area | dashboard, inspector |
| `page_actions` | Action buttons in header area | dashboard, inspector |
| `extra_js` | Additional scripts before `</body>` | base.html |

### Design Decisions

1. **Fonts: System font stack** (no Inter for MVP). Avoids GDPR issues with Google Fonts CDN in Austria. The stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`. Inter can be self-hosted later.

2. **Semantic color tokens** in `tailwind.config.js`. Use `bg-primary`, `text-accent` etc., not raw `bg-slate-800`. Makes rebranding trivial.

3. **HTMX CSRF**: `hx-headers='{"X-CSRFToken": "..."}'` on `<body>`. Simple, works with all HTMX verbs.

4. **HTMX error handling**: Global listener on `htmx:responseError` that shows an alert. Session expiration (403) redirects to login.

5. **Dashboard sidebar on mobile**: Collapsible slide-out drawer with hamburger icon and backdrop overlay (Alpine.js).

6. **Django messages**: Rendered above content in each layout, auto-dismiss after 5s with Alpine.js `x-init="setTimeout(...)"`

7. **Alpine.js version pinning**: Pin to specific version (3.14.8), add SRI hashes to both CDN scripts.

8. **Auth pages** (login/signup): Will use `base_public.html` — decided here so #15 doesn't need to revisit.

## Technical Considerations

### Tailwind Configuration

Extend `tailwind.config.js` with the full token set from CLAUDE.md:

```javascript
// tailwind.config.js
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#1e293b', light: '#334155' },   // slate-800/700
        secondary: { DEFAULT: '#475569' },                    // slate-600
        accent: { DEFAULT: '#f59e0b', light: '#fbbf24' },    // amber-500/400
        success: { DEFAULT: '#10b981' },                      // emerald-500
        warning: { DEFAULT: '#f59e0b' },                      // amber-500
        danger: { DEFAULT: '#f43f5e' },                       // rose-500
        surface: { DEFAULT: '#f8fafc' },                      // slate-50
        card: { DEFAULT: '#ffffff' },                         // white
        border: { DEFAULT: '#e2e8f0' },                       // slate-200
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],  // @tailwindcss/forms added when form-heavy features land
}
```

### HTMX + Alpine.js Integration in base.html

```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  <!-- Global HTMX error handler -->
  <script>
    document.body.addEventListener('htmx:responseError', function(evt) {
      if (evt.detail.xhr.status === 403) {
        window.location.href = '/accounts/login/';
      }
      // Show error alert for other errors
    });
  </script>
</body>
```

### Accessibility Baseline

- ARIA landmarks: `<nav role="navigation">`, `<main role="main">`, `<footer role="contentinfo">`
- Skip-to-content link in base.html
- Modal focus trapping with Alpine.js `x-trap` (from `@alpinejs/focus` plugin — evaluate if needed or use manual implementation)
- `prefers-reduced-motion` respected for any transitions
- Full WCAG AA audit deferred to a later issue

### System-Wide Impact

- **Interaction graph**: All future templates extend these layouts. Any block rename or removal is a breaking change.
- **Error propagation**: HTMX errors now have a global handler in base.html. Views returning non-2xx must be aware that the global handler will fire.
- **State lifecycle risks**: None — this is purely presentational, no database state.
- **API surface parity**: The three layout templates create a "template API" that all future views consume. This is the contract.

## Implementation Phases

### Phase 1: Foundation (~30 min)

Update the core files that everything depends on.

**Files to modify:**
- `tailwind.config.js` — Full color tokens, font family
- `templates/base.html` — Add `{% load static %}`, link `output.css`, CSRF config, HTMX error handler, Django messages block, skip-to-content link, pin Alpine.js version, add SRI hashes
- `static/css/input.css` — Add any `@layer` utilities if needed (e.g., `.htmx-indicator` styles)

**Verification:** `make up`, load `localhost:8000`, confirm Tailwind styles apply and no console errors.

### Phase 2: Layout Templates (~45 min)

Build the three layout templates.

**Files to create:**
- `templates/public/base_public.html` — Extends `base.html`. Includes `_navbar.html` and `_footer.html`. Defines `content` block for page content. Responsive: full-width content area, max-width container.
- `templates/dashboard/base_dashboard.html` — Extends `base.html`. Includes `_sidebar.html`. Defines `page_title`, `page_actions`, `content` blocks. Responsive: sidebar collapses to drawer on mobile (Alpine.js state).
- `templates/inspector/base_inspector.html` — Extends `base.html`. Includes `_bottom_nav.html`. Defines `page_title`, `content` blocks. Mobile-first: 375px baseline, large tap targets, bottom-anchored nav.

**Files to modify:**
- `templates/public/home.html` — Update to extend `base_public.html` instead of `base.html`.

**Verification:** Create minimal test pages for each layout, load them, verify responsive behavior at 375px, 768px, 1024px, 1280px.

### Phase 3: Components (~45 min)

Build reusable components with documented APIs.

**Files to create:**
- `templates/components/_navbar.html` — Logo, nav links (Startseite, Preise, Kontakt), Login CTA button. Mobile: hamburger menu with Alpine.js toggle.
- `templates/components/_footer.html` — Company info, links (Impressum, Datenschutz, AGB), copyright.
- `templates/components/_sidebar.html` — Dashboard nav items (apartments, inspections, reports, settings). Active state highlighting. Mobile: slide-out drawer with backdrop.
- `templates/components/_bottom_nav.html` — Inspector nav (Schedule, Inspect, Profile). Large icons + labels, 48px+ tap targets.
- `templates/components/_alert.html` — `{% with type="" message="" dismissible=True %}`. Maps to Django message tags (success, warning, error, info). Auto-dismiss with Alpine.js.
- `templates/components/_modal.html` — Alpine.js `x-data="{ open: false }"`. Backdrop, escape-to-close, basic focus management.
- `templates/components/_status_badge.html` — `{% with status="" %}`. OK=emerald, Attention=amber, Urgent=rose. Pill-shaped with icon.
- `templates/components/_loading.html` — HTMX indicator. Spinner + optional text. Used with `hx-indicator`.
- `templates/components/_card.html` — `{% with title="" %}`. White bg, subtle border, optional header. Content via block or slot.

Each component file starts with an HTML comment documenting its API:
```html
<!-- Component: _alert.html
     Context variables:
       type: "success" | "warning" | "error" | "info" (default: "info")
       message: string (required)
       dismissible: bool (default: True)
     Usage: {% include "components/_alert.html" with type="success" message="Saved!" %}
-->
```

**Verification:** Create a style guide page at `/dev/components/` (only in DEBUG mode) that renders every component with sample data.

### Phase 4: Polish and Verify (~20 min)

- Run `make lint` (ruff + djlint) and fix any issues
- Test all three layouts at key breakpoints (375px, 768px, 1024px, 1440px)
- Verify HTMX POST works (CSRF token) — can test with a simple form
- Verify Alpine.js interactions (sidebar toggle, alert dismiss, modal open/close)
- Verify Django messages render correctly in each layout
- Run `make test` to ensure nothing is broken

## Acceptance Criteria

- [ ] `base.html` loads Tailwind CSS, HTMX (pinned), Alpine.js (pinned) with CSRF config
- [ ] `base_public.html` renders with navbar + footer, responsive
- [ ] `base_dashboard.html` renders with sidebar (collapses on mobile), responsive
- [ ] `base_inspector.html` renders with bottom nav, mobile-first (375px baseline)
- [ ] Tailwind config has all 9 color tokens from CLAUDE.md
- [ ] All components created with documented APIs (HTML comment headers)
- [ ] `_alert.html` integrates with Django messages framework
- [ ] HTMX POST requests work (CSRF token configured)
- [ ] HTMX errors handled globally (403 → redirect to login)
- [ ] `home.html` updated to extend `base_public.html`
- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] All layouts tested at 375px, 768px, 1024px, 1280px

## Success Metrics

- All Phase 3 issues (#13, #14, #28, #15) can start immediately after this lands
- No template-level decisions need to be revisited by downstream issues
- Components are used (not bypassed) by the first 3 features that need them

## Dependencies & Risks

**Dependencies (all satisfied):**
- #1 Django project initialized
- #3 Docker environment running (Tailwind watcher included)

**Risks:**
- **Scope creep**: Easy to over-polish components that aren't needed yet. Stick to MVP — components should be functional, not pixel-perfect. They'll be refined when real content fills them.
- **djlint strictness**: 2-space indentation is enforced. Write templates correctly the first time to avoid churn.
- **CDN availability**: HTMX and Alpine loaded from unpkg. Pin versions + add SRI hashes. Self-hosting deferred unless CDN proves unreliable.

## Sources & References

- Issue: [#43 Responsive base template and design system](https://github.com/robert197/baky/issues/43)
- Roadmap: [#44 MVP Build Order](https://github.com/robert197/baky/issues/44)
- Existing files: `templates/base.html`, `tailwind.config.js`, `static/css/input.css`
- CLAUDE.md design context: Color tokens, design principles, brand personality
- Downstream consumers: #13 (Landing page), #14 (Pricing), #28 (Legal pages), #15 (Signup flow)
