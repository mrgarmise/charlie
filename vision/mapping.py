def pixel_to_angle(x, y, width=1280, height=720):
    """
    Convert camera pixel coordinates to conservative
    pan/tilt servo angles.
    """

    pan = 60 + (x / (width - 1) * 60)
    tilt = 70 + (y / (height - 1) * 40)

    pan = round(pan)
    tilt = round(tilt)

    return pan, tilt