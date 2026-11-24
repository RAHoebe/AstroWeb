# AstroWeb

[Nederlands](README.md) · [English](README.en.md) · [Bronnen en licenties](THIRD_PARTY.md) · [Bekijk de AstroWeb-film op YouTube](https://www.youtube.com/watch?v=mByBMSqRSbg)

[Demonstratie, voorbeeldfilms en installatiegids](https://rahoebe.github.io/AstroWeb/). Voor de NAS en Google TV op hetzelfde vertrouwde netwerk bevat deze release een zelfstandig `compose.lan.yaml` en een LAN-APK. Stel `ASTROWEB_LAN_IP` in op het privé-adres van de server. De LAN-configuratie gebruikt standaard `ASTROWEB_OFFLINE=1` voor lokale verwerking en weergave van eerder opgehaalde beelden.

AstroWeb maakt van je eigen astrofoto’s een lokale filmgalerij. Geef de sterren en de nevel elk een eigen beweging, kies waar de camera naartoe vliegt en publiceer je favoriete versie. Bezoekers kunnen de originele opname bekijken, vanuit de Melkweg naar het beeldveld reizen en de hemel van de opnamenacht verkennen.

## Viewerfuncties en opnamekalender

De objectviewer toont alleen de relevante extra tabs. De opnamekalender staat apart naast de hemelatlas in de galerij. Website en Google TV gebruiken dezelfde gegevens en lokaal bewaarde beelden.

- **Hemelmozaïek** verschijnt vanaf twee overlappende, gemeten opnamen. Reproject voegt ze samen met zachte overgangen en begrensde helderheidsaanpassing. Alle betrokken opnamedatums blijven zichtbaar. Het afgeleide beeld is maximaal 4096 pixels aan de lange zijde en zes miljoen pixels totaal; de originelen blijven ongewijzigd.
- **Sterren in 3D** ontvouwt de eigen foto tot een draaibare afstandskaart. Maximaal 900 sterbeelden komen uit de eigen sterrenlaag, met gekoppelde Gaia DR3-afstanden (parallax-SNR ≥ 10, RUWE < 1,4). Hoekposities volgen het opnamekader; de diepte-as gebruikt een logaritmische afstandsschaal. Dit is een afstandskaart, geen nagebouwd nevelvolume. De TV gebruikt één GPU-batch met een Canvas-terugval. Klik op een ster om zijn afstand en geschatte onzekerheid te bekijken.
- **Lichtreis** laat een lichtpuls van het object naar de Aarde reizen. Totale en resterende reistijd staan in beeld; bij aankomst verschijnt je eigen foto. Bekende nabije afstanden gaan voor roodverschuiving. Voor andere sterrenstelsels zoekt Astroquery in NED en rekent Astropy Planck18 de reistijd en afzonderlijk benoemde afstandsdefinities uit. Studio accepteert meetwaarden met een HTTPS-bronlink. De route is schematisch.
- **Zonvergelijking** verschijnt alleen bij zonopnamen. Vergelijk de eigen foto met SDO/HMI-continuüm of SDO/AIA 171 Å rond de opnametijd. Het echte FITS-tijdstip en tijdverschil blijven zichtbaar; treffers verder dan twaalf uur worden afgewezen. SunPy levert het raster en het rotatiemodel voor een geselecteerde zonnelocatie. De eigen oriëntatie blijft handmatig instelbaar. In de afzonderlijke eclipsdetailreis worden de zichtbare schijfranden gemeten en tijdens de overgang op hetzelfde middelpunt en dezelfde schaal gehouden.
- **Opnamekalender** opent als collectieoverzicht met maand en jaar, portretthumbnails op de opnamedagen en een voorbeeld van de geselecteerde dag. Klik op een dag voor de dagweergave met selecteerbare foto's en bekende DATE-OBS-tijdstempels. Ontbrekende tijden worden niet ingevuld. Standaard tonen de uren astronomische duisternis in Midden-Nederland. Kies optioneel een doel voor specifieke kijktijden (doel ≥ 30°, Zon ≤ −18°, Maan onder de horizon of ≥ 35° van het doel). De resolutie is 30 minuten, inclusief zomertijd; de jaarbalk bemonstert de 15e van elke maand. Dit bevat geen weersvoorspelling.

Op TV staan **Sterren in 3D**, **Lichtreis**, **Mozaïek** en **Zonvergelijking** bij het object. In de galerij staat **Kalender** naast **Hemelatlas**. Links/rechts kiest een dag; omhoog/omlaag wisselt de maand. OK opent de dagweergave, waar links/rechts een opname kiest en OK de foto opent. Terug herstelt de kalender. De uitleg per modus staat in beeld.

Zware voorbereiding loopt in de begrensde serverwachtrij. Resultaten staan buiten de broncode onder `data/observatory/`; opgehaalde Gaia-metingen blijven offline bruikbaar. Ontbrekende brongegevens worden gemeld en tijdelijke Gaia-uitval wordt opnieuw geprobeerd. Privé-opnamen blijven afgeschermd; openbare kijktijden gebruiken geen privé-locatie. Gebruik [web v1.6.10](https://github.com/RAHoebe/AstroWeb/releases/tag/v1.6.10) en [TV 0.8.2](https://github.com/RAHoebe/AstroWeb/releases/tag/tv-v0.8.2).

Na de eerste film zoekt de achtergrondtaak ook op catalogusnummer, naam en aliassen in de fotoarchieven van NOIRLab en ESO. Een kleurenreis richt zich op het gekleurde gas of stof en verschijnt zodra onafhankelijke sterren de uitlijning bevestigen. Bij nevels zoekt AstroWeb ook in Pan-STARRS1 naar driekleurenbeelden van de nevel en van deelgebieden. Voor geselecteerde NOIRLab-foto’s kan AstroWeb de positie, schaal en draaiing uit gedeelde sterren bepalen, ook als de archieffoto geen hemelcoördinaten bevat. Alleen volledig overlappende en gecontroleerde beelden worden als bestemming aangeboden. Geselecteerde kleurenfoto’s met een gecontroleerde uitlijning blijven aan de bijbehorende opname gekoppeld als de catalogus opnieuw wordt doorzocht. Bewaar bij een back-up ook de map `data/archive-photos/` en de database.

TV 0.8 houdt de viewerknoppen op één rij, met draaien en volledig scherm rechts als icoonknoppen. **Verken** biedt alleen de opnamenacht/vanavond en de benoemde onderdelen van de geopende opname. **Kijkmodi** op het hoofdscherm start direct een willekeurige avondvoorstelling van vijf minuten of een fotolijst van één uur. Galerij opent de hoofdgalerij met je object geselecteerd; Terug behoudt de herkomst, bijvoorbeeld de kalender.

## Aan de slag

Installeer Python 3.11–3.13 en FFmpeg met de encoder `libx264`. Zorg dat `python` en `ffmpeg` beschikbaar zijn in je terminal. De eerste installatie haalt Python-pakketten op. De CPU verzorgt de rendering.

```sh
git clone https://github.com/RAHoebe/AstroWeb.git
cd AstroWeb
```

**Windows:** dubbelklik op `Start-AstroWeb.cmd`. Op Linux of macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m astroweb serve
```

Open de [lokale galerij](http://127.0.0.1:8090/). Kies [Studio](http://127.0.0.1:8090/admin) en stel op dezelfde computer je eerste beheerderswachtwoord in (minimaal 11 tekens). De [ingebouwde handleiding](http://127.0.0.1:8090/guide) is beschikbaar in het Nederlands en Engels. Een nieuwe installatie begint met een lege galerij.

## Je eerste film

1. Kies **Nieuwe film** en selecteer je bestanden. Controleer de voorgestelde object-ID uit FITS of de bestandsnaam.
2. Voeg de uitgelijnde AstroWizard-exports toe: final, starless en stars. Stars_laid is optioneel. Een bijpassende final-FITS levert onder meer het richtpunt en de opnametijd.

   ```text
   NGC_7000_final.png
   NGC_7000_starless.png
   NGC_7000_stars.png
   NGC_7000_stars_laid.png (optioneel)
   NGC_7000_final.fits    (optioneel)
   ```

3. Kies sterrenparallax, Gaia-parallax met gemeten sterafstanden, nevelreliëf of klassieke pan/zoom. Stel **Aantal zoompunten** in op 1–8. Selecteer een nummer, versleep het kader en trek aan een hoek om de uitsnede te bepalen. Elk punt heeft een eigen zoomfactor tot 8×. De film bezoekt de punten op volgorde en keert terug naar het begin.
4. Kies **Maak film**. Elke geslaagde H.264-film wordt automatisch de galerijversie en verschijnt direct in de Studio-speler. De beeldstand van de film is instelbaar bij liggende bronfoto’s. Tijdens het renderen blijft de huidige film beschikbaar. Met **Render annuleren** stop je een wachtende of lopende taak. Je kunt een eerdere versie opnieuw selecteren. In Studio kun je ook een ongepubliceerde versie verwijderen of de object-ID en bijbehorende objectteksten wijzigen.

Studio herkent ook gangbare objectnamen, zoals **Plejaden**, **Zevengesternte** en **Melotte 22** voor M45. Ook **Sikkelnevel** (NGC 6888) en **Zielnevel** (IC 1848) worden offline herkend en hebben een tweetalige beschrijving. Bij een onbekende naam in het FITS-veld `OBJECT` kan Studio een Wikipedia-titel opzoeken via Wikidata. Een treffer moet een SIMBAD-verwijzing en een ondersteund catalogus-ID hebben. Als er geen eenduidige treffer is, gebruikt Studio de bestandsnaamprefix.

Voor broninformatie zoekt Studio ook naar een Nederlandse en Engelse Wikipedia-inleiding die via Wikidata aan hetzelfde catalogusobject is gekoppeld. Als een bron alleen Engels bevat, kan een geconfigureerde LibreTranslate-server die tekst vertalen. Het Vuurwerkstelsel (NGC 6946) en de nabij afgebeelde sterrenhoop NGC 6939 hebben ook offline Nederlandse en Engelse informatie. Nieuwe conceptopnamen krijgen ook vóór het renderen broninformatie. De lokale catalogus bevat onder meer OpenNGC-metingen, gecontroleerde Wikidata-gegevens en NASA-objectpagina’s. De Ringnevel (M57) heeft ook een tweetalige beschrijving. **Broninformatie ophalen** vervangt eerder opgehaalde bronnen. Studio bewaart de tekst die je zelf hebt gewijzigd.

PNG, JPEG en enkelbeeld-TIFF zijn geschikt. De beelden moeten dezelfde afmetingen hebben. De limieten zijn 40 megapixels en 100 MiB per beeld, 512 MiB voor FITS en 600 MiB voor de hele upload. De originelen krijgen een SHA-256-controlesom. Voor lokale batchimport: stop de server en voer `python -m astroweb import --source AstroPhotos --render` uit, met één submap per object.

## De viewer

| Tabblad | Wat je ziet |
| --- | --- |
| Film | De geselecteerde film op renderresolutie, met objectinformatie en fullscreenbediening. De galerij zelf gebruikt kleine previews en past het aantal kolommen aan de schermbreedte aan. |
| Extra objecttabs | Hemelmozaïek bij overlappende opnamen, sterren in 3D, lichtreis en zonvergelijking. De opnamekalender staat bij de galerij. |
| Origineel | De volledige foto. Zoom met het muiswiel of de schuifregelaar tot 10× de ingepaste weergave, versleep de foto of download het origineel. |
| Wat zie ik? | Kies een markering op de eigen foto, bekijk de uitleg en zoom naar het onderdeel. Bij deep-sky komen de posities uit de hemeluitlijning. De Maan krijgt automatische labels bij een geslaagde uitlijning. Op zonnestelselopnamen kun je als beheerder met **Markering toevoegen** zelf zichtbare details aanwijzen en per opname opslaan. Die verschijnen ook in de TV-gids. |
| Hemelreis | Een vlucht van het hemelpanorama via fijnere hemelmozaïeken naar je foto. Gaia-matching of een bevestigde FITS-WCS levert het kader. De eindstand is de kwartslag die het minste draaien vraagt. Bij alleen een richtpunt zie je een markering. Objectnamen zijn apart inschakelbaar. |
| Melkweg | Een geanimeerd bovenaanzicht voor herkende Melkwegobjecten met een afstand. Toon objectnamen, pauzeer of verplaats de tijdschuif. Voor andere bevestigde Melkwegobjecten kun je de afstand in Studio invullen. De kaart projecteert de posities op het galactische vlak. |
| Archiefreizen | Vlieg vanuit je foto naar een benoemde structuur in een uitgelijnd Hubble-, Euclid- of JWST-beeld. Bij elke bestemming staan de beeldbron en het instrument of archief. Het zoomdoel blijft tijdens de hele vlucht in beeld, zowel op de website als op Google TV. |
| Detailreizen Maan | Koppel je maanfoto aan de gedateerde NASA SVS-referentie en zoom via ingemeten LRO-mozaïeken naar Apollo 11, 12 of 14, Tycho, Copernicus, Plato, Aristarchus, Clavius of de maanzeeën Tranquillitatis en Imbrium. Apollo-gebieden hebben extra NAC-detail; kraters en zeeën gebruiken de WAC-kaart van 100 m/pixel. Opgehaalde beelden werken ook offline. Bij onbetrouwbare uitlijning verschijnt een melding in plaats van een willekeurige overvloeiing. |
| Omgeving | Verken naburige sterrenstelsels en hun bekende relaties. |
| Poolkaart | Cirkelvormige sterrenkaart rond de noordelijke of zuidelijke hemelpool, met sterrenbeeldlijnen, uurverdeling en een instelbare zoom naar het doel. |
| Skykaart | Een kaart van de echte opnamenacht op basis van tijd, positie en locatie, met sterren, sterrenbeeldlijnen en de baan van het doel. |

De parallaxdiepte is een artistieke instelling. Bij **Gaia-parallax** bepaalt de gemeten afstand de beweging van gekoppelde sterren. Studio toont het aantal bruikbare matches. Hiervoor zijn een uitgelijnde opname en een opnamedatum nodig. Bij **Ongekoppelde sterren** kies je beweging met de nevel of **Lokale interpolatie · geschat**. Interpolatie gebruikt alleen voldoende nabije sterren met overeenkomende afstanden en wordt apart geteld. De cameraverplaatsing wordt voor zichtbaarheid versterkt. Voor het kader van de Hemelreis vergelijkt AstroWeb de sterrenlaag lokaal met Gaia DR3. Nieuwe catalogusvelden, broninformatie en surveytegels vragen internet. Opnamen blijven lokaal. De exacte waarnemingslocatie is standaard privé. Zie [bronnen en licenties](THIRD_PARTY.md) voor de kaarten, catalogi en illustraties.

## Opslag en Docker

De Gaia-uitlijning probeert AIP en het officiële ESA-archief. Bij een tijdelijke storing volgen achtergrondpogingen na 1 minuut, 5 minuten, 30 minuten, 2 uur en daarna elke 6 uur. De wachttijd blijft bewaard na een herstart; filmrenders krijgen voorrang en de offline-modus schakelt netwerkherkansingen uit. Openen van de viewer of het mozaïek kan een geplande herkansing activeren zonder de pagina te blokkeren. Een nieuw beschikbaar mozaïektabblad verschijnt automatisch in de geopende viewer. Bij ontbrekende richtgegevens of een mislukte sterrenmatch moet de invoer worden verbeterd; die worden niet eindeloos opnieuw bevraagd. Originelen, films en gekozen archiefbestemmingen blijven behouden.

`data/` bevat de database, originelen, renders, kaartcache en sessiesleutel. Bewaar deze map als één geheel en stop AstroWeb voordat je een back-up maakt. Start één server of importproces per datamap. Met `ASTROWEB_DATA` kies je een andere locatie. Wachtwoord herstellen kan met `python -m astroweb admin` binnen dezelfde omgeving.

Voor Docker Compose:

```sh
docker compose build
docker compose run --rm astroweb python -m astroweb admin
docker compose up -d
```

De bindmount `./data` moet schrijfbaar zijn voor UID/GID `10001:10001`. Docker gebruikt deze map ook voor de tijdelijke uploadbuffer. Voor Synology bevat [compose.synology.yaml](compose.synology.yaml) een overlay met HTTPS-cookies. Pas hostnaam en datamap aan en laat de HTTPS-reverseproxy doorsturen naar `127.0.0.1:8090`. Gebruik beide composebestanden samen. Gebruik een geldig certificaat voor de publieke hostnaam. Stel bij een lege NAS-installatie het Studio-wachtwoord via de container in voordat je de proxy opent.

## Ontwikkelen

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --experimental-vm-modules tools/check-frontend.mjs
```

De frontend bestaat uit native JavaScript-modules en heeft geen buildstap. De applicatiecode valt onder de [MIT-licentie](LICENSE). Voor meegeleverde astronomische data en beeldmateriaal gelden de [afzonderlijke licenties](THIRD_PARTY.md).

Op **Origineel → Ontdek objecten** kun je catalogusobjecten aanklikken en als benoemd zoompunt naar Studio sturen. De markeringen volgen het oorspronkelijke raster bij zoomen en verslepen. Bij acht bestaande punten kies je welk punt je vervangt. De [ontwikkelagenda](docs/ROADMAP.md) toont de beschikbare functies en de geplande rondleiding met ondertiteling.

**Ander licht** vergelijkt onder Origineel je opname met een astrometrisch uitgelijnde AllWISE-infraroodkaart (W1, W2 en W4). Zoom en pan blijven gekoppeld. De eerste keer worden surveytegels opgehaald; het samengestelde beeld wordt lokaal bewaard. Het tabblad **Omgeving** toont voor herkende sterrenstelsels een hemelkaart met opnamekader, hoekafstanden, bronlinks en gedocumenteerde relaties. In Studio toont **Automatische zoomroute** een voorstel op basis van cataloguscentra en beeldcontrast. Pas het voorstel toe om de huidige route te vervangen. Upload bij een nieuwe opname eerst de bestanden met **Bestanden uploaden**. De voortgangsbalk toont hoeveel al verstuurd is. Na de controle blijft de opname als concept in Studio staan. De zoomroute gebruikt die opgeslagen bestanden en controleert de positie op de foto met FITS of Gaia. Start daarna de render met **Maak film**. Bevestigde posities krijgen een label. Andere stops worden aangeduid als beelddetails. Studio neemt de object-ID bij voorkeur uit het FITS-veld `OBJECT`. Bij een lege of onbekende waarde gebruikt Studio de bestandsnaamprefix. De renderwachtrij bereidt de Hemelreis voor zodra de positie bekend is, vóór de nieuwe film in de galerij verschijnt.

**[Persoonlijke hemelatlas](http://127.0.0.1:8090/atlas)** toont alle gepubliceerde opnamen op één sterrenkaart. Na inloggen zie je ook onuitgegeven opnamen. Kies een opname om in te zoomen, open het origineel of vergelijk twee kaders en posters. Zonder gemeten kader verschijnt een richtpunt als dat bekend is. Voor een tweede nacht of mozaïekpaneel vul je in Studio bij upload dezelfde catalogus-ID in, eventueel met een sessienaam. In de viewer blader je met Vorige en Volgende door de galerij. De hemelomgeving en optionele objectlabels blijven zichtbaar aan het einde van de Hemelreis.

### M31 en de sterren door de tijd

Bij een geregistreerde opname van M31 kun je via **Archiefreizen** de blauwe sterwolk NGC 206, satellietstelsel M32 of de kern van Andromeda kiezen. De vlucht begint op het eigen origineel en zoomt in op dezelfde positie in het PHAT/PHAST-mozaïek. Een keuze verschijnt wanneer het doelgebied in je opname valt. Voor de stofbanden is er ook een grondopname van Robert Gendler. AstroWeb haalt de benodigde zoomtegels bij de eerste weergave op en bewaart ze samen met de 12-secondenfilm lokaal.

De **Sterrentijdmachine** op de Poolkaart toont maximaal 50.000 jaar vóór en na de opnamedatum (of vandaag als de datum ontbreekt). Kies bijvoorbeeld Grote Beer of Zuiderkruis en schuif door de tijd of kies Tijd afspelen. De sporen volgen een model met constante cartesische snelheid uit HYG 4.1. Het coördinatenraster en de helderheden blijven vast; sterren zonder geldige afstand blijven op hun cataloguspositie.

### Nevelvelden, de atlas en zonnestelselopnamen

Bij andere geregistreerde opnamen zoekt **Archiefreizen** naar openbare optische beeldvelden in de Amerikaanse en Europese Hubble-archieven. AstroWeb controleert het volledige archiefveld en de werkelijke FITS-uitsnede en biedt maximaal zes verschillende Hubble-velden aan. Archiefdoel en filter staan bij de film. Een opname in één filter wordt in grijstinten getoond. Beschikbaarheid hangt af van de dekking en van geschikte, uitleesbare archiefproducten. Catalogusresultaten, beeldvelden en films worden lokaal gecachet.

De hemelatlas en Poolkaart tekenen de ongedraaide poster tussen de gemeten fotohoeken. Je kunt deze laag uitschakelen. Selecteer één of twee opnamen in de hemelatlas om de bijbehorende thumbnails te bekijken. Het tabblad Origineel toont de geschatte afstand en de zichtbare breedte en hoogte in lichtjaren op de afstand van het doel.

Kies bij upload **Zonnestelsel** voor de zon, maan of een planeet. Eén PNG, JPEG of TIFF is voldoende; een FITS met opnamedatum is optioneel. De Hemelreis volgt de richting vanaf de waarneemlocatie op het opnametijdstip. De film toont UTC, sterrenbeeld en hemelcoördinaten. Een herkenbare volledige schijf groeit vanuit het richtpunt op basis van de schijnbare diameter; een detailopname verschijnt als close-up. De Melkwegkaart wijst het zonnestelsel aan. De Skykaart volgt het hemellichaam van middernacht tot middernacht. Met alleen een datum gebruikt AstroWeb 12.00 uur lokale tijd. Ontbreekt de waarneemlocatie, dan geldt Midden-Nederland (52,15° N, 5,38° O). Bij **Detailreis** kies je missiebeelden van onder meer SDO, LRO, Juno en Cassini, met de bron bij de film. Met een bekende opnametijd kan de viewer de geocentrische afstand schatten. Een oppervlaktemaat vraagt aanvullende beeldkalibratie.

Na de eerste geslaagde film van een zonnestelselopname bereidt de server de detailreizen op de achtergrond voor. Bij de Maan kiest hij bestemmingen die zichtbaar en verlicht zijn op de ingemeten opname. Bij het opstarten vult de server ontbrekende reizen voor bestaande films aan. Voltooide reizen zijn direct afspeelbaar.

Een zonnestelselbeeld dat onder de normale minimumafmetingen valt en kleiner is dan 256 pixels aan de langste zijde krijgt een interpolatieversie van 256 pixels voor de weergave en de film. Download origineel levert de bronfoto. Bij ASIStudio-planeetstacks gebruikt AstroWeb een tijdstempel zoals `2026-11-20-180949` uit de bestandsnaam in de tijdzone Europe/Amsterdam. Als de naam geen eenduidig tijdstip bevat, vul je de opnametijd in Studio in. De oorspronkelijke FITS-header blijft bewaard. De detailreizen naar Saturnus gebruiken de gemeten ringrichting voor de overgang naar een Cassini-overzicht, als de ringen op de foto voldoende zichtbaar zijn. Als de ringen voldoende zichtbaar zijn, verschijnt bij **Wat zie ik?** ook automatisch een markering die naar **Saturnus en zijn ringen** leidt. Een handmatig geplaatste markering krijgt voorrang.

### Meerdere opnamen per object

Upload een volgende nacht met dezelfde catalogus-ID. Een nieuwe opname heeft eigen originelen, FITS, uitlijning en filmversies. Gebruik de FITS-datum of vul bij upload een opnamedatum in (bijvoorbeeld de echte opnamenacht van een samengestelde stack). De galerij en de knoppen Vorige/Volgende gebruiken één gepubliceerde opname per object: de recentste opnamedatum. Een onbekende datum komt achter bekende datums. Bij Opnamedatum zie je het aantal beschikbare opnamen en kun je een eerdere opname kiezen; het actieve tabblad blijft waar mogelijk behouden. Alle sessies blijven afzonderlijk zichtbaar in de hemelatlas.

Voor NGC 7000 toont de reis de Cygnusmuur en de donkere stofwolk in het Palomar/DSS2-kleurenmozaïek van Davide De Martin. Voor IC 1396 is de Olifantenslurf beschikbaar in Pan-STARRS-kleur. De NASA Hubble Skymap is vanuit dit tabblad te openen. De keuzelijst bij Archiefreizen onderscheidt opnamen van het doel, gedocumenteerde deelgebieden en andere archiefvelden in dezelfde kijkrichting. Automatisch toegevoegde archiefvelden en hun FITS-uitsneden moeten helemaal binnen je eigen foto vallen. De vlucht eindigt op werkelijk belichte pixels.

Bij **Object-ID wijzigen** voegt een bestaande ID de opname toe aan de betreffende datumlijst. Bevestigde catalogusaliassen worden gegroepeerd, bijvoorbeeld C 20 / Caldwell 20 / NGC 7000 en M31 / NGC 224. Je bestanden, filmversies en de oude viewerlink blijven bij de oorspronkelijke opname horen.

### Automatische archiefbestemmingen bij upload

Studio doorzoekt voor nieuwe deep-skyopnamen de [NASA Hubble Skymap](https://science.nasa.gov/mission/hubble/multimedia/online-activities/hubble-skymap/) op object-ID en catalogusaliassen. Een passende NASA-foto staat als eerste bij **Archiefreizen → Bestemming**. De film nadert de Skymap-positie wanneer die binnen het gemeten opnamekader ligt en gaat over in de volledige NASA-foto. Zonder gemeten kader begint de overgang vanuit de hele eigen opname. De Skymap geeft de objectpositie, maar geen betrouwbare oriëntatie en schaal voor iedere gepubliceerde foto. Na de uitlijning zoekt Studio ook bij een Skymap-treffer automatisch in NASA’s MAST en het ESA Hubble Science Archive op de doelnaam, catalogusaliassen en bekende deelgebieden. Beide archieven worden ook op hemelcoördinaten rond de gemeten fotohoeken doorzocht. De viewer onderscheidt het object, een bekend deelgebied en overige velden in dezelfde kijkrichting. Voor een automatische archiefbestemming moeten zowel het volledige gepubliceerde Hubble-beeldveld als de gebruikte FITS-uitsnede binnen het gemeten kader van deze opnamedatum vallen. Studio selecteert maximaal zes verschillende archiefvelden. Voor zowel de beeldvelden als de FITS-uitsneden moet de onderlinge overlap kleiner zijn dan de helft van het kleinste veld. Een passende Skymap-foto staat bovenaan, gevolgd door de genummerde velden met hun filter en hemelcoördinaten. Bestaande samengestelde reizen blijven beschikbaar. De catalogus en geselecteerde beelden worden lokaal bewaard.

Aanvullende achtergrondzoekacties gebruiken Astroquery TAP voor Euclid VIS-mozaïeken (DR1 en Q1) en openbare gekalibreerde JWST-beelden in het ESA-archief, met MAST als terugval voor JWST-catalogusgegevens. Euclid levert kleine optische uitsneden rond catalogusobjecten binnen je opname; JWST levert infraroodbeelden in één filter. Deze wetenschappelijke beelden worden in grijstinten getoond en zijn geen automatisch samengestelde kleurenfoto’s. De werkelijke FITS-pixelgrenzen, belichte dekking en hemelcoördinaten moeten kloppen voordat een bestemming verschijnt. Per extra telescoop kunnen maximaal drie verschillende bestemmingen worden toegevoegd; een passende Skymap-foto blijft bovenaan. Producten groter dan 96 MiB worden overgeslagen en downloads en zoekacties hebben een tijdslimiet. De extra zoekacties lopen na de huidige rendering en houden de publicatie van je film niet tegen. Goede resultaten worden lokaal bewaard voor offline afspelen; bij netwerkproblemen blijven bestaande bestemmingen behouden. De bestaande `/hubble`-media-URL’s en viewerbladwijzers blijven werken.

Kies in Studio bij **Soort opname** voor **Sterrensporen** of **Melkwegfoto**. Eén PNG met een vrije bestandsnaam volstaat. Voeg optioneel een FITS met opnamegegevens en een titel toe. Iedere upload krijgt een eigen galerijkaart, een zoombaar origineel en een pan/zoomfilm die standaard de oorspronkelijke oriëntatie behoudt.

Open **Nachtpanorama** boven de galerij om in het ESO-hemelpanorama naar jouw gepubliceerde opnamen te springen. Bij een eigen Melkwegfoto of sterrensporenopname kun je in Studio onder **Nachtpanorama** een opname kiezen, haar positie op de foto aanklikken en opslaan. Zet de 360°-optie aan als het beeld een hele ronde beslaat. Bezoekers kunnen slepen, zoomen en de gekoppelde foto openen. De knop **Foto’s** toont de eigen opnamen in hun gemeten kader. Klik op een kader of objectnaam om naar het origineel te zoomen. Bij terugkeer wordt je kijkpositie hersteld.

Op mobiel en tablet kun je in het nachtpanorama, op **Origineel** en in de hemelatlas met twee vingers zoomen. Houd daarna één vinger op het scherm om verder te slepen.

### Optionele objectteksten met Luna

**Een OpenAI API-key is optioneel.** AstroWeb kan zonder sleutel worden geïnstalleerd. De galerij, het renderen en de gewone bronfunctie in Studio blijven beschikbaar. Stel alleen voor Luna een sleutel in.

Stel `OPENAI_API_KEY` in op de server of koppel een alleen-lezen Docker-secret en zet `ASTROWEB_OPENAI_KEY_FILE` op het pad in de container. AstroWeb gebruikt de Responses API met `gpt-6-luna`. In de offlinemodus blijft de koppeling uit.

Kies in Studio bij **Objectinformatie bewerken → Luna** of je ontbrekende teksten na een render wilt aanvullen. De standaardstand is handmatig. Met **Bekijk tekstvoorstel** kun je de tekst en de bronlinks eerst lezen. **Bestaande beschrijving verdiepen** voegt, als de bronnen het toelaten, alinea’s toe over bijvoorbeeld het ontstaan van een nevel, zijn licht en herkenbare structuren. Een aparte keuze laat Luna op astronomische websites zoeken. Generatie en webzoeken kunnen API-tegoed kosten. De NAS bewaart overgenomen tekst voor website en TV. Alleen objecttekst gaat naar de API.

Bij **Wat zie ik?** kan een ingelogde beheerder bij een bevestigd cataloguslabel brongebonden uitleg in beide talen voorbereiden. In Studio kun je **Zoomroute met Luna** bekijken en overnemen, of onder **Volgorde archiefreizen** de voorgestelde volgorde bekijken en opslaan. Deze opties verschijnen bij deep-sky-opnamen als een API-key is ingesteld. Opgeslagen labeluitleg en archiefvolgordes blijven zonder API-key leesbaar.
