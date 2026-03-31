# BAKY - Apartment Monitoring & Inspection Platform

## Project Overview

BAKY is a specialized apartment monitoring and inspection service for short-term rental properties in Vienna.
The platform manages scheduling inspections, executing checklist-based walkthroughs, capturing photo documentation,
and delivering instant reports to property owners.

**Tagline**: Betreuung. Absicherung. Kontrolle. Your Home.

**Repo**: https://github.com/robert197/baky
**Roadmap**: https://github.com/robert197/baky/issues/44 (pinned issue with build order and dependencies)

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Django 5.x (Python 3.12) | ORM, auth, admin, forms, file uploads |
| Frontend | Django Templates + HTMX + Alpine.js | Server-rendered with interactive islands |
| Styling | Tailwind CSS | Utility-first, mobile-first |
| Database | PostgreSQL 16 | JSON fields for checklist schemas |
| File Storage | AWS S3 / Cloudflare R2 | django-storages, signed URLs |
| Background Tasks | Django-Q2 | Report generation, email dispatch |
| Email | Resend | Transactional email for reports |
| PDF | WeasyPrint | PDF report export |
| Admin | Django Admin + django-unfold | Modern admin UI |
| Hosting | Docker everywhere | Dev, CI, and production |

## Everything Runs in Docker

**Docker is the only prerequisite.** No local Python, pip, or Node installs.
The `Makefile` is the developer CLI.

```bash
make up                  # Start all services (web, db, redis, worker, tailwind, mailpit)
make down                # Stop all services
make migrate             # Run Django migrations
make makemigrations      # Create new migrations
make test                # Run pytest suite
make lint                # Run ruff + djlint
make shell               # Django shell (inside container)
make dbshell             # PostgreSQL shell
make createsuperuser     # Create admin user
make seed                # Load demo/seed data
make logs                # Tail all service logs
make manage CMD="..."    # Run any manage.py command
```

## Project Structure

```
baky/
├── CLAUDE.md              # This file
├── Dockerfile             # Multi-stage: dev + production
├── docker-compose.yml     # All services
├── Makefile               # Developer CLI (wraps docker compose)
├── pyproject.toml         # Python config, ruff, pytest
├── requirements/
│   ├── base.txt
│   ├── local.txt
│   └── production.txt
├── baky/                  # Django project
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/          # Custom User model, auth, roles (Owner, Inspector, Admin)
│   ├── apartments/        # Apartment CRUD, checklist templates
│   ├── inspections/       # Inspection execution, scheduling
│   ├── reports/           # Report generation, email delivery
│   ├── public/            # Landing page, pricing, legal pages
│   └── dashboard/         # Owner dashboard
├── templates/
│   ├── base.html          # HTML shell with Tailwind, HTMX, Alpine.js
│   ├── public/            # Public pages
│   ├── dashboard/         # Owner dashboard
│   ├── inspector/         # Inspector mobile app
│   └── components/        # Reusable template components
├── static/
├── media/                 # Local dev file uploads
├── docs/
│   ├── plans/             # Implementation plans (/ce:plan output)
│   ├── brainstorms/       # Feature brainstorms (/ce:brainstorm output)
│   └── solutions/         # Documented solutions (/ce:compound output)
└── tests/
    ├── conftest.py
    ├── factories.py
    └── [mirrors apps/ structure]
```

## Code Conventions

### Python
- Python 3.12+
- Ruff for linting and formatting (line-length: 120)
- Type hints on public functions
- Docstrings only where intent is non-obvious
- Django conventions: fat models, thin views
- Use `TimeStampedModel` base class for `created_at` / `updated_at`

### Django
- Custom User model (`apps.accounts.models.User`) with `role` field
- Role-based access: `@owner_required`, `@inspector_required` decorators
- Views: function-based for simple pages, class-based for CRUD
- URLs: German slugs for public pages (`/preise/`, `/datenschutz/`), English for app (`/dashboard/`, `/inspector/`)
- Settings split: `base.py` (shared), `local.py` (dev), `production.py` (prod)

### Templates
- HTMX for dynamic content (no SPA, no full page reloads for interactions)
- Alpine.js for local component state (toggles, modals, photo preview)
- Tailwind CSS utility classes (no custom CSS unless absolutely necessary)
- Component pattern: `templates/components/_name.html` with `{% include %}`
- Mobile-first: design for inspector's phone first, then scale up

