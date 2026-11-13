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
| LeefRadar local checkout | Flask/Docker/Synology files inspected | Portable service with durable state, loopback port and NAS HTTPS reverse proxy. The connector could not access the supplied GitHub repository; no local secret configuration was read. |

## Initial renderer decision

Already having starless and stars avoids AI star removal and generic monocular depth-model dependencies. The current renderer uses NumPy/OpenCV on the CPU with a separately installed FFmpeg H.264 encoder, without a GPU or commercial processing tool.

The pipeline validates all four inputs, preserves their bytes, compares both star exports under screen and additive blending, separates artistic near/far stars while keeping connected cores together, and applies smooth periodic camera transforms. An optional starless brightness relief provides subtle nebular deformation. Residual correction anchors the neutral composite to the final. Overscan and bounded controls keep empty borders outside the image. Publication occurs only after successful atomic MP4 completion.

Both examples selected `stars_laid + screen`: approximately 0.19% reconstruction MAE for HIP_106890 and 0.065% for NGC_7000 on downsampled images. This measures reconstruction, not artistic quality or scientific accuracy.

## Free object-information services

[NASA's official documentation](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf) describes the key-free `https://images-api.nasa.gov/search` API. It returns media titles, captions, dates and credits rather than canonical deep-sky catalog entries. AstroWeb checks target/alias matches, caches results and keeps external captions separate from editable descriptions.

NASA has no general Dutch translation endpoint. [LibreTranslate](https://docs.libretranslate.com/) can be self-hosted; its managed endpoint may be paid. [Argos Translate](https://github.com/argosopentech/argos-translate) is a potential offline extension. Both initial objects already have curated Dutch and English descriptions. Precise distances are not mixed across sources of different age or methodology.

## Animated Skykaart

The supplied FITS headers provide real site coordinates, RA/Dec, DATE-OBS, telescope/filter and integration time. Astropy/ERFA computes horizontal positions offline; Hipparcos supplies real stars with propagated proper motions, and Stellarium supplies constellation lines. The browser animates ten-minute sky samples, target track and altitude curve. Exact site coordinates remain server-internal by default.

This is a replay of the observation night, not the entire RaspAstroDisplay poster system: no survey cutout, JPL Moon ephemeris or weather recommendation is included. Future options include Gaia-based stellar depth, manual nebular planes, live WebGL previews and exporting Skykaart animation as a video.
