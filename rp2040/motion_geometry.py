"""Convex joint-space constraints shared by calibration and normal authority."""
import math


def polygon(values):
    if not isinstance(values, (list, tuple)) or not 3 <= len(values) <= 16:
        raise ValueError('INVALID_CLEARANCE_POLYGON')
    points = []
    for pair in values:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('INVALID_CLEARANCE_POLYGON')
        if any(isinstance(v, bool) for v in pair):
            raise ValueError('INVALID_CLEARANCE_POLYGON')
        p = tuple(float(v) for v in pair)
        if any(not math.isfinite(v) or not 0 <= v <= 180 for v in p):
            raise ValueError('INVALID_CLEARANCE_POLYGON')
        points.append(p)
    # Strict convexity, CCW winding, and all vertices on the interior side of
    # every edge also reject self-intersections and repeated/collinear points.
    for i, a in enumerate(points):
        b = points[(i+1) % len(points)]
        if a == b: raise ValueError('INVALID_CLEARANCE_POLYGON')
        for j, p in enumerate(points):
            if j not in (i, (i+1) % len(points)) and cross(a, b, p) <= 1e-9:
                raise ValueError('INVALID_CLEARANCE_POLYGON')
    return points


def cross(a, b, p):
    return (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])


def contains(points, pose, margin=0):
    return all(cross(a, points[(i+1) % len(points)], pose) >=
               margin * math.sqrt(sum((v-u)**2 for u,v in zip(a, points[(i+1) % len(points)]))) - 1e-9
               for i,a in enumerate(points))
