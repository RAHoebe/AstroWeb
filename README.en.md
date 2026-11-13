# AstroWeb

[English](README.en.md) · [Nederlands](README.md) · [Credits and licences](THIRD_PARTY.md)

Turn your astrophotographs into a local film gallery. Animate stars and nebulosity separately, direct the camera through the photograph and publish your favourite version. Visitors can explore the original image, fly from an all-sky panorama to the actual field, and replay the sky on the night of the observation.

## Quick start

Install Python 3.11–3.13 and FFmpeg with the `libx264` encoder on your PATH. The first setup downloads Python packages. Rendering runs on the CPU.

```sh
git clone https://github.com/RAHoebe/AstroWeb.git
cd AstroWeb
```

**Windows:** run `Start-AstroWeb.cmd`. On Linux or macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m astroweb serve
```

Open the [local gallery](http://127.0.0.1:8090/), then [Studio](http://127.0.0.1:8090/admin) to set your first administrator password on the same computer (at least 11 characters). The [browser guide](http://127.0.0.1:8090/guide) is available in English and Dutch. A fresh installation starts with an empty gallery.

## Create your first film

1. Select **New film** and enter a catalogue identifier, such as `NGC_7000`.
2. Upload the four aligned AstroWizard exports, for example `NGC_7000_final.png`, `NGC_7000_starless.png`, `NGC_7000_stars.png` and `NGC_7000_stars_laid.png`. An optional matching final FITS supplies observation and pointing metadata.
3. Choose stellar parallax, nebula relief or classic pan/zoom. Select **1–4 zoom targets**. Move and resize each numbered frame to choose its crop, up to 8× per stop. The film visits the stops in order before looping back to the opening view.
4. Render the film. The first successful H.264 export is published automatically. Play later versions with their settings in Studio and choose which one appears in the gallery. Studio can also delete unused versions and rename an object with refreshed bilingual metadata.

Use PNG, JPEG or single-frame TIFF. The four images must have the same dimensions. Limits are 40 megapixels and 100 MiB per image, 512 MiB per FITS and 600 MiB per upload. AstroWeb retains the original files and hashes the four images with SHA-256. For bulk import, stop the server and run `python -m astroweb import --source AstroPhotos --render` with one subdirectory per object.

## Explore an observation

| Tab | View |
| --- | --- |
| Film | The published movie at render resolution with object information and fullscreen controls. The responsive gallery uses smaller previews. |
| Original | The full photo, smooth zoom to 10× fitted size, drag-to-pan and original download. |
| Sky journey | A flight through the sky panorama and detailed survey mosaics into the photograph. Gaia registration or verified FITS WCS determines its footprint. A known pointing alone gives a marker. Object labels are optional. |
| Milky Way | An animated face-on map for recognised Galactic targets with a distance. Toggle object names, pause or scrub the zoom. For other confirmed Galactic objects, enter a distance in Studio. Positions are projected onto the Galactic plane. |
| Skykaart | A reconstruction of the observing night using the time, coordinates and site, with stars, constellation lines and the target track. |

Parallax depth is artistic. The astrometric footprint is measured separately using local star matching against Gaia DR3. New catalogue fields, source descriptions and survey tiles require internet access. Photographs stay local. Exact site coordinates are private by default. See the [data and artwork credits](THIRD_PARTY.md).

## Storage and deployment

The `data/` directory holds the database, originals, movies, cache and session key. Stop the server before backing it up as a unit. Use one application or import process per data directory. Override its location with `ASTROWEB_DATA`. Reset the administrator password with `python -m astroweb admin` in the same environment.

```sh
docker compose build
docker compose run --rm astroweb python -m astroweb admin
docker compose up -d
```

Make the `./data` bind mount writable by UID/GID `10001:10001`. For Synology, configure the host and volume in [compose.synology.yaml](compose.synology.yaml), use it alongside [compose.yaml](compose.yaml), and point the HTTPS reverse proxy to `127.0.0.1:8090`. The overlay enables secure session cookies. Deployment on physical Synology hardware remains unverified.

## Development

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --experimental-vm-modules tools/check-frontend.mjs
```

The frontend uses native JavaScript modules without a build step. Application code is [MIT-licensed](LICENSE). Bundled datasets and images retain their [respective licences](THIRD_PARTY.md).
