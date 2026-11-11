"""Shared helper: the pipeline band mask (data/extent_band.npy, lat/lon grid) with the held-out block + 2 km and the aerial
tip + 2 km removed, smoothed for a single clean outline. Use band_outline_ll() for lon/lat axes; contour level 0.3."""
import json
import numpy as np
from scipy.ndimage import uniform_filter
from shapely.geometry import shape
from shapely import contains_xy
def held_polys():
    return [shape(f["geometry"]) for f in json.load(open("site/data/heldout.geojson"))["features"]]
def band_outline_ll(smooth=15):
    B = np.load("data/extent_band.npy"); e = np.load("data/extent_ee.npz"); bx0, by0, bx1, by1 = e["extent"]; rb = float(e["res"])
    lo = bx0 + (np.arange(B.shape[1]) + 0.5) * rb; la = by1 - (np.arange(B.shape[0]) + 0.5) * rb; LO, LA = np.meshgrid(lo, la)
    held = np.zeros(B.shape, bool)
    for g in held_polys(): held |= contains_xy(g, LO, LA)
    Bs = uniform_filter(B.astype(float), smooth); Bs[held] = 0.0      # nothing drawn inside the held-out areas
    return lo, la, Bs, held
