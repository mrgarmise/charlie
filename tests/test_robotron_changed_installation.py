"""Authentic saved observations; offline geometry only, never native AF proof."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from experiments.ppal.eyes.settle import locate

FIXTURE = Path(__file__).parent/'fixtures/robotron-calibration-20261011'


def test_original_failed_observations_remain_byte_identical():
    manifest = json.loads((FIXTURE/'provenance.json').read_text())
    for row in manifest['observations']:
        assert hashlib.sha256((FIXTURE/row['file']).read_bytes()).hexdigest()==row['sha256']


def test_tilted_border_fit_survives_midpoint_alias_without_relaxing_support():
    diagnostics = {}
    frame = Image.open(FIXTURE/'exposure-ev-1.png')
    corners = locate(frame, require_uniform_border=False, diagnostics=diagnostics)
    # Approximate visible arena corners independently inspected in the saved
    # pixels; these are regression bounds, not deployment calibration.
    visible = np.array([(165,102),(1155,51),(1179,654),(194,686)])
    assert np.max(np.linalg.norm(corners-visible,axis=1)) < 12
    assert diagnostics['accepted'] > 0
    assert diagnostics['rejections']['edge_or_endpoint_support'] > 0


@pytest.mark.parametrize('ev', [0, 2, 3])
def test_unqualified_blurred_or_nonarena_frames_remain_rejected(ev):
    diagnostics = {}
    with pytest.raises(ValueError, match='No complete game border'):
        locate(Image.open(FIXTURE/f'exposure-ev-{ev}.png'),False,diagnostics=diagnostics)
    assert diagnostics['accepted']==0
