"""Pure dates: explicit complete input, retained year question, real calendars."""

from datetime import date
import unittest

from apps.assistant.date_language import DateYearRequired, parse_scheduled_dates, spoken_dates


class DateLanguageTests(unittest.TestCase):
    def parse(self, text, **kwargs):
        return parse_scheduled_dates(text, reference_date=date(2026, 11, 15), **kwargs)

    def test_single_absolute_dates_and_fillers(self):
        examples = (
            "5 de septiembre de 2026", "el cinco de setiembre del año 2026",
            "quiero que sea el 5 del mes de la primavera septiembre del año2026",
            "05/09/2026", "2026-09-05", "el 05/09/2026", "será el 5 de septiembre2026",
            "cinco de septiembre de dos mil veintiséis",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertEqual(self.parse(example), ["2026-09-05"])

    def test_lists_ranges_sorted_and_deduplicated(self):
        for text in ("5, 6 y 7 de septiembre de 2026", "5,6 y7 de septiembre2026", "5,6y7septiembre2026", "del5al7septiembre2026", "cinco, seis y siete de setiembre del año 2026", "del 5 al 7 de septiembre de 2026", "5 hasta el 7 de septiembre de 2026", "5, 5, 6 y 7 de septiembre de 2026"):
            with self.subTest(text=text):
                self.assertEqual(self.parse(text), ["2026-09-05", "2026-09-06", "2026-09-07"])
        self.assertEqual(self.parse("del 5 al 9 de septiembre de 2026"), [f"2026-09-{day:02}" for day in range(5, 10)])
        self.assertEqual(self.parse("25 de octubre y 10 de septiembre de 2026"), ["2026-09-10", "2026-10-25"])
        self.assertEqual(self.parse("2026-10-25 y 10/09/2026"), ["2026-09-10", "2026-10-25"])
        self.assertEqual(self.parse("treinta y uno de julio de 2026"), ["2026-07-31"])

    def test_current_year_past_days_allowed_and_future20xx(self):
        self.assertEqual(self.parse("5 de enero de 2026"), ["2026-01-05"])
        self.assertEqual(self.parse("5 de septiembre de 2040"), ["2040-09-05"])
        self.assertEqual(self.parse("5 de septiembre de dos mil noventa y nueve"), ["2099-09-05"])

    def test_missing_or_wrong_year_retains_month_days(self):
        for text in ("5 de septiembre", "5 de septiembre de 203", "5 de septiembre de 2021", "5 de septiembre de 2100", "5 de septiembre de 02026", "02026-09-05", "05/09", "05/09/2021"):
            with self.subTest(text=text), self.assertRaises(DateYearRequired) as caught:
                self.parse(text)
            self.assertEqual(caught.exception.pending, {"day_months": [[9, 5]]})
            self.assertIn("2026", str(caught.exception))
            self.assertEqual(self.parse("2026", pending=caught.exception.pending), ["2026-09-05"])
        with self.assertRaises(DateYearRequired) as caught:
            self.parse("5, 6 y 7 de septiembre")
        self.assertEqual(self.parse("del año dos mil veintiséis", pending=caught.exception.pending), ["2026-09-05", "2026-09-06", "2026-09-07"])

    def test_partial_year_stays_pending_and_full_new_date_can_replace(self):
        with self.assertRaises(DateYearRequired) as caught:
            self.parse("5 de septiembre")
        with self.assertRaises(DateYearRequired) as again:
            self.parse("203", pending=caught.exception.pending)
        self.assertEqual(again.exception.pending, caught.exception.pending)
        self.assertEqual(self.parse("7 de octubre de 2040", pending=caught.exception.pending), ["2040-10-07"])

    def test_extra_numbers_unknown_months_and_contradictions_rejected(self):
        invalid = (
            "5 6 de septiembre de 2026", "5 de septiembre de 2026 2027",
            "5 de septiembre de 2026 y 8", "5 de septiembre de 2026 10 personas",
            "septiembre 5 de 2026", "5 de septimbre de 2026", "5 de primavera de 2026",
            "del 9 al 5 de septiembre de 2026", "0 de septiembre de 2026",
            "32 de septiembre de 2026", "5 de septiembre de 2026 y 6 de octubre y 7 de noviembre de 2027",
            "2026-09-05 99", "2026-09-05 y 10 personas", "05/09/2026 2027",
        )
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)

    def test_actual_calendar_dates_and_leap_years(self):
        for text in ("31 de abril de 2026", "29 de febrero de 2026", "del 28 al 30 de febrero de 2028"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)
        self.assertEqual(self.parse("29 de febrero de 2028"), ["2028-02-29"])
        with self.assertRaises(DateYearRequired) as caught:
            self.parse("29 de febrero")
        self.assertEqual(self.parse("2028", pending=caught.exception.pending), ["2028-02-29"])

    def test_explicit_year_per_group_and_relative_server_day(self):
        self.assertEqual(self.parse("5 de septiembre de 2026 y 6 de octubre de 2027"), ["2026-09-05", "2027-10-06"])
        self.assertEqual(self.parse("mañana"), ["2026-11-16"])
        self.assertEqual(self.parse("hoy"), ["2026-11-15"])

    def test_invalid_pending_state_or_reference_never_assumes_year(self):
        for pending in ({}, {"day_months": [["9", 5]]}, {"day_months": [[9, 5]], "owner": 4}, {"day_months": [[9, 32]]}):
            with self.subTest(pending=pending), self.assertRaises(ValueError):
                self.parse("2026", pending=pending)
        with self.assertRaises(ValueError):
            parse_scheduled_dates("5 de septiembre de 2026", reference_date=None)

    def test_spoken_confirmation_includes_weekday_month_year_and_rest(self):
        self.assertEqual(spoken_dates(["2026-09-05"]), "Anotado: sábado 5 de septiembre de 2026.")
        self.assertEqual(spoken_dates(["2026-09-05", "2026-09-06", "2026-09-07"]), "Anotado: sábado 5 de septiembre de 2026 y 2 fechas más.")
