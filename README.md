# AstroWeb

[Nederlands](README.md) · [English](README.en.md) · [Bronnen en licenties](THIRD_PARTY.md)

AstroWeb maakt van je eigen astrofoto’s een lokale filmgalerij. Geef de sterren en de nevel elk een eigen beweging, kies waar de camera naartoe vliegt en publiceer je favoriete versie. Bezoekers kunnen de originele opname bekijken, vanuit de Melkweg naar het beeldveld reizen en de hemel van de opnamenacht verkennen.

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
2. Voeg de vier uitgelijnde AstroWizard-exports toe. Een bijpassende final-FITS levert onder meer het richtpunt en de opnametijd.

   ```text
   NGC_7000_final.png
   NGC_7000_starless.png
   NGC_7000_stars.png
   NGC_7000_stars_laid.png
   NGC_7000_final.fits    (optioneel)
   ```

3. Kies sterrenparallax, nevelreliëf of klassieke pan/zoom. Stel **Aantal zoompunten** in op 1–8. Selecteer een nummer, versleep het kader en trek aan een hoek om de uitsnede te bepalen. Elk punt heeft een eigen zoomfactor tot 8×. De film bezoekt de punten op volgorde en keert terug naar het begin.
4. Kies **Maak film**. Elke geslaagde H.264-film wordt automatisch de galerijversie. Tijdens het renderen blijft de huidige film beschikbaar. Met **Render annuleren** stop je een wachtende of lopende taak. Je kunt een eerdere versie opnieuw selecteren. In Studio kun je ook een ongepubliceerde versie verwijderen of de object-ID en bijbehorende objectteksten wijzigen.

PNG, JPEG en enkelbeeld-TIFF zijn geschikt. De vier beelden moeten dezelfde afmetingen hebben. De limieten zijn 40 megapixels en 100 MiB per beeld, 512 MiB voor FITS en 600 MiB voor de hele upload. De vier originelen krijgen een SHA-256-controlesom. Voor lokale batchimport: stop de server en voer `python -m astroweb import --source AstroPhotos --render` uit, met één submap per object.

## De viewer

| Tabblad | Wat je ziet |
| --- | --- |
| Film | De geselecteerde film op renderresolutie, met objectinformatie en fullscreenbediening. De galerij zelf gebruikt kleine previews en past het aantal kolommen aan de schermbreedte aan. |
| Origineel | De volledige foto. Zoom met het muiswiel of de schuifregelaar tot 10× de ingepaste weergave, versleep de foto of download het origineel. |
| Hemelreis | Een vlucht van het hemelpanorama via fijnere hemelmozaïeken naar je foto. Gaia-matching of een bevestigde FITS-WCS levert het kader. Bij alleen een richtpunt zie je een markering. Objectnamen zijn apart inschakelbaar. |
| Melkweg | Een geanimeerd bovenaanzicht voor herkende Melkwegobjecten met een afstand. Toon objectnamen, pauzeer of verplaats de tijdschuif. Voor andere bevestigde Melkwegobjecten kun je de afstand in Studio invullen. De kaart projecteert de posities op het galactische vlak. |
| Hubble | Vlieg vanuit je foto naar een benoemde structuur in een uitgelijnd optisch archiefbeeld. Bij elke bestemming staan de beeldbron en het instrument of archief. |
| Omgeving | Verken naburige sterrenstelsels en hun bekende relaties. |
| Poolkaart | Cirkelvormige sterrenkaart rond de noordelijke of zuidelijke hemelpool, met sterrenbeeldlijnen, uurverdeling en een instelbare zoom naar het doel. |
| Skykaart | Een kaart van de echte opnamenacht op basis van tijd, positie en locatie, met sterren, sterrenbeeldlijnen en de baan van het doel. |

De parallaxdiepte is een artistieke instelling. Voor het kader van de Hemelreis vergelijkt AstroWeb de sterrenlaag lokaal met Gaia DR3. Nieuwe catalogusvelden, broninformatie en surveytegels vragen internet. Opnamen blijven lokaal. De exacte waarnemingslocatie is standaard privé. Zie [bronnen en licenties](THIRD_PARTY.md) voor de kaarten, catalogi en illustraties.

