"""Zoom a fixed celestial target along a bounded path in screen coordinates."""
import numpy as np


class FocusZoom:
    def __init__(self, origin, target, start, end, width, height):
        self.target = np.asarray(target, dtype=float)
        self.center = (np.array([width, height], dtype=float) - 1) / 2
        delta = self.target - origin
        # Include even a target just beyond the initial raster, with a small margin.
        overflow = np.max(np.abs(delta) * start / (.96 * self.center))
        self.start = start / max(1., overflow)
        self.end = end
        self.initial_offset = delta * self.start

    def at(self, progress):
        scale = self.start * (self.end / self.start) ** progress
        # The target moves from its initial screen pixel straight to the centre.
        # Its remaining screen distance is independent of the growing zoom.
        offset = self.center + (1 - progress) * self.initial_offset - scale * self.target
        return scale, np.array([[scale, 0., offset[0]], [0., scale, offset[1]], [0., 0., 1.]])
