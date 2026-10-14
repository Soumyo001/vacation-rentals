# Vacation Rentals — GeoDjango, PostGIS & Semantic Search

A Django vacation-rental management application built for the **Advanced Vacation Rental Assignment**. It combines PostgreSQL/PostGIS geographic searches with pgvector semantic location search, a Django-rendered property frontend, and a Django REST Framework (DRF) autocomplete API.

## Features

- **Data foundation:** Django models for `Location`, `Property`, and `PropertyImage`; PostgreSQL 16 with PostGIS and pgvector; Pandas-based CSV, Excel (`.xlsx`), and Parquet imports.
- **Admin:** Custom filters, inline property-image uploads, and image previews.
- **Property search:** Homepage search, property listings with pagination, detail pages with images and amenities, city-distance calculation, 5 km radius search (configurable), and geographic footprint/boundary intersection filtering.
- **Semantic search:** `sentence-transformers/all-MiniLM-L6-v2` location-name embeddings (384 dimensions), pgvector cosine similarity, and an HNSW index.
- **Autocomplete:** DRF location autocomplete endpoint with validated parameters; live homepage suggestions using vanilla JavaScript and the JSON API.

## Requirements

The setup below is intended for **Ubuntu/Linux**, matching the development environment used for this project.

- Python **3.12** (tested version) and `python3-venv`
- Docker Engine with the **Docker Compose v2** plugin (`docker compose`)
- GeoDjango system libraries (GDAL, GEOS, and PROJ)
- Internet connection for initial Python package/model downloads and property-image downloads
- Available disk space for Docker's PostgreSQL volume, the Python environment, and downloaded images/model files

