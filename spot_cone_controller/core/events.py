"""In-memory event list for the operator screen, plus the rotating file log."""

from collections import deque
from datetime import datetime


class EventLog:
    def __init__(self, logger, limit=200):
        self.logger = logger
        self.records = deque(maxlen=limit)

    def add(self, message):
        now = datetime.now()
        self.records.append({"time": now.strftime("%H:%M:%S"), "message": message})
        if self.logger is not None:
            self.logger.info(message)

    def recent(self, count=40):
        items = list(self.records)[-count:]
        return list(reversed(items))
