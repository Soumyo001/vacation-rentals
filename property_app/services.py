from functools import lru_cache
from pgvector.django import CosineDistance
from property_app.models import Location, Property

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)

def semantic_location_search(search_text, limit=5, available_only=False):
    search_text = search_text.strip()
    if not search_text:
        return Location.objects.none()

    locations = Location.objects.filter(
        is_active=True,
        embedding__isnull=False,
    )

    if available_only:
        available_locations = Property.objects.filter(
            is_active=True,
            location__is_active=True,
        ).values("location_id")

        locations = locations.filter(id__in=available_locations)

    model = get_embedding_model()
    query_embedding = model.encode(search_text).tolist()

    return (
        locations.annotate(
            distance=CosineDistance(
                "embedding",
                query_embedding,
            )
        ).order_by("distance")[:limit]
    )