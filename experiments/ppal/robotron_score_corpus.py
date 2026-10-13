"""Known real-camera Robotron score observations.

These labels came from Charlie's actual 1280x720 camera frames, not ideal arcade
art. They document regression targets and digit coverage. Raw frames remain run
artifacts rather than source-code fixtures; inspect_robotron_score can replay
them when present.

Digit 7 is intentionally absent from observed coverage. The visual reader may
infer 7 from geometry at reduced confidence until a genuine example is captured.
"""

KNOWN_SCORES = {
    "raw_004.jpg": 8400,
    "raw_005.jpg": 8400,
    "raw_051.jpg": 9500,
    "raw_059.jpg": 12800,
    "raw_080.jpg": 13600,
    "raw_108.jpg": 15250,
    "raw_109.jpg": 18250,
    "raw_110.jpg": 18250,
    "raw_111.jpg": 18250,
    "raw_112.jpg": 18250,
    "raw_113.jpg": 18250,
    "raw_114.jpg": 18250,
    "raw_115.jpg": 18250,
    "raw_116.jpg": 18250,
}

OBSERVED_DIGITS = frozenset("012345689")
UNOBSERVED_DIGITS = frozenset("7")


def covered_digits() -> frozenset[str]:
    return frozenset(ch for score in KNOWN_SCORES.values() for ch in str(score))
