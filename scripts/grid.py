"""Common 10 m analysis grid for the pipeline: EPSG:32616, pixel edges on the 10 m lattice (centres at ...5),
covering the study box lon -87.60..-86.60, lat 30.40..31.80."""
import numpy as np
EPSG = 32616
RES = 10.0
X0, X1 = 442360.0, 538430.0          # left / right pixel edges
Y0, Y1 = 3363100.0, 3518430.0        # bottom / top pixel edges
W = int(round((X1 - X0) / RES)); H = int(round((Y1 - Y0) / RES))
XC = X0 + RES / 2 + RES * np.arange(W)          # column centres
YC = Y1 - RES / 2 - RES * np.arange(H)          # row centres (north-up)
