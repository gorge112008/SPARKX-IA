from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace

from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings
from django.utils.safestring import SafeData, mark_safe

from apps.planning.domain import MAX_SESSIONS, MAX_TASKS
from apps.planning.templatetags.planning_ui import agenda_rows, event_datetime, preparation_rows


class EventDatetimeTests(SimpleTestCase):
    def test_converts_utc_to_event_zone_across_calendar_day(self):
        result = event_datetime("2026-11-09T02:15:00Z", "America/Lima")
        self.assertEqual(result.isoformat(), "2026-11-08T21:15:00-05:00")

    def test_uses_historical_dst_rules_not_a_fixed_offset(self):
        summer = event_datetime("2026-07-09T12:00:00Z", "Europe/Madrid")
        winter = event_datetime("2026-11-09T12:00:00Z", "Europe/Madrid")
        self.assertEqual(summer.hour, 14)
        self.assertEqual(winter.hour, 13)

    def test_invalid_or_ambiguous_inputs_have_no_fabricated_time(self):
        for value, zone in [(None, "America/Lima"), ({}, "America/Lima"),
                            ("not-a-date", "America/Lima"),
                            ("2026-11-09T15:00:00", "America/Lima"),
                            ("2026-11-09T15:00:00Z", "Mars/Test"),
                            (datetime(2026, 11, 9), "America/Lima")]:
            with self.subTest(value=value, zone=zone):
                self.assertIsNone(event_datetime(value, zone))
        self.assertIsNotNone(event_datetime(datetime(2026, 11, 9, tzinfo=dt_timezone.utc), "America/Lima"))

    @override_settings(TIME_ZONE="Europe/London", USE_TZ=True, LANGUAGE_CODE="es")
    def test_template_displays_event_time_instead_of_source_or_server_zone(self):
        payload = {"summary": "", "sessions": [{"start": "2026-11-09T15:00:00Z",
                   "duration_minutes": 45, "title": "Ponencia", "speaker": "", "resource": ""}],
                   "tasks": [], "risks": []}
        html = render_to_string("events/_plan.html", {"payload": payload, "event": SimpleNamespace(timezone="America/Lima")})
        self.assertIn('datetime="2026-11-09T15:00:00Z">10:00</time>', html)
        self.assertNotIn('datetime="2026-11-09T15:00:00Z">15:00</time>', html)


class AgendaRowsTests(SimpleTestCase):
    def test_midnight_range_uses_the_event_zone_and_preserves_source_timestamp(self):
        row = agenda_rows({"sessions": [{
            "id": "s1", "title": "Cierre", "start": "2026-11-09T04:50:00Z",
            "duration_minutes": 30, "speaker": "Ponente", "resource": "Sala",
        }]}, "America/Lima")[0]
        self.assertEqual(row["start"], "2026-11-09T04:50:00Z")
        self.assertEqual(row["local_start"].isoformat(), "2026-11-08T23:50:00-05:00")
        self.assertEqual(row["local_end"].isoformat(), "2026-11-09T00:20:00-05:00")
        self.assertTrue(row["crosses_day"])

    def test_duration_is_elapsed_time_through_both_dst_transitions(self):
        for start, expected_end in [
            ("2026-03-29T00:30:00Z", "2026-03-29T03:30:00+02:00"),
            ("2026-10-25T00:30:00Z", "2026-10-25T02:30:00+01:00"),
        ]:
            with self.subTest(start=start):
                row = agenda_rows({"sessions": [{
                    "start": start, "duration_minutes": 60,
                }]}, "Europe/Madrid")[0]
                self.assertEqual(row["local_end"].isoformat(), expected_end)
                elapsed = (row["local_end"].astimezone(dt_timezone.utc)
                           - row["local_start"].astimezone(dt_timezone.utc))
                self.assertEqual(elapsed, timedelta(hours=1))
                self.assertFalse(row["crosses_day"])

    def test_invalid_candidates_have_no_invented_ranges(self):
        for start, duration, zone in [
            ("not-a-date", 30, "America/Lima"),
            ("2026-11-09T15:00:00", 30, "America/Lima"),
            ("2026-11-09T15:00:00Z", 30, "Mars/Test"),
            ("2026-11-09T15:00:00Z", True, "America/Lima"),
            ("2026-11-09T15:00:00Z", "30", "America/Lima"),
            ("2026-11-09T15:00:00Z", 0, "America/Lima"),
            ("2026-11-09T15:00:00Z", 1441, "America/Lima"),
            ("9999-12-31T23:45:00Z", 60, "UTC"),
        ]:
            with self.subTest(start=start, duration=duration, zone=zone):
                row = agenda_rows({"sessions": [{
                    "start": start, "duration_minutes": duration,
                }]}, zone)[0]
                self.assertIsNone(row["local_end"])
                self.assertFalse(row["crosses_day"])

    def test_malformed_containers_are_bounded_without_losing_valid_sessions(self):
        for payload in (None, [], "sessions", {"sessions": None}, {"sessions": "bad"}):
            with self.subTest(payload=payload):
                self.assertEqual(agenda_rows(payload, "UTC"), [])
        sessions = [{"id": str(index), "title": f"Sesión {index}"}
                    for index in range(MAX_SESSIONS)]
        rows = agenda_rows({"sessions": sessions}, "UTC")
        self.assertEqual([row["id"] for row in rows], [item["id"] for item in sessions])
        self.assertEqual(len(agenda_rows({"sessions": sessions + [{}]}, "UTC")), MAX_SESSIONS)
        rows = agenda_rows({"sessions": [None, "bad", {"title": ["bad"]}]}, "UTC")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "")


