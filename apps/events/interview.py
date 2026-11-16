"""Deterministic interview rules, independent of storage and AI providers.

Answers are declarations by the organizer. Neither a confirmed answer nor a
reference to the existing brief establishes independent verification. This
module never extracts facts from prose, copies a suggested plan or performs IO.
"""

from dataclasses import dataclass


MAX_ANSWER_LENGTH = 1000
STATUS_LABELS = {
    "confirmed": "Confirmado por mí",
    "assumed": "Supuesto de trabajo",
    "pending": "Pendiente",
    "not_applicable": "No aplica",
    "in_brief": "Ya está en la ficha",
}
STATUS_CHOICES = tuple(STATUS_LABELS.items())


@dataclass(frozen=True)
class Question:
    key: str
    label: str
    prompt: str
    help_text: str
    allow_na: bool = False
    allow_brief: bool = True


QUESTIONS = (
    Question(
        "objective", "Objetivo",
        "¿Qué deberían lograr los participantes al finalizar el evento?",
        "Indica el resultado esperado. Si ya lo describiste, puedes remitir a la ficha.",
    ),
    Question(
        "audience", "Público",
        "¿A quién está dirigido y qué experiencia previa necesita?",
        "Describe el perfil del público; el aforo ya se conserva en la ficha.",
    ),
    Question(
        "modality", "Modalidad",
        "¿El evento será virtual, presencial o híbrido?",
        "Puedes añadir cómo participará el público sin repetir la fecha ni el título.",
    ),
    Question(
        "duration_minutes", "Duración total",
        "¿Cuántos minutos debe durar el evento completo?",
        "Incluye apertura, sesiones, descansos y preguntas. Usa entre 1 y 1440 minutos.",
        allow_brief=False,
    ),
    Question(
        "location", "Lugar o acceso",
        "¿Qué lugar, plataforma o enlace de acceso se usará?",
        "Distingue lo disponible de lo pendiente. No incluyas contraseñas ni claves privadas.",
        allow_na=True,
    ),
    Question(
        "resources", "Recursos",
        "¿Con qué personas, materiales y recursos cuentas para organizarlo?",
        "Aclara qué está disponible y qué falta confirmar; una sugerencia no reserva recursos.",
        allow_na=True,
    ),
    Question(
        "constraints", "Restricciones",
        "¿Qué condiciones debe respetar el plan?",
        "Incluye límites de horario, presupuesto, accesibilidad u otras condiciones relevantes.",
        allow_na=True,
    ),
)
QUESTION_BY_KEY = {question.key: question for question in QUESTIONS}


def normalize_interview_answers(payload):
    """Validate and return a trimmed independent JSON-compatible answer mapping.

    Absent keys stay absent: an explicit pending answer means it was reviewed,
    whereas an absent answer has not yet been addressed. Optional ``in_brief``
    only records the organizer's reference and never derives a value from text.
    """
    if not isinstance(payload, dict):
        raise ValueError("Las respuestas de la entrevista deben ser un objeto.")
    if any(key not in QUESTION_BY_KEY for key in payload):
        raise ValueError("La entrevista contiene preguntas no permitidas.")

    normalized = {}
    for question in QUESTIONS:
        if question.key not in payload:
            continue
        answer = payload[question.key]
        if not isinstance(answer, dict) or set(answer) != {"status", "value"}:
            raise ValueError(f"{question.label}: se requieren solo estado y valor.")
        status = answer["status"]
        value = answer["value"]
        if not isinstance(status, str) or status not in STATUS_LABELS:
            raise ValueError(f"{question.label}: el estado no es válido.")
        if not isinstance(value, str):
            raise ValueError(f"{question.label}: el valor debe ser texto.")
        value = value.strip()
        if len(value) > MAX_ANSWER_LENGTH:
            raise ValueError(
                f"{question.label}: usa como máximo {MAX_ANSWER_LENGTH} caracteres."
            )
        if status == "not_applicable":
            if not question.allow_na:
                raise ValueError(f"{question.label}: no permite «No aplica».")
            if value:
                raise ValueError(f"{question.label}: «No aplica» requiere un valor vacío.")
        elif status == "in_brief":
            if not question.allow_brief:
                raise ValueError(f"{question.label}: indica la duración en minutos.")
            if value:
                raise ValueError(
                    f"{question.label}: la referencia a la ficha requiere un valor vacío."
                )
        elif status in {"confirmed", "assumed"}:
            if not value:
                raise ValueError(f"{question.label}: escribe una respuesta o déjala pendiente.")
            if question.key == "duration_minutes":
                # Canonical decimal strings exclude signs, decimals and leading zeros.
                if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 1440:
                    raise ValueError("Duración total: usa un entero entre 1 y 1440 minutos.")
                if str(int(value)) != value:
                    raise ValueError("Duración total: usa un entero entre 1 y 1440 minutos.")
        normalized[question.key] = {"status": status, "value": value}
    return normalized


def build_interview_context(answers):
    """Return a bounded summary without inferring or verifying any event facts.

    Counts describe the interview only, never task execution. ``next_question``
    identifies the first absent answer; explicit pending/assumed declarations
    remain visible in the summary without repeatedly asking the same question.
    """
    normalized = normalize_interview_answers(answers)
    entries = []
    for question in QUESTIONS:
        answer = normalized.get(question.key)
        status = answer["status"] if answer is not None else "pending"
        value = answer["value"] if answer is not None else ""
        if answer is None:
            source = "missing"
        elif status == "in_brief":
            source = "organizer_reference_to_brief"
        else:
            source = "organizer_declaration"
        entries.append({
            "key": question.key,
            "label": question.label,
            "value": value,
            "status": status,
            "status_label": STATUS_LABELS[status],
            "source": source,
        })
    return {
        "entries": entries,
        "reviewed_count": len(normalized),
        "total": len(QUESTIONS),
        "pending_count": sum(entry["status"] == "pending" for entry in entries),
        "assumed_count": sum(entry["status"] == "assumed" for entry in entries),
        "next_question": next(
            (question.key for question in QUESTIONS if question.key not in normalized),
            None,
        ),
    }
