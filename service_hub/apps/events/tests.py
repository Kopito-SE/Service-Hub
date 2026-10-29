from django.test import SimpleTestCase
from apps.events.dispatcher import dispatch, subscribe

class ExampleEvent:
    pass

class AnotherExampleEvent:
    pass

class EventDispatcherTests(SimpleTestCase):

    def setUp(self):
        # Use unique event classes in each test to avoid
        # depending on handlers registered by other tests.
        self.event_type = type("TestEvent", (), {})
        self.event = self.event_type()

    def test_dispatch_calls_registered_handler(self):
        received_events = []

        def handler(event):
            received_events.append(event)

        subscribe(self.event_type, handler)
        dispatch(self.event)

        self.assertEqual(received_events, [self.event])

    def test_dispatch_calls_multiple_handlers(self):
        received = []

        def first_handler(event):
            received.append("first")

        def second_handler(event):
            received.append("second")

        subscribe(self.event_type, first_handler)
        subscribe(self.event_type, second_handler)

        dispatch(self.event)

        self.assertEqual(received, ["first", "second"])
    def test_one_handler_failure_does_not_stop_other_handlers(self):
        received = []

        def failing_handler(event):
            raise RuntimeError("Simulated handler failure")

        def successful_handler(event):
            received.append(event)

        subscribe(self.event_type, failing_handler)
        subscribe(self.event_type, successful_handler)

        with self.assertLogs(
            "apps.events.dispatcher",
            level="ERROR",
        ):

            dispatch(self.event)

        self.assertEqual(received, [self.event])

    def test_unregistered_event_does_nothing(self):
        dispatch(AnotherExampleEvent())


