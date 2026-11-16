# Ensayo de agendas UNAC / GICA

Autorización de Jorge: seis eventos en total y seis agentes de prueba acotados,
uno por evento. Datos ficticios; no es una programación oficial de UNAC o GICA.
Semana simulada del 16 al 21 de noviembre de 2026, zona America/Lima.
No se espera una semana real para ejecutar la prueba.

## Casos y control

| Caso | Día | Institución | Evento | Cambio controlado |
| --- | --- | --- | --- | --- |
| E01 | Lunes | UNAC | Claves para desarrollar Tesis I, II y III | Cancela el ponente inicial; buscar sustituto habilitado. |
| E02 | Martes | UNAC | Tu ruta hacia el Grado de Maestro | Aparece otra reserva del ponente de la segunda sesión. |
| E03 | Miércoles | UNAC | De la idea al proyecto de tesis aprobado | Ningún ponente puede iniciar a la hora prevista; buscar otro horario. |
| E04 | Jueves | UNAC | Del proyecto a la sustentación de tesis | Los tres ponentes quedan sin disponibilidad; no inventar confirmaciones. |
| E05 | Viernes | UNAC | Últimos pasos para obtener tu Grado de Maestro | Cancela un ponente cuya asignación está bloqueada por decisión confirmada. |
| E06 | Sábado | GICA | Claves para desarrollar Tesis I, II y III | Cancela el ponente inicial y su sustituto está ocupado al comienzo. |

Los seis agentes locales trabajan por tandas de hasta tres. Cada uno recibe solo
su evento y el calendario ficticio compartido, escribe únicamente su ficha y no
usa red, subagentes, credenciales o base de datos. Preparan enfoque de marketing,
público, propuesta, tres sesiones y tareas pendientes; su solución de referencia
se valida localmente. No se atribuye esa referencia al modelo gratuito.

El coordinador prepara 42 celdas: seis casos por siete modelos. Máximo dos tareas
OpenCode a la vez, una ejecución por celda, sin alternativas automáticas de pago.
El ejecutable puede crear procesos hijos; dos tareas no equivalen a dos procesos
del sistema operativo. Cada tarea conserva los límites y permisos de [opencode.md](opencode.md),
incluidos contexto acotado, tres pasos y 180 segundos. Un fallo no se reintenta
automáticamente. Las tareas ya terminadas se leen sin volver a ejecutarlas.

Los cuatro modelos con condiciones adicionales se usan solo con datos ficticios
y aceptación registrada para esta prueba autorizada. Antes de cada ejecución se
verifica que el catálogo mantenga el modelo y sus precios a cero. No se activa la
API del agente de eventos ni se modifica la demo, cuenta o presupuesto de SparkX.

## Referencia y criterio fijados antes de inferir

`tools/opencode/event_benchmark.py` genera agendas reproducibles con semilla
**142026**, tres expositores ficticios P1/P2/P3 y sus actividades previas. Los
horarios iniciales y el orden de ponentes varían entre eventos mediante esa semilla.
Los conflictos se introducen de forma controlada; no son una muestra aleatoria
representativa de eventos reales.

Cada evento tiene tres sesiones contiguas de 30 minutos, orden S1 → S2 → S3,
inicios en cuadrícula de 15 minutos y una ventana máxima de 150 minutos. Se
comprueban habilitación del ponente, disponibilidad completa, otras reservas,
zona horaria, institución, título y decisiones bloqueadas. El recurso es una sala
virtual ficticia; no hay conexiones a Zoom u otros servicios.

La referencia enumera el espacio finito de horarios/asignaciones. Todas las agendas
iniciales son factibles. Tras el cambio, E01/E02/E03/E06 tienen solución;
E04/E05 no la tienen bajo las restricciones autorizadas. No se exige una solución
única o óptima. La referencia no se envía al modelo; el contexto sí incluye las
restricciones y la agenda preferida inicial.

Una celda pasa solo si conserva identidad y título y resuelve ambas fases:

- Agenda viable: tres sesiones con esquema, orden, duración y asignaciones válidas.
- Bloqueo real: sesiones vacías, explicación y de una a tres opciones que requieren
  confirmación; no afirmar una disponibilidad nueva como confirmada.
- Declarar bloqueo cuando hay alternativas factibles también falla.
- Los planes se contrastan además con `apps.planning.domain.validate_plan`, la
  función pura del producto; las reglas adicionales de disponibilidad pertenecen
  al ensayo y no se presentan como una función ya integrada en el producto.

Se conservan errores de formato, respuestas truncadas, fallos del proveedor y
contadores desconocidos. Un proceso con salida cero no demuestra agenda correcta.
Las referencias locales y las respuestas remotas se guardan por separado.

## Evidencia y límites

Comandos desde la raíz de SparkX:

```powershell
.\.venv\Scripts\python.exe -B -m unittest tools.opencode.test_event_benchmark
.\.venv\Scripts\python.exe -B -m tools.opencode.event_benchmark prepare
.\.venv\Scripts\python.exe -B -m tools.opencode.event_benchmark run
.\.venv\Scripts\python.exe -B -m tools.opencode.event_benchmark summary
```

`prepare` exige las seis fichas previamente revisadas y no llama modelos. `run`
realiza inferencias remotas y requiere la autorización correspondiente; para este
ensayo Jorge la dio expresamente. Volver a preparar una matriz existente se rechaza.

