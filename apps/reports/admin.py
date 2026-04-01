from django.contrib import admin
from unfold.admin import ModelAdmin

from baky.tasks import queue_task

from .models import Report


@admin.action(description="Bericht(e) neu erstellen")
def regenerate_reports(modeladmin, request, queryset):
    """Re-queue report generation for selected reports."""
    for report in queryset.select_related("inspection"):
        report.status = Report.Status.PENDING
        report.error_message = ""
        report.save(update_fields=["status", "error_message", "updated_at"])
        queue_task(
            "apps.reports.tasks.generate_report",
            report.inspection_id,
            task_name=f"regenerate_report_{report.inspection_id}",
        )


@admin.action(description="Bericht-E-Mail erneut senden")
def resend_report_email(modeladmin, request, queryset):
    """Clear email_sent_at and re-queue email delivery for selected reports."""
    count = 0
    for report in queryset.filter(status=Report.Status.COMPLETED):
        report.email_sent_at = None
        report.save(update_fields=["email_sent_at", "updated_at"])
        queue_task(
            "apps.reports.tasks.send_report_email",
            report.inspection_id,
            task_name=f"resend_report_email_{report.inspection_id}",
        )
        count += 1
    modeladmin.message_user(request, f"{count} Bericht-E-Mail(s) erneut gesendet.")


@admin.register(Report)
class ReportAdmin(ModelAdmin):
    list_display = ["__str__", "status", "email_sent_at", "generated_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["inspection__apartment__address"]
    raw_id_fields = ["inspection"]
    readonly_fields = ["html_content", "generated_at", "email_sent_at", "created_at", "updated_at"]
    actions = [regenerate_reports, resend_report_email]
    fieldsets = (
        (
            "Bericht",
            {
                "fields": ("inspection", "status", "generated_at", "email_sent_at"),
            },
        ),
        (
            "Inhalt",
            {
                "fields": ("html_content", "error_message"),
                "classes": ("collapse",),
            },
        ),
        (
            "Zeitstempel",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
