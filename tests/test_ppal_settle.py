import unittest
from PIL import Image, ImageDraw
import numpy as np
from experiments.ppal.eyes.settle import locate


class SettleTests(unittest.TestCase):
    def test_blank_screen_rejected(self):
        with self.assertRaises(ValueError):
            locate(Image.new('RGB',(1280,720),(40,40,40)))

    def test_changed_geometry_and_border_color(self):
        for points,color in [([(220,80),(1040,100),(1080,610),(180,590)],(240,190,40)),
                             ([(300,100),(990,60),(1040,590),(230,620)],(235,160,230))]:
            frame=Image.new('RGB',(1280,720),(40,40,40))
            ImageDraw.Draw(frame).line(points+[points[0]],fill=color,width=5)
            measured=locate(frame)
            self.assertLess(np.max(np.linalg.norm(measured-np.array(points),axis=1)),12)

    def test_white_thick_border_among_bright_room_edges(self):
        points = [(218,54),(838,75),(850,499),(188,493)]
        frame = Image.new('RGB', (1280,720), (50,50,50))
        draw = ImageDraw.Draw(frame)
        draw.rectangle((0,0,75,719), fill='white')
        draw.rectangle((990,0,1279,719), fill=(240,225,190))
        draw.line(points+[points[0]], fill='white', width=9)
        measured = locate(frame)
        self.assertLess(np.max(np.linalg.norm(measured-np.array(points),axis=1)),12)

    def test_incomplete_white_border_rejected(self):
        frame = Image.new('RGB', (1280,720), (50,50,50))
        ImageDraw.Draw(frame).line([(218,54),(838,75),(850,499),(188,493)],
                                   fill='white', width=9)
        with self.assertRaises(ValueError):
            locate(frame)

    def test_setup_recovers_after_one_bad_frame(self):
        from unittest.mock import Mock, patch
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from experiments.ppal.eyes.settle import prepare
        frame = Image.new('RGB', (1280,720))
        points = np.array([(218,54),(838,75),(850,499),(188,493)])
        source = Mock()
        source.read.return_value = frame
        with TemporaryDirectory() as folder, \
             patch('experiments.ppal.eyes.settle.locate', side_effect=[ValueError('flash')]+[points]*6), \
             patch('experiments.ppal.eyes.settle.time.sleep'):
            prepare(source, Path(folder))
            self.assertTrue((Path(folder)/'calibration.json').exists())

    def test_setup_never_accepts_moving_border(self):
        from unittest.mock import Mock, patch
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from experiments.ppal.eyes.settle import prepare
        points = np.array([(218,54),(838,75),(850,499),(188,493)])
        source = Mock()
        source.read.return_value = Image.new('RGB', (1280,720))
        with TemporaryDirectory() as folder, \
             patch('experiments.ppal.eyes.settle.locate', side_effect=[points,points+30]*12), \
             patch('experiments.ppal.eyes.settle.time.sleep'):
            with self.assertRaises(ValueError):
                prepare(source, Path(folder))
            self.assertFalse((Path(folder)/'calibration.json').exists())
            self.assertTrue((Path(folder)/'setup-failed.png').exists())
