# BAKY

**Betreuung. Absicherung. Kontrolle. Your Home.**

Apartment monitoring and inspection platform for short-term rentals in Vienna.

## What is BAKY?

BAKY helps property owners maintain oversight of their short-term rental apartments between guest stays. We schedule professional inspections, execute checklist-based walkthroughs with photo documentation, and deliver instant reports.

## Quick Start

```bash
# Prerequisites: Docker only
cp .env.example .env
make up
make migrate
make seed
# Visit http://localhost:8000
```

## Development

This project is built with Claude Code. See [CLAUDE.md](CLAUDE.md) for conventions, architecture, and workflow.

### Custom Skills

| Skill | Description |
|-------|------------|
| `/next-issue` | Pick the next issue from the roadmap |
| `/done-issue` | Complete current issue (verify, commit, PR, close) |
| `/baky-status` | Quick project status overview |
| `/new-django-app` | Scaffold a new Django app |
| `/new-model` | Add model + admin + factory + tests |
| `/new-view` | Create view + template + URL + tests |
| `/design-page` | Design a beautiful page with BAKY's design system |
| `/inspect-flow` | Domain guide for inspection features |

### Compound Engineering Workflows

| Workflow | When to Use |
|----------|------------|
| `/ce:brainstorm` | Exploring a new feature idea |
| `/ce:plan` | Planning implementation for an issue |
| `/ce:work` | Executing a plan |
| `/ce:compound` | Documenting a solved problem |
| `/ce:review` | Code review before merging |

## Tech Stack

Django 5.x + HTMX + Alpine.js + Tailwind CSS + PostgreSQL — all running in Docker.

## License

Proprietary. All rights reserved.
