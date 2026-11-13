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
| LeefRadar, lokale checkout | Python/Flask, Docker en Synology-configuratie geïnspecteerd | Zelfde soort zelfstandige service met duurzame datamap, loopback-poort en NAS-reverseproxy. De GitHub-connector gaf voor de opgegeven repository geen toegang; er zijn geen privésleutels of lokale configuratiegeheimen ingelezen. |

## Gekozen eerste renderer

Omdat starless en stars al beschikbaar zijn, is een AI-sterrenverwijderaar of een generiek monoculair AI-dieptemodel niet nodig. De eerste implementatie gebruikt NumPy/OpenCV op de CPU en FFmpeg voor H.264. Dit is voorspelbaar op een NAS en heeft geen GPU-, modeldownload- of licentieafhankelijkheid van commerciële pakketten.

1. Controleer afmetingen, inhoud en ID-prefix; bewaar de originelen ongewijzigd.
2. Vergelijk beide sterrenlagen via screen en optellen met de final. Kies de laagste MAE.
3. Maak een nevelachtergrond en twee artistieke sterrenlagen; houd verbonden sterkernen heel. Corrigeer een kleine residuafwijking ten opzichte van final.
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
