# AstroWeb TV

[English installation guide and APK downloads](https://rahoebe.github.io/AstroWeb/#install). The HTTPS edition asks for your server at first launch. The LAN edition connects directly to the server on a trusted private network. Build the LAN app with `gradlew.bat assembleLan` or download the signed package from the TV release.

## Nederlands

**Viewerfuncties:** bij een object staan alleen relevante opties: Sterren in 3D, Lichtreis, Mozaïek (vanaf twee overlappende opnamen) en Zonvergelijking (alleen Zon). Kalender staat in de galerij naast Hemelatlas. In het maandoverzicht kiest ←/→ een dag, ↑/↓ een maand en OK de dagweergave. Daar kiest ←/→ een opname en OK opent de foto. Terug herstelt eerst de kalender. De 3D-afstandskaart ontvouwt zich vanuit de foto; de lichtreis volgt een lichtpuls naar de Aarde. De toetsen staan per scherm in beeld. Gebruik [web v1.5.5](https://github.com/RAHoebe/AstroWeb/releases/tag/v1.5.5) en [TV 0.8.0](https://github.com/RAHoebe/AstroWeb/releases/tag/tv-v0.8.0).



Lokale, alleen-lezen proef voor Google TV. De galerij toont alle gepubliceerde objecten in de volgorde van de NAS. Ze ververst bij openen, terugkeer naar de galerij en iedere minuut zolang de galerij zichtbaar is. De viewer begint met de galerijfilm en speelt die direct af. Zonder film opent de foto. Bij meerdere opnamen wisselt **Opnamedatum** zowel de foto als de film. De app gebruikt HTTPS en heeft geen Studio-account nodig.

**Op de ingerichte Windows-pc:** dubbelklik op **Start-AstroWeb-TV.cmd**. Klik in het emulatorvenster om het toetsenbord te gebruiken. Pijltjes verplaatsen de focus, Enter kiest en Esc gaat terug. De virtuele TV-afstandsbediening is ook beschikbaar in de uitgebreide emulatorbediening.

- **Volledig scherm** toont de hele opname of film zonder knoppen. Kies bij een originele foto ↑/↓ om in stappen van 0,2× tot 10× te zoomen. OK wisselt tussen zoomen en schuiven. Bij schuiven werken alle vier de pijlen; vanuit 1× begint schuiven op 1,2×.
- **Terug** brengt de knoppen terug. Nogmaals **Terug** gaat naar dezelfde poster in de galerij. Bij een film werken de pauzeknop en de afspeel-/pauzetoets.
- **EN / NL** wisselt de taal en onthoudt de keuze.

**Verken** bij een opname heeft twee opties voor uitsluitend het geopende object: **Opnamenacht en vanavond** en **Wat zie ik?** Er verschijnt geen opnamekeuzelijst. Bij Wat zie ik? lopen de pijltjes langs de onderdelen binnen dezelfde foto.

**Kijkmodi** boven de galerij heeft alleen **Avondvoorstelling** en **Fotolijst**. Beide starten direct bij een willekeurige opname. Er zijn geen opname- of instellingenlijsten. Vergelijk opnamen is uit de TV-kijkmodi verwijderd.

| Functie | Bediening |
|---|---|
| Avondvoorstelling | Start direct een voorstelling van 5 minuten bij een willekeurige opname. ←/→ wisselt hoofdstuk en OK pauzeert. Hemel- en archiefreizen spelen mee zodra hun film lokaal klaarstaat. Terug opent Kijkmodi. |
| Fotolijst | Toon alle opnamen gedurende één uur, met een willekeurige startfoto. OK opent de huidige foto om te zoomen; Terug herstelt dezelfde dia. Terug vanuit de fotolijst opent Kijkmodi. |
| Opnamenacht en vanavond | Gebruikt altijd het geopende object. ↑/↓ wisselt datum, ←/→ gaat tien minuten terug of vooruit en OK speelt de tijd af. Terug opent Verken. |
| Wat zie ik? | Gebruikt altijd de geopende foto. ←/→ kiest een onderdeel en loopt rond binnen dezelfde opname. ↑ zoomt naar het onderdeel, ↓ toont het overzicht en OK wisselt daartussen. Houd OK vast voor een bijbehorende archiefreis wanneer beschikbaar. Terug opent Verken. |

**Nieuwe ontwikkelomgeving:** installeer JDK 17 en Android Studio met Android SDK Platform 36, Build Tools 36.0.0, Platform-Tools en Android Emulator. Maak via Device Manager een *Android TV (1080p)* met een **Google TV**-systeemimage. De Windows-starter verwacht de AVD-naam `AstroWeb_Google_TV`. Open de map `tv` als Android-project en kies Run, of voer in deze map `gradlew.bat assembleDebug` en daarna de starter uit. Na codewijzigingen installeert Android Studio de nieuwe build met Run.

**Persoonlijke hemelatlas en Nachtpanorama:** open ze bovenaan de galerij. Met ←/→ selecteer je een opname; het gouden kader en de naam volgen je keuze. ↑/↓ zoomt op de kaart. OK vliegt naar de geselecteerde opname en opent het origineel liggend op volledig scherm. In de foto zoom je met ↑/↓ tot 10×; OK wisselt naar schuiven met alle vier de pijlen. Terug herstelt het gekozen kader en de vorige kaartschaal, ook als je de vlucht onderweg afbreekt. Twee opnamen van hetzelfde object blijven afzonderlijk selecteerbaar.

**Kaarten:** open een opname en kies Skykaart, Poolkaart of (bij objecten met een positie binnen onze Melkweg) Melkweg. De kaart opent op volledig scherm. OK of de afspeel-/pauzetoets start, pauzeert en hervat de animatie. De Skykaart doorloopt de opnamenacht; de Poolkaart en Melkweg zoomen naar het object. ↑/↓ zoomt handmatig, lang OK herstelt het overzicht en Terug opent de kaartkeuze. Op de Skykaart wisselen ←/→ het tijdstip tijdens de opnamenacht.

**Reizen:** kies **Reizen**, dan **Hemelreis** of een bestemming onder **Archiefreizen**. OK start de reis op volledig scherm en pauzeert of hervat tijdens de film. Terug brengt je naar de laatstgekozen bestemming. De volgorde en beschikbaarheid volgen de geselecteerde opname op de NAS. De Cygnusmuur-bestemming bij NGC 7000 gebruikt een DSS2-opname uit de ESA/Hubble-collectie; de archiefvelden met HST-filter zijn afzonderlijke bestemmingen.

De tv draait staande foto’s en films bij weergave 90° linksom. De galerij behoudt de portretposters. Voor het klikbare D-pad: open **… → Directional pad** bij de emulator. Als ook de middelste toets niets doet, sluit deze AVD en start hem met **Start-AstroWeb-TV.cmd**. De starter schakelt hardwaretoetsenbordinvoer in en gebruikt na deze wijziging een koude start.

## English

**Viewer features:** each object exposes relevant actions only: Stars in 3D, Light journey, Mosaic (two or more overlapping captures) and Solar comparison (Sun only). Calendar sits beside Sky atlas in the gallery. In month view, left/right selects a day, up/down changes month and OK opens the day. In day view, left/right selects a capture and OK opens its photo. Back restores the calendar. The 3D distance map unfolds from the photograph; the light journey follows a pulse towards Earth. Each screen shows its controls. Use [web v1.5.5](https://github.com/RAHoebe/AstroWeb/releases/tag/v1.5.5) and [TV 0.8.0](https://github.com/RAHoebe/AstroWeb/releases/tag/tv-v0.8.0).



A read-only local Google TV prototype for the NAS gallery. Browse every published NAS object with the D-pad. The gallery refreshes on entry, on return and every minute while visible. Opening a capture plays its gallery film first, falling back to the photo when no film is available. **Full screen** fits the complete frame, Use up/down for 1–10× photo zoom in steps of 0.2× and OK to switch to four-way panning or back to zoom. Back restores the controls. Back again restores gallery focus. The language button remembers your preference.

**Explore** inside a capture offers only **Capture night and tonight** and **What am I seeing?**, both for that exact capture. It never opens a capture picker or moves to another photograph.

**Viewing modes** above the gallery offers only **Evening programme** and **Photo frame**. Both start immediately at a random capture, without a capture or settings picker. Compare captures has been removed from TV viewing modes.

| Feature | Remote controls |
|---|---|
| Evening programme | A five-minute programme starts at a random capture. Left/right skips chapters and OK pauses. Ready local sky and archive journeys are included. Back returns to Viewing modes. |
| Photo frame | Show all captures for one hour, starting at a random photograph. OK opens the current original for zooming; Back restores the same slide. Back from the slideshow returns to Viewing modes. |
| Capture night and tonight | Always uses the open object. Up/down changes date, left/right changes time by ten minutes, and OK animates the track. Back returns to Explore. |
| What am I seeing? | Always uses the open photograph. Left/right cycles its features; up zooms in, down restores the overview and OK toggles between them. Hold OK for a related archive journey when available. Back returns to Explore. |

Open this directory in Android Studio with JDK 17, SDK 36, Build Tools 36.0.0 and a 1080p Google TV AVD. Use Run to install and launch. On the configured Windows PC, **Start-AstroWeb-TV.cmd** opens the app in the **AstroWeb_Google_TV** emulator. Arrow keys, Enter and Esc simulate the remote. The APK requires network access to the AstroWeb NAS.

Choose **Journeys** and select the sky journey or an Archive journeys destination for the active capture. OK starts, pauses or resumes fullscreen playback. Back returns to the selected destination. Portrait photos and films turn counterclockwise for landscape viewing. Gallery posters retain their orientation. The Windows starter enables hardware keyboard input on this AVD so its clickable **Extended Controls → Directional pad** works after a cold boot.

**Maps:** open a capture and select the sky chart, polar chart or, where a Galactic position is available, the face-on Milky Way. OK or Play/Pause starts, pauses and resumes the animation. The sky chart follows the observation night; the polar chart and Milky Way zoom towards the target. Up/down zoom manually, holding OK restores the overview and Back returns to map selection. Left/right change observation time on the sky chart.

**Personal sky atlas and night panorama:** select a gallery header button. Left/right selects a capture by its unique ID, up/down zooms the map and OK flies to the original photo. Up/down zooms the photo up to 10× and OK switches between zoom and four-way panning. Back restores the frame and map zoom, including when cancelling a flight.

Bij het zoomen op de Poolkaart en Melkweg blijft de objectnaam in beeld. Pauzeer om alle kaartlabels op de gekozen schaal te zien. / While zooming the polar or Milky Way map, the target remains labelled. Pause to see the detailed labels at that scale.

**Rotatie / Rotation:** kies **Draai 90°** in de viewer. Op de foto in volledig scherm draait lang OK een kwartslag. Bij gewone films draaien ←/→ het beeld tijdens het afspelen. Hubble-reizen gebruiken de geregistreerde oriëntatie van het bestemmingsbeeld tijdens de hele vlucht. De NAS maakt per bestemming een aparte liggende tv-versie; de tv toont de credit rechtop. / Use **Rotate 90°** in the viewer, hold OK on fullscreen photos, or use left/right during ordinary fullscreen films. Hubble journeys have a fixed orientation determined by the destination image. With TV landscape rendering on the NAS, credits stay upright on the TV.

De volledige objectinformatie staat boven de posterrij. Onder elke poster staat de korte objectnaam. De HTTPS-editie gebruikt het eigen serveradres dat je bij de eerste start invoert. / The gallery places the full capture details above the posters and uses short object names beneath them. The HTTPS edition uses the server address you enter at first launch.

### Spraak / Voice

Gebruik de Assistent-knop voor **Open AstroWeb TV**. Zodra een film speelt ondersteunt de mediasessie **Pauzeer / Pause** en **Hervat / Resume**. Google TV bepaalt zelf welke gesproken zoekopdrachten het naar een geïnstalleerde app stuurt. In de galerij kun je altijd **Spreken / Speak** kiezen om een opdracht rechtstreeks aan AstroWeb te geven als spraakherkenning beschikbaar is. De herkenning volgt de gekozen app-taal.

| Nederlands | English |
|---|---|
| Speel M31 af | Play M31 |
| Toon de foto van de Slurfnevel | Show the photo of the Elephant’s Trunk region |
| Open de poolkaart van M31 | Open the polar chart of M31 |
| Open de Melkwegkaart van NGC 7000 | Open the Milky Way map of NGC 7000 |
| Start de hemelreis van Andromeda | Start the sky journey for Andromeda |
| Open de Hubble-bestemmingen van M31 | Open Hubble destinations for M31 |
| Open de hemelatlas | Open the sky atlas |
| Toon het nachtpanorama | Show the night panorama |
