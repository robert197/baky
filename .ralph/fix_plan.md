# BAKY MVP Build Plan

## Phase 1: Foundation
- [ ] #1 Initialize Django 5.x project with recommended stack
- [ ] #29 Set up environment and secrets management
- [ ] #3 Set up Docker development environment (everything runs in Docker)
- [ ] #2 Update CLAUDE.md with actual project paths after scaffolding
- [ ] #4 Configure linting, formatting, and pre-commit hooks
- [ ] #5 Set up testing infrastructure with pytest-django
- [ ] #43 Responsive base template and design system
- [ ] E2E: Set up pytest-playwright for end-to-end validation

## Phase 2: Data Layer
- [ ] #7 Implement core data models (Owner, Apartment, Inspection, etc.)
- [ ] #8 Set up Django authentication with role-based access control
- [ ] #30 Load default checklist template as Django fixture
- [ ] #10 Implement checklist template system with JSON schema
- [ ] #9 Configure S3/R2 file storage for photo uploads
- [ ] #11 Set up background task processing with Django-Q2
- [ ] #25 Implement security: encrypted fields, signed URLs, HSTS
- [ ] #12 Customize Django Admin with django-unfold
- [ ] SEED: Create comprehensive seed data for all models

## Phase 3: Public Website
- [ ] #13 Build public landing page with value proposition
- [ ] #14 Build pricing page
- [ ] #28 Build legal pages: Impressum, Datenschutz, AGB
- [ ] #15 Build owner signup and onboarding flow
- [ ] #42 Google Maps address autocomplete integration
- [ ] E2E: Public website validation (pages load, signup works)

## Phase 4: Inspector App
- [ ] #27 Build inspection scheduling system
- [ ] #19 Build inspector daily schedule view (mobile-optimized)
- [ ] #20 Build checklist execution interface with OK/Flag/N.A.
- [ ] #21 Build in-app photo capture per checklist item
- [ ] #22 Build inspection submission and report trigger flow
- [ ] E2E: Inspector workflow validation (schedule → checklist → submit)

## Phase 5: Reports & Notifications
- [ ] #23 Build automated report generation from inspection data
- [ ] #24 Implement email delivery for inspection reports
- [ ] E2E: Report generation and email delivery validation

## Phase 6: Owner Dashboard
- [ ] #16 Build owner dashboard - apartment list and management
- [ ] #17 Build inspection timeline and report detail view
- [ ] #18 Build subscription management for owners (basic MVP)
- [ ] E2E: Owner dashboard validation (view apartments, reports, timeline)

## Phase 7: Compliance & Launch
- [ ] #26 Implement GDPR compliance for inspection data and photos
- [ ] #40 Seed data and demo environment
- [ ] #6 Configure CI/CD pipeline with GitHub Actions
- [ ] #41 Production deployment configuration
- [ ] FINAL: Full E2E regression suite passes
