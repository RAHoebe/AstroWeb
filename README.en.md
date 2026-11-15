# AstroWeb

[English](README.en.md) · [Nederlands](README.md) · [Credits and licences](THIRD_PARTY.md) · [Watch the AstroWeb film on YouTube](https://youtu.be/wD7AvMVBKfU)

[Screening room, example films and installation guide](https://rahoebe.github.io/AstroWeb/). For a NAS and Google TV on the same trusted network, this release includes standalone `compose.lan.yaml` and a LAN APK. Set `ASTROWEB_LAN_IP` to the private address of the server. This configuration defaults to `ASTROWEB_OFFLINE=1`, allowing local processing and playback of previously downloaded material.

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
3. Choose stellar parallax, nebula relief or classic pan/zoom. Select **1–8 zoom targets**. Move and resize each numbered frame to choose its crop, up to 8× per stop. The film visits the stops in order before looping back to the opening view.
4. Render the film. Every successful H.264 render becomes the gallery movie and opens in the Studio player. Landscape source images have a film orientation control. The current film stays available during rendering. Use **Cancel render** for queued or running jobs, or select an earlier completed version. Studio can also delete unused versions and rename an object with refreshed bilingual metadata.

Use PNG, JPEG or single-frame TIFF. The four images must have the same dimensions. Limits are 40 megapixels and 100 MiB per image, 512 MiB per FITS and 600 MiB per upload. AstroWeb retains the original files and hashes the four images with SHA-256. For bulk import, stop the server and run `python -m astroweb import --source AstroPhotos --render` with one subdirectory per object.

## Explore an observation

| Tab | View |
| --- | --- |
| Film | The published movie at render resolution with object information and fullscreen controls. The responsive gallery uses smaller previews. |
| Original | The full photo, smooth zoom to 10× fitted size, drag-to-pan and original download. |
| Sky journey | A flight through the sky panorama and detailed survey mosaics into the photograph. Gaia registration or verified FITS WCS determines its footprint. A known pointing alone gives a marker. Object labels are optional. The final photo uses the quarter-turn requiring the least camera roll. |
| Milky Way | An animated face-on map for recognised Galactic targets with a distance. Toggle object names, pause or scrub the zoom. For other confirmed Galactic objects, enter a distance in Studio. Positions are projected onto the Galactic plane. |
| Hubble | Fly into a named structure in a registered optical image with a link to its source. The zoom target stays in the frame throughout the flight on both the website and Google TV. |
| Galaxy environment | Explore nearby galaxies and their documented relationships. |
| Polar sky chart | A circular equatorial chart centred on the northern or southern celestial pole, with constellation lines, hour divisions and a zoom to the target. |
| Skykaart | A reconstruction of the observing night using the time, coordinates and site, with stars, constellation lines and the target track. |

Parallax depth is artistic. The astrometric footprint is measured separately using local star matching against Gaia DR3. New catalogue fields, source descriptions and survey tiles require internet access. Photographs stay local. Exact site coordinates are private by default. See the [data and artwork credits](THIRD_PARTY.md).

## Storage and deployment

The `data/` directory holds the database, originals, movies, cache and session key. Stop the server before backing it up as a unit. Use one application or import process per data directory. Override its location with `ASTROWEB_DATA`. Reset the administrator password with `python -m astroweb admin` in the same environment.

```sh
docker compose build
docker compose run --rm astroweb python -m astroweb admin
docker compose up -d
```

Make the `./data` bind mount writable by UID/GID `10001:10001`. For Synology, configure the host and volume in [compose.synology.yaml](compose.synology.yaml), use it alongside [compose.yaml](compose.yaml), and point the HTTPS reverse proxy to `127.0.0.1:8090`. The overlay enables secure session cookies. Use a valid certificate for the public hostname. For an empty NAS installation, set the Studio password in the container before enabling the reverse proxy.

## Development

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --experimental-vm-modules tools/check-frontend.mjs
```

The frontend uses native JavaScript modules without a build step. Application code is [MIT-licensed](LICENSE). Bundled datasets and images retain their [respective licences](THIRD_PARTY.md).

On **Original → Discover objects**, select a catalogue centre and use it as a named Studio zoom target. Markers track the original image during zoom and pan. With eight existing stops, choose the one to replace. See the [roadmap](docs/ROADMAP.md) for the remaining proposals.

**Other wavelengths** compares the original photograph with a registered AllWISE W1/W2/W4 infrared mosaic and shares its zoom and pan. The first visit downloads survey tiles and caches the registered cutout. **Galaxy environment** maps the field, angular separations and documented relationships for recognised galaxies. **Suggest zoom route** previews a route based on catalogue centres and local image contrast. Applying it replaces the current draft route. As soon as the upload preview appears, you can apply a contrast-based route to the first movie. Studio prefers the FITS `OBJECT` identifier and falls back to the filename prefix for empty or unrecognised values. When a position is available, the render queue prepares the sky journey before the new movie appears in the gallery.

**[Personal sky atlas](http://127.0.0.1:8090/atlas)** maps published captures, plus unpublished captures when signed in. Select a footprint, open the original, or compare two outlines and posters. A pointing-only capture is shown as a cross. Upload another night or mosaic panel with the same catalogue ID and an optional session name in Studio. Previous and Next browse the gallery from the viewer. The sky surroundings and optional object labels remain visible through the final frame of the sky journey.

### M31 and stellar motion

For a registered M31 capture, the **Hubble** tab offers the NGC 206 star cloud, M32 satellite galaxy and Andromeda nucleus when their target areas lie within the capture. Each 12-second flight moves from the original raster into the same stars in the PHAT/PHAST mosaic. A separate ground-based wide-field image by Robert Gendler shows the dust lanes. First use fetches the necessary zoom tiles and caches both tiles and film locally.

The **Stellar time machine** on the polar chart spans 50,000 years on either side of the capture date (the present if unavailable). Try the Big Dipper or Southern Cross, move the time slider or play it automatically. The simulation uses constant HYG 4.1 Cartesian space velocities in fixed ICRS axes with constant magnitudes. Stars lacking a valid distance stay at their catalogue positions.

### Other Hubble fields, atlas photos and Solar System captures

For other registered captures, Hubble searches the ESA Hubble Science Archive for optical imaging products. AstroWeb validates each FITS cutout against the actual footprint and offers up to two overlapping fields. Each flight identifies the archive target and filter; a single-filter exposure is shown in grayscale. Availability depends on usable archive products and coverage. Results, cutouts and films are cached locally.

The collection atlas and polar chart draw the original-orientation poster inside the measured corners. Toggle the photo layer or compare two capture thumbnails. Original displays the estimated distance and visible projected width and height in light-years at the target distance.

Choose **Solar System** to upload the Sun, Moon or a planet as a single PNG, JPEG or TIFF with optional FITS. Sky journey follows the line of sight from the observing site at capture time and displays UTC, constellation and sky coordinates. A detected full disk grows from the target using its apparent diameter; a detail photograph appears as a close-up. The Milky Way map marks the Solar System. Skykaart tracks the body through its local calendar day. With only a date, the reference time is local noon. When the observing location is missing, the maps use central Netherlands (52.15° N, 5.38° E). Detail flight offers credited mission imagery from SDO, LRO, Juno, Cassini and other missions. A recorded capture time allows an approximate geocentric distance. Surface dimensions require additional image calibration.

### Multiple captures of one target

Upload again with the same catalogue ID. Each capture retains its own originals, FITS, registration and movies. Use the FITS observation timestamp or enter the actual observing date at upload. The gallery and Previous/Next use one published capture per object, selected by observation date. Undated captures follow dated ones. Use the date selector in the viewer sidebar for another capture; it preserves the active tab where available. The collection atlas continues to list individual sessions.

The date picker counts available captures. For NGC 7000, a Palomar/DSS2 colour image by Davide De Martin shows the Cygnus Wall and its bordering dark cloud. For IC 1396, a Pan-STARRS colour view shows the Elephant’s Trunk. The Hubble tab also links to the NASA Hubble Skymap. Hubble fields distinguish the target itself, documented regions and other pointings in the same capture. Partial overlaps are considered, and the flight ends on exposed detector pixels inside your own field.

Renaming a capture to an existing object groups the captures in one date selector. Confirmed catalogue cross-identifications (e.g. Caldwell 20 / NGC 7000 and M31 / NGC 224) share a gallery card. Each capture keeps its own files, film versions and historic viewer URL.

### Automatic Hubble destination on upload

Studio searches the [NASA Hubble Skymap](https://science.nasa.gov/mission/hubble/multimedia/online-activities/hubble-skymap/) by target and catalogue aliases for new deep-sky captures. A matching photograph becomes the first Hubble destination. The film approaches the Skymap position when it lies inside the measured footprint, then dissolves into the complete NASA image. Without a measured footprint the transition starts from the whole capture. Skymap provides an object position but does not specify a reliable orientation and scale for every published photograph. After alignment, Studio also searches NASA’s MAST and the ESA Hubble Science Archive by target name, catalogue aliases and known subregion names, including when Skymap has a match. Both archives are also searched by sky coordinates around the registered capture corners. Destinations distinguish the target, a known subregion and other fields in the same direction. Both the complete published Hubble footprint and the FITS cutout must fit within the measured footprint of this capture. Studio selects up to six distinct archive fields. Both observation footprints and FITS cutouts must overlap by less than half the smaller field. A matching Skymap image stays first, followed by numbered archive fields with filters and sky coordinates. Existing curated journeys remain available. The index and selected images are cached locally.

In Studio, select **Star trails** or **Milky Way photograph** as the capture type. Upload one PNG with any filename and optionally a FITS file with observation metadata and a title. Each upload gets its own gallery card, zoomable original and pan/zoom movie in the original orientation by default.

Open **Night panorama** above the gallery to explore your published captures in the ESO sky panorama. For your own Milky Way and star-trail photos, open **Night panorama** in Studio, choose a target capture, click its position on your image and save. Enable 360° wrapping for a full horizontal sweep. Visitors can pan, zoom and open the linked photograph. The **Photos** toggle shows your captures in their measured footprints. Select a frame or label to fly into the original. Returning restores your previous view.

On phones and tablets, pinch to zoom in the night panorama, the **Original** view and the sky atlas. Leave one finger on the screen to continue panning.
