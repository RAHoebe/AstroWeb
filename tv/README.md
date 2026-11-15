# AstroWeb TV

## Nederlands

Lokale, alleen-lezen proef voor Google TV. De galerij toont alle gepubliceerde objecten in de volgorde van de NAS. Ze ververst bij openen, terugkeer naar de galerij en iedere minuut zolang de galerij zichtbaar is. De viewer begint met de galerijfilm en speelt die direct af. Zonder film opent de foto. Bij meerdere opnamen wisselt **Opnamedatum** zowel de foto als de film. De app gebruikt HTTPS en heeft geen Studio-account nodig.

**Op de ingerichte Windows-pc:** dubbelklik op **Start-AstroWeb-TV.cmd**. Klik in het emulatorvenster om het toetsenbord te gebruiken. Pijltjes verplaatsen de focus, Enter kiest en Esc gaat terug. De virtuele TV-afstandsbediening is ook beschikbaar in de uitgebreide emulatorbediening.

- **Volledig scherm** toont de hele opname of film zonder knoppen. **Vul scherm** vult het scherm met een uitsnede. Bij een foto verschuif je die uitsnede met de pijltjes.
- **OK** of **Terug** brengt de knoppen terug. Nogmaals **Terug** gaat naar dezelfde poster in de galerij. Bij een film werken de pauzeknop en de afspeel-/pauzetoets.
- **EN / NL** wisselt de taal en onthoudt de keuze.

**Nieuwe ontwikkelomgeving:** installeer JDK 17 en Android Studio met Android SDK Platform 36, Build Tools 36.0.0, Platform-Tools en Android Emulator. Maak via Device Manager een *Android TV (1080p)* met een **Google TV**-systeemimage. De Windows-starter verwacht de AVD-naam `AstroWeb_Google_TV`. Open de map `tv` als Android-project en kies Run, of voer in deze map `gradlew.bat assembleDebug` en daarna de starter uit. Na codewijzigingen installeert Android Studio de nieuwe build met Run.

**Persoonlijke hemelatlas en Nachtpanorama:** open ze bovenaan de galerij. Met ←/→ selecteer je een opname; het gouden kader en de naam volgen je keuze. ↑/↓ zoomt op de kaart. OK vliegt naar de geselecteerde opname en opent het origineel liggend op volledig scherm. In de foto zoom je met ↑/↓ tot 10×; OK toont weer de hele foto. Terug herstelt het gekozen kader en de vorige kaartschaal, ook als je de vlucht onderweg afbreekt. Twee opnamen van hetzelfde object blijven afzonderlijk selecteerbaar.

**Kaarten:** open een opname en kies Skykaart, Poolkaart of (bij objecten met een positie binnen onze Melkweg) Melkweg. De kaart opent op volledig scherm. OK of de afspeel-/pauzetoets start, pauzeert en hervat de animatie. De Skykaart doorloopt de opnamenacht; de Poolkaart en Melkweg zoomen naar het object. ↑/↓ zoomt handmatig, lang OK herstelt het overzicht en Terug opent de kaartkeuze. Op de Skykaart wisselen ←/→ het tijdstip tijdens de opnamenacht.

**Reizen:** kies **Reizen**, dan **Hemelreis** of een bestemming onder **Hubble**. OK start de reis op volledig scherm en pauzeert of hervat tijdens de film. Terug brengt je naar de laatstgekozen bestemming. De volgorde en beschikbaarheid volgen de geselecteerde opname op de NAS. De Cygnusmuur-bestemming bij NGC 7000 gebruikt een DSS2-opname uit de ESA/Hubble-collectie; de archiefvelden met HST-filter zijn afzonderlijke bestemmingen.

De tv draait staande foto’s en films bij weergave 90° linksom. De galerij behoudt de portretposters. Voor het klikbare D-pad: open **… → Directional pad** bij de emulator. Als ook de middelste toets niets doet, sluit deze AVD en start hem met **Start-AstroWeb-TV.cmd**. De starter schakelt hardwaretoetsenbordinvoer in en gebruikt na deze wijziging een koude start.

## English

A read-only local Google TV prototype for the NAS gallery. Browse every published NAS object with the D-pad. The gallery refreshes on entry, on return and every minute while visible. Opening a capture plays its gallery film first, falling back to the photo when no film is available. **Full screen** fits the complete frame, **Fill screen** crops to fill and allows panning a photo. OK or Back restores the controls. Back again restores gallery focus. The language button remembers your preference.

Open this directory in Android Studio with JDK 17, SDK 36, Build Tools 36.0.0 and a 1080p Google TV AVD. Use Run to install and launch. On the configured Windows PC, **Start-AstroWeb-TV.cmd** opens the app in the **AstroWeb_Google_TV** emulator. Arrow keys, Enter and Esc simulate the remote. The APK requires network access to the AstroWeb NAS.

Choose **Journeys** and select the sky journey or a Hubble destination for the active capture. OK starts, pauses or resumes fullscreen playback. Back returns to the selected destination. Portrait photos and films turn counterclockwise for landscape viewing. Gallery posters retain their orientation. The Windows starter enables hardware keyboard input on this AVD so its clickable **Extended Controls → Directional pad** works after a cold boot.

**Maps:** open a capture and select the sky chart, polar chart or, where a Galactic position is available, the face-on Milky Way. OK or Play/Pause starts, pauses and resumes the animation. The sky chart follows the observation night; the polar chart and Milky Way zoom towards the target. Up/down zoom manually, holding OK restores the overview and Back returns to map selection. Left/right change observation time on the sky chart.

**Personal sky atlas and night panorama:** select a gallery header button. Left/right selects a capture by its unique ID, up/down zooms the map and OK flies to the original photo. Up/down zooms the photo up to 10× and OK fits it again. Back restores the frame and map zoom, including when cancelling a flight.
