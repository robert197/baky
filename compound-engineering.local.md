---
review_agents:
  - compound-engineering:review:architecture-strategist
  - compound-engineering:review:pattern-recognition-specialist
  - compound-engineering:review:performance-oracle
  - compound-engineering:review:security-sentinel
  - compound-engineering:review:data-integrity-guardian
---

## BAKY Review Context

### Project Type
Django web application — apartment inspection platform for short-term rentals in Vienna.

### Key Patterns to Enforce
- All data access scoped by user role (Owner sees only their data, Inspector only assigned)
- Apartment access codes stored encrypted (django-encrypted-model-fields)
- Photos served via signed URLs only (no public S3 access)
- All commands run via Docker (make targets)
- HTMX for server interactions, Alpine.js for local state only
- Mobile-first Tailwind CSS with design tokens from CLAUDE.md

### Security Priorities
- GDPR compliance (EU data storage, retention policies, right to deletion)
- No hardcoded secrets or API keys
- Role-based access control — 404 on unauthorized (not 403)
- Encrypted sensitive fields (access codes, PINs)
- Signed URLs with expiry for photos

### Performance Considerations
- Photo uploads compressed client-side before upload
- Thumbnails auto-generated (300x300)
- Lazy loading for photo galleries
- Minimal JS — HTMX + Alpine.js, no heavy SPA framework

### Database Patterns
- TimeStampedModel base class for created_at/updated_at
- JSONField for checklist schemas
- Proper indexes on frequently filtered fields
- Soft delete with grace period for GDPR compliance
