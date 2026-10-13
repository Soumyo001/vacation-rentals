from django.db.models import Q
from django.shortcuts import render
from property_app.forms import LocationSearchForm
from property_app.models import Location

def home(request):
    search_data = (request.GET if "location" in request.GET else None)

    form = LocationSearchForm(search_data)
    matching_locations = Location.objects.none()
    searched = False

    if form.is_bound and form.is_valid():
        searched = True
        location_name = form.cleaned_data["location"]

        matching_locations = (
            Location.objects.filter(is_active=True)
            .filter(
                Q(name__icontains=location_name)
                | Q(city__icontains=location_name)
                | Q(state__icontains=location_name)
                | Q(country__icontains=location_name)
            )
            .order_by("name", "city")[:10]
        )

    context = {
        "form": form,
        "matching_locations": matching_locations,
        "searched": searched,
    }

    return render(
        request,
        "property_app/home.html",
        context,
    )