### Testing
- pytest-django with factory_boy
- Run: `make test` (or `make test ARGS="-k test_name"` for specific tests)
- Factories in `tests/factories.py`
- One integration test per critical path (signup, inspection, report)
- Unit tests for business logic in models

### Git
- Branch naming: `feat/issue-number-short-description` (e.g., `feat/7-core-models`)
- Commit messages: conventional format (`feat(models): add Apartment model`)
- One feature branch per issue
- PR into `main`

## User Roles

| Role | Access | Entry Point |
|------|--------|-------------|
| Owner | Own apartments, own reports, subscription | `/dashboard/` |
| Inspector | Assigned inspections only | `/inspector/` |
| Admin | Everything | `/admin/` |

## Key Domain Concepts

- **Apartment**: A short-term rental property in Vienna, belongs to an Owner
- **ChecklistTemplate**: JSON-based list of items to inspect, customized per apartment
- **Inspection**: A scheduled visit by an Inspector to check an Apartment
- **InspectionItem**: One checklist item result (OK / Flagged / N.A.) with optional photos and notes
- **Overall Rating**: OK (all good), Attention (some flags), Urgent (critical issues)
- **Report**: Auto-generated from Inspection data, sent to Owner via email

## Workflow: How to Pick the Next Issue

1. Read the roadmap: `gh issue view 44 -R robert197/baky`
2. Find the first unchecked `- [ ]` item where all dependencies (after `←`) are closed
3. Open that issue, read requirements, implement it
4. After completing: close the issue, check it off in #44
5. Repeat

## Workflow: Implementing a Feature

1. **Pick issue** from roadmap (#44)
2. **Create branch**: `git checkout -b feat/ISSUE-short-desc`
3. **Plan** (for non-trivial issues): `/ce:plan` with the issue requirements
4. **Implement**: Follow the plan, use `make test` continuously
5. **Verify**: `/superpowers:verification-before-completion`
6. **Commit and PR**: Follow git conventions above
7. **Close issue** and update roadmap

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
- `/validate --full` — Full validation including e2e
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

### Makefile Targets (Docker)

The Makefile must include these targets (implemented in issue #3):

```makefile
e2e:          # Run pytest-playwright e2e tests
validate:     # Run full validation suite (lint + test + check + e2e)
seed:         # Load all seed data via seed_all management command
```

## Design Context

### Users
- **Property owners** in Vienna managing 1-5 short-term rental apartments remotely
- **BAKY inspectors** doing field work on mobile phones, often one-handed
- Users are German-speaking professionals who value reliability and clarity

### Brand Personality
Trustworthy, professional, approachable. Like a reliable building manager — competent but not cold.

### Aesthetic Direction
- **Tone**: Clean, professional, warm. Not corporate-sterile and not startup-flashy.
- **Color palette**: Deep navy/slate as primary, warm amber/gold as accent, clean whites. Evokes trust (blue) + home warmth (amber).
- **Typography**: Modern sans-serif. Clear hierarchy. Large readable text for mobile inspector use.
- **Inspiration**: Think Wise (banking app) meets Airbnb host tools. Professional dashboards with warmth.
- **Anti-references**: Generic SaaS templates, neon-on-dark "tech" aesthetics, overly minimalist no-personality designs.
- **Theme**: Light mode primary. Dark mode not needed for MVP.

### Design Principles
1. **Mobile-first, always** — Inspectors work on phones. Every UI must work beautifully at 375px.
2. **Information density over decoration** — Owners want data, not fluff. Show what matters.
3. **One-hand friendly** — Inspector UI: large tap targets, bottom-anchored actions, no precision required.
4. **Trust through clarity** — Clear status indicators, honest error states, no ambiguity in reports.
5. **Progressive disclosure** — Show essentials first, details on demand. Don't overwhelm.

### Color Tokens (Tailwind)
```
Primary:    slate-800 (#1e293b) — headings, nav, primary actions
Secondary:  slate-600 (#475569) — body text
Accent:     amber-500 (#f59e0b) — CTAs, highlights, active states
Success:    emerald-500 (#10b981) — OK status
Warning:    amber-500 (#f59e0b) — Attention status
Danger:     rose-500 (#f43f5e) — Urgent status
Surface:    slate-50 (#f8fafc) — page backgrounds
Card:       white (#ffffff) — card backgrounds
Border:     slate-200 (#e2e8f0) — subtle borders
```