## Opslag en Docker

`data/` bevat de database, originelen, renders, kaartcache en sessiesleutel. Bewaar deze map als één geheel en stop AstroWeb voordat je een back-up maakt. Start één server of importproces per datamap. Met `ASTROWEB_DATA` kies je een andere locatie. Wachtwoord herstellen kan met `python -m astroweb admin` binnen dezelfde omgeving.

Voor Docker Compose:

```sh
docker compose build
docker compose run --rm astroweb python -m astroweb admin
docker compose up -d
```

De bindmount `./data` moet schrijfbaar zijn voor UID/GID `10001:10001`. Voor Synology bevat [compose.synology.yaml](compose.synology.yaml) een overlay met HTTPS-cookies. Pas hostnaam en datamap aan en laat de HTTPS-reverseproxy doorsturen naar `127.0.0.1:8090`. Gebruik beide composebestanden samen. Gebruik een geldig certificaat voor de publieke hostnaam. Stel bij een lege NAS-installatie het Studio-wachtwoord via de container in voordat je de proxy opent.

## Ontwikkelen

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --experimental-vm-modules tools/check-frontend.mjs
```

De frontend bestaat uit native JavaScript-modules en heeft geen buildstap. De applicatiecode valt onder de [MIT-licentie](LICENSE). Voor meegeleverde astronomische data en beeldmateriaal gelden de [afzonderlijke licenties](THIRD_PARTY.md).

Op **Origineel → Ontdek objecten** kun je catalogusobjecten aanklikken en als benoemd zoompunt naar Studio sturen. De markeringen volgen het oorspronkelijke raster bij zoomen en verslepen. Bij acht bestaande punten kies je welk punt je vervangt. De [ontwikkelagenda](docs/ROADMAP.md) toont de beschikbare functies en de geplande rondleiding met ondertiteling.

**Ander licht** vergelijkt onder Origineel je opname met een astrometrisch uitgelijnde AllWISE-infraroodkaart (W1, W2 en W4). Zoom en pan blijven gekoppeld. De eerste keer worden surveytegels opgehaald; het samengestelde beeld wordt lokaal bewaard. Het tabblad **Omgeving** toont voor herkende sterrenstelsels een hemelkaart met opnamekader, hoekafstanden, bronlinks en gedocumenteerde relaties. In Studio toont **Automatische zoomroute** een voorstel op basis van cataloguscentra en beeldcontrast. Pas het voorstel toe om de huidige route te vervangen. Zodra het uploadvoorbeeld zichtbaar is, kun je al een route op basis van beeldcontrast toepassen op de eerste film. Studio neemt de object-ID bij voorkeur uit het FITS-veld `OBJECT`. Bij een lege of onbekende waarde gebruikt Studio de bestandsnaamprefix. De renderwachtrij bereidt de Hemelreis voor zodra de positie bekend is, vóór de nieuwe film in de galerij verschijnt.

**[Persoonlijke hemelatlas](http://127.0.0.1:8090/atlas)** toont alle gepubliceerde opnamen op één sterrenkaart. Na inloggen zie je ook onuitgegeven opnamen. Kies een opname om in te zoomen, open het origineel of vergelijk twee kaders en posters. Zonder gemeten kader verschijnt een richtpunt als dat bekend is. Voor een tweede nacht of mozaïekpaneel vul je in Studio bij upload dezelfde catalogus-ID in, eventueel met een sessienaam. In de viewer blader je met Vorige en Volgende door de galerij. De hemelomgeving en optionele objectlabels blijven zichtbaar aan het einde van de Hemelreis.

### M31 en de sterren door de tijd

Bij een geregistreerde opname van M31 kun je via **Hubble** de blauwe sterwolk NGC 206, satellietstelsel M32 of de kern van Andromeda kiezen. De vlucht begint op het eigen origineel en zoomt in op dezelfde positie in het PHAT/PHAST-mozaïek. Een keuze verschijnt wanneer het doelgebied in je opname valt. Voor de stofbanden is er ook een grondopname van Robert Gendler. AstroWeb haalt de benodigde zoomtegels bij de eerste weergave op en bewaart ze samen met de 12-secondenfilm lokaal.

De **Sterrentijdmachine** op de Poolkaart toont maximaal 50.000 jaar vóór en na de opnamedatum (of vandaag als de datum ontbreekt). Kies bijvoorbeeld Grote Beer of Zuiderkruis en schuif door de tijd of kies Tijd afspelen. De sporen volgen een model met constante cartesische snelheid uit HYG 4.1. Het coördinatenraster en de helderheden blijven vast; sterren zonder geldige afstand blijven op hun cataloguspositie.

### Nevelvelden, de atlas en zonnestelselopnamen

Bij andere geregistreerde opnamen zoekt **Hubble** naar openbare optische beeldvelden in het ESA Hubble Science Archive. AstroWeb controleert de hemelcoördinaten van de FITS-uitsnede en biedt maximaal twee overlappende velden aan. Archiefdoel en filter staan bij de film. Een opname in één filter wordt in grijstinten getoond. Beschikbaarheid hangt af van de dekking en van geschikte, uitleesbare archiefproducten. Catalogusresultaten, beeldvelden en films worden lokaal gecachet.

De hemelatlas en Poolkaart tekenen de ongedraaide poster tussen de gemeten fotohoeken. Je kunt deze laag uitschakelen. Selecteer één of twee opnamen in de hemelatlas om de bijbehorende thumbnails te bekijken. Het tabblad Origineel toont de geschatte afstand en de zichtbare breedte en hoogte in lichtjaren op de afstand van het doel.

Kies bij upload **Zonnestelsel** voor de zon, maan of een planeet. Eén PNG, JPEG of TIFF is voldoende; een FITS met opnamedatum is optioneel. De beschikbare weergaven zijn Film en Origineel; de film gebruikt pan/zoom. Er wordt geen vaste sterpositie aan het bewegende doel toegekend. Met een bekende opnametijd kan de viewer de geocentrische afstand schatten. Een oppervlaktemaat vraagt aanvullende beeldkalibratie.

### Meerdere opnamen per object

Upload een volgende nacht met dezelfde catalogus-ID. Een nieuwe opname heeft eigen originelen, FITS, uitlijning en filmversies. Gebruik de FITS-datum of vul bij upload een opnamedatum in (bijvoorbeeld de echte opnamenacht van een samengestelde stack). De galerij en de knoppen Vorige/Volgende gebruiken één gepubliceerde opname per object: de recentste opnamedatum. Een onbekende datum komt achter bekende datums. Bij Opnamedatum zie je het aantal beschikbare opnamen en kun je een eerdere opname kiezen; het actieve tabblad blijft waar mogelijk behouden. Alle sessies blijven afzonderlijk zichtbaar in de hemelatlas.

Voor NGC 7000 toont de reis de Cygnusmuur en de donkere stofwolk in het Palomar/DSS2-kleurenmozaïek van Davide De Martin. Voor IC 1396 is de Olifantenslurf beschikbaar in Pan-STARRS-kleur. De NASA Hubble Skymap is vanuit dit tabblad te openen. De Hubble-keuzelijst onderscheidt opnamen van het doel, gedocumenteerde deelgebieden en andere archiefvelden in dezelfde kijkrichting. De zoekactie neemt ook gedeeltelijk overlappende beelden mee; alleen werkelijk belichte pixels binnen je eigen foto kunnen de bestemming van de vlucht vormen.

Bij **Object-ID wijzigen** voegt een bestaande ID de opname toe aan de betreffende datumlijst. Bevestigde catalogusaliassen worden gegroepeerd, bijvoorbeeld C 20 / Caldwell 20 / NGC 7000 en M31 / NGC 224. Je bestanden, filmversies en de oude viewerlink blijven bij de oorspronkelijke opname horen.
