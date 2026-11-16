# Documentación de ArquiGica

Esta carpeta organiza la presentación técnica, la operación del prototipo y sus
resultados verificables. Los documentos fechados conservan el contexto de cada
entrega; una prueba local o simulada no acredita una inferencia real ni un
despliegue de producción.

## Recorrido de lectura

| Orden | Documento | Qué explica |
| --- | --- | --- |
| 1 | [Arquitectura](architecture.md) | Componentes, responsabilidades y recorrido de una solicitud. |
| 2 | [Inicio y ejecución](guias/inicio.md) | Cómo preparar, iniciar y detener ArquiGica. |
| 3 | [Plan de construcción](construction-plan.md) | Etapa vigente, alcance y pendientes. |
| 4 | [Verificación](verification.md) | Pruebas realizadas, evidencia y límites. |
| 5 | [Entrega del código](guias/release.md) | Paquete distribuible, instalación y preparación de GitHub. |

## Arquitectura y diseño

| Documento | Contenido |
| --- | --- |
| [Directorio y catálogo](arquitectura/directory-and-catalog.md) | Identidades, consultas, calendario y permisos. |
| [Lenguaje de Gica](arquitectura/romeo-language.md) | Intenciones, normalización, patrones y comandos permitidos. |
| [Sistema visual](arquitectura/design-system.md) | Tipografía, paletas, lectura y movimiento. |
| [Evolución de la arquitectura](historial/architecture-evolucion.md) | Antecedentes y decisiones de las versiones anteriores. |

## Guías de uso y operación

| Documento | Contenido |
| --- | --- |
| [Gestión de IA](guias/ai-management.md) | Proveedores, generación compacta, presupuesto y consumo. |
| [Agentes y voz](guias/agents-and-voice.md) | Guía local, conversación, inferencia y revisión humana. |
| [Despliegue](guias/deployment.md) | Condiciones pendientes para un entorno de producción. |
| [Ayudante OpenCode](guias/opencode.md) | Herramienta de desarrollo separada del agente del producto. |

## Decisiones y validación

| Documento | Contenido |
| --- | --- |
| [Revisión de Motion](decisiones/motion-dependency-review.md) | Procedencia, integridad, integración y límites de la dependencia. |
| [Auditoría de entrega](validacion/audit.md) | Controles observados y limitaciones de la revisión técnica. |
| [Ensayo de agendas UNAC/GICA](validacion/event-benchmark.md) | Escenarios, resultados medidos y tratamiento de cuotas y tokens. |

El código ejecutable permanece en `apps/`, `config/`, `templates/`, `static/` y
`tools/`. Los documentos Word, PowerPoint y ZIP generados se guardan en `entrega/`
y deben regenerarse cuando cambie su contenido. Los datos activos de `var/`, el
entorno `.venv/`, los auxiliares de `Temporal/` y el banco privado del mentor no
forman parte del paquete de código.
