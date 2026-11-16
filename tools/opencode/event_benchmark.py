"""Synthetic six-event scheduling benchmark; never writes to SparkX's database.

The reference enumerates a deliberately small finite search space. A feasible
reference is not an AI result. Each remote task stays within the existing broker.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import random
import re
import threading

from apps.planning.domain import validate_plan
from . import runner
from .catalog import ALLOWED_MODELS, MODEL_POLICIES
from .comparison import reported_cost
from .costs import summarize_usage


ROOT = runner.PROJECT_ROOT / "Temporal" / "opencode" / "event-benchmark"
SEED = 142026
TITLES = (
    "Claves para desarrollar Tesis I, II y III",
    "Tu ruta hacia el Grado de Maestro",
    "De la idea al proyecto de tesis aprobado",
    "Del proyecto a la sustentación de tesis",
    "Últimos pasos para obtener tu Grado de Maestro",
    "Claves para desarrollar Tesis I, II y III",
)
DAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado")
SPEAKERS = {
    "P1": {"name": "Expositor ficticio A", "focus": "Metodología y proyecto de tesis"},
    "P2": {"name": "Expositor ficticio B", "focus": "Escritura y sustentación"},
    "P3": {"name": "Expositor ficticio C", "focus": "Ruta académica y cierre"},
}
CHANGE_KINDS = ("substitute", "booking_conflict", "shift", "unavailable", "locked_decision", "shift_and_substitute")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def timestamp(day, minutes):
    return (datetime(2026, 11, 16 + day, tzinfo=timezone(timedelta(hours=-5)))
            + timedelta(minutes=minutes)).isoformat(timespec="minutes")


def instant(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("Fecha no válida")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() != timedelta(hours=-5):
        raise ValueError("Se requiere zona horaria America/Lima (-05:00)")
    return result


def overlaps(start, end, reservation):
    return start < instant(reservation["end"]) and instant(reservation["start"]) < end


def make_cases(seed=SEED):
    rng = random.Random(seed)
    cases = []
    for day, title in enumerate(TITLES):
        base = rng.choice((16 * 60, 17 * 60, 18 * 60, 19 * 60))
        people = list(SPEAKERS)
        rng.shuffle(people)
        sessions = []
        for index in range(3):
            sessions.append({"id": f"S{index + 1}", "title": (
                "Orientación y conceptos", "Aplicación guiada", "Preguntas y próximos pasos")[index],
                "duration_minutes": 30, "eligible_speakers": [people[index], people[(index + 1) % 3]],
                "preferred_speaker": people[index]})
        availability = {person: [{"start": timestamp(day, base), "end": timestamp(day, base + 150)}]
                        for person in SPEAKERS}
        bookings = []
        for person in SPEAKERS:
            earlier = rng.choice((12 * 60, 13 * 60, 14 * 60))
            bookings.append({"speaker_id": person, "start": timestamp(day, earlier),
                             "end": timestamp(day, earlier + 30), "reason": "Otra actividad ficticia"})
        preferred = [{"id": session["id"], "start": timestamp(day, base + index * 30),
                      "speaker_id": session["preferred_speaker"]} for index, session in enumerate(sessions)]
        case = {"id": f"E{day + 1:02d}", "day": DAYS[day], "date": f"2026-11-{16 + day}",
                "institution": "GICA" if day == 5 else "UNAC", "title": title,
                "timezone": "America/Lima", "synthetic": True,
                "window": {"start": timestamp(day, base), "end": timestamp(day, base + 150)},
                "rules": {"grid_minutes": 15, "contiguous_order": ["S1", "S2", "S3"],
                          "fixed_duration_minutes": 30, "resource": "Sala virtual ficticia"},
                "sessions": sessions, "preferred": preferred,
                "baseline": {"availability": availability, "bookings": bookings, "locks": []},
                "change_kind": CHANGE_KINDS[day]}
        changed = deepcopy(case["baseline"])
        if day in (0, 4, 5):
            changed["availability"][people[0]] = []
        if day == 1:
            changed["bookings"].append({"speaker_id": people[1], "start": timestamp(day, base + 30),
                "end": timestamp(day, base + 60), "reason": "Nueva reserva ficticia confirmada"})
        if day == 2:
            for person in SPEAKERS:
                changed["availability"][person] = [{"start": timestamp(day, base + 30), "end": timestamp(day, base + 150)}]
        if day == 3:
            changed["availability"] = {person: [] for person in SPEAKERS}
        if day == 4:
            case["baseline"]["locks"] = [deepcopy(preferred[0])]
            changed["locks"] = [deepcopy(preferred[0])]
        if day == 5:
            changed["bookings"].append({"speaker_id": people[1], "start": timestamp(day, base),
                "end": timestamp(day, base + 30), "reason": "El sustituto también está ocupado al inicio"})
        descriptions = (
            "El expositor preferido de S1 cancela toda su disponibilidad del día. Busca un sustituto habilitado.",
            "El expositor preferido de S2 tiene una reserva confirmada durante S2. Busca una asignación válida.",
            "Ningún expositor puede iniciar en los primeros 30 minutos. Busca otro horario dentro de la ventana.",
            "Los tres expositores cancelan toda la ventana del día. Explica el bloqueo y solicita nuevas opciones sin inventar disponibilidad.",
            "El ponente de S1 cancela, pero su asignación y horario están confirmados y bloqueados. No cambies esa decisión sin aprobación; propone opciones pendientes.",
            "Cancela el ponente de S1 y su sustituto está ocupado al inicio. Busca otra hora y una asignación válida.",
        )
        case["change_description"] = descriptions[day]
        case["changed"] = changed
        cases.append(case)
    return cases


def schedule_errors(case, phase, sessions):
    errors = []
    if not isinstance(sessions, list) or len(sessions) != 3:
        return ["Se requieren exactamente tres sesiones."]
    by_id = {}
    parsed = []
    state = case[phase]
    for item in sessions:
        if not isinstance(item, dict) or set(item) != {"id", "start", "speaker_id"}:
            errors.append("Esquema de sesión incorrecto.")
            continue
        if not isinstance(item["id"], str) or not isinstance(item["speaker_id"], str):
            errors.append("Identificadores de sesión o expositor incorrectos.")
            continue
        if item["id"] in by_id or item["id"] not in {s["id"] for s in case["sessions"]}:
            errors.append("Sesión duplicada o ajena.")
            continue
        by_id[item["id"]] = item
        spec = next(s for s in case["sessions"] if s["id"] == item["id"])
        if item["speaker_id"] not in spec["eligible_speakers"]:
            errors.append("Expositor ajeno o no habilitado para la sesión.")
            continue
        try:
            start = instant(item["start"])
        except (ValueError, TypeError, OverflowError):
            errors.append("Fecha o zona horaria incorrecta.")
            continue
        end = start + timedelta(minutes=30)
        if start < instant(case["window"]["start"]) or end > instant(case["window"]["end"]):
            errors.append("Horario fuera de la ventana autorizada.")
        if start.second or start.microsecond or start.minute % 15:
            errors.append("Horario fuera de la cuadrícula de 15 minutos.")
        slots = state["availability"].get(item["speaker_id"], [])
        if not any(instant(slot["start"]) <= start and end <= instant(slot["end"]) for slot in slots):
            errors.append("Expositor sin disponibilidad suficiente.")
        if any(r["speaker_id"] == item["speaker_id"] and overlaps(start, end, r) for r in state["bookings"]):
            errors.append("Expositor con otra reserva confirmada.")
        parsed.append((item["id"], start, end, item["speaker_id"]))
    if set(by_id) != {"S1", "S2", "S3"}:
        errors.append("Falta una sesión obligatoria.")
    if len(parsed) == 3:
        ordered = sorted(parsed)
        if any(ordered[i][2] != ordered[i + 1][1] for i in range(2)):
            errors.append("No se respetan el orden y los bloques consecutivos de 30 minutos.")
        payload = {"title": case["title"], "summary": "Ensayo ficticio", "tasks": [], "risks": [],
            "sessions": [{"id": item[0], "title": item[0], "start": item[1].isoformat(),
                          "duration_minutes": 30, "speaker": item[3], "resource": case["rules"]["resource"]} for item in parsed]}
        errors += validate_plan(payload)
    for lock in state["locks"]:
        candidate = by_id.get(lock["id"])
        try:
            unchanged = (candidate is not None and candidate["speaker_id"] == lock["speaker_id"]
                         and instant(candidate["start"]) == instant(lock["start"]))
        except (ValueError, TypeError, KeyError, OverflowError):
            unchanged = False
        if not unchanged:
            errors.append("Se modificó una decisión confirmada sin aprobación.")
    return sorted(set(errors))


def solutions(case, phase):
    start = instant(case["window"]["start"])
    latest = instant(case["window"]["end"]) - timedelta(minutes=90)
    answers = []
    while start <= latest:
        for speakers in product(*(s["eligible_speakers"] for s in case["sessions"])):
            agenda = [{"id": f"S{i + 1}", "start": (start + timedelta(minutes=30 * i)).isoformat(timespec="minutes"),
                       "speaker_id": person} for i, person in enumerate(speakers)]
            if not schedule_errors(case, phase, agenda):
                answers.append(agenda)
        start += timedelta(minutes=15)
    return answers


def parse_answer(text):
    if not isinstance(text, str) or len(text) > 24000:
        raise ValueError("Respuesta ausente o demasiado extensa.")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, count=1)
        stripped = re.sub(r"\s*```$", "", stripped, count=1)
    # Accept a single object surrounded by ordinary explanation. Multiple
    # objects or trailing JSON remain an error, rather than choosing a success.
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0:
        raise ValueError("La respuesta no contiene el objeto JSON solicitado.")
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Clave JSON duplicada.")
            obj[key] = value
        return obj
    return json.loads(stripped[start:end + 1], object_pairs_hook=unique)


def evaluate(case, answer):
    errors = []
    if not isinstance(answer, dict) or set(answer) != {"event_id", "institution", "title", "baseline", "changed"}:
        return {"passed": False, "errors": ["Esquema principal incorrecto."], "phases": {}}
    for field, expected in (("event_id", case["id"]), ("institution", case["institution"]), ("title", case["title"])):
        if answer[field] != expected:
            errors.append(f"No se conservó {field}.")
    phases = {}
    for phase in ("baseline", "changed"):
        result = answer[phase]
        possible = bool(solutions(case, phase))
        problems = []
        if not isinstance(result, dict) or set(result) != {"status", "sessions", "reason", "options"}:
            problems.append("Esquema de fase incorrecto.")
        else:
            if not isinstance(result["reason"], str) or not result["reason"].strip() or len(result["reason"]) > 1200:
                problems.append("Falta explicación breve.")
            if result["status"] == "scheduled":
                problems += schedule_errors(case, phase, result["sessions"])
                if not possible:
                    problems.append("Presenta una agenda confirmable cuando no existe solución autorizada.")
            elif result["status"] == "blocked":
                if result["sessions"] != []:
                    problems.append("Una fase bloqueada no puede presentar sesiones como confirmables.")
                if possible:
                    problems.append("Declara bloqueo aunque hay alternativas factibles.")
                if not isinstance(result["options"], list) or not 1 <= len(result["options"]) <= 3:
                    problems.append("El bloqueo requiere de una a tres opciones pendientes de confirmación.")
            else:
                problems.append("Estado desconocido.")
            options = result["options"]
            if not isinstance(options, list) or len(options) > 3:
                problems.append("Opciones incorrectas.")
            else:
                for option in options:
                    if (not isinstance(option, dict) or set(option) != {"description", "requires_confirmation"}
                        or not isinstance(option["description"], str) or not 1 <= len(option["description"].strip()) <= 600
                        or option["requires_confirmation"] is not True):
                        problems.append("Una alternativa no confirmada se presenta sin requerir aprobación.")
        phases[phase] = {"passed": not problems, "feasible_reference": possible, "errors": sorted(set(problems))}
        errors += [phase + ": " + p for p in problems]
    return {"passed": not errors, "errors": sorted(set(errors)), "phases": phases}


PROMPT = (
    "Eres el organizador de UN SOLO evento ficticio. Lee inputs/01-caso.json.txt. "
    "Resuelve baseline y changed de forma independiente usando solo sus disponibilidades, reservas, "
    "ponentes habilitados y locks. Nunca inventes disponibilidad, cambies decisiones bloqueadas o "
    "confundas instituciones. Las tres sesiones duran 30min y son consecutivas S1,S2,S3; "
    "inicio en cuadrícula de15min dentro de window. Busca otro expositor o un inicio posterior si procede. "
    "Si no hay solución, status blocked, sessions vacías y opciones pendientes de aprobación. "
    "Devuelve SOLO un objeto JSON, sin markdown ni razonamiento extenso, con claves exactas: "
    "event_id,institution,title,baseline,changed. Cada fase tiene exactamente "
    "status (scheduled o blocked), sessions, reason (breve), options. "
    "Cada sesión: {id:S1/S2/S3,start:ISO8601con-05:00,speaker_id:P1/P2/P3}. "
    "Cada opción: {description:texto,requires_confirmation:true}. options puede ser[] si scheduled. "
    "No uses otras claves, no ejecutes código, no escribas archivos ni llames a otros agentes. "
    "Es una simulación; no organices ni anuncies actividades reales."
)


def prepare_case(case, model):
    directory = runner.prepare_task(PROMPT, mode="review", model=model, synthetic=True, accept_model_policy=True)
    data = {k: v for k, v in case.items() if k not in {"change_kind"}}
    data["speakers"] = SPEAKERS
    # The native read tool truncates long individual lines. Pretty JSON keeps
    # every field visible without extra reads or expanding the context limit.
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if max(map(len, text.splitlines()), default=0) > 1500:
        raise ValueError("Una línea del caso supera el máximo legible del ensayo.")
    raw = text.encode("utf-8")
    if len(raw) > runner.MAX_INPUT_BYTES:
        raise ValueError("El caso supera el contexto permitido.")
    target = directory / "inputs" / "01-caso.json.txt"
    target.write_bytes(raw)
    manifest_path = directory / "task.json"
    task = json.loads(manifest_path.read_text(encoding="utf-8"))
    task["inputs"] = [{"source": "synthetic:" + case["id"], "copy": "inputs/01-caso.json.txt",
                       "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}]
    task["benchmark_case"] = case["id"]
    write_json(manifest_path, task)
    return directory


def load_briefs(cases):
    briefs = {}
    for case in cases:
        path = ROOT / "briefs" / (case["id"] + ".json")
        brief = json.loads(path.read_text(encoding="utf-8-sig"))
        if any(brief.get(key) != case[key] for key in ("institution", "title")) or brief.get("event_id") != case["id"]:
            raise ValueError("La ficha del agente no corresponde a su evento: " + case["id"])
        for key in ("audience", "value_proposition", "promotional_copy", "cta"):
            if not isinstance(brief.get(key), str) or not 1 <= len(brief[key]) <= 1500:
                raise ValueError("Ficha incompleta del agente: " + case["id"])
        for key in ("session_titles", "preparation_tasks"):
            if (not isinstance(brief.get(key), list) or len(brief[key]) != 3
                or any(not isinstance(item, str) or not 1 <= len(item) <= 300 for item in brief[key])):
                raise ValueError("Sesiones o preparación incompletas: " + case["id"])
        assessment = evaluate(case, brief.get("reference_answer"))
        if not assessment["passed"]:
            raise ValueError("La referencia del agente no supera las reglas: " + case["id"] + " " + str(assessment["errors"]))
        briefs[case["id"]] = brief
    return briefs


def prepare_suite():
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "briefs").mkdir(exist_ok=True)
    matrix_path = ROOT / "matrix.json"
    if matrix_path.exists():
        raise ValueError("Ya existe una matriz; no se prepara ni ejecuta otra automáticamente.")
    cases = make_cases()
    briefs = load_briefs(cases)
    for case in cases:
        brief = briefs[case["id"]]
        case["marketing"] = {key: brief[key] for key in ("audience", "value_proposition", "promotional_copy", "cta")}
        for session, title in zip(case["sessions"], brief["session_titles"]):
            session["title"] = title
    write_json(ROOT / "cases.json", {"seed": SEED, "synthetic": True, "speakers": SPEAKERS, "cases": cases})
    reference = {}
    for case in cases:
        reference[case["id"]] = {phase: {"solutions": len(answers), "example": answers[0] if answers else None}
            for phase in ("baseline", "changed") for answers in [solutions(case, phase)]}
    write_json(ROOT / "reference.json", reference)
    matrix = []
    for case in cases:
        for model in ALLOWED_MODELS:
            task = prepare_case(case, model)
            matrix.append({"event_id": case["id"], "day": case["day"], "model": model,
                           "task_id": task.name, "state": "prepared"})
    write_json(matrix_path, matrix)
    return {"events": 6, "models": len(ALLOWED_MODELS), "prepared": len(matrix)}


def run_suite():
    """One attempt per cell, max two broker processes; no paid fallback/retry."""
    cases = {case["id"]: case for case in make_cases()}
    matrix = json.loads((ROOT / "matrix.json").read_text(encoding="utf-8"))
    lock = threading.Lock()
    write_json(ROOT / "controller.json", {"pid": os.getpid(), "max_parallel": 2, "state": "running",
        "started_at": datetime.now(timezone.utc).isoformat(), "stop_file": str(ROOT / "STOP")})

    def work(row):
        original = row
        row = deepcopy(original)
        if (ROOT / "STOP").exists():
            print(json.dumps({"event": row["event_id"], "model": row["model"], "state": "not_started_stopped"}), flush=True)
            return row
        directory = runner.task_directory(row["task_id"])
        result_path = directory / "result.json"
        try:
            if result_path.exists():
                report = json.loads(result_path.read_text(encoding="utf-8"))
            elif (directory / ".execution-claim").exists():
                raise ValueError("La tarea quedó reclamada sin resultado; no se repite.")
            else:
                report = runner.run_task(row["task_id"])
            row["state"] = report["status"]
            row["seconds"] = report.get("seconds")
            row["observed_steps"] = report.get("observed_steps")
            row["usage"] = summarize_usage(report.get("observed_tokens"))
            row["reported_cost"] = reported_cost(report.get("reported_cost"), report.get("observed_steps"))
            if report.get("counters_incomplete") or report["status"] != "review_required":
                row["usage"]["complete"] = False
                row["reported_cost"].update(total=None, complete=False)
            text_path = directory / "outputs" / "respuesta.md"
            if report["status"] == "review_required" and text_path.exists():
                try:
                    answer = parse_answer(text_path.read_text(encoding="utf-8"))
                    write_json(directory / "benchmark-answer.json", answer)
                    row["evaluation"] = evaluate(cases[row["event_id"]], answer)
                except (ValueError, TypeError, KeyError, OverflowError) as error:
                    row["evaluation"] = {"passed": False, "errors": [str(error)], "phases": {}}
            else:
                row["evaluation"] = {"passed": False, "errors": [report.get("error", "No hubo respuesta completa utilizable.")], "phases": {}}
        except Exception as error:
            row.update(state="failed_before_or_during_inference", error=str(error), evaluation={"passed": False, "errors": [str(error)], "phases": {}})
        with lock:
            original.clear()
            original.update(row)
            write_json(ROOT / "matrix.json", matrix)
            print(json.dumps({"event": row["event_id"], "model": row["model"], "state": row["state"],
                              "passed": row["evaluation"]["passed"], "seconds": row.get("seconds")}), flush=True)
        return row

    pending = [row for row in matrix if "evaluation" not in row]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(work, row) for row in pending]):
            future.result()
    write_json(ROOT / "controller.json", {"pid": os.getpid(), "max_parallel": 2, "state": "finished",
        "finished_at": datetime.now(timezone.utc).isoformat()})
    summarize_suite()


def check_shared_calendar(answers, phase):
    """Check one model's six-event week, without merging different models."""
    payload = {"title": "Semana ficticia UNAC / GICA", "summary": "Calendario de tres expositores compartidos",
               "sessions": [], "tasks": [], "risks": []}
    missing = []
    scheduled = blocked = 0
    for case in make_cases():
        answer = answers.get(case["id"])
        if answer is None:
            missing.append(case["id"])
            continue
        review = evaluate(case, answer)
        identity_ok = isinstance(answer, dict) and all(answer.get(key) == value for key, value in (
            ("event_id", case["id"]), ("title", case["title"]), ("institution", case["institution"])))
        if not identity_ok or not review.get("phases", {}).get(phase, {}).get("passed"):
            missing.append(case["id"])
            continue
        proposal = answer[phase]
        if proposal["status"] == "blocked":
            blocked += 1
        else:
            scheduled += 1
            for session in proposal["sessions"]:
                payload["sessions"].append({"id": case["id"] + ":" + session["id"], "title": session["id"],
                    "start": session["start"], "duration_minutes": 30, "speaker": session["speaker_id"],
                    "resource": case["rules"]["resource"]})
    errors = validate_plan(payload)
    return {"complete": not missing, "passed": not missing and not errors,
            "scheduled_events": scheduled, "blocked_events": blocked, "missing_or_invalid_events": missing,
            "cross_event_errors": errors}


