from django.test import SimpleTestCase
from apps.events.dispatcher import dispatch, subscribe, _handlers
from apps.events.events import BookingCreated


class EventDispatcherTests(SimpleTestCase):

    def setUp(self):
        self._original = {k: v.copy() for k, v in _handlers.items()}
        _handlers.clear()

    def tearDown(self):
        _handlers.clear()
        _handlers.update(self._original)

    def _event(self):
        return BookingCreated(
            booking_id=1,
            customer_id=10,
            service_name="Haircut",
        )

    def test_single_handler(self):
        received = []
        subscribe(BookingCreated, received.append)
        event = self._event()
        dispatch(event)
        self.assertEqual(received, [event])

    def test_multiple_handlers_ordered(self):
        received = []
        subscribe(BookingCreated, lambda e: received.append("first"))
        subscribe(BookingCreated, lambda e: received.append("second"))
        dispatch(self._event())
        self.assertEqual(received, ["first", "second"])

    def test_duplicate_handler_ignored(self):
        received = []
        subscribe(BookingCreated, received.append)
        subscribe(BookingCreated, received.append)
        dispatch(self._event())
        self.assertEqual(len(received), 1)

    def test_handler_failure_isolated_and_logged(self):
        received = []

        def failing(event):
            raise RuntimeError("Simulated handler failure")

        subscribe(BookingCreated, failing)
        subscribe(BookingCreated, received.append)

        event = self._event()
        with self.assertLogs("apps.events.dispatcher", level="ERROR"):
            dispatch(event)

        self.assertEqual(received, [event])

    def test_unregistered_event_noop(self):
        class UnregisteredEvent:
            pass

        # Should not raise — no handlers registered for this type.
        dispatch(UnregisteredEvent())