"""A mismatch in the stellar export must never punch holes in the nebula."""
import numpy as np
import pytest
from astroweb.render import Scene, Parameters, compose


@pytest.mark.parametrize("method", ["layered", "depth"])
@pytest.mark.parametrize("blend", ["screen", "add"])
def test_starless_background_is_independent_of_final_residual(method, blend):
    bg = np.full((192, 128, 3), .35, np.float32)
    light = np.zeros_like(bg)
    light[30:35, 50:55] = .8
    final = compose(bg, light*.3, blend)
    images = {"final": final, "starless": bg, "stars": light, "stars_laid": light}
    params = Parameters(method=method, blend=blend, zoom=1.5, resolution=720)
    scene = Scene(images, params)
    np.testing.assert_array_equal(scene.bg[0], np.rint(bg*65535).astype(np.uint16))
    # Screen or additive foreground light cannot darken a uniform nebula,
    # including when the foreground and background travel different paths.
    for phase in (0, .17, .4, .75, 1):
        assert scene.frame(phase).min() >= .35 - 2/65535
    reconstructed = compose(scene.far[0]/65535, scene.near[0]/65535, blend)
    np.testing.assert_allclose(reconstructed, light, atol=2/65535)
