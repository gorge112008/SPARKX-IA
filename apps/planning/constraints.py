"""Small, deterministic event constraints; no Django, provider or I/O.

``{}`` preserves the legacy plan validator. An active JSON object has exactly:
version=1, window={start,end}, max_duration_minutes (per session), speakers and
resources=[{name,windows:[{start,end}],busy:[{start,end}]}], sessions=[{session_id,
allowed_speakers:[name],allowed_resources:[name]}], fixed=[{session_id, optional
start/speaker/resource/duration_minutes}]. Empty allowed lists require an empty
assignment; empty windows declare no availability. These are supplied constraints,
never evidence that named people/resources exist or have confirmed attendance.

Names retain accents and display spelling (NFC and collapsed spaces). Casefold is
used only to match names; ambiguous normalized names are rejected, never merged.
The session IDs in the plan must equal those in constraints. Instants are compared
across offsets; canonical constraints keep the event window's fixed ISO offset.
The caller retains the event's IANA zone and the version/authorization snapshot.

Repair preserves IDs, titles, tasks, risks, nonfixed durations and input ordering.
It may restore a fixed duration and propose only eligible, available assignments
and 15-minute starts. It first tries every session's original start, then permits
other starts. Each search orders unchanged assignments first. A result is only a
candidate for human approval. Finite search exhaustion is not proof of infeasibility
or optimality. Task dependencies are validated but never converted to agenda order.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unicodedata

from .domain import validate_plan

MAX_SESSIONS = 12
MAX_SPEAKERS = 3
MAX_RESOURCES = 3
MAX_WINDOWS = 16
MAX_BUSY = 32
MAX_WINDOW_MINUTES = 1440
GRID_MINUTES = 15
MAX_SEARCH_STEPS = 50000
_FIELDS = {"version", "window", "max_duration_minutes", "speakers", "resources", "sessions", "fixed"}
_SESSION_FIELDS = {"id", "title", "start", "duration_minutes", "speaker", "resource"}


def _object(value, fields, label):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label}: los campos requeridos son {', '.join(sorted(fields))}.")


def _list(value, limit, label):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"{label}: se requiere una lista de hasta {limit} elementos.")
    return value


def _text(value, label, limit=200, blank=False):
    if not isinstance(value, str) or len(value) > limit or (not blank and not value.strip()):
        raise ValueError(f"{label}: se requiere texto válido de hasta {limit} caracteres.")
    return unicodedata.normalize("NFC", " ".join(value.split()))


def _name(value):
    return unicodedata.normalize("NFC", " ".join(value.split())).casefold()


def _identifier(value, label):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 64 or len(value) > 64:
        raise ValueError(f"{label}: se requiere un identificador de 1 a 64 caracteres.")
    return value.strip()


def _instant(value, label, zone=None):
    try:
        if not isinstance(value, str) or len(value) > 64 or "T" not in value:
            raise ValueError
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError
        return instant.astimezone(zone) if zone is not None else instant
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{label}: se requiere una fecha ISO 8601 con zona horaria.") from exc


def _interval(value, label, zone=None):
    _object(value, {"start", "end"}, label)
    start = _instant(value["start"], label + ", inicio", zone)
    end = _instant(value["end"], label + ", fin", zone or start.tzinfo)
    if end <= start:
        raise ValueError(f"{label}: el fin debe ser posterior al inicio.")
    return {"start": start.isoformat(), "end": end.isoformat()}


def _catalog(values, label, limit, zone):
    result, known = [], {}
    for item in _list(values, limit, label):
        _object(item, {"name", "windows", "busy"}, label)
        name = _text(item["name"], label + ", nombre")
        key = _name(name)
        if key in known:
            raise ValueError(f"{label}: nombre normalizado ambiguo o repetido ({name}); usa nombres distintos sin fusionar identidades.")
        known[key] = name
        record = {"name": name}
        for field, maximum in (("windows", MAX_WINDOWS), ("busy", MAX_BUSY)):
            record[field] = sorted(
                (_interval(slot, f"{label}, {name}, {field}", zone)
                 for slot in _list(item[field], maximum, f"{label}, {field}")),
                key=lambda slot: (slot["start"], slot["end"]),
            )
        result.append(record)
    return sorted(result, key=lambda item: _name(item["name"])), known


def _allowed(values, known, label, limit):
    result, seen = [], set()
    for value in _list(values, limit, label):
        name = _text(value, label)
        key = _name(name)
        if key not in known:
            raise ValueError(f"{label}: {name} no figura en el catálogo autorizado.")
        if key in seen:
            raise ValueError(f"{label}: no se permiten nombres repetidos o ambiguos.")
        seen.add(key)
        result.append(known[key])
    return sorted(result, key=_name)


def normalize_constraints(value):
    """Return a detached canonical JSON dict, or raise a Spanish ValueError.

    No partial, unknown or confirmation/identity metadata is silently accepted.
    Inconsistent availability and fixed decisions may be stored: validation and
    repair report the conflict instead of silently releasing a human decision.
    """
    if isinstance(value, dict) and not value:
        return {}
    _object(value, _FIELDS, "Restricciones")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Restricciones: la versión admitida es 1.")
    window = _interval(value["window"], "Ventana del evento")
    start = _instant(window["start"], "Ventana del evento")
    end = _instant(window["end"], "Ventana del evento")
    if end - start > timedelta(minutes=MAX_WINDOW_MINUTES):
        raise ValueError("La ventana del evento no puede superar 24 horas en este prototipo.")
    maximum = value["max_duration_minutes"]
    if type(maximum) is not int or not 1 <= maximum <= 1440:
        raise ValueError("La duración máxima por sesión debe ser un entero de 1 a 1440 minutos.")
    speakers, speaker_names = _catalog(value["speakers"], "Ponentes", MAX_SPEAKERS, start.tzinfo)
    resources, resource_names = _catalog(value["resources"], "Recursos", MAX_RESOURCES, start.tzinfo)
    sessions, by_id = [], {}
    for item in _list(value["sessions"], MAX_SESSIONS, "Sesiones autorizadas"):
        _object(item, {"session_id", "allowed_speakers", "allowed_resources"}, "Sesión autorizada")
        identifier = _identifier(item["session_id"], "Sesión autorizada")
        if identifier in by_id:
            raise ValueError(f"Sesión autorizada duplicada: {identifier}.")
        record = {
            "session_id": identifier,
            "allowed_speakers": _allowed(item["allowed_speakers"], speaker_names, f"{identifier}, ponentes", MAX_SPEAKERS),
            "allowed_resources": _allowed(item["allowed_resources"], resource_names, f"{identifier}, recursos", MAX_RESOURCES),
        }
        sessions.append(record)
        by_id[identifier] = record
    fixed, seen = [], set()
    fixed_fields = {"session_id", "start", "speaker", "resource", "duration_minutes"}
    for item in _list(value["fixed"], MAX_SESSIONS, "Decisiones fijadas"):
        if not isinstance(item, dict) or "session_id" not in item or not set(item) <= fixed_fields or len(item) < 2:
            raise ValueError("Decisión fijada: indica session_id y al menos start, speaker, resource o duration_minutes.")
        identifier = _identifier(item["session_id"], "Decisión fijada")
        if identifier not in by_id or identifier in seen:
            raise ValueError(f"Decisión fijada ajena o duplicada: {identifier}.")
        seen.add(identifier)
        record = {"session_id": identifier}
        if "start" in item:
            record["start"] = _instant(item["start"], f"{identifier}, inicio fijado", start.tzinfo).isoformat()
        for field, known in (("speaker", speaker_names), ("resource", resource_names)):
            if field in item:
                name = _text(item[field], f"{identifier}, {field} fijado", blank=True)
                if name and _name(name) not in known:
                    raise ValueError(f"{identifier}: la asignación fijada no figura en el catálogo autorizado.")
                record[field] = known[_name(name)] if name else ""
        if "duration_minutes" in item:
            duration = item["duration_minutes"]
            if type(duration) is not int or not 1 <= duration <= 1440:
                raise ValueError(f"{identifier}: duración fijada inválida.")
            record["duration_minutes"] = duration
        fixed.append(record)
    return {
        "version": 1, "window": window, "max_duration_minutes": maximum,
        "speakers": speakers, "resources": resources,
        "sessions": sorted(sessions, key=lambda item: item["session_id"]),
        "fixed": sorted(fixed, key=lambda item: item["session_id"]),
    }


def _inside(start, end, slots):
    return any(_instant(slot["start"], "Disponibilidad") <= start and end <= _instant(slot["end"], "Disponibilidad") for slot in slots)


def _busy(start, end, slots):
    return any(start < _instant(slot["end"], "Reserva") and _instant(slot["start"], "Reserva") < end for slot in slots)


def _grid(start):
    return not start.second and not start.microsecond and start.minute % GRID_MINUTES == 0


def _context(constraints):
    return (
        {item["session_id"]: item for item in constraints["sessions"]},
        {item["session_id"]: item for item in constraints["fixed"]},
        {kind: {_name(item["name"]): item for item in constraints[collection]}
         for kind, collection in (("speaker", "speakers"), ("resource", "resources"))},
    )


def _constraint_errors(payload, constraints):
    errors = []
    specs, fixed, catalogs = _context(constraints)
    sessions = payload["sessions"]
    if len(sessions) > MAX_SESSIONS:
        errors.append(f"El prototipo admite hasta {MAX_SESSIONS} sesiones con restricciones.")
    identifiers = {session["id"].strip() for session in sessions}
    if identifiers != set(specs):
        errors.append("Las sesiones deben coincidir exactamente con los identificadores autorizados en las restricciones.")
    window_start = _instant(constraints["window"]["start"], "Ventana")
    window_end = _instant(constraints["window"]["end"], "Ventana")
    scheduled = []
    for session in sessions[:MAX_SESSIONS]:
        identifier = session["id"].strip()
        if identifier not in specs:
            continue
        spec, lock = specs[identifier], fixed.get(identifier, {})
        try:
            start = _instant(session["start"], identifier, window_start.tzinfo)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        duration = session["duration_minutes"]
        if type(duration) is not int or not 1 <= duration <= 1440:
            continue  # Already reported by the base validator.
        try:
            end = start + timedelta(minutes=duration)
        except OverflowError:
            errors.append(f"{identifier}: el final está fuera del rango permitido.")
            continue
        if duration > constraints["max_duration_minutes"]:
            errors.append(f"{identifier}: supera la duración máxima por sesión.")
        if start < window_start or end > window_end:
            errors.append(f"{identifier}: el horario está fuera de la ventana autorizada.")
        if not _grid(start):
            errors.append(f"{identifier}: el inicio debe estar en la cuadrícula de 15 minutos de la ventana del evento.")
        for field, allowed_field, noun in (("speaker", "allowed_speakers", "ponente"), ("resource", "allowed_resources", "recurso")):
            name = _name(session[field])
            allowed = {_name(value) for value in spec[allowed_field]} or {""}
            if name not in allowed:
                errors.append(f"{identifier}: {noun} fuera de la lista habilitada.")
            elif name:
                item = catalogs[field][name]
                if not _inside(start, end, item["windows"]):
                    errors.append(f"{identifier}: {noun} sin disponibilidad suficiente.")
                if _busy(start, end, item["busy"]):
                    errors.append(f"{identifier}: {noun} tiene una reserva que se solapa.")
            if field in lock and name != _name(lock[field]):
                errors.append(f"{identifier}: se modificó el {noun} fijado sin aprobación.")
        if "start" in lock and start != _instant(lock["start"], identifier):
            errors.append(f"{identifier}: se modificó el inicio fijado sin aprobación.")
        if "duration_minutes" in lock and duration != lock["duration_minutes"]:
            errors.append(f"{identifier}: se modificó la duración fijada sin aprobación.")
        # The legacy checker casefolds names but does not compose Unicode. Keep
        # NFC-equivalent spellings from evading shared-person/resource conflicts.
        for previous, previous_start, previous_end, previous_speaker, previous_resource in scheduled:
            if start < previous_end and previous_start < end:
                for field, previous_name, noun in (("speaker", previous_speaker, "ponente"), ("resource", previous_resource, "recurso")):
                    name = _name(session[field])
                    if name and name == previous_name:
                        errors.append(f"{previous} y {identifier}: se solapan para el mismo {noun} normalizado.")
        scheduled.append((identifier, start, end, _name(session["speaker"]), _name(session["resource"])))
    return errors


def validate_event_plan(payload, constraints):
    """Return Spanish errors, including the existing complete validate_plan check."""
    errors = validate_plan(payload)
    try:
        canonical = normalize_constraints(constraints)
    except ValueError as exc:
        return errors + [str(exc)]
    if not canonical:
        return errors
    if errors and _structural_errors(payload, canonical):
        return errors
    return errors + _constraint_errors(payload, canonical)


def _blocked(errors, reason, steps=0, *, fixed=False):
    options = [{"description": "Revisar y confirmar nuevas disponibilidades o una ventana distinta antes de preparar otra propuesta.", "requires_confirmation": True}]
    if fixed:
        options.append({"description": "Revisar las decisiones fijadas y liberar solo las que el organizador autorice; todavía no se ha liberado ninguna.", "requires_confirmation": True})
    return {"status": "blocked", "payload": None, "errors": errors, "reason": reason, "options": options, "steps": steps}


def _structural_errors(payload, constraints):
    # Only scheduling fields are repaired. Reusing the base validator on neutral
    # scheduling values still rejects malformed content, graph cycles and states.
    neutral = deepcopy(payload)
    if isinstance(neutral, dict) and isinstance(neutral.get("sessions"), list):
        locks = {item["session_id"]: item for item in constraints["fixed"]}
        for index, session in enumerate(neutral["sessions"][:MAX_SESSIONS]):
            if isinstance(session, dict) and set(session) == _SESSION_FIELDS:
                identifier = session["id"].strip() if isinstance(session["id"], str) else None
                lock = locks.get(identifier, {})
                if "duration_minutes" in lock:
                    session["duration_minutes"] = lock["duration_minutes"]
                if isinstance(session["start"], str) and len(session["start"]) <= 64:
                    session["start"] = (datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)).isoformat()
                for field in ("speaker", "resource"):
                    if isinstance(session[field], str) and len(session[field]) <= 200:
                        session[field] = ""
    return validate_plan(neutral)


def _choices(session, spec, lock, constraints, catalogs, preserve_start):
    window_start = _instant(constraints["window"]["start"], "Ventana")
    window_end = _instant(constraints["window"]["end"], "Ventana")
    duration = lock.get("duration_minutes", session["duration_minutes"])
    if duration > constraints["max_duration_minutes"]:
        return []
    try:
        original = _instant(session["start"], "Inicio original", window_start.tzinfo)
    except ValueError:
        original = None
    if "start" in lock:
        starts = [_instant(lock["start"], "Inicio fijado", window_start.tzinfo)]
    elif preserve_start:
        starts = [original] if original is not None else []
    else:
        try:
            first = window_start.replace(second=0, microsecond=0)
            if first < window_start:
                first += timedelta(minutes=1)
            first += timedelta(minutes=(-first.minute) % GRID_MINUTES)
        except OverflowError:
            return []
        count = int((window_end - first).total_seconds() // (GRID_MINUTES * 60)) + 1
        starts = [first + timedelta(minutes=GRID_MINUTES * index) for index in range(max(0, count))]
    speakers = [lock["speaker"]] if "speaker" in lock else spec["allowed_speakers"] or [""]
    resources = [lock["resource"]] if "resource" in lock else spec["allowed_resources"] or [""]
    choices = []
    for start in starts:
        try:
            end = start + timedelta(minutes=duration)
        except OverflowError:
            continue
        if start < window_start or end > window_end or not _grid(start):
            continue
        for speaker in speakers:
            for resource in resources:
                assignment = {"speaker": speaker, "resource": resource}
                valid = True
                for field, allowed_field in (("speaker", "allowed_speakers"), ("resource", "allowed_resources")):
                    name = _name(assignment[field])
                    if name not in ({_name(value) for value in spec[allowed_field]} or {""}):
                        valid = False
                        break
                    if name:
                        item = catalogs[field][name]
                        if not _inside(start, end, item["windows"]) or _busy(start, end, item["busy"]):
                            valid = False
                            break
                if valid:
                    changes = int(start != original) + sum(_name(assignment[field]) != _name(session[field]) for field in assignment)
                    choices.append((changes, start, end, speaker, resource, duration))
    return sorted(choices, key=lambda item: (item[0], item[1], _name(item[3]), _name(item[4])))


def _conflicts(choice, assigned):
    _, start, end, speaker, resource, _ = choice
    return any(start < other[2] and other[1] < end and (
        (speaker and _name(speaker) == _name(other[3])) or
        (resource and _name(resource) == _name(other[4]))
    ) for other in assigned.values())


def repair_plan(payload, constraints):
    """Return bounded JSON with a validated candidate or a truthful blocked result.

    At most 50,000 candidate placements across both searches; no wall clock,
    randomness, external lookup or optimality claim. No active plan is modified.
    A blocked payload is always null and options always require confirmation.
    """
    try:
        canonical = normalize_constraints(constraints)
    except ValueError as exc:
        return _blocked([str(exc)], "Las restricciones necesitan corregirse antes de buscar una propuesta.")
    original_errors = validate_event_plan(payload, canonical)
    if not original_errors:
        return {"status": "candidate", "payload": deepcopy(payload), "errors": [], "reason": "La propuesta respeta las restricciones declaradas; requiere revisión y aprobación humana.", "options": [], "steps": 0}
    if not canonical:
        return _blocked(original_errors, "Sin restricciones declaradas no se pueden inferir horarios o asignaciones alternativos.")
    structural = _structural_errors(payload, canonical)
    if structural:
        return _blocked(structural, "El contenido o las dependencias deben corregirse antes de reparar la agenda.", fixed=bool(canonical["fixed"]))
    specs, locks, catalogs = _context(canonical)
    sessions = payload["sessions"]
    if len(sessions) > MAX_SESSIONS or {item["id"].strip() for item in sessions} != set(specs):
        return _blocked(original_errors, "La cantidad o los identificadores de las sesiones no coinciden con el alcance autorizado.", fixed=bool(locks))
    steps = 0
    exhausted = False
    for preserve_start in (True, False):
        choices = {item["id"].strip(): _choices(item, specs[item["id"].strip()], locks.get(item["id"].strip(), {}), canonical, catalogs, preserve_start) for item in sessions}
        order = sorted(choices, key=lambda identifier: (len(choices[identifier]), identifier))
        assigned = {}

        def search(index):
            nonlocal steps, exhausted
            if index == len(order):
                return True
            identifier = order[index]
            for choice in choices[identifier]:
                if steps >= MAX_SEARCH_STEPS:
                    exhausted = True
                    return False
                steps += 1
                if not _conflicts(choice, assigned):
                    assigned[identifier] = choice
                    if search(index + 1):
                        return True
                    del assigned[identifier]
                    if exhausted:
                        return False
            return False

        if search(0):
            candidate = deepcopy(payload)
            for session in candidate["sessions"]:
                _, start, _, speaker, resource, duration = assigned[session["id"].strip()]
                # Preserve equivalent source labels and timestamps when possible.
                try:
                    original_start = _instant(session["start"], "Inicio original")
                except ValueError:
                    original_start = None
                if start != original_start:
                    session["start"] = start.isoformat()
                for field, name in (("speaker", speaker), ("resource", resource)):
                    if _name(session[field]) != _name(name):
                        session[field] = name
                session["duration_minutes"] = duration
            remaining = validate_event_plan(candidate, canonical)
            if remaining:
                return _blocked(remaining, "La propuesta calculada no superó la validación final; no puede aprobarse.", steps, fixed=bool(locks))
            return {"status": "candidate", "payload": candidate, "errors": [], "reason": "Se preparó una alternativa con disponibilidades declaradas y decisiones fijadas; requiere revisión y aprobación humana.", "options": [], "steps": steps}
        if exhausted:
            break
    reason = ("Se alcanzó el límite de búsqueda; no se ha demostrado que sea imposible encontrar una alternativa."
              if exhausted else "No se encontró una agenda factible en la cuadrícula y el alcance declarados; se necesitan decisiones del organizador.")
    return _blocked(original_errors, reason, steps, fixed=bool(locks))
