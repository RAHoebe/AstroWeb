# AstroWeb — projectafspraken / project conventions

## Nederlands
- Bouw een lokale website die later in Docker op een Synology NAS draait, vergelijkbaar met LeefRadar. Geen cloudafhankelijkheid voor galerij of rendering.
- De volledige website, admininterface, foutmeldingen en documentatie zijn beschikbaar in Nederlands en Engels. Nederlands is de standaard. Een zichtbare NL/EN-schakelaar onthoudt de browserkeuze. Houd vertaalsleutels in beide talen gelijk.
- Gebruik een donker, rustig cinematografisch thema met nevelkleuren: nachtblauw, cyaan, violet, magenta en warm sterrenlicht. De eigen astrofoto's staan centraal.
- Bewaar de vier AstroWizard-originelen ongewijzigd: `<ASTRO_ID>_*_final`, `_starless`, `_stars`, `_stars_laid`. Astroidentificaties zoals NGC_7000 zijn de invoersleutel. Ondersteun PNG, JPEG en TIFF met gelijke afmetingen.
- Vergelijk stars en stars_laid met additieve en screencompositie; neem niet aan dat stars_laid de juiste laag is. Toon de gekozen combinatie en reconstructiefout.
- Lever echte H.264 MP4-video's uit een duurzame wachtrij, met instelbare methode, beweging, zoom, x/y-pan, diepte, duur, fps en resolutie. Publiceer alleen na succesvolle rendering. Behoud de vorige film bij een mislukte herberekening.
- Galerij: final-foto als poster, film speelt bij aanwijzen of toetsenbordfocus. Klik/tik opent een toegankelijk venster. Dubbelklik en een zichtbare knop activeren volledig scherm. Respecteer verminderde beweging.
- Korte objectinformatie op de homepage, uitgebreidere informatie en bronlinks in de viewer. NASA Images API heeft geen sleutel nodig. Geen verzonnen feiten of Engelse tekst die als Nederlands wordt gelabeld. Optionele vertaling moet via expliciet geconfigureerde LibreTranslate lopen. Behoud bron, tijdstip en vertaalstatus.
- HIP_106890 is een sterrenidentificatie die hier als opnamelabel voor het IC 1396-gebied wordt gebruikt; het is geen wetenschappelijk synoniem van de nevel. Bewaar die nuance en maak het catalogusdoel bewerkbaar.
- Parallaxdiepte uit beeldhelderheid is een artistieke interpretatie, geen gemeten 3D-structuur of sterafstand. Geen AI-beeldgeneratie of extra sterren in de standaardrenderer.
- Authenticeer beheer, controleer CSRF, bestandsinhoud, omvang, afmetingen en paden. Geen wachtwoorden in Git. Foto's, database, cache en films staan buiten de broncode in data/ en worden niet gecommit.
- Een optionele vijfde final-FITS levert echte opnamegegevens. Behoud FITS bytes en lees alleen relevante headergegevens. Onderscheid integratietijd van verstreken tijd en DATE-OBS van een gegarandeerd opnamestarttijdstip. Gebruik geen bestandsdatum als opnamedatum. Exacte opnamelocatie en lokale HISTORY-paden zijn standaard niet openbaar.
- De geanimeerde Skykaart gebruikt Hipparcos-sterren, Stellarium-lijnen en Astropy-posities voor de echte locatie en vaste opnamenacht. Markeer ontbrekende locatie/tijd/coördinaten; bied handmatige aanvulling in beheer. Geen verzonnen sterren of landschapsnauwkeurigheid. Bewaar bronlicenties.
- Test belangrijke render-, upload-, queue- en beveiligingspaden; controleer de UI in een browser. Documenteer beperkingen eerlijk. Geen deployment naar NAS of hosting tenzij gevraagd.

## English
- Build locally first; prepare Docker deployment to a Synology NAS, following LeefRadar's portable approach. Gallery playback and rendering must work offline.
- All public/admin UI, errors and documentation must support Dutch and English. Default to Dutch. Provide a persistent, visible NL/EN switch and matching translation keys.
- Use a quiet dark cinematic design with nebula-inspired navy, cyan, violet, magenta and warm starlight. Prioritize the user's original photographs.
- Preserve all four original AstroWizard exports byte-for-byte: final, starless, stars and stars_laid, prefixed by the astronomy identifier. Validate dimensions, contents and limits. Support PNG/JPEG/TIFF.
- Select star layer and additive/screen blending by measuring reconstruction error against final. Never assume stars_laid is the correct export.
- Produce actual H.264 MP4 files with a persistent job queue and configurable rendering/motion parameters. Publish only successful renders and preserve the last good movie on failure.
- Final posters, hover/focus playback, accessible click/tap viewer, double-click/button fullscreen and reduced-motion support are required.
- Include bilingual short and extended object descriptions, provenance, timestamps and source links. Use the key-free NASA Images API. Optional translation uses explicitly configured LibreTranslate; never present untranslated English as Dutch.
- Distinguish the capture label HIP_106890 from its editable IC 1396 nebula target. Mark artistic depth as an interpretation, not measured astrometry.
- Require admin authentication and CSRF protection. Keep credentials and all runtime media/database/cache outside Git. Test critical behavior and verify the UI. Deploy only when requested.
- Support an optional fifth final FITS file for real observation metadata and an animated Skykaart. Preserve originals, retain time provenance, distinguish integration from elapsed time, and keep exact site coordinates and HISTORY paths private by default. Use Hipparcos, Stellarium and Astropy with attribution; allow missing metadata to be completed in admin.
