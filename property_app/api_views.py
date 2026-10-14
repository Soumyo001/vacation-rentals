from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from property_app.serializers import LocationSuggestionSerializer, LocationAutocompleteQuerySerializer
from property_app.services import semantic_location_search

@api_view(["GET"])
def location_autocomplete(request):
    is_htmx = request.headers.get("HX-Request") == "true"
    query_data = request.query_params.copy()
    if is_htmx and "q" not in query_data:
        query_data["q"] = query_data.get("location", "")

    query_serializer = LocationAutocompleteQuerySerializer(data=query_data)

    if is_htmx:
        if not query_serializer.is_valid():
            return render(
                request,
                "property_app/partials/location_suggestions.html",
                {"locations": []},
            )
    else: 
        query_serializer.is_valid(raise_exception=True)

    search_text = query_serializer.validated_data["q"]
    limit = query_serializer.validated_data["limit"]

    locations = semantic_location_search(search_text, limit=limit)

    if is_htmx:
        return render(
            request,
            "property_app/partials/location_suggestions.html",
            {"locations": locations},
        )
    
    result_serializer = LocationSuggestionSerializer(locations, many=True)
    results = result_serializer.data

    return Response({
        "query": search_text,
        "count": len(results),
        "results": results,
    })