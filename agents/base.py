from abc import ABC, abstractmethod

class BaseAgent(ABC):

    @abstractmethod
    def should_process(self, event, state):
        pass

    @abstractmethod
    def process(self, event, state):
        pass