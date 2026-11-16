# Ontwikkelagenda / Roadmap

## Objectweergaven en opnamekalender / Object views and capture calendar

Lokaal geïmplementeerd, nog niet opgenomen in een gepubliceerde release:

| Functie / Feature | Gedrag / Behaviour |
| --- | --- |
| Eigen hemelmozaïek / Own sky mosaic | Reproject combineert overlappende gemeten opnamen; panelen kiezen, zoomen en rondleiding. / Registered, feathered capture mosaics with panel selection, zoom and a tour. |
| Gaia-sterrenreis / Gaia stellar journey | Eigen sterpixels met gemeten afstanden, GPU-weergave en een vlak voor onbekende afstanden. / Original stellar pixels at measured distances, GPU rendering and an image plane for unknown distances. |
| Lichtreistijd / Light-travel time | Catalogusafstanden of NED-roodverschuiving met Astropy Planck18 en benoemde afstandsdefinities. / Catalogue distances or NED redshifts with Astropy Planck18 and explicit distance definitions. |
| Opnamekalender / Observing calendar | Lokale nachten, maanafstand, duisternis en een jaarindicatie; privé-locaties blijven afgeschermd. / Local nights, Moon separation, darkness and a seasonal overview; private sites stay protected. |
| Zonvergelijking / Solar comparison | Eigen opname naast gedateerde HMI/AIA-beelden, SunPy-raster en differentiële rotatie van een geselecteerde zonnelocatie. / Own capture alongside dated HMI/AIA imagery, a SunPy grid and differential rotation of a selected solar location. |

Website en Google TV delen deze functies, geïntegreerd bij het object of in de collectiebrede opnamekalender. De installatie en voorbeelden zijn beschreven in de README; de toetsen staan per TV-scherm in beeld. / The website and Google TV share these features in the object viewer or collection-wide capture calendar. Setup and examples are documented in the README; each TV screen displays its controls.

Vervolg op **Ontdek objecten**. Voorstellen 2, 3 en 5 zijn beschikbaar. Voorstel 4 staat nog open. De nummers verwijzen naar de oorspronkelijke voorstellen.

| # | Voorstel | Eerste bruikbare versie | Benodigd |
| --- | --- | --- | --- |
| 2 | **Beschikbaar · Dezelfde uitsnede in ander licht** | Vergelijk de eigen opname van IC 1396 met een infraroodmozaïek via een schuif. Zoom en pan blijven gekoppeld. Toon bron, golflengte en beeldschaal. | WCS voor beide lagen, lokale tegelcache en controle van de uitlijning. [AllWISE](https://irsa.ipac.caltech.edu/data/hips/CDS/AllWISE/RGB-W4-W2-W1/) |
| 3 | **Beschikbaar · Omgeving van een sterrenstelsel** | Toon bijvoorbeeld M51, NGC 5195 en andere objecten rond het opnamekader. Maak onderscheid tussen projectie aan de hemel en bevestigde fysieke begeleiders. | Catalogusposities, classificatie en afstand met bron. [NASA/IPAC NED](https://ned.ipac.caltech.edu/byname) |
| 4 | **Een rondleiding met zoomstops** | Bouw voort op de benoemde Studio-zoompunten. Geef iedere stop een korte NL/EN-toelichting, eigen verblijftijd en optionele ondertiteling. | Tijdlijn met behoud van bestaande filmparameters. [WWT-tourhandleiding](https://docs.worldwidetelescope.org/tour-authoring-guide/1/) |
| 5 | **Beschikbaar · Persoonlijke hemelatlas en opnamesessies** | Toon de gemeten kaders van de hele collectie op één kaart. Open een opname vanuit de kaart en vergelijk meerdere nachten of mozaïekpanelen van hetzelfde doel. | Scheiding tussen catalogusobject en sessie, WCS per opname, migratie van bestaande collecties. [N.I.N.A. Framing Assistant](https://nighttime-imaging.eu/docs/master/site/advanced/framingassistant/) |

## English

2. **Available · Multiwavelength comparison** — a registered wipe between the original image and infrared survey data with shared zoom and pan.
3. **Available · Galaxy environment** — a field map of nearby objects with documented physical associations and distance sources.
4. **Narrated zoom stops** — bilingual captions, adjustable dwell times and optional subtitles for the existing named camera targets.
5. **Available · Personal sky atlas** — a collection-wide footprint map and support for multiple capture sessions per target.
