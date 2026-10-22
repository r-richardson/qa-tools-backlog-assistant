import unittest
import os
from datetime import date
from generate_reminders import (
    get_next_weekday,
    get_previous_workday,
    evaluate_tickets,
    format_ticket_list,
    format_mention,
    build_payload,
    parse_user_mapping,
    load_slack_mapping
)

class TestReminders(unittest.TestCase):
    def test_get_next_weekday(self):
        base = date(2026, 10, 21) # Wednesday
        self.assertEqual(get_next_weekday("monday", base), date(2026, 10, 26))
        self.assertEqual(get_next_weekday("tuesday", base), date(2026, 10, 27))
        self.assertEqual(get_next_weekday("wednesday", base), date(2026, 10, 28))

    def test_get_previous_workday(self):
        monday = date(2026, 10, 26)
        self.assertEqual(get_previous_workday(monday), "Friday")

        tuesday = date(2026, 10, 27)
        self.assertEqual(get_previous_workday(tuesday), "Monday")

        friday = date(2026, 10, 23)
        self.assertEqual(get_previous_workday(friday), "Thursday")

    def test_format_mention(self):
        self.assertEqual(format_mention("alice_bob"), "@alice_bob")
        self.assertEqual(format_mention("@alice_bob"), "@alice_bob")
        self.assertEqual(format_mention("Robert Richardson"), "@Robert Richardson")
        self.assertEqual(format_mention("<@U012345678>"), "@U012345678")

        self.assertEqual(format_mention(None), "@here")
        self.assertEqual(format_mention(""), "@here")
        self.assertEqual(format_mention("here"), "@here")
        self.assertEqual(format_mention("@here"), "@here")
        self.assertEqual(format_mention("<!here>"), "@here")

    def test_empty_list_returns_checkmark(self):
        result = format_ticket_list([], mapping={})
        self.assertEqual(result, "🔸✅ No tickets right now")

    def test_format_ticket_list_with_user_id(self):
        t1 = {
            "id": 12345,
            "subject": "Sample ticket subject",
            "status": {"name": "In Progress"},
            "assigned_to": {"name": "user_alpha"}
        }
        mapping = {"user_alpha": "Alice"}
        formatted = format_ticket_list([t1], mapping)

        expected = (
            "🔸 (In Progress) Sample ticket subject - @Alice\n"
            "    🔸 https://progress.opensuse.org/issues/12345"
        )
        self.assertEqual(formatted, expected)

    def test_build_payload_includes_weekdays(self):
        target_date = date(2026, 10, 26) # Monday
        t = {
            "id": 101,
            "subject": "Test due ticket",
            "status": {"name": "Feedback"},
            "priority": {"id": 5},
            "due_date": "2026-10-24",
            "assigned_to": {"name": "user_a"}
        }
        groups = evaluate_tickets([t], [], [], target_date)
        payload = build_payload(groups, mapping={"user_a": "Alice"}, target_date=target_date)

        self.assertEqual(payload["weekday"], "Monday")
        self.assertEqual(payload["previous_workday"], "Friday")
        self.assertEqual(payload["prev_workday"], "Friday")
        self.assertEqual(payload["target_date"], "2026-10-26")
        self.assertEqual(payload["slo_high"], "🔸✅ No tickets right now")
        self.assertIn("@Alice", payload["due_date"])

if __name__ == "__main__":
    unittest.main()
