# Onderzoek: cinematografische astrofotografie

[Nederlands](ONDERZOEK.md) · [English](RESEARCH.en.md)

Onderzocht op 13 november 2026. Doel: een zelfstandige lokale/NAS-app die de bestaande AstroWizard-exports gebruikt en echte films opslaat.

| Voorbeeld / code | Beschikbaarheid | Bruikbaar idee / keuze |
| --- | --- | --- |
| [DeepParallax Studio](https://www.deepskycolors.com/apps/deepparallax-studio/) en [technische referentie](https://www.deepskycolors.com/astro/docs/tools/DeepParallax/DeepParallax.html) | Commerciële software; geen geverifieerde vrij herbruikbare broncode | Aparte starless/stars-invoer, verschillende sterdiepten, camerabanen en veiligheidsuitsnede. De documentatie maakt expliciet onderscheid tussen artistieke en gemeten Gaia-diepte. |
| [Zenith Cinematic](https://www.zenith-astro.com/cinematic) | Commercieel; geen herbruikbare broncode geverifieerd | Visuele referentie voor een rustige orbit-/fly-throughpresentatie. De pagina was niet volledig tekstueel inspecteerbaar; er is geen interne implementatie afgeleid. |
| [Cinematic Astro](https://cinematicastro.web.app/) en de [gedeelde Reddit-post](https://www.reddit.com/r/SideProject/comments/1x0qpsn/i_built_a_free_tool_that_turns_deepsky/) | Ophalen werd geblokkeerd/onbeschikbaar | Geen claims over de werking of broncode; de opgegeven referenties blijven opgenomen. |
| [Seiza parallax](https://github.com/theatrus/seiza/tree/main/seiza-parallax) en [depth-planesontwerp](https://github.com/theatrus/seiza/blob/main/docs/design/parallax-depth-planes.md) | Apache-2.0, Rust | Sterren als afzonderlijke zachte sprites, reststerrenveld, screencompositie in lichtdomein, camera fitting en gelaagde stofstructuren. Beste kandidaat voor een latere renderer met Gaia-afstanden en plate solving. Niet als dependency opgenomen. |
| [DepthFlow](https://github.com/BrokenSource/DepthFlow) | AGPL-3.0, GPU-pipeline | Dieptekaart en ray marching voor bewegende stilstaande beelden. Interessant als aparte optionele backend, met een eigen licentie-/GPU-afweging. Geen code gekopieerd. |
| [Depthy](https://github.com/panrafal/depthy) | MIT, oudere browserimplementatie | Dieptekaartverplaatsing en browserparallax. Conceptuele referentie voor een toekomstige interactieve preview. |
| [Parallax Designer](https://github.com/robert-hoffmann/parallax-designer) | MIT | Visueel bewerken van meerdere lagen en HTML-export; relevant voor een latere tijdlijn of handmatige dieptelagen. |
| [Three.js](https://github.com/mrdoob/three.js) | MIT | Mogelijke live WebGL-preview. Voor opgeslagen NAS-video's is de huidige CPU-renderer eenvoudiger te beheren. |
| [RaspAstroDisplay](https://github.com/RAHoebe/RaspAstroDisplay) | MIT voor code; aparte cataloguslicenties | Concrete hergebruikte catalogusdata, cataloguslezer, sterrennamen en het principe van een vastgelegde opnamenacht. De oorspronkelijke dashboard-/Skyfield-app wordt niet als geheel overgenomen. |
| LeefRadar, lokale checkout | Python/Flask, Docker en Synology-configuratie geïnspecteerd | Zelfde soort zelfstandige service met duurzame datamap, loopback-poort en NAS-reverseproxy. |

## Gekozen eerste renderer

Omdat starless en stars al beschikbaar zijn, is een AI-sterrenverwijderaar of een generiek monoculair AI-dieptemodel niet nodig. De eerste implementatie gebruikt NumPy/OpenCV op de CPU en FFmpeg voor H.264. Dit is voorspelbaar op een NAS en heeft geen GPU-, modeldownload- of licentieafhankelijkheid van commerciële pakketten.

1. Controleer afmetingen, inhoud en ID-prefix; bewaar de originelen ongewijzigd.
2. Vergelijk beide sterrenlagen via screen en optellen met de final. Kies de laagste MAE.
3. Maak een nevelachtergrond en twee artistieke sterrenlagen; houd verbonden sterkernen heel. Behoud de starless-achtergrond zonder residucorrectie vanuit final.
4. Pas periodieke camerapaden toe, met onafhankelijke verschuiving/zoom en optioneel een glad helderheidsreliëf van de nevel.
5. Gebruik overscan en beperk parameterbereiken zodat lege randen buiten beeld blijven.
6. Schrijf een tijdelijke MP4, voltooi FFmpeg en publiceer het bestand atomair. Een mislukte taak raakt de vorige film niet.

Voor de voorbeelden won `stars_laid + screen`: MAE circa 0,19% voor HIP_106890 en 0,065% voor NGC_7000, gemeten op verkleinde beelden. Deze score beoordeelt reconstructie, niet artistieke kwaliteit of wetenschappelijke nauwkeurigheid.

## Objectinformatie en gratis bronnen

[NASA's officiële API-documentatie](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf) beschrijft de key-free dienst `https://images-api.nasa.gov/search`. Deze geeft titels, beschrijvingen, datum en credits, maar is een media-archief en kan verkeerde zoekmatches geven. Daarom controleert AstroWeb het doel en de aliassen, cachet de response en houdt de broncaption los van eigen tekst.

Er is geen algemene Nederlandse NASA-vertaal-API. [LibreTranslate](https://docs.libretranslate.com/) kan zelf gehost worden; de beheerde dienst kan betaald zijn. [Argos Translate](https://github.com/argosopentech/argos-translate) is een mogelijke latere offline vertaler. Beide initiële objecten hebben nu eigen Nederlandse en Engelse teksten. Exacte afstanden zijn bewust niet samengevoegd uit verschillende, soms verouderde bronnen.

## Geanimeerde Skykaart

De FITS-headers bevatten echte locatie, RA/Dec, DATE-OBS, telescoop/filter en integratieduur. Astropy/ERFA berekent zonder netwerk actuele horizontale posities. De hergebruikte Hipparcos-sterren bewegen inclusief benaderde eigenbewegingen; Stellarium levert de sterrenbeeldlijnen. De browser animeert tienminutenstappen en toont het doelpad en een hoogtecurve. Exacte locatie blijft standaard serverintern.

De kaart is geen volledige kopie van de RaspAstroDisplay-poster: er wordt geen surveybeeld opgehaald, geen JPL-Maanpositie berekend en geen weeradvies gegeven. Het doel is hier het terugspelen van de opnamenacht. Gaia-sterrenparallax, handmatige neveldieptelagen, een live WebGL-preview en een export van de Skykaart als video zijn mogelijke vervolgstappen.

## Controle op donkere sterafdrukken · 15 november 2026

De eerdere residucorrectie veranderde de starless-achtergrond met het verschil tussen final en de samengestelde lagen. Bij een te heldere sterrenlaag ontstonden negatieve sterafdrukken die loskwamen van de bewegende sterren. Deze correctie is verwijderd. De gekozen screen- of additieve compositie blijft actief. Verschillen in de AstroWizard-exports kunnen daardoor in de totale helderheid zichtbaar zijn. De sterrenlagen voegen uitsluitend licht toe.

Voor Gaia-diepte moeten de sterafbeeldingen afzonderlijk aan Gaia-bronnen worden gekoppeld. De huidige lokale Gaia-uitlijning vraagt alleen positie en magnitude op. Helderheid bepaalt nu de artistieke verdeling van de sterren over twee bewegingslagen. Een volgende afstandsgestuurde modus vraagt bron-ID, parallax, parallaxfout, eigenbeweging en kwaliteitsgegevens, met propagatie naar de opnamedatum. Gebruik onderbouwde afstandsschattingen en onzekerheden, bijvoorbeeld Bailer-Jones, voor onzekere parallaxes. Ongekoppelde of onzekere sterren blijven in een gemeenschappelijke restlaag. Toon bij zo'n modus dat de cameraverplaatsing voor zichtbaarheid wordt versterkt.

De ESA-animatie versterkt parallax en eigenbeweging met een factor 10.000. Het artikel van Luri et al. beschrijft onzekerheden en vertekeningen bij het omzetten van Gaia-parallax naar afstand. Seiza demonstreert een bruikbaar ontwerp met starless-achtergrond, afzonderlijke stersprites en gemeten Gaia-afstanden. Voor deze correctie is behoud van de aangeleverde nevel gekozen. Studio biedt nu een aparte Gaia-methode zoals hieronder beschreven.

Bronnen
- [ESA · Parallax and proper motion](https://www.esa.int/esatv/Videos/2018/04/Parallax_and_proper_motion)
- [Luri et al. 2018 · Using Gaia parallaxes](https://doi.org/10.1051/0004-6361/201832964)
- [Bailer-Jones · GeDR3 distance FAQ](https://bailer-jones.www3.mpia.de/gedr3_distances/FAQ.html)
- [Seiza · Depth planes for parallax videos](https://github.com/theatrus/seiza/blob/main/docs/design/parallax-depth-planes.md)

### Beschikbaar · Gaia-parallax

De methode gebruikt Gaia DR3-sterren helderder dan G=14. Posities worden met de eigenbeweging naar DATE-OBS verplaatst. Alleen positieve parallaxes met signaal-ruisverhouding van minstens 10 en RUWE tussen 0 en 1,4 worden gebruikt. De afstand is de benadering 1000/parallax in parsec, zonder nulpuntcorrectie of Bayesiaanse prior. Dit is bedoeld als diepteverdeling voor de film. Deze selectie garandeert geen foutloze afstand.

Sterkernen worden eenduidig aan de gemeten posities gekoppeld. Elke gekoppelde ster krijgt een klein beeldfragment met zachte rand. De resterende sterrenlaag beweegt mee met de starless-nevel. De gemeten afstanden bepalen de volgorde van de bewegingssnelheden, begrensd rond de mediane sterafstand. Camerabeweging en schaal blijven artistiek. De nevel krijgt geen verzonnen gemeten afstand. Studio toont het aantal gekoppelde sterren en het afstandsbereik.

Catalogusgegevens worden lokaal gecachet en kunnen daarna offline worden gebruikt. Ontbrekende uitlijning, opnamedatum, afstandsgegevens of eenduidige matches geven een foutmelding. De renderer schakelt niet stilzwijgend terug naar helderheid als afstand. Zowel preview als filmrendering gebruiken dezelfde koppelingen.

### Optionele lokale interpolatie en gemeenschappelijke camera

Bij Gaia kan Studio ongekoppelde sterren laten meebewegen met de nevel, of hun beweging lokaal schatten. Interpolatie vraagt minstens vier gemeten sterren binnen 6% van de beelddiagonaal en binnen het door de gemeten sterren omsloten gebied. Sterk uiteenlopende buurafstanden worden afgewezen. De gewogen inverse-afstand wordt gebruikt als artistieke bewegingsschatting. Deze sterren worden afzonderlijk als geschat geteld. Er worden maximaal 3000 aanvullende sterfragmenten gebruikt.

Gaia-sterren volgen nu dezelfde begrensde camera en zoom als de nevel. De extra parallax komt uitsluitend uit de daadwerkelijk toegepaste cameraverplaatsing. Als een beeldrand de camerabeweging tegenhoudt, schuiven sterren op die as niet zelfstandig door.
