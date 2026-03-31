---
name: inspect-flow
description: Domain guide for implementing inspection-related features. Covers the full lifecycle from scheduling to report delivery.
user-invokable: true
argument-hint: "[aspect: scheduling|checklist|execution|reporting|notifications]"
---

# Inspection Workflow Domain Guide

Reference this when implementing any inspection-related feature.

## The Inspection Lifecycle

```
Schedule → Assign Inspector → Day-of Reminder
    ↓
Inspector Opens App → Views Schedule → Starts Inspection
    ↓
Walk Through Checklist → Mark OK/Flag/N.A. → Take Photos → Add Notes
    ↓
Review Summary → Set Overall Rating → Submit
    ↓
Background: Generate Report → Send Email to Owner
    ↓
If Urgent: Immediate Alert (email, future: SMS)
    ↓
Owner Views Report in Dashboard → Exports PDF (v1.1)
```

## Key Business Rules

### Scheduling
- Basis plan: 2 inspections/month per apartment
- Extra plan: 4 inspections/month per apartment
- Business hours only: 08:00-18:00
- No overlapping inspections for same inspector
- Day-before reminder to both inspector and owner

### Checklist Execution
- Items: OK / Flagged / N.A.
- Flagged items MUST have severity (low/medium/high/urgent)
- Photos optional for OK items, strongly encouraged for flagged items
- Progress auto-saves per item (no lost work)
- Inspector can add general notes at any time

### Severity Classification
- **OK**: All items passed
- **Attention**: Any flagged items with low/medium severity
- **Urgent**: Any item with high/urgent severity → triggers immediate alert

### Report Generation
- Must complete within 30 minutes of submission
- Includes: all checklist results, photos, notes, overall rating
- Grouped by category (General, Kitchen, Bathroom, etc.)
- Flagged items highlighted with severity badge and photos

### Photo Handling
- Max 10MB per photo, JPEG/PNG/HEIC accepted
- HEIC converted to JPEG on upload
- Thumbnails auto-generated (300x300)
- Stored in S3 with signed URLs (24h expiry)
- Client-side compression before upload

## Data Flow

```
InspectionItem.result = "flagged"
    → InspectionItem.severity = "urgent"
    → Inspection.overall_rating = "urgent" (auto-calculated on submit)
    → Report.generate() (background task)
    → Email.send_report() (background task)
    → Email.send_urgent_alert() (immediate, separate from report)
```

## Models Involved

- `Inspection` — the visit itself
- `InspectionItem` — one checklist item result
- `Photo` — attached to InspectionItem or Inspection
- `ChecklistTemplate` — source of items for the apartment
- `Apartment` — the property being inspected
- `Inspector` — the person doing the inspection
- `Owner` — receives the report

## Testing Scenarios

When testing inspection features, always cover:
1. Happy path: full inspection, all OK
2. Mixed results: some OK, some flagged (low severity)
3. Urgent finding: at least one item flagged with urgent severity
4. Edge cases: empty checklist, all N.A., inspection cancelled mid-way
5. Photo upload: success, failure, retry
6. Offline: items saved locally, synced when online (if PWA)
