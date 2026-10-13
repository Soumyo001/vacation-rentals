
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from property_app.models import Location, Property


REQUIRED_COLUMNS = {
    "location_id",
    "city",
    "state",
    "country",
    "location_lonlat",
    "location_boundary_geojson",
    "property_name",
    "property_slug",
    "property_type_category",
    "usd_price",
    "bedroom_count",
    "bathroom_count",
    "amenity_categories",
    "property_lonlat",
    "property_footprint_geojson",
    "property_status",
    "published",
}


def read_dataset(file_path):
    extension = file_path.suffix.lower()

    if extension == ".csv":
        dataframe = pd.read_csv(
            file_path,
            dtype=str,
            keep_default_na=False,
        )
    elif extension == ".xlsx":
        dataframe = pd.read_excel(
            file_path,
            sheet_name="Properties",
            dtype=str,
            keep_default_na=False,
        )
    elif extension == ".parquet":
        dataframe = pd.read_parquet(file_path)
    else:
        raise CommandError(
            "Unsupported file format. Use CSV, XLSX, or Parquet."
        )

    # Keep values consistent across file formats.
    dataframe = dataframe.fillna("").astype(str)

    missing = REQUIRED_COLUMNS - set(dataframe.columns)

    if missing:
        raise CommandError(
            f"Missing required columns: {sorted(missing)}"
        )

    if dataframe.empty:
        raise CommandError("The dataset is empty.")

    if dataframe["property_slug"].duplicated().any():
        raise CommandError("Duplicate property slugs found.")

    return dataframe


def make_location_slug(row):
    location_id = row["location_id"]

    name = (
        f"{row['city']}-"
        f"{row['state']}-"
        f"{row['country']}"
    )

    maximum_length = 49 - len(location_id)

    if maximum_length < 1:
        raise ValueError("Location ID is too long.")

    prefix = slugify(name)[:maximum_length].rstrip("-")

    return f"{prefix}-{location_id}"


def parse_point(value):
    data = json.loads(value)
    longitude, latitude = data["coordinates"]

    longitude = float(longitude)
    latitude = float(latitude)

    if not (-180 <= longitude <= 180):
        raise ValueError("Invalid longitude.")

    if not (-90 <= latitude <= 90):
        raise ValueError("Invalid latitude.")

    return Point(longitude, latitude, srid=4326)


def parse_geometry(value, expected_type):
    geometry = GEOSGeometry(value, srid=4326)

    if geometry.geom_type != expected_type:
        raise ValueError(
            f"Expected {expected_type}, got {geometry.geom_type}."
        )

    if not geometry.valid:
        raise ValueError("Invalid geographic geometry.")

    return geometry


class Command(BaseCommand):
    help = "Import vacation rentals from CSV, Excel, or Parquet."

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=Path,
            help="Path to the rental dataset.",
        )

        parser.add_argument(
            "--limit",
            type=int,
            help="Import only the first N records.",
        )

    def handle(self, *args, **options):
        file_path = options["file"]

        if not file_path.is_absolute():
            file_path = Path(settings.BASE_DIR) / file_path

        if not file_path.is_file():
            raise CommandError(f"File not found: {file_path}")

        dataframe = read_dataset(file_path)

        self.stdout.write(
            f"Dataset contains {len(dataframe)} properties."
        )

        # Basic data analysis using Pandas
        country_counts = (
            dataframe.groupby("country")
            .size()
            .sort_values(ascending=False)
        )

        self.stdout.write("Properties by country:")

        for country, count in country_counts.items():
            self.stdout.write(f"  {country}: {count}")

        limit = options["limit"]

        if limit is not None:
            if limit < 1:
                raise CommandError("--limit must be positive.")

            dataframe = dataframe.head(limit)

        created_locations = 0
        created_properties = 0
        updated_properties = 0

        # Roll back the entire import if a record is invalid.
        with transaction.atomic():
            for row_number, row in enumerate(
                dataframe.to_dict("records"),
                start=2,
            ):
                try:
                    status = row["property_status"].lower()
                    published = row["published"].lower()

                    if status not in {"draft", "published"}:
                        raise ValueError("Invalid property status.")

                    if published not in {"true", "false"}:
                        raise ValueError("Invalid published value.")

                    if (status == "published") != (published == "true"):
                        raise ValueError(
                            "Property status and published value disagree."
                        )

                    amenities = json.loads(row["amenity_categories"])

                    if not isinstance(amenities, list):
                        raise ValueError("Amenities must be a list.")

                    location, location_created = (
                        Location.objects.update_or_create(
                            slug=make_location_slug(row),
                            defaults={
                                "name": row["city"],
                                "city": row["city"],
                                "state": row["state"],
                                "country": row["country"],
                                "point": parse_point(
                                    row["location_lonlat"]
                                ),
                                "boundary": parse_geometry(
                                    row["location_boundary_geojson"],
                                    "MultiPolygon",
                                ),
                            },
                        )
                    )

                    property_obj, property_created = (
                        Property.objects.update_or_create(
                            slug=row["property_slug"],
                            defaults={
                                "location": location,
                                "title": row["property_name"],
                                "property_type": row[
                                    "property_type_category"
                                ],
                                "status": status,
                                "price": Decimal(row["usd_price"]),
                                "bedrooms": int(row["bedroom_count"]),
                                "bathrooms": int(row["bathroom_count"]),
                                "amenities": amenities,
                                "point": parse_point(
                                    row["property_lonlat"]
                                ),
                                "footprint": parse_geometry(
                                    row["property_footprint_geojson"],
                                    "Polygon",
                                ),
                                "is_active": published == "true",
                            },
                        )
                    )

                    if location_created:
                        created_locations += 1

                    if property_created:
                        created_properties += 1
                    else:
                        updated_properties += 1

                except (
                    KeyError,
                    ValueError,
                    TypeError,
                    InvalidOperation,
                ) as error:
                    raise CommandError(
                        f"Dataset row {row_number}: {error}"
                    ) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Import successful! "
                f"Locations created: {created_locations}, "
                f"Properties created: {created_properties}, "
                f"Properties updated: {updated_properties}."
            )
        )
