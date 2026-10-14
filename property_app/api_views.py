from rest_framework.decorators import api_view
from rest_framework.response import Response
from property_app.serializers import LocationSuggestionSerializer, LocationAutocompleteQuerySerializer
from property_app.services import semantic_location_search

@api_view(["GET"])
def location_autocomplete(request):
    query_serializer = LocationAutocompleteQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)

    search_text = query_serializer.validated_data["q"]
    limit = query_serializer.validated_data["limit"]

    locations = semantic_location_search(search_text, limit=limit)
    result_serializer = LocationSuggestionSerializer(locations, many=True)
    results = result_serializer.data

    return Response({
        "query": search_text,
        "count": len(results),
        "results": results,
    })