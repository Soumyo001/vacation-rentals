
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile

from PIL import Image, UnidentifiedImageError

from property_app.models import Location, Property, PropertyImage

MAX_IMAGE_SIZE = 8 * 1024 * 1024

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
    "images",
    "property_description",
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

def download_image(url):
    parsed_url = urlparse(url)

    # dataset contains Unsplash image URLs
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "images.unsplash.com"
    ):
        raise ValueError("Unsupported image URL.")

    request = Request(
        url,
        headers={"User-Agent": "VacationRentalAssignment/1.0"},
    )

    with urlopen(request, timeout=20) as response:
        image_data = response.read(MAX_IMAGE_SIZE + 1)

    if len(image_data) > MAX_IMAGE_SIZE:
        raise ValueError("Image exceeds the 8 MB limit.")
    
    with Image.open(BytesIO(image_data)) as image:
        image_format = image.format
        image.verify()

    extensions = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
    }

    extension = extensions.get(image_format)

    if extension is None:
        raise ValueError("Unsupported image format.")

    return image_data, extension

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

        parser.add_argument(
            "--with-images",
            action="store_true",
            help="Download and import property images.",
        )

    
    def import_images(self, dataframe):
        downloaded_images = {}

        created = 0
        repaired = 0
        skipped = 0
        failed = 0

        for row in dataframe.to_dict("records"):
            property_obj = Property.objects.get(
                slug=row["property_slug"]
            )

            try:
                image_urls = json.loads(row["images"])

                if not isinstance(image_urls, list):
                    raise ValueError("Images must be a list.")

            except (ValueError, TypeError) as error:
                self.stderr.write(
                    f"Invalid images for {property_obj.title}: {error}"
                )
                failed += 1
                continue

            for position, image_url in enumerate(image_urls):
                existing_image = PropertyImage.objects.filter(
                    property=property_obj,
                    sort_order=position,
                ).first()

                if (
                    existing_image
                    and existing_image.image
                    and existing_image.image.storage.exists(existing_image.image.name)
                ):
                    skipped += 1
                    continue

                if not isinstance(image_url, str) or not image_url.strip():
                    failed += 1
                    continue

                # Reuse downloaded bytes when URLs repeat.
                if image_url not in downloaded_images:
                    try:
                        downloaded_images[image_url] = download_image(
                            image_url
                        )

                    except (
                        HTTPError,
                        URLError,
                        TimeoutError,
                        OSError,
                        ValueError,
                        UnidentifiedImageError,
                    ) as error:
                        downloaded_images[image_url] = None

                        self.stderr.write(
                            f"Image download failed: {error}"
                        )

                downloaded_image = downloaded_images[image_url]

                if downloaded_image is None:
                    failed += 1
                    continue

                image_data, extension = downloaded_image

                property_image = existing_image or PropertyImage(
                    property=property_obj,
                    sort_order=position,
                )

                property_image.alt_text = property_obj.title
                property_image.is_primary = (position == 0)

                filename = f"{property_obj.slug}-{position + 1}{extension}"

                property_image.image.save(
                    filename,
                    ContentFile(image_data),
                    save=True,
                )

                if existing_image:
                    repaired += 1
                else:
                    created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Images created: {created}, "
                f"repaired: {repaired}, "
                f"skipped: {skipped}, "
                f"failed: {failed}."
            )
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
                                "description": row["property_description"].strip(),
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

        if options["with_images"]:
            self.import_images(dataframe)
