"""Offline header/slot boundary failures; synthetic bytes are never a firmware image."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('image_gate',Path(__file__).resolve().parents[1]/'check_image.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ImageGate(unittest.TestCase):
    def test_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.bin'
            for size,chip,magic,valid in [(23,9,0xe9,False),(24,9,0xe9,True),
                    (24,0,0xe9,False),(24,9,0,False),(0x330000,9,0xe9,True),
                    (0x330001,9,0xe9,False)]:
                data=bytearray(size);data[0]=magic;data[12:14]=chip.to_bytes(2,'little');path.write_bytes(data)
                if valid:self.assertEqual(module.inspect(path)['bytes'],size)
                else:
                    with self.assertRaises(ValueError):module.inspect(path)

if __name__=='__main__':unittest.main()
