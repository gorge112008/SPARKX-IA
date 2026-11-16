"""Calendar date boundaries, approved agenda projection and owner isolation."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan

from apps.events.calendar import build_calendar_context
from apps.events.models import Event


def projected_event(*, starts_at=None, zone="America/Lima", sessions=None, title="Evento propio"):
    identifier = uuid4()
    plan = SimpleNamespace(event_id=identifier, version=2, payload={"sessions": sessions}) if sessions is not None else None
    return SimpleNamespace(
        pk=identifier, title=title, starts_at=starts_at, timezone=zone,
        active_plan_id=uuid4() if plan else None, active_plan=plan,
    )


def session(*, start="2026-11-12T19:30:00-05:00", duration=90, title="Agenda aprobada"):
    return {"id": "s1", "title": title, "start": start, "duration_minutes": duration, "speaker": "Ponente", "resource": "Sala"}


class CalendarProjectionTests(SimpleTestCase):
    def build(self, events=(), **params):
        return build_calendar_context(events=events, params=params, today=date(2026, 11, 8))

    def test_default_selection_is_local_today(self):
        result = self.build()
        self.assertEqual(result["month_key"], "2026-11")
        self.assertEqual(result["selected_day"], date(2026, 11, 8))
        self.assertEqual(result["selected_day_label"], "Domingo, 8 de noviembre de 2026")

    def test_month_only_selects_first_day_and_day_only_selects_its_month(self):
        result = self.build(month="2028-02")
        self.assertEqual(result["selected_day"], date(2028, 2, 1))
        result = self.build(day="2028-02-29")
        self.assertEqual(result["month_key"], "2028-02")
        self.assertEqual(result["selected_day"], date(2028, 2, 29))

    def test_calendar_is_monday_first_and_uses_complete_weeks(self):
        for month, week_count in (("2021-02", 4), ("2026-11", 6), ("2026-12", 5)):
            with self.subTest(month=month):
                weeks = self.build(month=month)["weeks"]
                self.assertEqual(len(weeks), week_count)
                self.assertTrue(all(len(week) == 7 for week in weeks))
                self.assertTrue(all(week[0]["date"].weekday() == 0 for week in weeks))
                self.assertTrue(all(week[-1]["date"].weekday() == 6 for week in weeks))

    def test_invalid_and_contradictory_inputs_are_rejected(self):
        for params in (
            {"month": "2026-13"}, {"month": "2026-1"}, {"month": ""},
            {"month": "1899-12"}, {"month": "2101-01"}, {"month": "0000-01"},
            {"day": "2026-02-29"}, {"day": "2026-11-31"}, {"day": "2026-11-8"},
            {"day": "9999-01-01"}, {"day": ""},
            {"month": "2026-11", "day": "2026-12-01"},
        ):
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.build(**params)

    def test_year_boundaries_disable_navigation_and_out_of_range_cells(self):
        lower = self.build(month="1900-01")
        self.assertIsNone(lower["previous_url"])
        self.assertIsNotNone(lower["next_url"])
        upper = self.build(month="2100-12")
        self.assertIsNone(upper["next_url"])
        self.assertIsNotNone(upper["previous_url"])
        outside = [cell for week in upper["weeks"] for cell in week if cell["date"].year == 2101]
        self.assertTrue(outside)
        self.assertTrue(all(cell["url"] is None for cell in outside))

    def test_adjacent_days_link_to_their_own_month(self):
        result = self.build(month="2026-11")
        first = result["weeks"][0][0]
        self.assertEqual(first["date"], date(2026, 10, 26))
        self.assertIn("month=2026-10", first["url"])
        self.assertIn("day=2026-10-26", first["url"])

    def test_event_is_placed_in_its_own_timezone_not_utc_date(self):
        event = projected_event(starts_at=datetime(2026, 11, 1, 0, 30, tzinfo=UTC))
        october = self.build([event], month="2026-10", day="2026-10-31")
        self.assertEqual(october["scheduled_count"], 1)
        self.assertEqual(october["day_events"][0]["start_time"], "19:30")
        self.assertEqual(october["day_events"][0]["timezone"], "America/Lima")
        self.assertEqual(self.build([event])["scheduled_count"], 0)

    def test_event_without_plan_remains_scheduled_without_fake_sessions(self):
        event = projected_event(starts_at=datetime(2026, 11, 12, 19, 30, tzinfo=UTC))
        result = self.build([event], day="2026-11-12")
        self.assertEqual(result["scheduled_count"], 1)
        self.assertEqual(result["approved_count"], 0)
        self.assertFalse(result["day_events"][0]["has_plan"])
        self.assertEqual(result["day_events"][0]["sessions"], [])

    def test_undated_event_is_separate_and_does_not_get_a_fake_date(self):
        event = projected_event()
        result = self.build([event])
        self.assertEqual(result["undated_count"], 1)
        self.assertIsNone(result["undated_events"][0]["date_source"])
        self.assertEqual(result["month_events"], [])
        self.assertEqual(result["day_events"], [])

    def test_plan_can_supply_a_labelled_date_without_confirming_event_date(self):
        event = projected_event(sessions=[session()])
        result = self.build([event], day="2026-11-12")
        self.assertEqual(result["undated_count"], 0)
        self.assertEqual(result["day_events"][0]["date_source"], "plan")
        self.assertEqual(result["day_events"][0]["date"], date(2026, 11, 12))
        self.assertIsNone(event.starts_at)

    def test_event_title_occurs_once_in_grid_but_agenda_spans_midnight(self):
        event = projected_event(sessions=[session(start="2026-11-12T23:30:00-05:00", duration=90)])
        first_day = self.build([event], day="2026-11-12")
        next_day = self.build([event], day="2026-11-13")
        self.assertEqual(sum(len(cell["events"]) for week in first_day["weeks"] for cell in week), 1)
        first_session = first_day["day_events"][0]["sessions"][0]
        next_session = next_day["day_events"][0]["sessions"][0]
        self.assertTrue(first_session["continues_to_next"])
        self.assertTrue(next_session["continues_from_previous"])
        self.assertEqual(next_session["time_label"], "23:30–01:00 · hasta 13/11")

    def test_session_ending_exactly_at_midnight_does_not_occupy_next_day(self):
        event = projected_event(sessions=[session(start="2026-11-12T23:00:00-05:00", duration=60)])
        self.assertEqual(self.build([event], day="2026-11-13")["day_events"], [])

    def test_daylight_saving_transition_uses_elapsed_duration(self):
        event = projected_event(zone="America/New_York", sessions=[session(start="2026-11-01T01:30:00-04:00", duration=120)])
        result = self.build([event], day="2026-11-01")
        item = result["day_events"][0]["sessions"][0]
        self.assertEqual(item["time_label"], "01:30–02:30")
        self.assertEqual(item["start"].utcoffset().total_seconds(), -4 * 3600)
        self.assertEqual(item["end"].utcoffset().total_seconds(), -5 * 3600)
        self.assertEqual((item["end"].astimezone(UTC) - item["start"].astimezone(UTC)).total_seconds(), 7200)

    def test_foreign_active_plan_pointer_never_discloses_its_content(self):
        event = projected_event(sessions=[session(title="Contenido privado de otro evento")])
        event.active_plan.event_id = uuid4()
        result = self.build([event])
        self.assertFalse(result["undated_events"][0]["has_plan"])
        self.assertEqual(result["undated_events"][0]["sessions"], [])

    def test_malformed_historical_session_does_not_break_calendar(self):
        event = projected_event(sessions=[None, session(start="fecha inválida"), session(start="2026-11-12T19:30:00"), session(duration=True), session(start="9999-12-31T23:59:59+00:00")])
        result = self.build([event])
        self.assertEqual(result["undated_count"], 1)
        self.assertEqual(result["undated_events"][0]["sessions"], [])


class CalendarViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="calendar-owner")
        self.other = user_model.objects.create_user(username="calendar-other")
        self.event = Event.objects.create(owner=self.owner, title="Calendario propio", brief="Plan privado propio", starts_at=datetime(2026, 11, 14, 14, tzinfo=UTC))
        self.foreign = Event.objects.create(owner=self.other, title="Evento ajeno secreto", brief="Contenido confidencial", starts_at=datetime(2026, 11, 14, 14, tzinfo=UTC))
        self.url = reverse("events:calendar")
        self.client.force_login(self.owner)

    def get(self, **params):
        return self.client.get(self.url, {"month": "2026-11", "day": "2026-11-14", **params})

    def approve(self, event, actor, payload):
        event.refresh_from_db()
        candidate = create_candidate(event=event, actor=actor, payload=payload, base_revision=event.revision, base_plan_id=event.active_plan_id)
        return approve_candidate(candidate_id=candidate.pk, actor=actor)

    def test_calendar_requires_login_and_is_read_only(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_calendar_only_exposes_owned_events_even_for_htmx(self):
        for extra in ({}, {"HTTP_HX_REQUEST": "true"}):
            with self.subTest(extra=extra):
                response = self.client.get(self.url, {"month": "2026-11", "day": "2026-11-14"}, **extra)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Calendario propio")
                self.assertNotContains(response, "Evento ajeno secreto")
                self.assertNotContains(response, "Contenido confidencial")
                self.assertEqual(response.context["calendar"]["event_count"], 1)

    def test_day_panel_shows_active_plan_and_excludes_pending_candidate(self):
        self.approve(self.event, self.owner, valid_plan())
        self.event.refresh_from_db()
        pending = valid_plan()
        pending["sessions"][0]["title"] = "Candidata pendiente que no debe publicarse"
        create_candidate(event=self.event, actor=self.owner, payload=pending, base_revision=self.event.revision, base_plan_id=self.event.active_plan_id)
        response = self.get()
        agenda = response.context["calendar"]["day_events"][0]
        self.assertTrue(agenda["has_plan"])
        self.assertEqual(agenda["plan_version"], 1)
        self.assertEqual([item["title"] for item in agenda["sessions"]], ["Apertura", "Conversatorio"])
        self.assertContains(response, "Apertura")
        self.assertNotContains(response, "Candidata pendiente que no debe publicarse")

    def test_superseded_approved_revision_is_not_current_agenda(self):
        self.approve(self.event, self.owner, valid_plan())
        changed = valid_plan()
        changed["sessions"][0]["title"] = "Apertura vigente revisada"
        self.approve(self.event, self.owner, changed)
        response = self.get()
        agenda = response.context["calendar"]["day_events"][0]
        self.assertEqual(agenda["plan_version"], 2)
        self.assertEqual(agenda["sessions"][0]["title"], "Apertura vigente revisada")

    def test_bad_month_or_day_returns_controlled_400(self):
        for params in ({"month": "2026-99"}, {"day": "2026-11-31"}, {"month": "2101-01", "day": "2101-01-01"}, {"day": "2026-12-01"}):
            with self.subTest(params=params):
                response = self.get(**params)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response["Content-Type"].startswith("text/html"))
                self.assertContains(response, "Volver al calendario", status_code=400)
                self.assertNotContains(response, "Traceback", status_code=400)

    def test_owned_events_and_active_plans_load_in_one_query(self):
        self.approve(self.event, self.owner, valid_plan())
        with self.assertNumQueries(1):
            result = build_calendar_context(events=Event.objects.filter(owner=self.owner).select_related("active_plan"), params={"month": "2026-11", "day": "2026-11-14"}, today=date(2026, 11, 8))
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(len(result["day_events"][0]["sessions"]), 2)

    def test_untrusted_titles_are_escaped_in_rendered_calendar(self):
        self.event.title = '<script>alert("calendar")</script>'
        self.event.save(update_fields=["title"])
        response = self.get()
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("calendar")</script>')
