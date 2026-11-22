# Skykaart source data

- `hipparcos.tsv`: ESA Hipparcos Main Catalogue (1997), VizieR I/239/hip_main.
  Retrieved 1 October 2026 from the CDS ASU service with Johnson V magnitude <6.5.
  Fields: HIP, ICRS RA/Dec at J1991.25, V magnitude, and proper motions.
  The sky chart propagates proper motions from J1991.25 to the observing year in sky.py.
  Source: https://cdsarc.cds.unistra.fr/viz-bin/cat/I/239
  Data rights: https://cds.unistra.fr/vizier-org/licences_vizier.html
- `western.json`: official Stellarium western sky culture, retrieved 1 October
  2026 from https://github.com/Stellarium/stellarium-skycultures/tree/master/western.
  Only constellation lines and names are used; no constellation illustrations.
  The unmodified source is retained. See the bundled description for attribution
  and upstream licensing, and the project's existing Stellarium credits.
- The animated charts use the names, positions and observing-night calculations in `astroweb/sky.py`. See [sources and licences](../../THIRD_PARTY.md) for other bundled catalogues, images and derived tables.

- `object-facts.json`: offline NGC/IC facts, unique cross-references, galaxy distances in Mpc, verified Dutch/English Wikidata names and descriptions, and NASA article links. For each object the array contains the OpenNGC type, IAU constellation abbreviation, ICRS RA and Dec in degrees, major and minor axes in arcminutes, V magnitude and common names. Missing measurements are null. Run `python tools/update_object_catalogue.py` to build a new snapshot. Review the diff and run the recognition tests before publishing it. See [source credits](../../THIRD_PARTY.md).
