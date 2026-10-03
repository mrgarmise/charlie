import json
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
from experiments.ppal.eyes.sprites import SpriteDetector
from experiments.ppal.eyes.pipeline import VisionPipeline


class SpriteTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(Path('config/robotron/sprites-draft.json').read_text())

    def test_blank_frame_has_no_objects(self):
        self.assertEqual(SpriteDetector(self.profile).detect(Image.new('RGB', (640,480))), [])

    def test_known_example_cannot_authorize_world_state(self):
        example = next(e for e in self.profile['examples'] if e['kind'] == 'player')
        frame = Image.new('RGB', (640,480))
        frame.paste(Image.fromarray(np.array(example['rgb'],dtype=np.uint8)), (200,200))
        result = VisionPipeline(SpriteDetector(self.profile)).process(frame,0)
        self.assertTrue(any(d.kind == 'player' for d in result.detections))
        self.assertIsNone(result.world)
        self.assertIn('OBSERVATION ONLY',result.status)

    def test_conflicting_identical_examples_stay_unknown(self):
        example = next(e for e in self.profile['examples'] if e['kind'] == 'player')
        self.profile['examples'].append(dict(example,kind='human'))
        frame = Image.new('RGB', (640,480))
        frame.paste(Image.fromarray(np.array(example['rgb'],dtype=np.uint8)), (200,200))
        result = SpriteDetector(self.profile).detect(frame)
        self.assertTrue(result)
        self.assertTrue(all(d.kind == 'unknown' for d in result))
