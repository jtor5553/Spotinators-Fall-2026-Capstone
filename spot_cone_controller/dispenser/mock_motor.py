"""Mock motor. It records commands and never touches GPIO."""

import time


class MockMotor:
    def __init__(self):
        self.running = False
        self.started_at = 0.0
        self.direction = None
        self.commands = []

    def initialize(self):
        self.stop()

    def run(self, direction):
        self.direction = direction
        self.started_at = time.monotonic()
        self.running = True
        self.commands.append(direction)

    def stop(self):
        self.running = False
        self.direction = None

    def shutdown(self):
        self.stop()
