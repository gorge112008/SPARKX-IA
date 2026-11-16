"""Shared catalog filtering, isolation, pagination and calendar navigation."""

from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import EventReviewAssignment, PortalAccount
from apps.directory.models import EventPerson, Organization, Person
from apps.directory.normalization import search_key
from apps.planning.services import approve_candidate, create_candidate
from apps.planning.tests import valid_plan

from .calendar import build_calendar_context
from .catalog import find_events, parse_filters
from .models import Event


class CatalogInputTests(SimpleTestCase):
    def test_filters_reject_bad_types_dates_ranges_and_identifiers(self):
        for params in (
            {"q": "x" * 201}, {"q": []}, {"organization": "wrong"},
            {"from": "2026-1-01"}, {"to": "2026-02-29"},
            {"from": "1899-12-31"}, {"to": "2101-01-01"},
            {"from": "2026-11-16", "to": "2026-11-15"},
            {"plan": "approved_by_model"}, QueryDict("q=one&q=two"),
        ):
            with self.subTest(params=params), self.assertRaises(ValueError):
                parse_filters(params)

    def test_blank_filters_are_optional_and_preserve_no_navigation_fields(self):
        result = parse_filters({"q": "   ", "month": "2026-11", "day": "2026-11-14", "page": "3"})
        self.assertEqual(result, {"q": "", "organization": "", "from": "", "to": "", "plan": ""})


class EventCatalogTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="catalog-owner")
        self.other = users.objects.create_user(username="catalog-other")
        self.reviewer = users.objects.create_user(username="catalog-reviewer")
        PortalAccount.objects.create(user=self.reviewer, role=PortalAccount.Role.REVIEWER)
        self.organization = self.make_organization(self.owner, "Compañía Innovación")
        self.secret_organization = self.make_organization(self.other, "Empresa secreta ajena")
        self.event = Event.objects.create(
            owner=self.owner, title="Encuentro académico", brief="Investigación y colaboración",
            starts_at=datetime(2026, 11, 15, 1, tzinfo=UTC), organization=self.organization,
        )
        self.foreign = Event.objects.create(
            owner=self.other, title="Evento privado ajeno", brief="Datos confidenciales",
            starts_at=datetime(2026, 11, 15, 1, tzinfo=UTC), organization=self.secret_organization,
        )
        self.client.force_login(self.owner)

    def make_organization(self, owner, name, **values):
        return Organization.objects.create(owner=owner, name=name, name_key=search_key(name), **values)

    def find(self, **params):
        return find_events(actor=self.owner, params=params)

    def approve(self, event=None, payload=None):
        event = event or self.event
        event.refresh_from_db()
        candidate = create_candidate(
            event=event, actor=self.owner, payload=payload or valid_plan(),
            base_revision=event.revision, base_plan_id=event.active_plan_id,
        )
        return approve_candidate(candidate_id=candidate.pk, actor=self.owner)

    def test_search_normalizes_case_accents_and_compatibility_characters(self):
        for query in ("ACADEMICO", "  investigacion   Y colaboracion  ", "ＣＯＭＰＡＮＩＡ innovacion"):
            with self.subTest(query=query):
                result = self.find(q=query)
                self.assertEqual([entry["event"].pk for entry in result["entries"]], [self.event.pk])
        self.assertEqual(self.find(q="Datos confidenciales")["total"], 0)
        self.assertEqual(self.find(organization=str(self.secret_organization.pk))["total"], 0)

    def test_primary_company_is_not_inferred_from_a_persons_employer(self):
        employer = self.make_organization(self.owner, "Empresa del invitado")
        person = Person.objects.create(owner=self.owner, full_name="Invitado", organization=employer)
        EventPerson.objects.create(event=self.event, person=person, role="guest")
        self.assertEqual(self.find(organization=str(employer.pk))["total"], 0)
        self.assertEqual(self.find(q=employer.name)["total"], 0)

    def test_corrupt_cross_owner_company_is_hidden_and_cannot_match(self):
        Event.objects.filter(pk=self.event.pk).update(organization=self.secret_organization)
        result = self.find()
        self.assertIsNone(result["entries"][0]["organization"])
        self.assertNotIn(self.secret_organization, result["organization_options"])
        self.assertEqual(self.find(organization=str(self.secret_organization.pk))["total"], 0)
        self.assertEqual(self.find(q="Empresa secreta")["total"], 0)
        for endpoint in ("index", "calendar"):
            response = self.client.get(reverse("events:" + endpoint), {"month": "2026-11", "day": "2026-11-14"})
            self.assertNotContains(response, self.secret_organization.name)

    def test_administrator_still_sees_only_owned_events_and_companies(self):
        PortalAccount.objects.create(user=self.owner, role=PortalAccount.Role.ADMIN)
        result = self.find()
        self.assertEqual(result["total"], 1)
        self.assertNotIn(self.secret_organization, result["organization_options"])

    def test_reviewer_selectors_only_expose_currently_assigned_event_companies(self):
        unused = self.make_organization(self.owner, "Institución sin evento asignado")
        hidden = Event.objects.create(owner=self.owner, title="No asignado", brief="Privado", organization=unused)
        EventReviewAssignment.objects.create(
            event=self.event, reviewer=self.reviewer, assigned_by=self.owner,
            reviewer_version=self.reviewer.portal_account.access_version,
        )
        result = find_events(actor=self.reviewer, params={})
        self.assertEqual(result["organization_options"], [self.organization])
        self.assertEqual([entry["event"].pk for entry in result["entries"]], [self.event.pk])
        self.assertNotIn(hidden.pk, [entry["event"].pk for entry in result["entries"]])
        self.client.force_login(self.reviewer)
        for endpoint in ("index", "calendar"):
            response = self.client.get(reverse("events:" + endpoint))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, unused.name)
        PortalAccount.objects.filter(user=self.reviewer).update(access_version=2)
        self.assertEqual(find_events(actor=self.reviewer, params={})["total"], 0)

    def test_anonymous_and_inactive_actors_receive_no_catalog_or_selectors(self):
        self.owner.is_active = False
        for actor in (AnonymousUser(), self.owner):
            result = find_events(actor=actor, params={})
            self.assertEqual(result["total"], 0)
            self.assertEqual(result["organization_options"], [])

    def test_local_civil_date_is_used_instead_of_utc_date(self):
        result = self.find(**{"from": "2026-11-14", "to": "2026-11-14"})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["entries"][0]["date"], date(2026, 11, 14))
        self.assertEqual(self.find(**{"from": "2026-11-15"})["total"], 0)

    def test_approved_plan_fallback_and_continued_sessions_match_date_range(self):
        Event.objects.filter(pk=self.event.pk).update(starts_at=None)
        payload = valid_plan()
        payload["sessions"] = [{
            "id": "late", "title": "Sesión nocturna", "start": "2026-11-14T23:30:00-05:00",
            "duration_minutes": 90, "speaker": "", "resource": "",
        }]
        self.approve(payload=payload)
        result = self.find(**{"from": "2026-11-15", "to": "2026-11-15"})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["entries"][0]["date_source"], "plan")
        calendar = build_calendar_context(entries=result["entries"], params={
            "month": "2026-11", "day": "2026-11-15", **result["filter_values"],
        })
        self.assertEqual(len(calendar["day_events"]), 1)
        self.assertTrue(calendar["day_events"][0]["sessions"][0]["continues_from_previous"])
        self.event.refresh_from_db()
        self.assertIsNone(self.event.starts_at)

    def test_session_ending_at_midnight_does_not_match_the_following_day(self):
        payload = valid_plan()
        payload["sessions"] = [{
            "id": "late", "title": "Sesión nocturna", "start": "2026-11-14T23:00:00-05:00",
            "duration_minutes": 60, "speaker": "", "resource": "",
        }]
        self.approve(payload=payload)
        self.assertEqual(self.find(**{"from": "2026-11-15", "to": "2026-11-15"})["total"], 0)

    def test_undated_event_and_pending_candidate_never_supply_a_range_date(self):
        Event.objects.filter(pk=self.event.pk).update(starts_at=None)
        self.event.refresh_from_db()
        create_candidate(event=self.event, actor=self.owner, payload=valid_plan(), base_revision=self.event.revision)
        self.assertEqual(self.find()["total"], 1)
        self.assertEqual(self.find(**{"from": "2026-11-14"})["total"], 0)
        self.assertEqual(self.find(plan="approved")["total"], 0)
        self.assertEqual(self.find(plan="pending")["total"], 1)

    def test_superseded_approved_plan_cannot_supply_date_matches(self):
        Event.objects.filter(pk=self.event.pk).update(starts_at=None)
        self.approve()
        replacement = valid_plan()
        for session in replacement["sessions"]:
            session["start"] = session["start"].replace("2026-11-14", "2026-12-01")
        self.approve(payload=replacement)
        self.assertEqual(self.find(**{"from": "2026-12-01", "to": "2026-12-01"})["total"], 1)
        self.assertEqual(self.find(**{"from": "2026-11-14", "to": "2026-11-14"})["total"], 0)

    def test_limit_is_applied_after_filtering_and_counting(self):
        Event.objects.bulk_create([
            Event(owner=self.owner, title=f"Coincidencia {index:02d}", brief="Consulta acotada")
            for index in range(13)
        ])
        result = find_events(actor=self.owner, params={"q": "Coincidencia"}, limit=10)
        self.assertEqual(result["total"], 13)
        self.assertEqual(len(result["entries"]), 10)
        self.assertTrue(result["has_more"])
        for value in (0, -1, True, 101, "10"):
            with self.subTest(limit=value), self.assertRaises(ValueError):
                find_events(actor=self.owner, params={}, limit=value)

    def test_catalog_queries_do_not_grow_per_event_or_company(self):
        Event.objects.bulk_create([
            Event(owner=self.owner, title=f"Otro {index}", brief="Consulta", organization=self.organization)
            for index in range(12)
        ])
        with self.assertNumQueries(4):
            result = self.find()
        self.assertEqual(result["total"], 13)

    def test_index_paginates_twenty_after_filtering_and_keeps_query(self):
        Event.objects.bulk_create([
            Event(owner=self.owner, title=f"Página {index:02d}", brief="Consulta paginada")
            for index in range(23)
        ])
        response = self.client.get(reverse("events:index"), {"q": "pagina", "page": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["catalog"]["total"], 23)
        self.assertEqual(len(response.context["events"]), 3)
        self.assertEqual(parse_qs(urlsplit(response.context["previous_url"]).query), {"q": ["pagina"], "page": ["1"]})

    def test_calendar_preserves_all_filters_in_every_navigation_link(self):
        filters = {"q": "academico", "organization": str(self.organization.pk), "from": "2026-11-01", "to": "2026-12-31", "plan": "pending"}
        response = self.client.get(reverse("events:calendar"), {**filters, "month": "2026-11", "day": "2026-11-01"})
        self.assertEqual(response.status_code, 200)
        context = response.context["calendar"]
        self.assertEqual(context["event_count"], 1)
        urls = [context[key] for key in ("previous_url", "next_url", "today_url")]
        urls.extend(cell["url"] for week in context["weeks"] for cell in week)
        urls.extend(entry["calendar_url"] for entry in context["month_events"])
        for url in urls:
            query = parse_qs(urlsplit(url).query)
            for name, value in filters.items():
                self.assertEqual(query[name], [value])

    def test_bad_filters_return_controlled_400_on_both_pages(self):
        for endpoint in ("index", "calendar"):
            for params in ({"organization": "not-a-uuid"}, {"to": "2026-02-30"}, {"q": "x" * 201}):
                with self.subTest(endpoint=endpoint, params=params):
                    response = self.client.get(reverse("events:" + endpoint), params)
                    self.assertEqual(response.status_code, 400)
                    self.assertNotContains(response, "Traceback", status_code=400)

    def test_organization_and_synthetic_labels_are_escaped_and_visible(self):
        self.organization.name = '<script>Empresa</script>'
        self.organization.save(update_fields=["name"])
        Event.objects.filter(pk=self.event.pk).update(is_synthetic=True)
        for endpoint in ("index", "calendar"):
            response = self.client.get(reverse("events:" + endpoint), {"month": "2026-11", "day": "2026-11-14"})
            self.assertContains(response, "Ficticio")
            self.assertContains(response, "&lt;script&gt;Empresa&lt;/script&gt;")
            self.assertNotContains(response, '<script>Empresa</script>')

    def test_unknown_authorized_company_filter_returns_no_events(self):
        self.assertEqual(self.find(organization=str(uuid4()))["total"], 0)
