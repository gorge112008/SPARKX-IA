"""Presentation behavior at preview boundaries and during proposal review."""

from html.parser import HTMLParser
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings


class _Markup(HTMLParser):
    """Small structural reader; no browser or third-party HTML parser needed."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = {"tag": tag, "attrs": dict(attrs), "ancestors": tuple(self.stack), "text": ""}
        self.elements.append(element)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for element in self.stack:
            element["text"] += data

    def select(self, tag=None, class_name=None):
        return [element for element in self.elements
                if (tag is None or element["tag"] == tag)
                and (class_name is None
                     or class_name in element["attrs"].get("class", "").split())]


def _payload(session_count=4, task_count=4):
    return {
        "title": "Seminario", "summary": "Plan pendiente de revisión", "risks": [],
        "sessions": [{
            "id": f"s{index}", "title": f"Sesión {index}",
            "start": "2026-11-13T00:30:00Z", "duration_minutes": 30,
            "speaker": "Ponente", "resource": "",
        } for index in range(1, session_count + 1)],
        "tasks": [{
            "id": f"t{index}", "title": f"Tarea {index}", "purpose": f"Objetivo {index}",
            "status": "pending", "depends_on": [f"t{index - 1}"] if index > 1 else [],
        } for index in range(1, task_count + 1)],
    }


@override_settings(TIME_ZONE="Europe/London", USE_TZ=True, LANGUAGE_CODE="es")
class PlanPresentationTests(SimpleTestCase):
    def render_plan(self, template, payload, **context):
        return render_to_string(template, {
            "payload": payload, "event": SimpleNamespace(timezone="America/Lima"),
            **context,
        })

    def assert_scroll_preview(self, template, collection, row_class, list_class, scroll_class):
        for count in (0, 1, 3, 4):
            with self.subTest(collection=collection, count=count):
                payload = _payload(session_count=count, task_count=count)
                markup = _Markup(self.render_plan(template, payload, preview=True))
                rows = markup.select("li", row_class)
                self.assertEqual(len(rows), count)
                for item, row in zip(payload[collection], rows, strict=True):
                    self.assertIn(item["title"], row["text"])
                    self.assertNotIn("hidden", row["attrs"])
                    self.assertFalse(any("hidden" in node["attrs"]
                                         or node["tag"] == "details"
                                         for node in row["ancestors"]))
                lists = markup.select("ol", list_class)
                self.assertEqual(len(lists), int(count > 0))
                self.assertEqual(markup.select("details", "list-more"), [])
                self.assertFalse(any("data-agenda-pagination" in node["attrs"]
                                     or "data-agenda-pages" in node["attrs"]
                                     for node in markup.elements))
                if count:
                    self.assertTrue(all(lists[0] in row["ancestors"] for row in rows))
                scrolls = markup.select("div", "plan-scroll")
                self.assertEqual(len(scrolls), int(count > 3))
                if count > 3:
                    scroll = scrolls[0]
                    self.assertIn(scroll_class, scroll["attrs"].get("class", "").split())
                    self.assertEqual(scroll["attrs"].get("tabindex"), "0")
                    self.assertEqual(scroll["attrs"].get("role"), "region")
                    self.assertTrue(scroll["attrs"].get("aria-label", "").strip())
                    self.assertTrue(all(scroll in row["ancestors"] for row in rows))
                else:
                    self.assertFalse(any(node["attrs"].get("tabindex") == "0"
                                         for node in markup.elements))

    def test_agenda_scroll_preview_preserves_every_session_at_three_item_boundary(self):
        self.assert_scroll_preview(
            "events/_agenda.html", "sessions", "agenda-row", "agenda-list", "agenda-scroll",
        )

    def test_preparation_scroll_preview_preserves_every_task_at_three_item_boundary(self):
        self.assert_scroll_preview(
            "events/_preparation.html", "tasks", "preparation-row", "preparation-list",
            "preparation-scroll",
        )

    def test_proposal_review_shows_all_rows_even_when_preview_is_requested_by_caller(self):
        payload = _payload(session_count=7, task_count=11)
        html = self.render_plan("events/_plan.html", payload, proposed=True, preview=True)
        markup = _Markup(html)
        self.assertEqual(markup.select("details", "list-more"), [])
        self.assertFalse(any("data-agenda-pagination" in node["attrs"]
                             or "data-agenda-pages" in node["attrs"]
                             for node in markup.elements))
        self.assertEqual(markup.select("div", "plan-scroll"), [])
        self.assertFalse(any(node["attrs"].get("tabindex") == "0"
                             for node in markup.elements))
        for collection, row_class in (("sessions", "agenda-row"), ("tasks", "preparation-row")):
            rows = markup.select("li", row_class)
            self.assertEqual(len(rows), len(payload[collection]))
            for item, row in zip(payload[collection], rows, strict=True):
                self.assertIn(item["title"], row["text"])
                # Per-row instructions may fold, but the approval review cannot hide whole rows.
                self.assertFalse(any(node["tag"] == "details" for node in row["ancestors"]))
                self.assertFalse(any("hidden" in node["attrs"] for node in row["ancestors"]))

    def test_dependencies_render_readable_titles_and_untrusted_content_stays_text(self):
        payload = _payload(session_count=1, task_count=2)
        payload["tasks"][0].update(id="source-id", title="Preparar sala")
        payload["tasks"][1].update(
            title='<script>alert("task")</script>',
            purpose='<svg onload="alert(1)">',
            depends_on=["source-id", '<img src=x onerror="alert(2)">'],
        )
        payload["sessions"][0].update(
            title='<script>alert("session")</script>',
            speaker='<img src=x onerror="alert(3)">',
            resource='<iframe src="https://example.invalid">',
        )
        html = self.render_plan("events/_plan.html", payload, proposed=True)
        markup = _Markup(html)
        dependencies = markup.select("div", "preparation-dependencies")
        self.assertEqual(len(dependencies), 1)
        self.assertIn("Preparar sala", dependencies[0]["text"])
        self.assertNotIn("source-id", dependencies[0]["text"])
        self.assertIn('<img src=x onerror="alert(2)">', dependencies[0]["text"])
        for tag in ("script", "img", "iframe", "svg"):
            self.assertEqual(markup.select(tag), [])
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)

    def test_agenda_groups_by_event_local_day_instead_of_server_or_source_day(self):
        payload = _payload(session_count=3, task_count=0)
        for session, start in zip(payload["sessions"], (
            "2026-11-12T02:00:00Z", "2026-11-12T03:00:00Z", "2026-11-12T06:00:00Z",
        ), strict=True):
            session["start"] = start
        markup = _Markup(self.render_plan("events/_agenda.html", payload))
        days = markup.select("p", "agenda-day")
        self.assertEqual(len(days), 2)
        self.assertIn("11", days[0]["text"])
        self.assertIn("12", days[1]["text"])
        times = markup.select("time")
        self.assertEqual([time["text"] for time in times], [
            "21:00", "21:30", "22:00", "22:30", "01:00", "01:30",
        ])
        self.assertEqual(times[0]["attrs"]["datetime"], "2026-11-12T02:00:00Z")

    def test_session_crossing_midnight_exposes_end_date_and_aware_end_instant(self):
        payload = _payload(session_count=1, task_count=0)
        payload["sessions"][0].update(start="2026-11-13T04:50:00Z", duration_minutes=30)
        markup = _Markup(self.render_plan("events/_agenda.html", payload))
        times = markup.select("time")
        self.assertEqual(times[0]["text"], "23:50")
        self.assertEqual(times[1]["attrs"]["datetime"], "2026-11-13T00:20:00-05:00")
        self.assertTrue(times[1]["text"].startswith("00:20"))
        end_date = markup.select("span", "agenda-end-date")
        self.assertEqual(len(end_date), 1)
        self.assertIn("13", end_date[0]["text"])
