from decimal import Decimal
from django.contrib.gis.db.models.functions import Distance
from django.db.models import F
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from property_app.forms import LocationSearchForm, SpatialFilterForm
from property_app.models import Location, Property
from property_app.services import semantic_location_search

def home(request):
    search_data = (request.GET if "location" in request.GET else None)

    form = LocationSearchForm(search_data)
    matching_locations = Location.objects.none()
    searched = False
    semantic_suggestions = False

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
            ).order_by("name", "city")[:10]
        )

        if not matching_locations.exists():
            matching_locations = semantic_location_search(location_name, limit=5)
            semantic_suggestions = True

    context = {
        "form": form,
        "matching_locations": matching_locations,
        "searched": searched,
        "semantic_suggestions": semantic_suggestions,
    }

    return render(
        request,
        "property_app/home.html",
        context,
    )

def property_list(request):
    properties = (
        Property.objects.filter(
            is_active=True,
            location__is_active=True,
        ).select_related("location").prefetch_related("images")
    )

    location_query = request.GET.get("location", "").strip()
    location_id = request.GET.get("location_id")

    selected_location = None
    spatial_form = None
    search_error = ""
    spatial_message = ""
    boundary_filter_active = False
    semantic_locations = Location.objects.none()

    if location_id:
        try:
            location_pk = int(location_id)
        except ValueError:
            raise Http404("Invalid location ID.")

        selected_location = get_object_or_404(
            Location,
            pk=location_pk,
            is_active=True,
        )

        filter_data = request.GET.copy()

        if "radius_km" not in filter_data:
            filter_data["radius_km"] = "5"

        spatial_form = SpatialFilterForm(filter_data)

        if spatial_form.is_valid():
            radius_km = (
                spatial_form.cleaned_data["radius_km"]
                or Decimal("5.0")
            )

            within_boundary = (
                spatial_form.cleaned_data["within_boundary"]
            )

            if selected_location.point is None:
                properties = properties.none()
                spatial_message = (
                    "This location has no geographic coordinates."
                )
            else:
                radius_metres = float(radius_km) * 1000

                properties = properties.filter(
                    point__dwithin=(
                        selected_location.point,
                        radius_metres,
                    )
                )

            if within_boundary:
                if selected_location.boundary is None:
                    properties = properties.none()
                    spatial_message = (
                        "This location has no geographic boundary."
                    )
                else:
                    properties = properties.filter(
                        footprint__intersects=selected_location.boundary
                    )
                    boundary_filter_active = True
        else:
            properties = properties.none()

    elif location_query:
        search_form = LocationSearchForm(
            {"location": location_query}
        )

        if search_form.is_valid():
            location_name = search_form.cleaned_data["location"]

            properties = properties.filter(
                Q(location__name__icontains=location_name)
                | Q(location__city__icontains=location_name)
                | Q(location__state__icontains=location_name)
                | Q(location__country__icontains=location_name)
            )

            if not properties.exists():
                semantic_locations = semantic_location_search(
                    location_name,
                    limit=5,
                    available_only=True,
                )
        else:
            properties = properties.none()
            search_error = "Enter a valid location name."

    properties = properties.order_by("-created_at", "id")

    paginator = Paginator(properties, 6)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    query_parameters = request.GET.copy()
    query_parameters.pop("page", None)

    context = {
        "page_obj": page_obj,
        "selected_location": selected_location,
        "location_query": location_query,
        "spatial_form": spatial_form,
        "search_error": search_error,
        "spatial_message": spatial_message,
        "boundary_filter_active": boundary_filter_active,
        "query_string": query_parameters.urlencode(),
        "semantic_locations": semantic_locations,
    }

    return render(
        request,
        "property_app/property_list.html",
        context,
    )

def property_detail(request, slug):
    property_obj = get_object_or_404(
        Property.objects.filter(
            is_active=True,
            location__is_active=True,
        ).select_related("location")
        .prefetch_related("images")
        .annotate(
            distance_to_city=Distance(
                "point",
                F("location__point"),
            )
        ),
        slug=slug,
    )

    context = {
        "property": property_obj,
    }

    return render(
        request,
        "property_app/property_detail.html",
        context,
    )