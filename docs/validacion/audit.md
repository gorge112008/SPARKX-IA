# Auditoría técnica de preparación de entrega

Revisión del 16 de noviembre de 2026. Abarca lectura de componentes críticos,
búsquedas estáticas sobre código mantenido, comprobaciones locales y fronteras
del paquete. No es una certificación ni una prueba de penetración externa. No se
han consultado claves ni modificado datos activos para esta auditoría.

## Controles observados

| Área | Evidencia en el código | Evaluación |
| --- | --- | --- |
| Acceso | `apps/accounts/access.py`, `middleware.py`, `backends.py` | Identificador normalizado correo/usuario; ambigüedad rechazada; eventos por propietario o asignación de revisor con versión vigente. |
| Privilegios | `apps/accounts/services.py`, `apps/assistant/execution.py` | Gestión de cuentas serializada; protege último administrador; contexto del agente deniega módulos de administración y cambios de presupuesto. |
| Sesiones | `apps/accounts/middleware.py`, `services.py` | Cambio de rol/activación invalida versiones de sesión y asignaciones antiguas. |
| CSRF y métodos | Middleware Django y vistas de cuentas, eventos, directorio, acciones y API | Las mutaciones usan los métodos y formularios protegidos; no se encontraron `csrf_exempt` en componentes mantenidos. |
| Contenido no confiable | Plantillas Django, `config/middleware.py`, scripts de la interfaz | Escape de plantillas, CSP de origen propio y texto insertado con APIs de texto; la búsqueda dirigida no encontró `innerHTML`, `insertAdjacentHTML`, `eval` ni `shell=True` en código funcional. |
| Credenciales | `apps/ai_management/credential_security.py`, `runtime_credentials.py`, `control_views.py` | HTTPS o loopback directo validado; formularios redactados incluso en DEBUG; secretos en RAM con caducidad de dos horas y referencias versionadas; no se envían al navegador. |
| Proveedores | `apps/assistant/provider.py`, `free_harness.py` | Destinos y modelos permitidos; límites de tamaño/tiempo, sin redirecciones de claves ni proxy heredado; salida del modelo tratada como datos. |
| Aislamiento de contexto | `apps/assistant/provider.py` y pruebas `test_*context_isolation.py` | Instantáneas y contextos independientes por trabajo/modelo; esto es aislamiento de aplicación, no una máquina virtual o sandbox del sistema operativo. |
| Presupuesto | `apps/ai_management/services.py`, `pilot.py`, `agent_access.py`, `free_pool.py` | Reserva previa conservadora; consumo desconocido conserva reserva; autorización/versiones separadas del proveedor; tarifas y gasto son estimaciones, no facturas. |
| Plan y tareas | `apps/planning/services.py`, `event_rules.py`, `constraints.py`, `task_progress.py` | Validación del servidor, revisión base y plan vigente; aprobación humana independiente; conflictos de ponente/recurso/horario no se aceptan por decisión del modelo. |
| Directorio | `apps/directory/services.py`, `queries.py`, modelos | Propiedad vigente, registros versionados, auditoría y selección explícita; no concede disponibilidad real de la persona. |
| Calendario | `apps/events/calendar.py`, `catalog.py`, `views.py` | Proyección de eventos autorizados, fechas civiles IANA y agenda aprobada; los candidatos pendientes no se publican como agenda aprobada. |
| Inscripción | `apps/registration/services.py`, `views.py` | Gestión del propietario, publicación versionada, recepción no enumerativa y aforo sujeto al estado del evento/plan. |
| Cursor y navegación | `static/js/romeo-actions.js`, `romeo-presence.js`, `gica-navigation.js` | Intenciones acotadas, vigencia y comprobación del destino; el cursor mostrado pertenece a la interfaz y no controla el ratón del sistema. |
| Piloto narrado | `apps/assistant/pilot_workflow.py`, `gica-demo.js` | Inicio humano, UUID fijo y dueño vigente, JSON estricto, CSRF, reserva con caducidad e idempotencia. Los clics autorizados usan formularios existentes; Stop cancela pasos futuros y conserva lo ya guardado. No llama proveedores. |
| Edición de horarios | `apps/events/schedule_views.py` | Sólo organizador dueño; revisión y plan base, conjunto exacto de sesiones y fechas locales sin ambigüedad DST. Crea candidato; la aprobación normal valida conflictos y conserva versiones. |
| Apagado local | `config/local_views.py`, `local_runtime.py` | Sólo desarrollo directo y superusuario técnico; POST, CSRF y token vinculado al runtime; no expuesto como permiso del agente. |
| Distribución | `tools/package_release.py` y `test_package_release.py` | Allowlist independiente de Git, verificación de hashes y rutas, exclusión de secretos/datos activos y pruebas de archivo manipulado. |

## Hallazgos y límites de entrega

