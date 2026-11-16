const films = [
 [
  "gaia-america",
  "Capture films",
  "Through the North America Nebula",
  "NGC 7000 · Gaia + interpolation",
  "Four automatic zoom stops visit bright gas and the dark cloud LDN 935 in the 9 November capture. Gaia distances order the stellar motion. Camera travel is amplified for visibility.",
  "Capture: Ron Hoebe. Stellar data: Gaia DR3 / ESA / AIP. Locally interpolated stellar motion is an artistic estimate."
 ],
 [
  "gaia-ic1396",
  "Capture films",
  "Depth in the Elephant’s Trunk",
  "IC 1396 · Gaia + interpolation",
  "Travel between four selected details. Measured Gaia stars and locally estimated stars respond to the camera path, with a shared stop at the image boundaries.",
  "Capture: Ron Hoebe. Stellar data: Gaia DR3 / ESA / AIP. Unmatched stellar motion is estimated only in consistent local neighbourhoods."
 ],
 [
  "gaia-m31",
  "Capture films",
  "Andromeda and its star field",
  "M31 · Gaia + interpolation",
  "A multi-stop route visits Andromeda and its neighbours. Gaia supplies distances for matched stars; the main galaxy remains in the starless background. Interpolated motion is a visual estimate.",
  "Capture: Ron Hoebe. Foreground stellar data: Gaia DR3 / ESA / AIP."
 ],
 [
  "gaia-veil",
  "Capture films",
  "Filaments of the Eastern Veil",
  "NGC 6992 · Gaia + interpolation",
  "The camera approaches the Veil’s fine filaments while matched stars move according to Gaia distance estimates. Uncertain neighbourhoods remain on the background plane.",
  "Capture: Ron Hoebe. Stellar data: Gaia DR3 / ESA / AIP."
 ],
 [
  "journey",
  "Journeys",
  "Sky journey",
  "North America Nebula",
  "Fly from the all-sky photograph through survey tiles to the measured edges of the capture. The final quarter-turn follows the shortest camera roll.",
  "Capture: Ron Hoebe. Sky: ESO/S. Brunier; optical survey: DSS2 / STScI / CDS."
 ],
 [
  "hubble",
  "Journeys",
  "Into Andromeda",
  "M31 · Hubble",
  "Dust lanes line up as the wide-field capture dissolves into the Hubble mosaic. The camera keeps the selected destination in view.",
  "Capture: Ron Hoebe. Hubble image: NASA, ESA, J. Dalcanton, B. F. Williams, L. C. Johnson, the PHAT team and R. Gendler."
 ],
 [
  "hubble-america",
  "Journeys",
  "A Hubble field in North America",
  "NGC 7000 · HST/WFPC2",
  "Start in the 12 September capture and fly into Hubble’s WFPC2 view of a dust arc around a young star. The destination lies within the measured capture footprint.",
  "Capture: Ron Hoebe. NASA, ESA, K. Stapelfeldt (JPL); processing: Gladys Kober (NASA/CUA)."
 ],
 [
  "elephants-trunk",
  "Journeys",
  "Into the Elephant’s Trunk",
  "IC 1396 · nebula detail",
  "Start in Ron Hoebe’s wide-field capture of IC 1396 and follow the dark trunk into a registered Pan-STARRS1 detail of IC 1396A.",
  "Capture: Ron Hoebe. Detail: Pan-STARRS1 Surveys (PS1) / STScI / CDS."
 ],
 [
  "parallax",
  "Capture films",
  "Stellar parallax",
  "North America Nebula",
  "The isolated star field drifts across the glowing gas. AstroWeb checks which star layer reconstructs the final image most closely.",
  "Capture: Ron Hoebe. AstroWeb layered renderer."
 ],
 [
  "relief",
  "Capture films",
  "Nebula relief",
  "Elephant’s Trunk region",
  "A softly varying depth map gives the starless nebula relief, while the separated stars follow their own motion. This depth is an artistic interpretation.",
  "Capture: Ron Hoebe. AstroWeb depth renderer."
 ],
 [
  "panzoom",
  "Capture films",
  "Pan and zoom",
  "Andromeda Galaxy",
  "The camera approaches the galactic core using the finished image. In Studio, a sequence can visit up to eight named regions.",
  "Capture: Ron Hoebe. AstroWeb pan/zoom renderer."
 ],
 [
  "sun",
  "Capture films",
  "The solar disk",
  "Sun · single image",
  "A single finished solar photograph is enough to make a film. Surface markings stay attached to the disk as the camera moves.",
  "Capture: Ron Hoebe."
 ],
 [
  "trails",
  "Capture films",
  "Star trails",
  "La Silla · single image",
  "A gentle camera move follows circular trails above the observatory. This is a film rendered from one long-exposure photograph.",
  "G. Lambert/ESO, CC BY 4.0. Adapted for pan/zoom."
 ],
 [
  "milky-photo",
  "Capture films",
  "A Milky Way landscape",
  "Paranal · single image",
  "A wide nightscape retains its horizon and original orientation. Studio can add clickable panorama markers to a landscape.",
  "ESO/G. Brammer, CC BY 4.0. Adapted for pan/zoom."
 ],
 [
  "sky",
  "Maps",
  "The observation night",
  "Sky chart · NGC 7000",
  "Watch the target and bright stars cross the local sky. The line records the object’s altitude through the night.",
  "ESA Hipparcos / CDS; Stellarium constellation lines, CC BY-SA 4.0; Astropy / ERFA."
 ],
 [
  "polar",
  "Maps",
  "From pole to footprint",
  "Polar chart · M31",
  "Zoom across the northern sky to the measured capture frame. The photograph inside keeps its celestial orientation.",
  "Capture: Ron Hoebe. ESA Hipparcos / CDS; Stellarium, CC BY-SA 4.0; HYG / Astronexus."
 ],
 [
  "epoch",
  "Maps",
  "Stars across epochs",
  "Polar chart · proper motion",
  "Follow the changing shape of the Big Dipper. The chart extrapolates catalogue velocity vectors; this is an illustrative time experiment.",
  "ESA Hipparcos / CDS; HYG / Astronexus, CC BY-SA 4.0; Stellarium constellation lines."
 ],
 [
  "milky-map",
  "Maps",
  "Our place in the disk",
  "Face-on Milky Way",
  "The Sun and the North America Nebula appear on an artist’s reconstruction of the Galactic disk. Labels remain separate from the artwork.",
  "NASA/JPL-Caltech/R. Hurt (SSC/Caltech)."
 ],
 [
  "environment",
  "Maps",
  "Andromeda’s neighbours",
  "Galaxy environment",
  "Select catalogued neighbours around M31. The outline shows which parts of the environment fall inside this capture.",
  "OpenNGC and AstroWeb catalogue; see the data credits."
 ],
 [
  "atlas",
  "Maps",
  "A personal sky atlas",
  "Collection footprints",
  "Zoom into an outlined capture on a chart of the whole collection. Individual dates retain their own measured footprint.",
  "Captures: Ron Hoebe. ESA Hipparcos / CDS; Stellarium, CC BY-SA 4.0."
 ],
 [
  "panorama",
  "Maps",
  "Across the night panorama",
  "All-sky panorama",
  "Travel across the photographic sky with the capture frames laid on top. A frame links to its own original photograph.",
  "ESO/S. Brunier, CC BY 4.0; captures: Ron Hoebe."
 ],
 [
  "other-light",
  "Maps",
  "The same field in infrared",
  "Optical / AllWISE",
  "Move the divider over Andromeda to compare the optical capture with infrared imagery registered to the same sky field.",
  "Capture: Ron Hoebe. AllWISE / NASA/JPL-Caltech / IRSA; CDS HiPS."
 ],
 [
  "tv-tour",
  "Google TV",
  "Gallery to chart",
  "Google TV · remote control",
  "Browse the poster row, open the selected film and zoom into the polar chart with the directional pad. Recorded from the English TV interface.",
  "AstroWeb TV interface; captures: Ron Hoebe. Polar chart data as credited above."
 ]
];
