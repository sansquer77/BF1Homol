from datetime import datetime, timedelta
import unittest

from services.deadlines import evaluate_championship_deadline
from utils.datetime_utils import SAO_PAULO_TZ


class ChampionshipDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.deadline = datetime(2026, 3, 8, 10, 0, tzinfo=SAO_PAULO_TZ)

    def test_before_is_open(self):
        self.assertTrue(evaluate_championship_deadline(self.deadline, self.deadline - timedelta(microseconds=1))[0])

    def test_exactly_equal_is_closed(self):
        self.assertFalse(evaluate_championship_deadline(self.deadline, self.deadline)[0])

    def test_after_is_closed(self):
        self.assertFalse(evaluate_championship_deadline(self.deadline, self.deadline + timedelta(microseconds=1))[0])

    def test_missing_is_closed_and_alerts_admin(self):
        allowed, message, deadline = evaluate_championship_deadline(None, datetime.now(SAO_PAULO_TZ))
        self.assertFalse(allowed)
        self.assertIsNone(deadline)
        self.assertIn("administrador", message.lower())
