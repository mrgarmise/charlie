"""Retain completed player steps even if report finalization is interrupted."""
import json


class DurableRows(list):
    def __init__(self, path):
        super().__init__()
        self.path = path

    def append(self, row):
        with self.path.open('a') as stream:
            stream.write(json.dumps(row)+'\n')
        super().append(row)
