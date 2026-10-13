"""Deterministic viewpoint world. Simulation cannot authorize physical use."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from .active_vision import ActiveVision
from .camera_lease import CameraLease

class SimulatedHead:
    connected = True
    def __init__(self, pose=(90,90)):
        self.pose = pose
        self.moves = []
        self.stops = 0
    def look(self, pan, tilt, *, rate=None):
        self.pose = (pan,tilt)
        self.moves.append(self.pose)
        return self.connected
    def stop(self):
        self.stops += 1
        return self.connected


class SimulatedCamera:
    def __init__(self, controller, lease_dir=None, *, optimum=(108,96)):
        self.optimum = optimum
        self.controller = controller
        self.focus = 1.
        self.closed = False
        self.reads = 0
        self.lease = CameraLease(directory=lease_dir) if lease_dir else None
    def lens_position(self):return self.focus
    def set_manual_focus(self, p):self.focus = p
    def read(self):
        self.reads += 1
        pan,tilt = self.controller.pose
        # Physical angle changes perspective and centering. Correct pose is
        # known only to the simulated world, never to optimizer configuration.
        skew = (pan-self.optimum[0])*1.4
        cy = 180+(tilt-self.optimum[1])*2
        points = [(85+skew, cy-105), (390-skew, cy-105),
                  (390+skew, cy+105), (85-skew, cy+105)]
        image = Image.new('RGB',(480,360),'black')
        draw = ImageDraw.Draw(image)
        draw.polygon(points, fill=(45,45,45), outline='white', width=4)
        for x in range(130,350,12):
            for y in range(110,255,12):
                draw.rectangle((x,y,x+5,y+5),fill='white')
        return image.filter(ImageFilter.GaussianBlur(abs(self.focus-1.5)*.5))
    read_fresh = read
    def close(self):
        self.closed = True
        if self.lease:self.lease.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    head = SimulatedHead()
    camera = SimulatedCamera(head)
    optimizer = ActiveVision(lambda:camera, head, args.output,
        initial_pose=head.pose, simulated=True, wait=lambda _:None)
    result = optimizer.run()
    qualities = [e['quality'] for e in optimizer.events if e['decision']=='observe target']
    summary = dict(schema='charlie-active-vision-simulation-v1', simulated=True,
        initial_quality=qualities[0], final_quality=qualities[-1],
        improvement=qualities[-1]-qualities[0], final_pose=result['pose'],
        final_focus=result['focus']['lens_position'], movements=len(head.moves),
        optimization_samples=camera.reads, camera_released=camera.closed,
        state=result['state'], background_optimization_workers=0)
    (args.output/'simulation-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
