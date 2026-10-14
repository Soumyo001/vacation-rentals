from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from sentence_transformers import SentenceTransformer
from property_app.models import Location

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384

class Command(BaseCommand):
    help = "Generate embeddings for locations without existing vectors."

    def handle(self, *args, **options):

        pending_locations = list(
            Location.objects.filter(
                embedding__isnull=True
            ).order_by("id")
        )

        locations = [
            location for location in pending_locations if location.name.strip()
        ]

        skipped = len(pending_locations) - len(locations)

        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {skipped} locations with empty names."
                )
            )

        if not locations:
            self.stdout.write(
                self.style.SUCCESS(
                    "No locations need new embeddings."
                )
            )
            return

        self.stdout.write(
            f"Generating embeddings for {len(locations)} locations..."
        )

        # Load the model only once.
        model = SentenceTransformer(MODEL_NAME)

        location_names = [
            location.name for location in locations
        ]

        # Each location name becomes a 384-dimensional vector.
        embeddings = model.encode(
            location_names,
            convert_to_numpy=True,
            show_progress_bar=True,
        )

        if embeddings.shape != (len(locations), EMBEDDING_DIMENSIONS,):
            raise CommandError("Generated embeddings have unexpected dimensions.")

        # Save vectors without changing other location fields.
        with transaction.atomic():
            for location, embedding in zip(locations, embeddings):
                location.embedding = embedding.tolist()
                location.save(update_fields=["embedding"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully saved {len(locations)} embeddings."
            )
        )
