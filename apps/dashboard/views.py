from django.http import HttpResponse

from apps.accounts.decorators import owner_required


@owner_required
def index(request):
    return HttpResponse("Dashboard — coming soon")