| ID | Prioridad y estado | Hallazgo o acción |
| --- | --- | --- |
| A01 | Corregido en procedimiento de entrega | Una copia nueva sin `var/` no puede abrir la base SQLite. `docs/guias/release.md` crea el directorio antes de `migrate`; los datos activos siguen excluidos del paquete. |
| A02 | Resuelto en empaquetado y exclusiones Git | Comprimir la carpeta de trabajo completa incluiría `.venv`, datos, respaldos y configuración privada. El empaquetador usa lista permitida y genera un `AGENTS.md` portátil. `.gitignore` excluye también el banco/configuración privados y `entrega/`. No se distribuye el historial Git local. |
| A03 | Requisito antes de despliegue público | `DEBUG=1` y una clave de desarrollo conocida son valores del modo local. Producción rechaza la ausencia de un secreto propio y exige PostgreSQL salvo excepción explícita de prueba. No exponer el lanzador local. |
| A04 | Pendiente de entorno real | SQLite no acredita bloqueos de filas, seguridad de varios workers ni capacidad concurrente. Ejecutar los casos PostgreSQL y medir carga antes de afirmar capacidad multiusuario. |
| A05 | Límite conocido | Claves configuradas desde el panel viven en un proceso. Un despliegue con web/worker separados necesita un gestor de secretos compartido o configuración privada de cada proceso. Reiniciar elimina las claves RAM. |
| A06 | Límite conocido | Voz y reconocimiento dependen del navegador, dispositivo y permisos. Una síntesis simulada en QA no demuestra audio físico ni transcripción correcta con ruido. |
| A07 | Pendiente de actualización periódica | Dependencias fijadas y `pip check` sin incompatibilidades no equivalen a ausencia de CVE. Se verificó el aviso oficial de Django correspondiente a la versión instalada; no se realizó un análisis completo de vulnerabilidades de todos los paquetes ni del sistema operativo. |
| A08 | Límite conocido | Las cuotas gratuitas son externas y no ilimitadas. Una cuota agotada y su consumo desconocido no pueden presentarse como inferencia correcta ni gasto cero medido. El piloto con nombres reales conserva las restricciones de salida de los proveedores; tanto el puente gratuito como el piloto OpenAI de USD 1 exigen eventos sintéticos. |
| A09 | Pendiente de aceptación humana | Un nombre y una relación con Gicaingenieros son datos declarados por el organizador. No acreditan contrato, disponibilidad, consentimiento, reunión provisionada ni reemplazo aceptado por terceros. |
| A10 | Alcance del escáner | Los formatos reconocidos de claves y exclusiones reducen riesgos de filtración en el ZIP. No detectan todo secreto imaginable; revisar los artefactos y la historia del repositorio antes de publicar. |

La separación local de claves, permisos y planes es una buena base para el piloto.
Los puntos pendientes de infraestructura no impiden una demostración local
controlada, pero impiden describirla como producción multiusuario validada.

## Dependencias y procedencia

`requirements.txt` fija Django 5.2.19, psycopg 3.3.8, WhiteNoise 6.12.0, asgiref
3.13.0, sqlparse 0.6.1, tzdata 2026.6 y typing_extensions 4.16.0. No se cambió
ninguna versión en esta revisión. El aviso de Django del 3 de noviembre de 2026
incluye la versión 5.2.19 y sus correcciones de seguridad.
Fuentes primarias consultadas el 16 de noviembre:
[aviso oficial](https://www.djangoproject.com/weblog/2026/nov/03/security-releases/)
y [notas de 5.2.19](https://docs.djangoproject.com/en/5.2/releases/5.2.19/).

HTMX y Motion se sirven localmente con sus licencias en `static/vendor/`.
`static/audio/romeo/NOTICE.txt` identifica la muestra fija de comparación de voz;
el motor Piper y su modelo no se distribuyen ni se invocan como voz conversacional
de la aplicación. El afiche aportado permanece como recurso del caso original.

## Comprobaciones ejecutadas en esta auditoría

- `pip check`: sin dependencias incompatibles.
- `manage.py check`: sin incidencias del sistema Django.
- Suite funcional final: 1.459 casos, 1.445 correctos y 14 omitidos que requieren PostgreSQL.
- Ocho pruebas del empaquetador: exclusiones, traversal/nombres Windows,
  credenciales desconocidas, AGENTS portátil, determinismo, destino permitido,
  manifiesto manipulado y enlace simbólico en ZIP.
- `package_release.py --check-only`: selección de fuentes y escaneo por formatos
  completados, sin compresión de datos activos ni llamadas API.

Los resultados del recorrido, sus capturas y la suite funcional final están en
`docs/verification.md`. Las pruebas de esta auditoría no sustituyen las de la
interfaz ni atribuyen las ejecuciones anteriores a esta revisión. El hash y la
verificación del ZIP final se producen después de congelar el código, para evitar
dejar una entrega desfasada respecto al prototipo.
