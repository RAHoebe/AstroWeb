# AstroWeb

[English](README.en.md) · [Nederlands](README.md) · [Credits and licences](THIRD_PARTY.md) · [Watch the AstroWeb film on YouTube](https://www.youtube.com/watch?v=mByBMSqRSbg)

[Screening room, example films and installation guide](https://rahoebe.github.io/AstroWeb/). For a NAS and Google TV on the same trusted network, this release includes standalone `compose.lan.yaml` and a LAN APK. Set `ASTROWEB_LAN_IP` to the private address of the server. This configuration defaults to `ASTROWEB_OFFLINE=1`, allowing local processing and playback of previously downloaded material.

Turn your astrophotographs into a local film gallery. Animate stars and nebulosity separately, direct the camera through the photograph and publish your favourite version. Visitors can explore the original image, fly from an all-sky panorama to the actual field, and replay the sky on the night of the observation.

## Viewer features and capture calendar

The object viewer exposes relevant extra tabs only. The capture calendar is a separate collection view beside the sky atlas in the gallery. The website and Google TV share the same data and locally cached imagery.

- **Sky mosaic** appears for two or more overlapping registered captures. Reproject combines them with feathering and bounded brightness matching. Every contributing capture date remains visible. The derived image is limited to a 4096-pixel long edge and six million pixels overall; originals remain unchanged.
- **Stars in 3D** unfolds the photograph into a rotatable distance map. Up to 900 stellar crops come from your own star layer, matched to Gaia DR3 distances (parallax SNR ≥ 10, RUWE < 1.4). Angular positions follow the capture footprint; the depth axis uses a logarithmic distance scale. This is a distance map, not a reconstructed nebula volume. TV rendering uses one GPU batch with a Canvas fallback. Click a star to inspect its distance and approximate uncertainty.
- **Light journey** follows a light pulse from the object to Earth. Total and remaining travel times are displayed; your own photograph appears on arrival. Known nearby distances take priority over redshift. For other galaxies, Astroquery searches NED and Astropy Planck18 calculates lookback time and separately labelled distance measures. Studio accepts published measurements with an HTTPS source link. The path is schematic.
- **Solar comparison** appears for solar captures only. Compare the photograph with SDO/HMI continuum or SDO/AIA 171 Å near the capture time. Actual FITS times and offsets remain visible; matches farther than twelve hours are rejected. SunPy supplies the grid and rotation model for a selected solar surface coordinate. Your own photo orientation remains manually adjustable. The separate eclipse detail journey fits the visible disk boundaries and keeps their centres and scales aligned throughout the dissolve.
- **Capture calendar** is a collection-wide month view with portrait thumbnails on observing dates and a preview of the selected day. Select a day for a day view containing selectable photos and known DATE-OBS timestamps. Missing times are not invented. Hours initially indicate astronomical darkness in central Netherlands. Optionally select a target for specific windows (target ≥ 30°, Sun ≤ −18°, Moon below the horizon or ≥ 35° from the target). Sampling is every 30 minutes, with daylight-saving transitions; the annual strip samples the 15th of each month. Weather is not included.

On TV, **Stars in 3D**, **Light journey**, **Mosaic** and **Solar comparison** are object-viewer actions. **Calendar** sits beside **Sky atlas** in the gallery. Left/right selects a day and up/down changes month. OK opens the day view, where left/right selects a capture and OK opens its photo. Back restores the calendar. Each mode displays its controls.

Heavy preparation uses the bounded server queue. Results live outside the source tree under `data/observatory/`; downloaded Gaia measurements remain usable offline. Missing source data are reported and temporary Gaia outages are retried. Private captures stay protected and public observing windows do not use private sites. Use [web v1.6.1](https://github.com/RAHoebe/AstroWeb/releases/tag/v1.6.1) and [TV 0.8.2](https://github.com/RAHoebe/AstroWeb/releases/tag/tv-v0.8.2).

TV 0.8 fits the viewer actions on one row, with rotate and fullscreen icons at the right. **Explore** offers only the capture-night/tonight chart and named features for the open capture. **Viewing modes** on the home screen starts a random five-minute evening programme or a one-hour photo frame immediately. Gallery opens the main collection with the current object selected; Back preserves the route, including the capture calendar.

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
2. Upload the aligned AstroWizard exports, for example `NGC_7000_final.png`, `NGC_7000_starless.png`, `NGC_7000_stars.png` and optionally `NGC_7000_stars_laid.png`. A matching final FITS, if supplied, supplies observation and pointing metadata.
3. Choose stellar parallax, Gaia parallax with measured stellar distances, nebula relief or classic pan/zoom. Gaia requires a registered field and capture date. Studio reports usable matches. Choose whether unmatched stars move with the nebula or use local interpolation from nearby stars with consistent distances. Estimated stars are counted separately. Camera travel is amplified for visibility. Select **1–8 zoom targets**. Move and resize each numbered frame to choose its crop, up to 8× per stop. The film visits the stops in order before looping back to the opening view.
4. Render the film. Every successful H.264 render becomes the gallery movie and opens in the Studio player. Landscape source images have a film orientation control. The current film stays available during rendering. Use **Cancel render** for queued or running jobs, or select an earlier completed version. Studio can also delete unused versions and rename an object with refreshed bilingual metadata.

Studio recognises common names such as **Pleiades**, **Seven Sisters** and **Melotte 22** for M45 using its offline catalogue. The **Crescent Nebula** (NGC 6888) and **Soul Nebula** (IC 1848) also work offline and have bilingual descriptions. When the FITS `OBJECT` name is unfamiliar, Studio can look up a Wikipedia title through Wikidata. A match must have a SIMBAD reference and a supported catalogue ID. Studio falls back to the file prefix when a unique match is unavailable.

Choose the object on the left and the capture date or session in the editor. For a new capture, choose **Upload files** and follow the transfer progress. AstroWeb validates the files and saves the draft in Studio. The automatic zoom route reads the saved files and reports catalogue recognition separately from FITS or Gaia alignment. Use **Create film** to queue the render. Confirmed positions are named and other stops are marked as image details. Cancel an active render or queue another one for the same capture while it is cancelling.

Use PNG, JPEG or single-frame TIFF. All images must have the same dimensions. Limits are 40 megapixels and 100 MiB per image, 512 MiB per FITS and 600 MiB per upload. AstroWeb retains the original files and hashes the uploaded images with SHA-256. For bulk import, stop the server and run `python -m astroweb import --source AstroPhotos --render` with one subdirectory per object.

## Explore an observation

| Tab | View |
| --- | --- |
| Film | The published movie at render resolution with object information and fullscreen controls. The responsive gallery uses smaller previews. |
| Extra object tabs | Overlapping sky mosaics, stars in 3D, light journeys and solar comparison. The capture calendar is in the gallery. |
| Original | The full photo, smooth zoom to 10× fitted size, drag-to-pan and original download. |
| What am I seeing? | Select a marker on the original, read its description and zoom to the feature. Deep-sky labels use sky registration. The Moon gets automatic labels after successful lunar registration. On Solar System captures, administrators can use **Add marker** to place visible details and save them for that capture. The TV guide reads the same labels. |
| Sky journey | A flight through the sky panorama and detailed survey mosaics into the photograph. Gaia registration or verified FITS WCS determines its footprint. A known pointing alone gives a marker. Object labels are optional. The final photo uses the quarter-turn requiring the least camera roll. |
| Milky Way | An animated face-on map for recognised Galactic targets with a distance. Toggle object names, pause or scrub the zoom. For other confirmed Galactic objects, enter a distance in Studio. Positions are projected onto the Galactic plane. |
| Archive journeys | Fly from your capture into a registered Hubble, Euclid or JWST image, with its telescope, filter and source. The destination stays visible during the flight on the website and Google TV. |
| Lunar detail flights | Register your Moon capture against the dated NASA SVS reference, then zoom through georeferenced LRO mosaics to Apollo 11, 12 or 14, Tycho, Copernicus, Plato, Aristarchus, Clavius or the seas Tranquillitatis and Imbrium. Apollo regions add NAC detail; craters and seas use the 100 m/pixel WAC mosaic. Previously cached imagery works offline. Unreliable registration is reported rather than replaced with an arbitrary fade. |
| Galaxy environment | Explore nearby galaxies and their documented relationships. |
| Polar sky chart | A circular equatorial chart centred on the northern or southern celestial pole, with constellation lines, hour divisions and a zoom to the target. |
| Skykaart | A reconstruction of the observing night using the time, coordinates and site, with stars, constellation lines and the target track. |

Parallax depth is artistic. The astrometric footprint is measured separately using local star matching against Gaia DR3. New catalogue fields, source descriptions and survey tiles require internet access. Photographs stay local. Exact site coordinates are private by default. See the [data and artwork credits](THIRD_PARTY.md).

Gaia alignment tries AIP and the official ESA archive. Transient failures retry in the background after 1 minute, 5 minutes, 30 minutes, 2 hours and then every 6 hours. Retry state survives a restart; active film renders take priority, and offline mode suppresses network retries. Opening an object's viewer or mosaic can schedule a due retry without waiting for it. A newly available mosaic tab appears automatically while the viewer is open. Failed matching or missing pointing metadata requires corrected input instead of repeated catalogue requests. Existing source files, films and archive destination selections are retained.

## Storage and deployment

The `data/` directory holds the database, originals, movies, cache and session key. Stop the server before backing it up as a unit. Use one application or import process per data directory. Override its location with `ASTROWEB_DATA`. Reset the administrator password with `python -m astroweb admin` in the same environment.

```sh
docker compose build
docker compose run --rm astroweb python -m astroweb admin
docker compose up -d
```

Make the `./data` bind mount writable by UID/GID `10001:10001`. Docker also uses this directory to buffer incoming uploads. For Synology, configure the host and volume in [compose.synology.yaml](compose.synology.yaml), use it alongside [compose.yaml](compose.yaml), and point the HTTPS reverse proxy to `127.0.0.1:8090`. The overlay enables secure session cookies. Use a valid certificate for the public hostname. For an empty NAS installation, set the Studio password in the container before enabling the reverse proxy.

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

For a registered M31 capture, the **Archive journeys** tab offers the NGC 206 star cloud, M32 satellite galaxy and Andromeda nucleus when their target areas lie within the capture. Each 12-second flight moves from the original raster into the same stars in the PHAT/PHAST mosaic. A separate ground-based wide-field image by Robert Gendler shows the dust lanes. First use fetches the necessary zoom tiles and caches both tiles and film locally.

The **Stellar time machine** on the polar chart spans 50,000 years on either side of the capture date (the present if unavailable). Try the Big Dipper or Southern Cross, move the time slider or play it automatically. The simulation uses constant HYG 4.1 Cartesian space velocities in fixed ICRS axes with constant magnitudes. Stars lacking a valid distance stay at their catalogue positions.

### Archive fields, atlas photos and Solar System captures

For other registered captures, Archive journeys searches the US and European Hubble archives for optical imaging products. AstroWeb validates both the archive footprint and actual FITS cutout against the capture and offers up to six distinct Hubble fields. Each flight identifies the target and filter; a single-filter exposure is shown in grayscale. Availability depends on usable public products and coverage. Results, cutouts and films are cached locally.

The collection atlas and polar chart draw the original-orientation poster inside the measured corners. Toggle the photo layer or compare two capture thumbnails. Original displays the estimated distance and visible projected width and height in light-years at the target distance.

Choose **Solar System** to upload the Sun, Moon or a planet as a single PNG, JPEG or TIFF with optional FITS. Sky journey follows the line of sight from the observing site at capture time and displays UTC, constellation and sky coordinates. A detected full disk grows from the target using its apparent diameter; a detail photograph appears as a close-up. The Milky Way map marks the Solar System. Skykaart tracks the body through its local calendar day. With only a date, the reference time is local noon. When the observing location is missing, the maps use central Netherlands (52.15° N, 5.38° E). Detail flight offers credited mission imagery from SDO, LRO, Juno, Cassini and other missions. A recorded capture time allows an approximate geocentric distance. Surface dimensions require additional image calibration.

### Multiple captures of one target

Upload again with the same catalogue ID. Each capture retains its own originals, FITS, registration and movies. Use the FITS observation timestamp or enter the actual observing date at upload. The gallery and Previous/Next use one published capture per object, selected by observation date. Undated captures follow dated ones. Use the date selector in the viewer sidebar for another capture; it preserves the active tab where available. The collection atlas continues to list individual sessions.

The date picker counts available captures. For NGC 7000, a Palomar/DSS2 colour image by Davide De Martin shows the Cygnus Wall and its bordering dark cloud. For IC 1396, a Pan-STARRS colour view shows the Elephant’s Trunk. The Archive journeys tab also links to the NASA Hubble Skymap. Hubble fields distinguish the target itself, documented regions and other pointings in the same capture. Automatically added archive fields and their FITS cutouts must fit entirely inside your capture. The flight ends on exposed detector pixels.

Renaming a capture to an existing object groups the captures in one date selector. Confirmed catalogue cross-identifications (e.g. Caldwell 20 / NGC 7000 and M31 / NGC 224) share a gallery card. Each capture keeps its own files, film versions and historic viewer URL.

### Automatic archive destinations on upload

Studio searches the [NASA Hubble Skymap](https://science.nasa.gov/mission/hubble/multimedia/online-activities/hubble-skymap/) by target and catalogue aliases for new deep-sky captures. A matching photograph becomes the first archive destination. The film approaches the Skymap position when it lies inside the measured footprint, then dissolves into the complete NASA image. Without a measured footprint the transition starts from the whole capture. Skymap provides an object position but does not specify a reliable orientation and scale for every published photograph. After alignment, Studio also searches NASA’s MAST and the ESA Hubble Science Archive by target name, catalogue aliases and known subregion names, including when Skymap has a match. Both archives are also searched by sky coordinates around the registered capture corners. Destinations distinguish the target, a known subregion and other fields in the same direction. Both the complete published Hubble footprint and the FITS cutout must fit within the measured footprint of this capture. Studio selects up to six distinct archive fields. Both observation footprints and FITS cutouts must overlap by less than half the smaller field. A matching Skymap image stays first, followed by numbered archive fields with filters and sky coordinates. Existing curated journeys remain available. The index and selected images are cached locally.

Additional background searches use Astroquery TAP for Euclid VIS mosaics (DR1 and Q1) and public calibrated JWST images in the ESA archive, with MAST as a fallback for JWST catalogue access. Euclid supplies small optical cutouts around catalogue features inside the capture; JWST supplies single-filter infrared images. These are scientific grayscale images, not automatically generated colour publicity images. Actual FITS pixel boundaries, exposure coverage and sky registration must pass validation before a destination appears. Up to three distinct destinations per additional telescope can be offered. A matching Skymap image stays first. Products over 96 MiB are skipped; downloads and searches have time budgets. Additional searches run after the current render so they do not hold up publication of your film. Successful products are cached for offline playback; network failures preserve saved destinations and retry later. The existing `/hubble` media URLs and viewer bookmarks remain compatible.

In Studio, select **Star trails** or **Milky Way photograph** as the capture type. Upload one PNG with any filename and optionally a FITS file with observation metadata and a title. Each upload gets its own gallery card, zoomable original and pan/zoom movie in the original orientation by default.

Solar System images below the normal minimum dimensions can be enlarged to 256 pixels along their longest edge for viewing and rendering. Download original returns the source image. For ASIStudio planetary stacks, AstroWeb reads a timestamp such as `2026-11-20-180949` from the filename in the Europe/Amsterdam time zone. Enter the capture time in Studio if the filename does not provide an unambiguous time. The original FITS header is preserved. Saturn detail journeys align the ring axis with a Cassini overview when the rings are sufficiently visible in the capture. When the ring wings can be measured, **What am I seeing?** also shows a Rings marker linked to the Saturn detail journey. A manually placed marker takes priority.

Open **Night panorama** above the gallery to explore your published captures in the ESO sky panorama. For your own Milky Way and star-trail photos, open **Night panorama** in Studio, choose a target capture, click its position on your image and save. Enable 360° wrapping for a full horizontal sweep. Visitors can pan, zoom and open the linked photograph. The **Photos** toggle shows your captures in their measured footprints. Select a frame or label to fly into the original. Returning restores your previous view.

On phones and tablets, pinch to zoom in the night panorama, the **Original** view and the sky atlas. Leave one finger on the screen to continue panning.
