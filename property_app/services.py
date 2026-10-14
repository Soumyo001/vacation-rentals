from functools import lru_cache
from pgvector.django import CosineDistance
from property_app.models import Location

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)

def semantic_location_search(search_text, limit=5):
    search_text = search_text.strip()
    if not search_text:
        return Location.objects.none()

    model = get_embedding_model()
    query_embedding = model.encode(search_text).tolist()

    matching_locations = (
        Location.objects.filter(
            is_active=True,
            embedding__isnull=False,
        ).annotate(
            distance=CosineDistance(
                "embedding",
                query_embedding,
            )
        ).order_by("distance")[:limit]
    )
    return matching_locations