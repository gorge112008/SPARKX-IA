"""Deterministic Spanish dates: consume the complete declaration, never guess years.

Only a bounded grammar is accepted. Calendar validation uses real dates; repeated
days are deduplicated, whereas unused numbers and contradictory ranges fail.
"""

from datetime import date, timedelta
import re
import unicodedata

from .creation_language import clean_text, parse_integer


MONTHS = {name: index for index, name in enumerate((
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
), 1)}
MONTHS["setiembre"] = 9
MONTH_NAMES = tuple(name for name in MONTHS if name != "setiembre")
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
NUMBER_WORDS = (
    "primero", "uno", "un", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve",
    "veinte", "veintiuno", "veintiun", "veintidos", "veintitres", "veinticuatro", "veinticinco", "veintiseis",
    "veintisiete", "veintiocho", "veintinueve", "treinta", "treinta y uno",
)
DAY = r"(?:[0-9]{1,2}|" + "|".join(re.escape(word) for word in sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"
MONTH = re.compile(r"\b(" + "|".join(MONTHS) + r")(?=\b|[0-9])")
UNDER_HUNDRED = (
    r"(?:noventa|ochenta|setenta|sesenta|cincuenta|cuarenta|treinta)(?: y (?:uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve))?"
    r"|veintinueve|veintiocho|veintisiete|veintiseis|veinticinco|veinticuatro|veintitres|veintidos|veintiuno"
    r"|diecinueve|dieciocho|diecisiete|dieciseis|quince|catorce|trece|doce|once|diez|veinte|nueve|ocho|siete|seis|cinco|cuatro|tres|dos|uno"
)
YEAR = r"(?:[0-9]{1,5}|dos mil(?: (?:" + UNDER_HUNDRED + r"))?)"
YEAR_PREFIX = re.compile(r"\s*(?:(?:de|del)\s+)?(?:(?:el\s+)?ano\s*)?(?P<year>" + YEAR + r")(?=$|[\s,.;])")
NUMERIC_DATE = re.compile(r"(?<![\w/\-])(?:(?P<iy>[0-9]{3,5})-(?P<im>[0-9]{1,2})-(?P<id>[0-9]{1,2})|(?P<d>[0-9]{1,2})/(?P<m>[0-9]{1,2})(?:/(?P<y>[0-9]{1,5}))?)(?![\w/\-])")
INTRO = re.compile(
    r"^(?:(?:hola\s+)?(?:gica\s+)?(?:quiero que (?:sea|sean)|quisiera que (?:sea|sean)|"
    r"me gustaria que (?:sea|sean)|que (?:sea|sean)|quiero (?:el evento|el seminario)|"
    r"(?:el evento|el seminario) (?:sera|seria|es)|sera|seria|seran|son|es|para)(?:\s+(?:el|los|las))?\s+)"
)


class DateYearRequired(ValueError):
    """A valid day/month selection is retained until its explicit year arrives."""

    def __init__(self, pending, reference_year):
        self.pending = pending
        self.reference_year = reference_year
        super().__init__(year_question(pending, reference_year))


def _fold(text):
    value = " ".join("".join(ch for ch in unicodedata.normalize("NFKD", clean_text(text))
                              .casefold() if not unicodedata.combining(ch)).split()).strip(" .!?¡¿")
    # Common compact typing, only at numeric/calendar grammar boundaries.
    value = re.sub(r"(?<=\d)(?=(?:" + "|".join(MONTHS) + r"))", " ", value)
    value = re.sub(r"\bdel(?=\d)", "del ", value)
    value = re.sub(r"(?<=\d)al(?=\d)", " al ", value)
    value = re.sub(r"(?<=\d)\s*y\s*(?=\d)", " y ", value)
    value = re.sub(r"\by(?=\d)", "y ", value)
    return value


def _intro(text):
    previous = None
    for _ in range(3):
        if previous == text:
            break
        previous, text = text, INTRO.sub("", text)
    return text


def _number(text):
    return 1 if text == "primero" else parse_integer(text, min_value=1, max_value=31)


def _day_spec(text, *, first):
    value = text.strip()
    if not first:
        match = re.match(r"^(?:,\s*|y\s+)", value)
        if match is None:
            raise ValueError("Separa cada grupo de fechas con «y» o una coma; no añadiré números que no estén claros.")
        value = value[match.end():].strip()
    value = _intro(value) if first else value
    value = re.sub(r"^(?:desde\s+el|entre\s+el|los\s+dias|los\s+dia|los|el\s+dia|el|del|dias|dia)\s+", "", value)
    # These fillers describe the named month, never provide a missing month.
    suffixes = ("del mes de la primavera", "del mes de la temporada de primavera",
                "del mes de", "del mes", "de la primavera", "de", "del")
    for suffix in suffixes:
        if value.endswith(" " + suffix):
            value = value[:-(len(suffix) + 1)].strip()
            break
    interval = re.fullmatch(rf"(?P<start>{DAY})\s+(?:al|hasta(?:\s+el)?)\s+(?P<end>{DAY})", value)
    if interval:
        start, end = _number(interval["start"]), _number(interval["end"])
        if start > end:
            raise ValueError("El día inicial del rango debe ser anterior o igual al final. Indica el rango en orden.")
        return list(range(start, end + 1))
    single = re.fullmatch(DAY, value)
    if single:
        return [_number(value)]
    # Do not split the grammatical «y» in «treinta y uno».
    list_pattern = rf"{DAY}(?:\s*(?:,|\by\b)\s*(?:el\s+)?{DAY})+"
    if not re.fullmatch(list_pattern, value):
        raise ValueError("Indica los días antes del mes: por ejemplo «5, 6 y 7 de septiembre de 2026» o «del 5 al 9 de septiembre de 2026».")
    return [_number(item.group()) for item in re.finditer(rf"(?<!\w){DAY}(?!\w)", value)]


def _pending(pairs):
    unique = sorted({(month, day) for month, day in pairs})
    if not unique or len(unique) > 366:
        raise ValueError("Indica entre una y 366 fechas válidas.")
    # A leap reference validates February 29 without guessing the eventual year.
    for month, day in unique:
        try:
            date(2000, month, day)
        except ValueError as exc:
            raise ValueError("Indica una fecha válida: ese día no existe en el mes indicado. Corrige el día o el mes.") from exc
    return {"day_months": [[month, day] for month, day in unique]}


def year_question(pending, reference_year):
    pairs = pending.get("day_months", []) if isinstance(pending, dict) else []
    first = ""
    if pairs:
        month, day = pairs[0]
        if type(month) is int and type(day) is int and 1 <= month <= 12:
            first = f"Conservo el {day} de {MONTH_NAMES[month - 1]}"
            first += f" y {len(pairs) - 1} fechas más. " if len(pairs) > 1 else ". "
    return first + f"¿De qué año? Usa cuatro cifras entre {reference_year} y 2099, por ejemplo {reference_year}."


def _year_only(value):
    value = re.sub(r"^(?:(?:seria|sera|es)\s+)?(?:(?:el|del|para el)\s+)?(?:ano\s*)?", "", value)
    if not re.fullmatch(YEAR, value):
        return None
    if value.isascii() and value.isdecimal():
        return int(value) if len(value) == 4 and value.startswith("20") else -1
    try:
        return parse_integer(value, min_value=0, max_value=99999)
    except ValueError:
        return None


def _numeric(value):
    matches = list(NUMERIC_DATE.finditer(value))
    if not matches:
        return None
    remainder = value
    for match in reversed(matches):
        remainder = remainder[:match.start()] + " DATE " + remainder[match.end():]
    remainder = _intro(remainder.strip())
    remainder = re.sub(r"^(?:el|los dias|los|dia)\s+", "", remainder)
    if not re.fullmatch(r"DATE(?:\s*(?:,|\by\b)\s*DATE)*", remainder):
        raise ValueError("La fecha contiene números o palabras adicionales. Indica sólo las fechas completas, separadas por «y» o comas.")
    result = []
    for match in matches:
        year = match["iy"] or match["y"]
        result.append((int(match["im"] or match["m"]), int(match["id"] or match["d"]), _year_only(year) if year else None))
    return result


def _natural(value):
    groups, cursor = [], 0
    matches = list(MONTH.finditer(value))
    if not matches:
        raise ValueError("Indica un día, un mes reconocido y el año: por ejemplo «5 de septiembre de 2026».")
    for index, month in enumerate(matches):
        if month.start() < cursor:
            raise ValueError("Las fechas se superponen o contienen un año incompleto.")
        days = _day_spec(value[cursor:month.start()], first=index == 0)
        cursor = month.end()
        year = None
        match = YEAR_PREFIX.match(value, cursor)
        if match:
            year = _year_only(match["year"])
            cursor = match.end()
        groups.extend((MONTHS[month[1]], day, year) for day in days)
    if value[cursor:].strip(" .,;!?"):
        raise ValueError("La fecha contiene números o palabras adicionales. Revisa el año y separa claramente cada grupo de días y mes.")
    return groups


def parse_scheduled_dates(text, *, reference_date, pending=None):
    """Return ordered ISO dates or ask for a year while retaining day/month pairs."""
    if type(reference_date) is not date or not 2000 <= reference_date.year <= 2099:
        raise ValueError("Se necesita la fecha local actual del servidor para comprobar el año.")
    value = _fold(text)
    if pending is not None:
        year = _year_only(value)
        if year is not None:
            if not isinstance(pending, dict) or set(pending) != {"day_months"} or not isinstance(pending["day_months"], list):
                raise ValueError("Vuelve a indicar los días, el mes y el año para revisar la fecha.")
            try:
                pairs = [(item[0], item[1]) for item in pending["day_months"]
                         if isinstance(item, list) and len(item) == 2 and all(type(part) is int for part in item)]
            except (TypeError, IndexError) as exc:
                raise ValueError("Vuelve a indicar los días, el mes y el año.") from exc
            if len(pairs) != len(pending["day_months"]):
                raise ValueError("Vuelve a indicar los días, el mes y el año.")
            selection = _pending(pairs)
            declarations = [(month, day, year) for month, day in pairs]
        else:
            declarations = None
    else:
        declarations = None
    if declarations is None:
        if value in {"hoy", "manana", "pasado manana"}:
            offset = {"hoy": 0, "manana": 1, "pasado manana": 2}[value]
            actual = reference_date + timedelta(days=offset)
            declarations = [(actual.month, actual.day, actual.year)]
        else:
            declarations = _numeric(value)
            if declarations is None:
                declarations = _natural(value)
        selection = _pending([(month, day) for month, day, _ in declarations])
    explicit_years = {year for _, _, year in declarations if year is not None}
    if any(not reference_date.year <= year <= 2099 for year in explicit_years) or not explicit_years:
        raise DateYearRequired(selection, reference_date.year)
    if len(explicit_years) > 1 and any(year is None for _, _, year in declarations):
        raise ValueError("Hay varios años distintos. Indica el año de cada grupo de fechas para no asignarlo por suposición.")
    shared = next(iter(explicit_years))
    result = set()
    for month, day, year in declarations:
        try:
            result.add(date(year or shared, month, day).isoformat())
        except ValueError as exc:
            raise ValueError("Indica una fecha válida: ese día no existe en el mes y año indicados. Revisa también si el año es bisiesto.") from exc
    if not 1 <= len(result) <= 366:
        raise ValueError("Puedes seleccionar entre una y 366 fechas.")
    return sorted(result)


def spoken_dates(dates):
    if not dates:
        return "Fecha pendiente."
    first = date.fromisoformat(dates[0])
    result = f"Anotado: {WEEKDAYS[first.weekday()]} {first.day} de {MONTH_NAMES[first.month - 1]} de {first.year}"
    return result + (f" y {len(dates) - 1} fechas más." if len(dates) > 1 else ".")
