"""Bounded plan validation, independent of Django and of an AI provider.

This is a constraint checker, not an optimizer. It never claims optimality or
that suggested people/resources actually exist or are available.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta

MAX_SESSIONS = 200
MAX_TASKS = 500
MAX_RISKS = 50
MAX_DEPENDENCIES = 50


def _string(value, label, errors, *, limit, allow_blank=False):
    if not isinstance(value, str) or len(value) > limit or (not allow_blank and not value.strip()):
        errors.append(f"{label}: se requiere texto {'opcional de' if allow_blank else 'de 1 a'} {limit} caracteres como máximo.")
        return False
    return True


def _keys(value, required, label, errors):
    if not isinstance(value, dict):
        errors.append(f"{label}: se requiere un objeto.")
        return False
    if set(value) != set(required):
        errors.append(f"{label}: los campos permitidos y requeridos son {', '.join(sorted(required))}.")
        return False
    return True


def _items(payload, key, limit, errors):
    value = payload.get(key)
    if not isinstance(value, list) or len(value) > limit:
        errors.append(f"{key}: se requiere una lista con un máximo de {limit} elementos.")
        return []
    return value


def validate_plan(payload):
    """Return Spanish validation errors without trusting types or metadata.

    Task states are initially pending: generated content cannot certify that
    real-world preparation or execution took place. Later task evidence will
    require its own authorized transition, outside this plan payload.
    """
    errors = []
    if not _keys(payload, {"title", "summary", "sessions", "tasks", "risks"}, "Plan", errors):
        return errors
    _string(payload["title"], "Título", errors, limit=200)
    _string(payload["summary"], "Resumen", errors, limit=4000)
    sessions = _items(payload, "sessions", MAX_SESSIONS, errors)
    tasks = _items(payload, "tasks", MAX_TASKS, errors)
    risks = _items(payload, "risks", MAX_RISKS, errors)
    for index, risk in enumerate(risks, start=1):
        _string(risk, f"Riesgo {index}", errors, limit=1000)

    session_ids = set()
    assignments = defaultdict(list)
    for index, session in enumerate(sessions, start=1):
        label = f"Sesión {index}"
        if not _keys(session, {"id", "title", "start", "duration_minutes", "speaker", "resource"}, label, errors):
            continue
        if _string(session["id"], f"{label}, identificador", errors, limit=64):
            identifier = session["id"].strip()
            if identifier in session_ids:
                errors.append(f"{label}: identificador duplicado ({identifier}).")
            session_ids.add(identifier)
        _string(session["title"], f"{label}, título", errors, limit=200)
        speaker_ok = _string(session["speaker"], f"{label}, ponente", errors, limit=200, allow_blank=True)
        resource_ok = _string(session["resource"], f"{label}, recurso", errors, limit=200, allow_blank=True)
        duration = session["duration_minutes"]
        duration_ok = type(duration) is int and 1 <= duration <= 1440
        if not duration_ok:
            errors.append(f"{label}: la duración debe ser un entero entre 1 y 1440 minutos.")
        start = None
        try:
            if not isinstance(session["start"], str) or len(session["start"]) > 64:
                raise ValueError
            start = datetime.fromisoformat(session["start"].replace("Z", "+00:00"))
            if start.tzinfo is None or start.utcoffset() is None:
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            errors.append(f"{label}: el inicio debe ser una fecha ISO 8601 con zona horaria.")
        if start is not None and start.tzinfo is not None and duration_ok:
            try:
                end = start + timedelta(minutes=duration)
            except OverflowError:
                errors.append(f"{label}: la fecha final está fuera del rango permitido.")
                continue
            for kind, valid in (("speaker", speaker_ok), ("resource", resource_ok)):
                if valid and session[kind].strip():
                    key = (kind, " ".join(session[kind].split()).casefold())
                    assignments[key].append((start, end, index))

    for (kind, name), intervals in assignments.items():
        intervals.sort(key=lambda item: item[0])
        if not intervals:
            continue
        furthest_end = intervals[0][1]
        furthest_index = intervals[0][2]
        for start, end, index in intervals[1:]:
            if start < furthest_end:
                noun = "ponente" if kind == "speaker" else "recurso"
                errors.append(f"Las sesiones {furthest_index} y {index} se solapan para el mismo {noun}: {name}.")
            if end > furthest_end:
                furthest_end, furthest_index = end, index

    graph = {}
    for index, task in enumerate(tasks, start=1):
        label = f"Tarea {index}"
        if not _keys(task, {"id", "title", "depends_on", "status", "purpose"}, label, errors):
            continue
        id_ok = _string(task["id"], f"{label}, identificador", errors, limit=64)
        _string(task["title"], f"{label}, título", errors, limit=200)
        _string(task["purpose"], f"{label}, propósito", errors, limit=1000)
        if task["status"] != "pending":
            errors.append(f"{label}: una propuesta solo puede crear tareas pendientes (pending).")
        dependencies = task["depends_on"]
        if not isinstance(dependencies, list) or len(dependencies) > MAX_DEPENDENCIES:
            errors.append(f"{label}: depends_on debe contener hasta {MAX_DEPENDENCIES} identificadores.")
            dependencies = []
        valid_dependencies = []
        for dependency in dependencies:
            if _string(dependency, f"{label}, dependencia", errors, limit=64):
                valid_dependencies.append(dependency.strip())
        if len(valid_dependencies) != len(set(valid_dependencies)):
            errors.append(f"{label}: no se permite repetir una dependencia.")
        if id_ok:
            identifier = task["id"].strip()
            if identifier in graph:
                errors.append(f"{label}: identificador duplicado ({identifier}).")
            graph[identifier] = valid_dependencies

    for identifier, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in graph:
                errors.append(f"La tarea {identifier} depende de una tarea inexistente: {dependency}.")
    # Kahn's algorithm avoids recursive stack exhaustion on untrusted graphs.
    indegree = {identifier: 0 for identifier in graph}
    children = defaultdict(list)
    for identifier, dependencies in graph.items():
        for dependency in set(dependencies):
            if dependency in graph:
                indegree[identifier] += 1
                children[dependency].append(identifier)
    ready = deque(identifier for identifier, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        identifier = ready.popleft()
        visited += 1
        for child in children[identifier]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(graph):
        errors.append("Las dependencias de tareas contienen un ciclo.")
    return errors


def plan_impact(previous, proposed):
    """Compare validated payloads by stable local IDs; does not invent impact."""
    result = {}
    for collection in ("sessions", "tasks"):
        before = {item["id"]: item for item in (previous or {}).get(collection, [])}
        after = {item["id"]: item for item in proposed.get(collection, [])}
        result[collection] = {
            "added": sorted(after.keys() - before.keys()),
            "removed": sorted(before.keys() - after.keys()),
            "changed": sorted(key for key in before.keys() & after.keys() if before[key] != after[key]),
        }
    result["summary_changed"] = (previous or {}).get("summary") != proposed.get("summary")
    result["risks_changed"] = (previous or {}).get("risks", []) != proposed.get("risks", [])
    return result
