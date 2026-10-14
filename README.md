# Vacation Rentals — GeoDjango & Semantic Search

A Django-based vacation rental management system featuring geographic property search and AI-powered location autocomplete.

Built using **Django, PostgreSQL, PostGIS, pgvector, Django REST Framework, and Sentence Transformers**.

## Features

- Property listings, location search, pagination, property details, images, and amenities
- Geographic radius and boundary-intersection searches using PostGIS
- Semantic location search using `all-MiniLM-L6-v2` and pgvector with HNSW indexing
- Live location autocomplete powered by a REST API
- Django Admin with filters, inline image uploads, and previews
- Pandas-based data imports supporting CSV, Excel, and Parquet

## Getting Started

### Prerequisites

- Python 3.12
- Docker Engine and Docker Compose
- GDAL and GEOS system libraries
- Internet connection for initial model and image downloads

On Ubuntu, install the required system libraries:

```bash
sudo apt update
sudo apt install -y python3-venv gdal-bin libgdal-dev libgeos-dev
```

### 1. Configure the environment

From the cloned project directory:

```bash
cp .env.example .env
```

Update `.env` with the configuration and credentials provided separately.

### 2. Start PostgreSQL

```bash
docker compose up --build -d
docker compose ps
```

Wait for the database container to become healthy. Docker automatically initializes PostgreSQL with PostGIS and pgvector extensions.

### 3. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Initialize the database

```bash
python manage.py migrate
```

This creates the database tables and HNSW vector index.

### 5. Import properties and images

```bash
mkdir -p media
python manage.py import_rentals data/rental_properties_assignment_ready.csv --with-images
```

This imports 100 sample properties and their locations. The `--with-images` option downloads property images into Django's local `media/` directory.

**The `media/` directory is not stored in GitHub.** Images are downloaded from the dataset's external URLs during setup. Check the import output for failed downloads; the same command can be rerun to retry missing images.

The importer also supports `.xlsx` and `.parquet` datasets.

### 6. Generate location embeddings

```bash
python manage.py generate_location_embeddings
```

This downloads the required Sentence Transformers model on first use and stores 384-dimensional location embeddings in pgvector. Existing embeddings are skipped on subsequent runs.

### 7. Configure Django Admin

```bash
python manage.py createsuperuser
```

Create the admin account using the credentials provided separately. This step is required for a fresh database.

### 8. Run the application

```bash
python manage.py runserver
```

The application is now accessible at **http://127.0.0.1:8000/**.

## Application URLs

| Path | Description |
|---|---|
| `/` | Homepage with live semantic location autocomplete |
| `/?location=Japan` | Search locations by name, city, or country |
| `/properties/` | Browse published properties with pagination |
| `/properties/?location=Japan` | Filter properties by location |
| `/properties/?location_id=5&radius_km=5` | Find properties within a 5 km radius using PostGIS |
| `/properties/?location_id=5&radius_km=5&within_boundary=on` | Filter properties by radius and footprint-boundary intersection |
| `/properties/<slug>/` | Property details, images, amenities, and distance from the reference location |
| `/api/locations/autocomplete/?q=Umeda&limit=5` | Semantic location autocomplete REST API |
| `/admin/` | Django administration |

*Note: `location_id=5` represents Umeda in the tested database. IDs may differ after a fresh installation.*

## Project Structure

```bash
vacation-rentals/
├── .env.example
├── .gitignore
├── compose.yaml
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── data/
│   ├── rental_properties_assignment_ready.csv
│   ├── rental_properties_assignment_ready.parquet
│   └── rental_properties_assignment_ready.xlsx
├── docker/
│   └── db/
│       ├── Dockerfile
│       └── init.sql
├── LICENSE
├── manage.py
├── property_app/
│   ├── __init__.py
│   ├── admin.py
│   ├── api_views.py
│   ├── apps.py
│   ├── forms.py
│   ├── management/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── generate_location_embeddings.py
│   │       └── import_rentals.py
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── 0001_initial.py
│   │   ├── 0002_alter_property_options.py
│   │   └── 0003_location_location_embedding_hnsw_index.py
│   ├── models.py
│   ├── serializers.py
│   ├── services.py
│   ├── static/
│   │   └── property_app/
│   │       ├── autocomplete.js
│   │       └── style.css
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── requirements.txt
└── templates/
    ├── base.html
    └── property_app/
        ├── home.html
        ├── property_detail.html
        └── property_list.html

```

## Running Tests

```bash
python manage.py check
python manage.py test property_app.tests
```

## Notes

- The sample dataset includes 100 properties, of which 40 are published and 60 are drafts.
- Geographic coordinates and boundaries in the dataset are synthetic demonstration data.
- Semantic similarity results are based on location-name embeddings and may not always represent geographical proximity.
- `.env`, `media/`, and `.venv/` are excluded from version control.