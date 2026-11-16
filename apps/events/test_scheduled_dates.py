"""Multi-day events remain one event, visible on each selected calendar day."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, SimpleTestCase
from unittest.mock import patch

from .calendar import build_calendar_context
from .catalog import filter_entries, parse_filters, project_event
from .forms import EventForm
from .schedule_dates import normalize_scheduled_dates
from .services import create_event
from apps.planning.event_rules import validate_event_plan
from apps.planning.tests import valid_plan


class DateIntegrityTests(SimpleTestCase):
    def test_calendar_validation_and_year_boundaries(self):
        self.assertEqual(normalize_scheduled_dates(["2040-02-29", "2040-02-29"], reference_year=2026), ["2040-02-29"])
        for dates in (["2026-02-29"], ["2026-09-31"], ["2021-01-01"], ["2100-01-01"], ["203-01-01"], "2026-01-01", [1]):
            with self.subTest(dates=dates), self.assertRaises(ValueError):
                normalize_scheduled_dates(dates, reference_year=2026)


class MultipleEventDaysTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="dates-owner")
        self.days = ["2026-09-10", "2026-10-25", "2026-10-26"]

    def make_event(self, **extra):
        return create_event(actor=self.owner, title="Tesis UNAC", brief="Demostración ficticia de tres fechas",
                            scheduled_dates=self.days, **extra)

    def test_each_day_is_projected_and_filtered_without_duplicate_event(self):
        event = self.make_event()
        projection = project_event(event)
        result = build_calendar_context(entries=[projection], params={"month": "2026-10", "day": "2026-10-25"}, today=date(2026, 11, 15))
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["scheduled_count"], 1)
        self.assertEqual(len(result["day_events"]), 1)
        marked = [cell["iso"] for week in result["weeks"] for cell in week if cell["events"]]
        self.assertEqual(marked, ["2026-10-25", "2026-10-26"])
        filtered = filter_entries([projection], parse_filters({"from": "2026-10-26", "to": "2026-10-26"}))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(result["undated_count"], 0)

    def test_start_must_match_first_selected_day(self):
        with self.assertRaises(ValidationError):
            self.make_event(starts_at=datetime(2026, 10, 25, 19, 30, tzinfo=ZoneInfo("America/Lima")))
        event = self.make_event(starts_at=datetime(2026, 9, 10, 19, 30, tzinfo=ZoneInfo("America/Lima")))
        self.assertEqual(event.scheduled_dates_display, [date.fromisoformat(value) for value in self.days])

    def test_manual_form_dates_remain_editable_and_historical_data_is_preserved(self):
        data = {"title": "Tesis", "brief": "Datos públicos ficticios", "timezone": "America/Lima", "capacity": "50",
                "scheduled_dates": "10/09/2026, 25/10/2026, 26/10/2026"}
        with patch("apps.events.forms.django_timezone.localdate", return_value=date(2026, 11, 15)):
            form = EventForm(data, actor=self.owner)
            self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["scheduled_dates"], self.days)
        event = self.make_event()
        with patch("apps.events.forms.django_timezone.localdate", return_value=date(2027, 1, 1)):
            current = EventForm(data, instance=event, actor=self.owner)
            self.assertTrue(current.is_valid(), current.errors)
            new = EventForm(data, actor=self.owner)
            self.assertFalse(new.is_valid())
            self.assertIn("scheduled_dates", new.errors)

    def test_agenda_accepts_selected_days_and_enforces_total_duration(self):
        event = self.make_event()
        event.interview_answers = {"duration_minutes": {"status": "confirmed", "value": "180"}}
        payload = valid_plan()
        base = dict(payload["sessions"][0])
        payload["sessions"] = [
            {**base, "id": "day-1", "start": "2026-09-10T19:30:00-05:00", "duration_minutes": 60},
            {**base, "id": "day-2", "start": "2026-10-25T19:30:00-05:00", "duration_minutes": 60},
            {**base, "id": "day-3", "start": "2026-10-26T19:30:00-05:00", "duration_minutes": 60},
        ]
        self.assertEqual(validate_event_plan(event, payload), [])
        event.interview_answers["duration_minutes"]["value"] = "90"
        self.assertTrue(any("jornadas" in error for error in validate_event_plan(event, payload)))
        payload["sessions"][1]["start"] = "2026-10-24T19:30:00-05:00"
        self.assertTrue(any("no seleccionaste" in error for error in validate_event_plan(event, payload)))