Evidencia en `Temporal/opencode/event-benchmark/`: fichas de agentes, casos,
referencia, matriz con identificadores de tareas, resumen y reporte. Cada celda
conserva sus eventos, recibo y comparación económica en `Temporal/opencode/tasks/`.
Las estimaciones con tarifas pagadas se distinguen del coste reportado gratuito.

Seis casos y una ejecución por modelo/caso no permiten concluir superioridad
estadística, seguridad integral, ahorro general ni capacidad multiusuario. La
evaluación automática mide restricciones y formato; no acredita calidad docente,
corrección de trámites de maestría o eficacia real de marketing. Tampoco prueba
persistencia, permisos web o inferencia del agente integrado de SparkX.

## Resultados del 14 de noviembre de 2026

Las **42 celdas principales terminaron**. Pasaron 19; otras dos entregaron una
respuesta completa con fechas inválidas. Diecinueve terminaron con `reason=length`
y dos con `provider.free-limit`, HTTP 429. No se reintentaron ni se pagó para
continuar. La matriz mide el perfil restringido de **2.048 tokens de salida por
solicitud**, incluyendo razonamiento; no mide la capacidad máxima de cada modelo.

| Modelo gratuito | Casos correctos / 6 | Respuestas completas |
| --- | ---: | ---: |
| GLM 5.3 Flash | 6 | 6 |
| DeepSeek V4.1 Flash | 3 | 3 |
| MiniMax M3.1 Flash | 2 | 2 |
| LongCat 2.5 | 2 | 2 |
| Beam | 3 | 3 |
| MiMo V2.6 Flash | 3 | 5 |
| Nemotron 3.5 Lightning | 0 | 0 |

GLM completó la semana inicial y la adaptada sin solapamientos: resolvió los cuatro
cambios factibles y mantuvo bloqueados E04/E05. Es la opción con mejor resultado
en **esta muestra y este perfil**, sin garantía estadística o de disponibilidad.
MiMo produjo una fecha inválida en E01 y otra en E03. En E06, MiMo y Nemotron
recibieron cuota gratuita agotada antes de leer el caso; ese fallo no evalúa su
planificación. No deducimos de esos dos 429 una cuota fija por modelo, por día o
por usuario, ni garantizamos la fecha de recuperación del servicio.

Las revisiones independientes de cada evento separan el score de restricciones
de la calidad de la explicación. Detectaron alternativas textuales incompletas:
un cambio de horario puede necesitar mover también sesiones anteriores, cambiar
un bloqueo exige autorización explícita y posponer no recupera por sí solo la
disponibilidad cancelada. Las alternativas no se consideran agendas aprobadas.
Los textos de marketing son borradores ficticios, sin revisión académica oficial.

## Incidente de preparación y trazabilidad

El primer piloto usó JSON en una sola línea. La herramienta nativa de lectura
recortaba líneas largas a unos 2.000 caracteres, aunque su indicador general de
truncamiento fuera falso. Fue un error de preparación del ensayo, no un fallo
atribuible a los modelos. Se interrumpió únicamente el árbol del coordinador propio
y se cambió a JSON indentado, con líneas menores de 1.500 caracteres y hash de la
copia. Las seis fichas de referencia se validaron antes de la matriz corregida.

Se excluyen del comparativo **nueve intentos de piloto**, dos de ellos interrumpidos
sin contadores completos. La matriz principal contiene 42 intentos con entradas
corregidas. Total de este ensayo: **51 intentos acotados**, no 51 peticiones HTTP
exactas; el harness puede hacer varias solicitudes. La prueba sintética anterior
de desarrollo permanece separada. No se repitió ninguna tarea ya reclamada.
Se conserva el piloto solo como evidencia útil del defecto y de su corrección.

## Tokens y representación económica

Los seis recibos completos de GLM suman **30.696 tokens**: 21.250 de entrada sin
caché, 5.440 de lectura de caché, 2.220 de salida visible y 1.786 de razonamiento.
OpenCode reportó **USD 0** en esos seis recibos; no es una factura auditada.
Aplicando las tarifas de referencia del 14 de noviembre a **los mismos contadores**:

| Escenario pagado hipotético | USD por los seis trabajos |
| --- | ---: |
| GLM 5.3 Flash | 0,00535370 |
| DeepSeek V4.1 Flash | 0,01121484 |
| MiniMax M3 | 0,01150860 |

MiniMax M3 es distinto del modelo gratuito M3.1 Flash. Cambiar de modelo puede
cambiar tokens, razonamiento, caché y pasos: estas cifras ilustran el mecanismo
de presupuesto y no predicen una factura real ni el coste de seis eventos reales.
Las tarifas y su fuente están en [opencode.md](opencode.md). Los fallos conservan
contadores parciales: el gasto y los tokens totales del ensayo completo permanecen
desconocidos cuando falta evidencia. El subtotal conocido no se presenta como total.

## Cierre técnico

**124/124 pruebas locales correctas en 4,364 s**, sin red ni modelos. Incluyen
15 casos del evaluador y conservación de evidencia parcial al interrumpir una tarea.
`manage.py check` correcto; web local con salud HTTP 200. La comprobación de base
de datos solo leyó Job=0, AIUsage=0, perfil activo nulo, pago deshabilitado y
presupuesto USD 0. No se importaron estas agendas a la demo ni se activó su worker.

El informe detallado se encuentra en `Temporal/opencode/event-benchmark/report.md`;
`assessment.json` contiene las causas, contadores y estimaciones. Las seis
revisiones están en `reviews/E01.json` a `E06.json`. La integración de inferencia
en el agente de eventos y los entregables del concurso siguen pendientes.