On Ubuntu, install the GeoDjango system libraries if they are not already available:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip binutils gdal-bin libgdal-dev libgeos-dev libproj-dev
```

Install Docker Engine and its Compose plugin separately if needed. Confirm they are available:

```bash
docker --version
docker compose version
python3 --version
```

> The Django application runs **locally on the host**, while PostgreSQL runs **inside Docker**. The project's default database connection uses `127.0.0.1:5433`, as configured in `.env.example`. Do not run the Django commands inside the database container.

## Quick start — first-time setup (follow in order)

All commands below are run **from the project root** (the directory containing `manage.py`, `compose.yaml`, `requirements.txt`, and `data/`), unless otherwise indicated. Clone or download this repository and open a terminal in that directory first.

### 1. Configure the environment

```bash
cp .env.example .env
```

Populate `.env` with the environment configuration supplied separately. Do this **before** starting Docker or running Django. The application and `compose.yaml` read the same local `.env` file, so the database name, username, password, host, and port must be consistent. Do not commit `.env` to Git.

### 2. Start the PostgreSQL container

```bash
docker compose up --build -d
docker compose ps
```

Wait until the `db` service is **healthy** before continuing. The initial build installs PostGIS in the PostgreSQL/pgvector image, and the first initialization creates the `postgis` and `vector` database extensions using `docker/db/init.sql`. Docker automatically creates and retains the named PostgreSQL data volume.

### 3. Create the Python virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Keep the virtual environment activated for the remaining commands. `requirements.txt` includes Django, Django REST Framework, Pandas, the Excel/Parquet readers, GeoDjango-related Python dependencies, pgvector, Pillow, and Sentence Transformers.

### 4. Create database tables and indexes

```bash
python manage.py migrate
python manage.py check
```

Migrations create the Django tables and the **HNSW cosine-distance index** for `Location.embedding` (`location_embedding_hnsw_index`, `m=16`, `ef_construction=64`). There is no need to run `makemigrations` on a clean checkout.

### 5. Import the dataset **and download property images**

```bash
mkdir -p media
python manage.py import_rentals data/rental_properties_assignment_ready.csv --with-images
```

This is the key setup command for property data and images:

- Imports the **100 sample properties** and their locations from the bundled CSV using Pandas.
- Imports geographic points and polygon boundaries/footprints into PostGIS fields.
- Imports the published/draft statuses (the provided dataset contains **40 published** and **60 draft** properties).
- Downloads the image URLs in the dataset and saves the images through Django's `PropertyImage.image` storage under **`media/properties/YYYY/MM/`**. The `mkdir -p media` command ensures the parent directory exists even before the first successful download.
- Does **not** require committing the `media/` folder to GitHub. The downloaded files remain local and are ignored by `.gitignore`.

**Important:** Image downloading requires an internet connection and access to the third-party `images.unsplash.com` URLs in the dataset. The importer reports `Images created`, `repaired`, `skipped`, and `failed`. A successful property-data import **does not guarantee that every remote image was downloaded**: review the `failed` count. If an image request fails temporarily, retry the same import command; existing image files are skipped and missing ones are retried:

```bash
python manage.py import_rentals data/rental_properties_assignment_ready.csv --with-images
```

The importer uses `update_or_create()`, so rerunning it updates the same property records instead of adding duplicates. **Do not delete the media folder or database volume between runs.**

### 6. Generate location-name embeddings

```bash
python manage.py generate_location_embeddings
```

On first execution, Sentence Transformers downloads the `all-MiniLM-L6-v2` model (internet required), generates **384-dimensional embeddings** for locations without vectors, and saves them in pgvector. On a fresh import of the included dataset, expect approximately **100 embedded locations**. If you rerun the command, existing non-null vectors are left unchanged.

The model cache is created automatically by the underlying machine-learning libraries and does not need to be stored in this repository.

### 7. Create a Django Admin user (one time, on a fresh database)

```bash
python manage.py createsuperuser
```

Follow the prompts to create the Admin account. **A fresh database will not contain an Admin user just because a username/password was shared separately**; create that account once using the intended credentials. If an Admin user already exists in the connected database, skip this step. Credentials are **not** stored in this README.

### 8. Start the Django application

```bash
python manage.py runserver
```

Open these URLs locally:

| Page | URL |
| --- | --- |
| Homepage / location search / live suggestions | <http://127.0.0.1:8000/> |
| Property listings | <http://127.0.0.1:8000/properties/> |
| Django Admin | <http://127.0.0.1:8000/admin/> |
| Semantic autocomplete API (example) | <http://127.0.0.1:8000/api/locations/autocomplete/?q=Umeda&limit=5> |

The development server serves local static files and downloaded media when `DJANGO_DEBUG=True`, as configured for local development. **This is a development setup, not a production deployment guide.**

## Verify the installation

In a separate terminal, from the project root and with the environment activated:

```bash
python manage.py check
python manage.py showmigrations property_app
python manage.py test property_app.tests -v 2
```

Check the expected dataset counts with:

```bash
python manage.py shell -c "from property_app.models import Location, Property; print('Locations:', Location.objects.count()); print('Embedded:', Location.objects.filter(embedding__isnull=False).count()); print('Properties:', Property.objects.count()); print('Active:', Property.objects.filter(is_active=True).count())"
```

On a **fresh setup using only the included CSV**, the expected counts are `100 locations`, `100 embeddings`, `100 properties`, and `40 active properties`, assuming all commands completed successfully. An existing development database may have additional manually created records.

Test semantic autocomplete from a terminal:

```bash
curl -i -H "Accept: application/json" \
  "http://127.0.0.1:8000/api/locations/autocomplete/?q=Umeda&limit=3"