class PreparationRowsTests(SimpleTestCase):
    def test_dependencies_use_titles_and_unknown_ids_remain_visible(self):
        payload = {"tasks": [
            {"id": "room", "title": "Preparar sala", "depends_on": []},
            {"id": "rehearsal", "title": "Ensayar", "depends_on": [" room ", "unknown"]},
        ]}
        rows = preparation_rows(payload)
        self.assertEqual(rows[1]["depends_on_titles"], ["Preparar sala", "unknown"])
        self.assertEqual(rows[0]["depends_on_titles"], [])

    def test_dependency_titles_and_fallback_ids_are_escaped_by_templates(self):
        title = '<img src=x onerror="alert(1)">'
        fallback = '<script>alert(2)</script>'
        payload = {"tasks": [
            {"id": "unsafe", "title": mark_safe(title), "depends_on": []},
            {"id": "later", "title": "Revisar", "depends_on": ["unsafe", mark_safe(fallback)]},
        ]}
        for dependency in preparation_rows(payload)[1]["depends_on_titles"]:
            self.assertNotIsInstance(dependency, SafeData)
        html = Template(
            "{% load planning_ui %}{% for task in payload|preparation_rows %}"
            "{% for title in task.depends_on_titles %}{{ title }}{% endfor %}{% endfor %}"
        ).render(Context({"payload": payload}))
        self.assertIn("&lt;img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<script>", html)

    def test_helpers_do_not_change_payload_or_share_mutable_dependency_lists(self):
        payload = {
            "sessions": [{"id": "s1", "title": "Inicio", "start": "2026-11-12T00:30:00Z",
                          "duration_minutes": 45, "speaker": "Ponente", "resource": "Sala"}],
            "tasks": [{"id": "t1", "title": "Preparar", "purpose": "Comprobar audio",
                       "status": "pending", "depends_on": ["unknown"]}],
        }
        original = deepcopy(payload)
        sessions = agenda_rows(payload, "America/Lima")
        tasks = preparation_rows(payload)
        sessions[0]["title"] = "Otro título"
        tasks[0]["depends_on_titles"].append("Otra dependencia")
        self.assertEqual(payload, original)

    def test_malformed_containers_and_dependencies_do_not_break_review(self):
        for payload in (None, [], "tasks", {"tasks": None}, {"tasks": "bad"}):
            with self.subTest(payload=payload):
                self.assertEqual(preparation_rows(payload), [])
        rows = preparation_rows({"tasks": [
            None, "bad", {"title": {"bad": True}, "depends_on": "not-a-list"},
            {"title": "Revisar", "depends_on": [None, {}, "unknown"]},
        ]})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "")
        self.assertEqual(rows[0]["depends_on_titles"], [])
        self.assertEqual(rows[1]["depends_on_titles"], ["unknown"])
        tasks = [{"id": str(index), "title": f"Tarea {index}"} for index in range(MAX_TASKS)]
        self.assertEqual(len(preparation_rows({"tasks": tasks})), MAX_TASKS)
        self.assertEqual(len(preparation_rows({"tasks": tasks + [{}]})), MAX_TASKS)
