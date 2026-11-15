# Research: cinematic astrophotography

[Nederlands](ONDERZOEK.md) · [English](RESEARCH.en.md)

Reviewed 13 November 2026. Goal: a standalone local/NAS application using existing AstroWizard exports to produce actual movie files.

| Reference / code | Availability | Application to AstroWeb |
| --- | --- | --- |
| [DeepParallax Studio](https://www.deepskycolors.com/apps/deepparallax-studio/) and [technical reference](https://www.deepskycolors.com/astro/docs/tools/DeepParallax/DeepParallax.html) | Proprietary commercial software | Separate starless/stars inputs, stellar depth, camera paths and edge fitting. Its documentation explicitly separates artistic depth from Gaia measurements. |
| [Zenith Cinematic](https://www.zenith-astro.com/cinematic) | Commercial, no reusable source verified | Visual orbit/fly-through reference. The page was not fully text-inspectable; no claims about its internals are made. |
| [Cinematic Astro](https://cinematicastro.web.app/) and [Reddit reference](https://www.reddit.com/r/SideProject/comments/1x0qpsn/i_built_a_free_tool_that_turns_deepsky/) | Retrieval blocked/unavailable | References retained without claiming inspection of their implementation. |
| [Seiza parallax](https://github.com/theatrus/seiza/tree/main/seiza-parallax), [depth-plane design](https://github.com/theatrus/seiza/blob/main/docs/design/parallax-depth-planes.md) | Apache-2.0, Rust | Strongest future renderer candidate: soft star sprites, residual starfield, light-domain screen blending, fitted camera paths, layered dust and Gaia distances through the CLI. No source copied. |
| [DepthFlow](https://github.com/BrokenSource/DepthFlow) | AGPL-3.0, GPU | Depth-map ray marching. Possible separate optional backend requiring a deliberate license/GPU choice. No source copied. |
| [Depthy](https://github.com/panrafal/depthy) | MIT, older browser project | Depth displacement and live browser parallax reference. |
| [Parallax Designer](https://github.com/robert-hoffmann/parallax-designer) | MIT | A visual multilayer editor, relevant for future manual depth layers or camera editing. |
| [Three.js](https://github.com/mrdoob/three.js) | MIT | Possible future WebGL preview; the current stored-film workflow uses a CPU renderer for portability. |
| [RaspAstroDisplay](https://github.com/RAHoebe/RaspAstroDisplay) | MIT code, separate data rights | Actual reuse of catalog data, adapted reader, star names and the fixed observation-night principle. The original dashboard/Skyfield application is not imported wholesale. |
| LeefRadar local checkout | Flask/Docker/Synology files inspected | Portable service with durable state, loopback port and NAS HTTPS reverse proxy. |

## Initial renderer decision

Already having starless and stars avoids AI star removal and generic monocular depth-model dependencies. The current renderer uses NumPy/OpenCV on the CPU with a separately installed FFmpeg H.264 encoder, without a GPU or commercial processing tool.

The pipeline validates all four inputs, preserves their bytes, compares both star exports under screen and additive blending, separates artistic near/far stars while keeping connected cores together, and applies smooth periodic camera transforms. An optional starless brightness relief provides subtle nebular deformation. Keep the starless background intact. A residual correction against the final can leave negative star-shaped imprints when layers move. Overscan and bounded controls keep empty borders outside the image. Publication occurs only after successful atomic MP4 completion.

Both examples selected `stars_laid + screen`: approximately 0.19% reconstruction MAE for HIP_106890 and 0.065% for NGC_7000 on downsampled images. This measures reconstruction, not artistic quality or scientific accuracy.

## Free object-information services

[NASA's official documentation](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf) describes the key-free `https://images-api.nasa.gov/search` API. It returns media titles, captions, dates and credits rather than canonical deep-sky catalog entries. AstroWeb checks target/alias matches, caches results and keeps external captions separate from editable descriptions.

NASA has no general Dutch translation endpoint. [LibreTranslate](https://docs.libretranslate.com/) can be self-hosted; its managed endpoint may be paid. [Argos Translate](https://github.com/argosopentech/argos-translate) is a potential offline extension. Both initial objects already have curated Dutch and English descriptions. Precise distances are not mixed across sources of different age or methodology.

## Animated Skykaart

The supplied FITS headers provide real site coordinates, RA/Dec, DATE-OBS, telescope/filter and integration time. Astropy/ERFA computes horizontal positions offline; Hipparcos supplies real stars with propagated proper motions, and Stellarium supplies constellation lines. The browser animates ten-minute sky samples, target track and altitude curve. Exact site coordinates remain server-internal by default.

This is a replay of the observation night, not the entire RaspAstroDisplay poster system: no survey cutout, JPL Moon ephemeris or weather recommendation is included. Future options include Gaia-based stellar depth, manual nebular planes, live WebGL previews and exporting Skykaart animation as a video.

## Dark stellar imprints · 15 November 2026

The former residual correction altered the starless background by the difference between final and the recomposed layers. An overbright stellar export produced negative stellar imprints, exposed when the foreground moved. This correction has been removed. Screen and additive composition remain available. Export mismatches can consequently affect the total brightness, while stellar layers only add light.

A future Gaia depth mode requires matching individual stellar image components to Gaia sources. The current alignment query fetches only position and magnitude. Its two moving stellar layers use brightness as an artistic depth cue. Distance-driven motion needs source IDs, parallax and uncertainty, proper motion and quality data, propagated to the observation epoch. Use distance estimates with uncertainty, such as Bailer-Jones, for noisy parallaxes. Unmatched or uncertain stars should stay on a shared residual plane. Indicate any amplification of camera travel used to make the effect visible.

ESA amplifies parallax and proper motion by 10,000 in the linked animation. Luri et al. discuss uncertainty and bias in converting parallax to distance. Seiza provides a relevant design using a starless background, individual stellar sprites and Gaia distances. This correction retains the supplied nebula layer. Studio now includes the separate Gaia method described below.

Sources
- [ESA · Parallax and proper motion](https://www.esa.int/esatv/Videos/2018/04/Parallax_and_proper_motion)
- [Luri et al. 2018 · Using Gaia parallaxes](https://doi.org/10.1051/0004-6361/201832964)
- [Bailer-Jones · GeDR3 distance FAQ](https://bailer-jones.www3.mpia.de/gedr3_distances/FAQ.html)
- [Seiza · Depth planes for parallax videos](https://github.com/theatrus/seiza/blob/main/docs/design/parallax-depth-planes.md)

### Available · Gaia parallax

Gaia DR3 sources brighter than G=14 are propagated to DATE-OBS using their proper motion. The mode accepts positive parallaxes with SNR >= 10 and 0 < RUWE < 1.4. Distances use the approximation 1000/parallax in parsecs, without a zero-point correction or Bayesian prior. These estimates provide a film depth distribution. The cuts do not guarantee unbiased distances.

Unambiguous image components are lifted into small, softly edged stellar crops. The remaining stellar light moves with the unchanged starless nebula. Measured distances order the motion factors, bounded relative to the median measured stellar distance. Camera travel and scaling are artistic. Studio reports the match count and distance range. The nebula is not assigned an invented measured distance.

The catalogue is cached locally for subsequent offline rendering. Missing registration, date, catalogue data or unambiguous matches produce an actionable error. Preview and movie rendering use the same preparation.

### Optional local interpolation and shared camera

Gaia can leave unmatched stars with the nebula or estimate their motion locally. Estimates require at least four measured neighbours within 6% of the image diagonal and inside the measured stars' convex hull. Neighbourhoods with strongly conflicting distances are rejected. Weighted inverse distance supplies an artistic motion estimate. Estimated sprites are counted separately, with a maximum of 3000 additional sprites.

Gaia stars now share the nebula's constrained camera and zoom. Additional parallax uses only camera travel actually applied after image-boundary constraints. Stars cannot continue independently along an axis whose camera travel has been stopped by the image boundary.

Gaia parallax also responds to actual camera travel between zoom targets. A smoothly bounded displacement based on the applied camera centres preserves a visible effect with a small orbit setting. Parallax depth controls the artistic amplitude. A stationary constrained camera produces stationary relative stellar offsets.
