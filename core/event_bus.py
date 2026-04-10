# core/event_bus.py

from queue import Queue

class EventBus:
    def __init__(self):
        self.queue = Queue()

    def publish(self, event):
        self.queue.put(event)

    def consume(self):
        if not self.queue.empty():
            return self.queue.get()
        return None