"""Fixed educational comparison of RGB, CIELAB and Oklab distances.

CIEDE2000: Sharma, Wu, Dalal (2005), doi:10.1002/col.20070.
Oklab: https://bottosson.github.io/posts/oklab/ (2021 matrices).
No external input, observer data, or production integration.
"""
from __future__ import annotations

import argparse
import json
import math

from .perceptual_color_study import PAIRS, _lab, _linear


def oklab(rgb):
    """Convert a fixed 8-bit sRGB triplet to D65 Oklab."""
    r, g, b = (_linear(c) for c in rgb)
    l = math.cbrt(0.4122214708*r + 0.5363325363*g + 0.0514459929*b)
    m = math.cbrt(0.2119034982*r + 0.6806995451*g + 0.1073969566*b)
    s = math.cbrt(0.0883024619*r + 0.2817188376*g + 0.6299787005*b)
    return (
        0.2104542553*l + 0.7936177850*m - 0.0040720468*s,
        1.9779984951*l - 2.4285922050*m + 0.4505937099*s,
        0.0259040371*l + 0.7827717662*m - 0.8086757660*s,
    )


def delta_e_2000(first, second):
    """CIEDE2000 with unit parametric factors, finite ordinary Lab inputs."""
    l1, a1, b1 = first
    l2, a2, b2 = second
    if not all(math.isfinite(x) for x in (*first, *second)):
        raise ValueError("Lab coordinates must be finite")
    cmean = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(cmean**7 / (cmean**7 + 25**7)))
    a1, a2 = (1 + g)*a1, (1 + g)*a2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    h1 = math.degrees(math.atan2(b1, a1)) % 360 if c1 else 0.0
    h2 = math.degrees(math.atan2(b2, a2)) % 360 if c2 else 0.0
    dh = h2 - h1
    # Stabilize exact antipodal cases against roundoff in atan2.
    if math.isclose(abs(dh), 180, rel_tol=0, abs_tol=1e-12):
        dh = math.copysign(180, dh)
    if not c1 or not c2:
        dh = 0.0
        hm = h1 + h2
    elif abs(dh) <= 180:
        hm = (h1 + h2) / 2
    else:
        hm = (h1 + h2 + (360 if h1 + h2 < 360 else -360)) / 2
        dh += -360 if dh > 180 else 360
    dl, dc = l2-l1, c2-c1
    d_h = 2 * math.sqrt(c1*c2) * math.sin(math.radians(dh/2))
    lm, cm = (l1+l2)/2, (c1+c2)/2
    def cos(deg):
        return math.cos(math.radians(deg))
    t = (1 - 0.17*cos(hm-30) + 0.24*cos(2*hm)
         + 0.32*cos(3*hm+6) - 0.20*cos(4*hm-63))
    sl = 1 + 0.015*(lm-50)**2 / math.sqrt(20+(lm-50)**2)
    sc = 1 + 0.045*cm
    sh = 1 + 0.015*cm*t
    theta = 30 * math.exp(-((hm-275)/25)**2)
    rc = 2 * math.sqrt(cm**7 / (cm**7 + 25**7))
    rt = -rc * math.sin(math.radians(2*theta))
    x, y, z = dl/sl, dc/sc, d_h/sh
    return math.sqrt(x*x + y*y + z*z + rt*y*z)


def advanced_color_study():
    observations = []
    for name, first, second in PAIRS:
        lab1, lab2 = _lab(first), _lab(second)
        ok1, ok2 = oklab(first), oklab(second)
        observations.append({
            "example": name,
            "first_srgb8": list(first),
            "second_srgb8": list(second),
            "first_lab_d65": list(lab1),
            "second_lab_d65": list(lab2),
            "first_oklab": list(ok1),
            "second_oklab": list(ok2),
            "encoded_rgb_distance": math.dist(first, second),
            "delta_e_76": math.dist(lab1, lab2),
            "delta_e_2000": delta_e_2000(lab1, lab2),
            "oklab_distance": math.dist(ok1, ok2),
        })
    keys = ("encoded_rgb_distance", "delta_e_76", "delta_e_2000", "oklab_distance")
    return {
        "schema": "klone.advanced_color_study.v1",
        "observations": observations,
        "descending_order_by_model": {
            key: [r["example"] for r in sorted(observations,
                  key=lambda r: (-r[key], r["example"]))]
            for key in keys
        },
        "limitations": [
            "Five synthetic pairs inherited from V10.4; no external images.",
            "CIELAB D65 with unit CIEDE2000 parametric factors.",
            "Distances have distinct scales; do not subtract or pool across models.",
            "Ordering is descriptive, with name-based tie breaking, not observer validation.",
            "No display calibration, artistic score, consciousness or production claim.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(advanced_color_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
