from django.http import HttpResponse

from apps.accounts.decorators import inspector_required


@inspector_required
def index(request):
    return HttpResponse("Inspector — coming soon")