def summarize_suite():
    matrix = json.loads((ROOT / "matrix.json").read_text(encoding="utf-8"))
    groups = {}
    for model in ALLOWED_MODELS:
        rows = [r for r in matrix if r["model"] == model]
        durations = [r["seconds"] for r in rows if isinstance(r.get("seconds"), (int, float))]
        usage = [r.get("usage", {}).get("tokens", {}).get("total") for r in rows]
        costs = [r.get("reported_cost", {}).get("total") for r in rows]
        groups[model] = {"planned": len(rows), "evaluated": sum("evaluation" in r for r in rows),
            "passed": sum(r.get("evaluation", {}).get("passed", False) for r in rows),
            "complete_responses": sum(r.get("state") == "review_required" for r in rows),
            "known_tokens": sum(value for value in usage if type(value) is int),
            "unknown_token_receipts": sum(not r.get("usage", {}).get("complete", False) for r in rows),
            "reported_cost_known_subtotal": str(sum((Decimal(v) for v in costs if v is not None), Decimal(0))),
            "unknown_cost_receipts": sum(v is None for v in costs),
            "mean_completed_process_seconds": round(sum(durations) / len(durations), 3) if durations else None}
        answers = {}
        for row in rows:
            answer_path = runner.task_directory(row["task_id"]) / "benchmark-answer.json"
            if row.get("state") == "review_required" and answer_path.exists():
                answers[row["event_id"]] = json.loads(answer_path.read_text(encoding="utf-8"))
        groups[model]["shared_calendar"] = {phase: check_shared_calendar(answers, phase) for phase in ("baseline", "changed")}
    summary = {"synthetic": True, "seed": SEED, "events": 6, "models": groups,
               "planned_cells": len(matrix), "evaluated_cells": sum("evaluation" in r for r in matrix),
               "passed_cells": sum(r.get("evaluation", {}).get("passed", False) for r in matrix),
               "product_database_changed": False, "paid_models_invoked": False,
               "limits": ["Seis casos controlados, una muestra por modelo/caso; sin conclusión estadística de superioridad.",
                          "No es una integración del modelo dentro del agente de eventos ni una prueba de carga.",
                          "Los estados de fallo y contadores ausentes se conservan; los subtotales conocidos no son gasto total verificado."]}
    write_json(ROOT / "summary.json", summary)
    lines = ["# Ensayo ficticio UNAC / GICA", "", "No es una agenda oficial ni un anuncio. Datos y expositores ficticios.", "",
             "| Día | Institución | Evento | Cambio probado |", "| --- | --- | --- | --- |"]
    for c in make_cases():
        lines.append(f"| {c['day']} | {c['institution']} | {c['title']} | {c['change_description']} |")
    lines += ["", "## Organización por los seis agentes de prueba", "",
              "Propuestas locales de los agentes, verificadas con reglas. No se atribuyen a los modelos gratuitos.", ""]
    for case in make_cases():
        brief_path = ROOT / "briefs" / (case["id"] + ".json")
        if not brief_path.exists():
            continue
        brief = json.loads(brief_path.read_text(encoding="utf-8-sig"))
        lines += [f"### {case['day']} · {case['institution']} · {case['title']}", "",
                  "**Público:** " + brief["audience"], "", "**Propuesta:** " + brief["value_proposition"], "",
                  brief["promotional_copy"], "", "**Invitación:** " + brief["cta"], "",
                  "| Sesión | Agenda inicial · Lima | Expositor ficticio |", "| --- | --- | --- |"]
        for index, session in enumerate(brief["reference_answer"]["baseline"]["sessions"]):
            start = instant(session["start"])
            end = start + timedelta(minutes=30)
            lines.append(f"| {brief['session_titles'][index]} | {start:%H:%M}–{end:%H:%M} | {session['speaker_id']} |")
        adapted = brief["reference_answer"]["changed"]
        lines += ["", "**Tras el cambio:** " + adapted["reason"], ""]
        if adapted["status"] == "scheduled":
            for session in adapted["sessions"]:
                start = instant(session["start"])
                lines.append(f"- {session['id']}: {start:%H:%M}–{start + timedelta(minutes=30):%H:%M}, {session['speaker_id']}.")
        else:
            lines.append("**Bloqueado: no hay una agenda confirmable bajo las restricciones actuales.**")
            lines += ["- Pendiente de aprobación: " + option["description"] for option in adapted["options"]]
        lines += ["", "Preparación pendiente:", "", *["- " + task for task in brief["preparation_tasks"]], ""]
    lines += ["", "## Resultados por modelo", "", "Una celda aprobada requiere agenda inicial y adaptación correctas.", "",
              "| Modelo | Correctas / 6 | Respuestas completas | Tokens conocidos | Recibos incompletos | Segundos medios del proceso completado |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for model, g in groups.items():
        lines.append(f"| {model} | {g['passed']} / 6 | {g['complete_responses']} | {g['known_tokens']} | {g['unknown_token_receipts']} | {g['mean_completed_process_seconds']} |")
    lines += ["", "## Calendario compartido por modelo", "",
              "| Modelo | Semana inicial verificada | Semana adaptada verificada |",
              "| --- | --- | --- |"]
    for model, group in groups.items():
        labels = ["Correcta" if group["shared_calendar"][phase]["passed"] else "Incompleta o inválida"
                  for phase in ("baseline", "changed")]
        lines.append(f"| {model} | {labels[0]} | {labels[1]} |")
    lines += ["", "## Fallos conservados", ""]
    for r in matrix:
        if "evaluation" in r and not r["evaluation"]["passed"]:
            lines.append(f"- {r['event_id']} · {r['model']} · {r['state']}: " + "; ".join(r["evaluation"]["errors"]))
    lines += ["", "## Alcance", "", *["- " + line for line in summary["limits"]], "",
              "Los recibos de cada tarea están en Temporal/opencode/tasks/<task_id>/, identificados en matrix.json.", ""]
    (ROOT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "summary"))
    args = parser.parse_args(argv)
    if args.command == "prepare":
        print(json.dumps(prepare_suite()))
    elif args.command == "run":
        run_suite()
    else:
        print(json.dumps(summarize_suite(), ensure_ascii=True))


if __name__ == "__main__":
    main()
