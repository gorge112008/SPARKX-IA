"""Synthetic plan fixture shared by maintained test modules."""

def valid_plan():
    return {
        "title": "Seminario académico",
        "summary": "Sesión virtual con preparación y revisión del organizador.",
        "sessions": [
            {"id": "s1", "title": "Apertura", "start": "2026-11-14T09:00:00-05:00", "duration_minutes": 30, "speaker": "", "resource": "Sala virtual"},
            {"id": "s2", "title": "Conversatorio", "start": "2026-11-14T09:30:00-05:00", "duration_minutes": 30, "speaker": "", "resource": "Sala virtual"},
        ],
        "tasks": [
            {"id": "t1", "title": "Confirmar ponente", "depends_on": [], "status": "pending", "purpose": "Obtener confirmación antes de publicar."},
            {"id": "t2", "title": "Revisar agenda", "depends_on": ["t1"], "status": "pending", "purpose": "Validar la agenda con datos confirmados."},
        ],
        "risks": ["El ponente aún no está confirmado."],
    }
