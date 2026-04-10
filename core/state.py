# core/state.py

class StateStore:
    def __init__(self):
        self.state = {}

    def get(self):
        return self.state

    def update(self, new_state):
        self.state.update(new_state)