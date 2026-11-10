import ee
ee.Initialize(project="blowdown")
AL = ee.Geometry.Rectangle([-87.35, 30.95, -86.85, 31.45])
FL = ee.Geometry.Rectangle([-87.25, 30.55, -86.95, 30.80])
BOXES = {"AL": AL, "FL": FL}
