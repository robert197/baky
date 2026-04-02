"""Add partial unique index for global slot exclusivity (one booking per date+time_slot).

Cancels duplicate slot bookings from seed data before creating the constraint.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("inspections", "0005_photo_flagged_at_photo_is_flagged"),
    ]

    operations = [
        # Cancel duplicate slot bookings — keep the lowest ID, cancel the rest
        migrations.RunSQL(
            sql="""
                UPDATE inspections_inspection
                SET status = 'cancelled'
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY DATE(scheduled_at AT TIME ZONE 'Europe/Vienna'), time_slot
                                   ORDER BY id
                               ) AS rn
                        FROM inspections_inspection
                        WHERE status IN ('scheduled', 'in_progress', 'completed')
                        AND time_slot != ''
                    ) ranked
                    WHERE rn > 1
                );
            """,
            reverse_sql="SELECT 1;",  # No sensible reverse for data fix
        ),
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX unique_active_slot_per_day
                ON inspections_inspection (
                    DATE(scheduled_at AT TIME ZONE 'Europe/Vienna'),
                    time_slot
                )
                WHERE status IN ('scheduled', 'in_progress', 'completed')
                AND time_slot != '';
            """,
            reverse_sql="DROP INDEX IF EXISTS unique_active_slot_per_day;",
        ),
    ]