```

Expect HTTP `200 OK` and JSON containing `query`, `count`, and a `results` array with fields including `id`, `name`, `city`, `state`, `country`, and `distance` (cosine distance; smaller is closer in the embedding space).

**Browser test:** Type `Umeda` on the homepage; suggested locations should appear while typing. Select **Umeda**, then verify that the spatial listing can show **Umeda Garden House** within 5 km. Changing the radius and enabling the boundary-intersection option should preserve that matching property.

## Other supported import formats

CSV, Excel, and Parquet versions of the same dataset are included in `data/`. **Choose one format for initial setup**; all three describe the same properties. To validate or re-import using an alternative format:

```bash
python manage.py import_rentals data/rental_properties_assignment_ready.xlsx
# OR
python manage.py import_rentals data/rental_properties_assignment_ready.parquet
```

Add `--with-images` to either command to download/repair images too. The Excel reader expects the workbook's **`Properties`** sheet. These formats were verified to contain the same 100 property slugs.

## How the searches work

1. **Homepage:** Validates the location search and checks text matches; if there are none, it provides vector-based semantic location suggestions.
2. **Live autocomplete:** The homepage JavaScript calls the DRF JSON endpoint as the user types and renders clickable location suggestions without refreshing the page.
3. **Spatial property search:** Selecting a location opens `/properties/?location_id=<id>`. PostGIS performs the radius search using `DWithin`; the optional boundary filter uses `Intersects` on the property footprint and location boundary.
4. **Semantic location search:** Uses the same `all-MiniLM-L6-v2` model for the query as was used for the stored vectors. pgvector ranks locations using cosine distance. The HNSW index supports approximate nearest-neighbor searching.
5. **Availability:** The listing pages show active properties. Semantic fallback suggestions within the property-listing view can be restricted to locations with active properties; the general autocomplete API searches active locations without that restriction.

**Dataset note:** Location and property coordinates/polygons are synthetic demonstration data. Similarity between *location-name embeddings* is not the same as physical distance or guaranteed country membership, so some semantically returned destinations can be geographically unrelated. The geographic property filters are handled separately by PostGIS.

## Common troubleshooting

| Symptom | What to check |
| --- | --- |
| Django cannot connect to PostgreSQL | Confirm `docker compose ps` shows a healthy `db`; check that `.env` matches the database created on first Docker initialization. |
| Port 5433 already in use | Check local services and ensure `DB_PORT` in `.env` matches the port exposed in `compose.yaml`. |
| `django.core.exceptions.ImproperlyConfigured` or missing environment key | Verify `.env` exists in the project root and contains the required configuration. |
| `GDAL` / `GEOS` / `PROJ` loading error | Install the Ubuntu GeoDjango system packages listed above. |
| Property images missing | Rerun `import_rentals ... --with-images` and inspect the `failed` count. Downloads depend on the external image host. |
| Autocomplete not returning suggestions | Check that embeddings were generated and that the DRF endpoint returns JSON; verify the browser's Network tab shows the autocomplete request. |
| Hugging Face download warning | The model may still download successfully without authentication; network access is required on first use. |
| Admin credentials do not work on a fresh installation | Run `python manage.py createsuperuser` once for that new database. |

### Stopping and restarting

```bash
# Stop the Django server with Ctrl+C in its terminal.
docker compose down          # Stops/removes containers; retains the named DB volume.

# On the next run:
docker compose up -d
source .venv/bin/activate
python manage.py runserver
```

**Do not use `docker compose down -v` during normal use**: `-v` removes the persistent PostgreSQL volume and its database records.

## Project structure (selected)

```text
vacation_rentals/
├── .env.example
├── compose.yaml
├── config/                   # Django configuration and root URLs
├── data/                     # CSV / Excel / Parquet datasets
├── docker/db/                # PostgreSQL + PostGIS + pgvector image/init
├── property_app/
│   ├── management/commands/
│   │   ├── import_rentals.py
│   │   └── generate_location_embeddings.py
│   ├── migrations/
│   ├── static/property_app/   # CSS and autocomplete JavaScript
│   ├── models.py
│   ├── admin.py
│   ├── forms.py
│   ├── views.py
│   ├── services.py
│   ├── serializers.py
│   ├── api_views.py
│   ├── urls.py
│   └── tests.py
├── templates/
│   ├── base.html
│   └── property_app/
├── manage.py
├── requirements.txt
└── README.md

# Created locally during setup; not committed:
# .env, .venv/, media/, Docker database volume, model download cache
```

## Scope

This repository implements the assignment's Day 1 (setup/data), Day 2 (search/frontend), and Day 3 (semantic search/API) work. The sample data and `runserver` configuration are intended for **local educational demonstration** rather than a production rental booking service.
