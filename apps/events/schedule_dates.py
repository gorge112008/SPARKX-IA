"""Canonical civil event dates, independent of speech and model providers."""
from datetime import date
import re


def normalize_scheduled_dates(value, *, reference_year=None):
    if type(value) is not list or len(value) > 366:
        raise ValueError("Indica una lista de hasta 366 fechas válidas.")
    if reference_year is not None and (type(reference_year) is not int or not 1 <= reference_year <= 9999):
        raise ValueError("El año actual de referencia no es válido.")
    result = set()
    for item in value:
        if not isinstance(item, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", item):
            raise ValueError("Cada fecha debe incluir día, mes y año completos.")
        try:
            parsed = date.fromisoformat(item)
        except ValueError as error:
            raise ValueError("Ese día no existe en el mes y año indicados.") from error
        if reference_year is not None and not reference_year <= parsed.year <= 2099:
            raise ValueError(f"Indica un año de cuatro cifras, entre {reference_year} y 2099.")
        result.add(parsed.isoformat())
    return sorted(result)
