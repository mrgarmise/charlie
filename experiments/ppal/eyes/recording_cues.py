"""Small precomputed recording tones; playback never blocks frame capture."""
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import wave


class RecordingCues:
    def __init__(self, mode='auto'):
        self.mode = mode
        self.process = None
        self.directory = None
        self.player = None
        self.failed = False
        if mode == 'auto':
            self.player = next((shutil.which(p) for p in ('paplay', 'aplay') if shutil.which(p)), None)
            if self.player:
                self.directory = tempfile.TemporaryDirectory(prefix='charlie-cues-')
                patterns = {'tick': [(660, .07)], 'start': [(880, .12), (1320, .18)],
                            'halfway': [(880, .09)], 'finish': [(1320, .12), (880, .12), (660, .25)]}
                for name, tones in patterns.items():
                    samples = []
                    for frequency, duration in tones:
                        count = int(16000*duration)
                        for i in range(count):
                            envelope = min(1, i/160, (count-1-i)/160)
                            samples.append(int(6000*envelope*math.sin(2*math.pi*frequency*i/16000)))
                        samples.extend([0]*640)
                    with wave.open(str(Path(self.directory.name)/f'{name}.wav'), 'wb') as out:
                        out.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                        out.writeframes(struct.pack('<'+'h'*len(samples), *samples))
            else:
                print('Audio player unavailable; using terminal bell (may be muted by terminal settings).', flush=True)

    def play(self, name):
        if self.mode == 'off':
            return
        if self.process is not None:
            status = self.process.poll()
            if status is None:
                return  # Never stack playback processes or delay a camera frame.
            if status != 0:
                self.failed = True
                print('Audio playback failed; using terminal bell. Check Pi audio output.', flush=True)
            self.process = None
        if self.player and not self.failed:
            try:
                self.process = subprocess.Popen([self.player, str(Path(self.directory.name)/f'{name}.wav')],
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                self.failed = True
        print('\a' * (2 if name in ('start', 'finish') else 1), end='', flush=True)

    def close(self):
        # Called after recording, so the finish tone may complete before cleanup.
        if self.process is not None:
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.directory is not None:
            self.directory.cleanup()
