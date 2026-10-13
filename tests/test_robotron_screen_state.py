import numpy as np
from PIL import Image, ImageDraw

from experiments.ppal.robotron_screen_state import classify_screen_state


def _border_image(colors):
    image = Image.new("RGB", (640, 480), "black")
    draw = ImageDraw.Draw(image)
    width = 12
    if len(colors) == 1:
        draw.rectangle((2, 2, 637, 477), outline=colors[0], width=width)
        return image
    # Colored perimeter segments approximate Robotron's striped attract border.
    segments = 8
    for i in range(segments):
        c = colors[i % len(colors)]
        x0 = 2 + i * 636 // segments
        x1 = 2 + (i + 1) * 636 // segments
        draw.line((x0, 6, x1, 6), fill=c, width=width)
        draw.line((x0, 473, x1, 473), fill=c, width=width)
        y0 = 2 + i * 476 // segments
        y1 = 2 + (i + 1) * 476 // segments
        draw.line((6, y0, 6, y1), fill=c, width=width)
        draw.line((633, y0, 633, y1), fill=c, width=width)
    return image


def test_uniform_border_is_gameplay():
    image=_border_image([(255, 0, 255)])
    draw=ImageDraw.Draw(image)
    draw.rectangle((100,100,110,115),fill='white');draw.rectangle((300,300,310,315),fill='white')
    result = classify_screen_state(image)
    assert result["state"] == "gameplay"


def test_multicolor_striped_border_is_not_gameplay():
    result = classify_screen_state(
        _border_image([(255, 0, 0), (255, 255, 0), (0, 255, 0),
                       (0, 255, 255), (0, 0, 255), (255, 0, 255)]))
    assert result["state"] == "not_gameplay"


def test_missing_border_is_unknown_not_terminal():
    result = classify_screen_state(Image.new("RGB", (640, 480), "black"))
    assert result["state"] == "unknown"
