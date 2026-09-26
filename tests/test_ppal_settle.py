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
