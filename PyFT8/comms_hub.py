import os
import json

class Config:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename) as f:
                return json.load(f)
        return {"txFreq": 2000, "rxFreq": 2000}

    def save(self):
        with open(self.filename, "w") as f:
            json.dump(self.data, f, indent=2)

class Events:
    def __init__(self):
        self.subs = {}  # dict: topic -> list of subscriber callbacks

    def subscribe(self, topic, fn):
        self.subs.setdefault(topic, []).append(fn)

    def publish(self, topic, data):
        for fn in self.subs.get(topic, []):
            fn(data)

events = Events()
config = Config()
