# plugins/signals/test_adapter.py

from core.event import Event

class TestAdapter:

    def simulate_failure(self):
        return Event(
            source="test_automation",
            event_type="test_failure",
            severity="error",
            context={
                "test_name": "test_device_boot",
                "error": "TimeoutError"
            }
        )