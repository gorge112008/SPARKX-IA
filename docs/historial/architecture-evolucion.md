# Antecedente documental — 16 de noviembre de 2026

Este documento conserva el contenido previo a la organización formal. Incluye decisiones y funciones sustituidas. Para el funcionamiento vigente, consulta [la portada](../../README.md), [la arquitectura](../architecture.md) y [la guía de inicio](../guias/inicio.md).

---

# Arquitectura de SparkX 3.0

## Piloto narrado con generación compacta y revisión

### Recorrido vigente: directorio, evento y continuidad guiada

La presentación breve introduce SparkX y a **Gica, bot arquitecto**. Antes de la
ficha se recorre Directorio: alta normal de Gicaingenieros, alta de **Jorge
Gayoso** como expositor, y regreso a Eventos. Robert permanece asociado a la
UNAC y se usa inicialmente en el evento; Jorge se selecciona después como
reemplazo. El UUID reservado para esta versión es
`bcf52dbd-206b-4d22-a294-8c487c770c56`. Bootstrap no registra a Jorge por detrás
del formulario. No se inventan correo, participación confirmada ni disponibilidad.

Las respuestas compactas válidas pasan a **Respuesta recibida** durante 3.000 ms
antes de continuar. Preguntas pendientes muestran una confirmación neutral;
fallos y cancelaciones no muestran éxito. Detener, cambiar de cuenta o abandonar
la página cancela ese plazo y sus callbacks. Se respeta movimiento reducido.

`guided_event` conserva el paso y las preguntas pendientes en metadatos privados
del borrador. `gica-guided.js` conecta voz/texto, preguntas de directorio y
prefill de formularios. `openGuided` sólo abre rutas GET permitidas del mismo
origen; tiene identidad de evento y permisos separados de la demo. Guardar,
generar y aprobar usan sus controles habituales con revisión humana. El cierre
del guion explica ese acompañamiento, sin conceder autorización de demo a la voz.
La inferencia real de datos no ficticios sigue acotada al piloto autorizado.

El retiro de contactos usa `archived_at`, independiente de desactivar una ficha:
se excluyen incluso del filtro de inactivos y sus IDs no pueden reutilizarse.
Las restricciones únicas permiten registrar de nuevo un nombre/correo retirado
con otro UUID. Se conservan referencias y planes históricos; las cuentas de
acceso y el gasto acumulado no se borran. Los servicios impiden retirar fichas
con asignaciones vigentes sin resolver.

### Antecedente completado y conservación del anterior

El piloto previo fue `ebd54e40-752c-4f8a-9376-f2735e2c6a41`. El anterior se retiró
mediante `Event.archived_at`, con respaldo y ensayo; no se borraron sus Jobs,
consumos ni planes. `archive_event` exige propietario, revisión vigente y ausencia
de trabajos activos. Las consultas operativas, formularios de inscripción,
directorio, editor de horarios y reservas de recursos excluyen archivados; los
comandos vuelven a comprobar ese límite. El control USD 1 sigue sumando todo el
historial, también el del evento retirado.

El recorrido real nuevo terminó con una llamada GPT-5.4 mini, cuatro sesiones de
90 minutos en total, tres tareas y tres comunicaciones. Se guardó la copia antes
de aplicar y se aprobó el reemplazo Robert → Jorge sin otra consulta. La revisión
semántica independiente considera adecuada esta nueva agenda para el piloto;
el diagnóstico previo `needs_adjustments` corresponde a la agenda anterior conservada.

### Modos del recorrido

**Iniciar demo con OpenAI**, el acceso principal, selecciona `agenda-openai` por
un clic explícito. Usa el perfil principal configurado `gpt-5.4-mini`, por
autorización expresa del organizador y dentro del tope acumulado de USD 1.
Muestra el prompt y guarda una copia normal de la propuesta con `saveCopy`
antes de aplicar la agenda mediante el formulario de aprobación. Sólo continúa
si `archive` confirma el trabajo y `copy_saved=True`; un fallo detiene el recorrido.
Después muestra el calendario y el reemplazo local de Robert por Jorge. No
concede aprobación automática a otros eventos ni acceso a administración.
La continuación `agenda-openai-continue`, iniciada desde **Continuar agenda con
OpenAI**, reutiliza la ficha y las respuestas confirmadas de una aclaración
fallida. Conserva la misma copia previa y aprobación acotada del piloto.

**Demo con IA gratuita** conserva `agenda-live` como opción explícita separada.
No se cambia de proveedor por un error ni por presupuesto insuficiente.
`full` conserva la pausa **Aprobar y continuar** para cada propuesta visible.
`agenda-review` es opcional y guarda el resultado privado sin crear candidatos.
Los modos mantienen las mismas guardas de propietario, sesión, UUID,
revisión y cancelación. La disponibilidad de inferencia real se comprueba por
su resultado, no por haber implementado estos modos.

### Prueba privada de la solicitud

**Guardar agenda para comparar**, en Conoce a Gica, ejecuta el mismo llenado con
`CompactPlanRequest.review_only=True`. Antes de cada envío, `preview` presenta
el texto de sistema y la entrada generados por el mismo constructor que usa el
adaptador. La previsualización no crea trabajos ni reservas. El prompt se escribe
progresivamente en un campo de sólo lectura y se verifica contra el texto exacto.
El cursor pulsa **Ejecutar solicitud**; en uso manual se espera ese clic humano.
El panel se cierra al recibir el Job y comienza la escena de espera ligada al
estado consultado, con el modelo real admitido por la cola.

El worker privado valida el resultado pero no crea `PlanCandidate` ni aprueba
planes. `private_ready` no entrega agenda ni comunicaciones al navegador.
`archive` persiste un JSON local bajo
`Temporal/gica-agenda-review/<owner>/<job>.json`, con respuesta validada, horarios
calculados, modelo, prompt público y consumo informado. No se sirve por HTTP.
El propietario conserva acceso a sus archivos locales; no se promete exclusividad
frente al dueño del equipo. La segunda ronda hereda el modo privado y sólo admite
el lote de opciones de las preguntas previas. No sustituye el recorrido principal.

### Recorrido completo

El recorrido vigente, solicitado el 16 de noviembre, crea el piloto mediante
formularios y servicios normales. `POST /assistant/pilot-control/` sólo admite
bootstrap, creación idempotente y reemplazo local del expositor del UUID fijo del piloto.
Exige cuenta humana organizadora, propietario vigente, CSRF, JSON estricto,
revisión de ficha y reserva de sesión con caducidad. No acepta órdenes arbitrarias,
cuentas de agente, rutas de administración, proveedores o cambios de presupuesto.

`gica-demo.js` reserva la presentación dentro de un clic explícito, conserva
borradores humanos y mantiene apagado el micrófono. Registra Gicaingenieros con
el formulario del directorio, selecciona a Robert y completa quince campos y las
siete respuestas editables. El cursor SVG muestra selecciones, calendario, escritura
de los campos cortos y clics con desplazamiento suave. El router sólo admite los formularios
y destinos del recorrido ligados al piloto; vuelve a comprobar lease, propietario,
rol, destino y visibilidad. No controla el ratón del sistema.

`/assistant/pilot-ai/` admite una elección explícita `provider=openai|free` y
encola mediante `CompactPlanRequest` y el worker integrado. Las aclaraciones
heredan proveedor y modo de su trabajo padre. El contrato v1 admite dos rondas: solicitud inicial y un
único lote de respuestas a hasta cuatro preguntas de opciones cerradas. El
contexto exportado es un tema público predefinido y preferencias del catálogo;
nombres, institución, contacto, fechas, UUID e historial permanecen locales.
`requirements` fija caso aplicado y preguntas con sesiones y minutos propios,
y preparación de ensayo técnico y moderación. Son valores cerrados del piloto,
compartidos por preview e inferencia, sin exportar libremente la ficha. Si la IA
pregunta, Gica lee opciones A/B/C, espera la elección por botón o texto, permite
corregir la anterior o cancelar y envía el lote sólo al completar las respuestas.
La ejecución nueva no necesitó aclaraciones; la espera de elección se comprobó
con pruebas locales identificadas.
La ruta gratuita conserva los tres modelos revisados y el grupo aprobado por
un humano. La ruta OpenAI usa únicamente el principal `gpt-5.4-mini`; exige clave
disponible, autorización de pago y reservas por cuenta, agente y piloto global.
El tope global de USD 1 incluye todos los meses, propietarios, modelos y reservas
OpenAI anteriores, también las inciertas. No se reinicia con esta integración.
Reserva como máximo 12.000 tokens de entrada y 1.800 de salida por solicitud;
son límites, no consumos medidos.

OpenAI reutiliza Responses con `store=false`, servicio Standard, razonamiento
`none` y salida estructurada estricta. Un objeto raíz `result` contiene las dos
alternativas del contrato; el servidor retira ese envoltorio y valida el mismo
JSON compacto. La solicitud inicial permite preguntas o propuesta; con respuestas
confirmadas, tanto las instrucciones como el esquema admiten sólo una propuesta.
Preview, envío y archivo comparten el constructor de sistema,
entrada y esquema. No se habilitan herramientas ni recuperación de otro modelo.

La IA devuelve JSON estricto con dos a seis sesiones que suman 90 minutos, una a
seis tareas y uno a tres borradores de comunicación. SparkX calcula fechas,
horas, identificadores y asignación de expositor, y valida antes de crear una
propuesta. Los borradores no se envían. La aprobación conserva el servicio y
formulario normales: `full` pide revisión humana y los modos `agenda-openai` y
`agenda-live`, incluida la continuación OpenAI, aplican únicamente el piloto
autorizado tras guardar su copia.

Una aclaración OpenAI fallida admite un único reintento explícito, nunca automático,
mediante `retry` y `failed_job_id`. Conserva respuestas, proveedor, Jobs fallidos y
consumo; puede partir de una nueva sesión de recorrido del mismo propietario.
Exige fallo reciente (dos horas), ficha/plan/asignación vigentes y presupuesto.
Su padre enlaza el intento fallido y no se permiten cadenas de reintentos.
Los errores de contrato producen sólo el diagnóstico local `compact_invalid`,
sin persistir texto remoto ni detalles de excepciones.

La primera aceptación real del 16 de noviembre completó esa recuperación: la IA produjo
cuatro sesiones de 90 minutos en total, cuatro tareas y tres comunicaciones.
Se archivó la respuesta antes de aprobar y se aprobó después el reemplazo local,
conservando temas, horarios y recursos sin otra llamada a la IA. El calendario
inicial y el actualizado se comprobaron. La revisión semántica independiente
identificó ajustes: la secuencia es coherente, pero no reserva tiempos explícitos
para caso práctico y preguntas pedidos en la ficha. El contexto exportado sólo
llevó `focus=planning`; no incluyó nivel intermedio ni formato de caso. Esta
brecha de la proyección del prompt queda separada de la validación estructural.
La agenda original se conserva retirada para comparar. El corte nuevo incorpora
los requisitos explícitos de caso, preguntas, ensayo y moderación; evidencia y consumo en
[verificación](../verification.md).

Después Robert no puede participar el jueves 19 y se selecciona a Jorge Gayoso
Ugas, conservando esa fecha, horarios y contenido. Se prepara y revisa el
reemplazo sin otra inferencia. La afiliación UNAC de Robert se conserva: la relación
con el evento pertenece a `EventPerson`. Identidad declarada no equivale a
disponibilidad confirmada, reunión provisionada ni actividad ejecutada.

`/events/<uuid>/schedule/` ofrece edición manual de inicio y duración. Copia el
plan aprobado a una nueva propuesta; comprueba dueño, revisión, conjunto exacto
de sesiones, fechas locales y ambigüedad DST. La aprobación reutiliza las reglas
de solapamiento y dependencias. Las versiones previas permanecen inmutables y el
detalle muestra propuestas y versiones aprobadas en sus paneles correspondientes.

Detener aborta futuras acciones y callbacks, libera controles y restaura campos
sin enviar. Las operaciones ya guardadas permanecen. Repetir reutiliza el mismo
evento e institución; genera nuevas versiones sólo cuando se aprueban cambios.
La burbuja conserva su arrastre manual y se aparta temporalmente del control
activo y del artículo completo del calendario durante la presentación. Un punto
rojo señala contenido sin conceder clics. La punta queda centrada verticalmente
en el control, sin desplazamiento vertical añadido; en botones y selectores se
aparta hacia el margen para no tapar el texto. Los bloques del formulario se alinean
arriba y los campos conservan alturas acotadas para evitar el estiramiento de
filas. La espera muestra actividad indeterminada y fases observadas, sin inventar
porcentajes. La escena SVG representa Gica, el intercambio y el proveedor; no
expone pensamientos del modelo. Las pistas originales Órbita pop (124 BPM),
Brisa groove (119 BPM) y Chispa latina (128 BPM) se sintetizan localmente; el micrófono
sólo se abre con un clic y consentimiento para detener
o continuar esa música. Se apaga al terminar la espera. La síntesis elegida
depende del navegador. La narración solicita una voz femenina local conocida,
con preferencia por Sabina; si falta, informa sin recurrir a una voz remota o
masculina. La selección por nombre no es una comprobación de género ni de audio.
Un recibo de cancelación persistente cerca un enqueue
pendiente; las inferencias ya despachadas pueden terminar y conservar consumo.
Un 429 gratuito pausa esa pasarela, sin rotación para eludir cuota ni agenda prefabricada
presentada como generación real.

### Recorrido anterior de sólo lectura — sustituido

`gica-demo.js` reproduce un guion local sobre el único piloto GICA existente.
La voz cede su sesión y el dictado; una reserva temporal evita micrófono y
respuestas manuales simultáneas. La lectura comienza dentro del clic, antes de
esperar la red; después recupera el estado para proteger un borrador humano.

`GET /assistant/demo-pilot/` devuelve sólo el piloto sintético del propietario
humano vigente, sin revelar registros ajenos ni escribir. El controlador valida
identidad, fecha, horario y estructura. `gica-demo-preview.js` proyecta los quince
campos en el formulario como lectura, mantiene siete respuestas y restaura los
controles y nodos originales al terminar. La ficha identifica el recorrido como
visualización de un evento ya guardado, nunca como otro borrador.

La presentación empieza en Mis eventos, activa su enlace real de Nuevo evento
y vuelve por el enlace de Eventos. `SparkXGicaDemoCursor` controla únicamente el
marcador SVG: movimiento, pulso y activación de esos dos destinos GET fijos.
Exige reserva de demo, propietario/rol vigentes, destino visible, señal vigente
y confirmación del router; no es un permiso genérico para clicar ni enviar.
Los campos y bloques de la proyección sólo reciben foco ilustrativo. Su secuencia
agrupa identidad, programación, audiencia, descripción y preparación. Sólo el
título usa escritura incremental abortable; las demás respuestas se proyectan
completas. La descripción de pantalla usa un resumen editorial local para la
presentación; no sustituye la descripción ni la procedencia guardadas del evento.
Detener también cancela un GET pendiente y restaura las clases de los
bloques y valores originales, sin callbacks que sigan escribiendo.

No hay rutas de creación o confirmación en el narrador. Si falta el piloto,
informa; no intenta crearlo. Al terminar abre Eventos por GET. Detener, ocultar,
navegar o cambiar de cuenta invalida callbacks y restaura el formulario sin
cambiar datos de negocio. Los errores de voz aparecen en la burbuja y su estado;
el panel completo sólo se abre manualmente. La demo
usa la voz local elegida, sin reconocimiento, modelos o entrenamiento.

## Intención de creación por conceptos

`creation_language.is_creation_request` cruza tokens normalizados con conjuntos
de variantes de acción y de tipo de evento. Ambos conceptos bastan, sin marcos
ni `fullmatch` de la oración: orden, distancia y relleno no definen el acceso.
El JSON sólo admite palabras individuales y falla cerrado con esquema/versión
incorrectos. Guardas separadas revisan negación, relatos/citas, condiciones y
conflictos. No se usan prefijos abiertos cre*/event*, modelos o red. La detección
abre la entrevista del servidor; campos activos y confirmación final mantienen
sus reglas. Las antiguas restricciones gramaticales de los cortes .1/.2 se
sustituyeron por decisión expresa de Jorge.

## Respuestas breves y acompañante de Gica

`gica-creation.js` publica una presentación de sólo lectura del borrador:
propietario, UUID, revisión, paso, estado, pregunta, ocupado y hasta cuatro
respuestas revisadas para ese campo. `validateChoice` rechaza tokens obsoletos,
campos distintos, errores y solicitudes en curso. `romeo-voice.js` vuelve a
comprobar el estado de la conversación y envía la respuesta canónica por el
mismo servicio de entrevista. Un clic explícito puede interrumpir la pregunta
hablada propia: invalida sus callbacks y mantiene una sola captura. Por texto
no se activa el micrófono. La revisión final no ofrece confirmaciones rápidas.

`gica-companion.js` muestra sólo el intercambio reciente en RAM y reutiliza los
mismos nodos de opciones dentro del panel o de la burbuja. No hace solicitudes,
no guarda conversaciones y no ejecuta herramientas. Selecciona posiciones por
solapamiento con campo/foco, navegación y menús; usa Web Animations sin estilos
inline, movimiento reducido y controles para minimizar/abrir/apagar micrófono.
Un agarre accesible permite arrastre con ratón/touch y flechas del teclado. La
posición manual vive en RAM, prevalece sobre el posicionamiento automático y se
limita al viewport al redimensionar. Inicio o doble clic recupera el modo
automático; minimizar y ampliar conserva la posición elegida.
La ocultación de la página, salida o cambio de cuenta limpia su presentación.
Zoom/Meet son declaraciones de plataforma con enlace pendiente, sin provisión
externa. No se modifican permisos, aprobaciones, modelos ni presupuesto.

La ficha manual usa tres bloques superiores y dos inferiores, con adaptación a
dos/una columnas. `event-form.js` ofrece valores fijos de capacidad y zona horaria
como mejora progresiva; conserva los mismos nombres y validación del formulario
Django. Sus opciones se bloquean durante entrevista o proyección, sin introducir
campos persistentes ni permisos nuevos.

## Fechas múltiples, formulario vivo y control del turno

`apps.assistant.date_language` amplía la creación guiada sin modificar el parser
`parse_date` anterior. Consume una declaración completa de días antes del mes,
listas, rangos o varios meses, con números escritos, meses/setiembre y relleno
revisado. Fechas ISO o DD/MM/AAAA también se admiten. Números sobrantes, meses
desconocidos, fechas imposibles y rangos inversos fallan; no se extrae una fecha
parcial para ignorar una contradicción. Un año nuevo debe ser 20xx completo y no
anterior al año local del servidor; los días pasados del mismo año se permiten.

`DateYearRequired` conserva sólo pares día/mes en `_pending_date_year`, dentro del
borrador privado y fuera de los campos de respuesta. UUID y revisión cubren ese
guardado; responder únicamente el año completa la selección. Corregir una fecha
incompleta oculta la selección anterior para que no parezca la nueva. Tras validar,
la respuesta confirma día de semana, mes, año y cantidad de fechas restantes.

`Event.scheduled_dates` conserva hasta 366 fechas civiles ISO ordenadas y sin
duplicados. `normalize_scheduled_dates` es la regla canónica compartida; la
restricción del año actual se aplica al declarar fechas, mientras la integridad
del modelo admite datos históricos sin invalidarlos al cambiar el año. El inicio,
si existe, debe pertenecer al primer día seleccionado en la zona del evento.
Las fechas sin hora siguen visibles en el calendario con hora por definir.
Formulario, servicios, catálogo y calendario usan la misma selección; un evento
aparece en varios días o meses sin duplicar la entidad ni su aforo. La proyección
y los filtros siguen limitados a `visible_events`; el contexto del proveedor
incluye la lista como dato, sin activar una consulta remota.

Los planes sólo pueden ocupar días seleccionados. En varias jornadas, la duración
total confirmada limita la suma del tramo ocupado por cada día, incluidos los
descansos entre sus sesiones; no se aplica el final de la primera jornada a todas
las demás. Se divide correctamente una sesión que cruza medianoche; terminar
exactamente a medianoche no ocupa el día posterior. La integridad histórica permite
editar otros campos o reordenar las mismas fechas tras cambiar el año; una nueva
fecha o inicio manual modificado sigue la regla del año actual.

El flujo abre `/events/new/` en el shell permitido y conserva la conversación.
`gica-creation.js` refleja campos guardados, fecha(s) y siete respuestas de
entrevista en el formulario principal. Una transcripción provisional tiene marca
visual propia y no escribe en el servidor. Los campos guiados se protegen frente
a edición paralela en ese formulario; el envío final utiliza el mismo borrador,
revisión y confirmación. Roles, propiedad, CSRF e idempotencia no cambian.
Por voz, el panel se contrae una vez por borrador para descubrir el formulario,
sin apagar la conversación; en texto permanece abierto. El cursor sigue el campo
actual mediante eventos locales y conserva su posición entre actualizaciones de
estado. Señala cambios observados; no controla el ratón del sistema ni acredita
acciones externas.

«Gica espera» detiene el envío automático y conserva el texto pendiente;
«Gica corrige», sólo desde espera, limpia ese texto y permite dictarlo otra vez;
«Gica continúa» retoma el turno y su espera de dos segundos. No cambian datos ya
confirmados ni otorgan acciones nuevas. La escucha anticipada es una excepción
acotada al estado `collecting`, excluye el resumen `review` y tiene checkbox visible:
usa `onboundary` y tiempo
estimado para intentar escuchar cuando resten cinco segundos estimados. Un filtro
de eco descarta coincidencias con la pregunta, pero no acredita cancelación
acústica. Si el navegador falla, vuelve a esperar el final de la lectura.
Nunca despacha mientras Gica está hablando; después exige dos segundos de texto
estable. `remainingEstimateMs` no es una medida de los segundos reales restantes;
la disponibilidad de `boundary` depende del navegador y la voz. El límite móvil
sube de 20 a 40 inicios/5min sólo con un borrador activo; se conservan dos
reconexiones cortas consecutivas, sin reintentar errores de reconocimiento.
Referencias:
[Web Speech API](https://webaudio.github.io/web-speech-api/) y
[evento boundary](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisUtterance/boundary_event).

Migración `events.0007_event_scheduled_dates` aplicada con respaldo y 43 tablas/
columnas anteriores preservadas. Runtime normal reiniciado y salud200; aceptación
cerrada con 550 casos (545 correctos/cinco PostgreSQL omitidos) y21bloques UI.
Audio físico y concurrencia PostgreSQL siguen pendientes; detalle en verificación.

## Creación guiada del evento — 15/11/2026

Solicitud expresa de Jorge: Gica debe ofrecer crear un evento al saludar, preguntar
paso a paso y completar la ficha con sus respuestas. Se implementa un flujo local
independiente del runner de seis acciones: `creation_language.py` reconoce una
petición directa de creación; `event_creation.py` conserva y valida el diálogo;
`POST /assistant/event-creation/` expone sólo operaciones humanas autorizadas.
`gica-creation.js` muestra pregunta, avance, ficha, correcciones y confirmación.

`EventCreationDraft` es privado por dueño, con UUID, revisión positiva, estado
`collecting/review/created/cancelled`, datos JSON y caducidad de 24 horas. Sólo hay
un borrador activo por cuenta; bloqueo del usuario y restricción única parcial
serializan las mutaciones en PostgreSQL. Cada entrega requiere UUID y revisión
esperada: la última entrega idéntica devuelve su recibo, un UUID reutilizado con
otro contenido o una revisión antigua produce conflicto con el estado actual.
Reanudar es lectura; una orden ajena sin UUID de borrador no captura el diálogo
persistido. Las pruebas SQLite no acreditan los bloqueos concurrentes de PostgreSQL.

Quince pasos recogen ocho campos de ficha y siete de entrevista. Los parsers
aceptan formatos explícitos de fecha/hora y cantidades acotadas; una hora ambigua
pregunta por su franja. La zona de Perú se adopta tras respuesta afirmativa, sin
inferirla de otro campo. Instituciones sólo del directorio propio y sin altas
implícitas; «sin institución» queda sin relación. Los estados de entrevista se
validan mediante `normalize_interview_answers`; datos opcionales pueden quedar
pendientes y no se inventan respuestas desde la descripción.

Durante el borrador, las respuestas son datos literales, incluso si parecen una
orden o HTML; la interfaz las inserta como texto. Los controles exactos de atrás,
revisión y cancelación se tratan aparte. «Gica cancela» en una sesión de voz con
borrador activo cancela ese borrador y reanuda la escucha; sin borrador conserva
su control local anterior y no llama al endpoint de creación. Una corrección mantiene las demás
declaraciones. El límite por respuesta es 300 caracteres, título 200 e institución
160; la ficha completa existente sigue permitiendo edición posterior más extensa.
El contexto no se envía a conocimientos, alias, herramientas, trabajos o proveedores.

Sólo `review` permite la confirmación final inequívoca «crear evento» o el botón
**Crear evento**; un «sí» aislado no basta. Una transacción reutiliza `EventForm`,
`create_event` y las reglas de entrevista para crear exactamente un evento y
vincularlo al borrador. La relación `PROTECT` conserva ese recibo frente a borrados.
No crea plan, tareas, `UIAction`, `Job` ni `AIUsage`. Autoridad humana vigente,
propiedad, revisión y CSRF se comprueban en el servidor; Revisor y contexto de
ejecución del agente carecen de esta capacidad. La síntesis/reconocimiento de voz
conservan permiso, pausa de captura salvo la ventana anticipada acotada descrita
arriba y descartes de callbacks antiguos; la interfaz
de texto ofrece el mismo recorrido sin micrófono.

El lenguaje de **Gica → Tu orden** se resuelve en `apps.jobs.command_language`
mediante un diccionario composicional y reglas puras, sin modelos ni tokens de
LLM. El manifiesto `romeo_intents.es.json` y los módulos fijos de vocabulario,
intenciones, diálogos y normalización comparten la versión `es-2026-11-15.6`. Componen saludos,
verbos, destinos y slots; no cargan código, regex dinámicos ni herramientas nuevas.
Un módulo ausente, inválido o con otra versión hace fallar cerrado el banco.
`POST /romeo/interpret/` comprueba autoridad humana vigente y devuelve intención,
datos o aclaración, sin consultar personas ni crear trabajos/recibos. El runner
valida las seis acciones `UIAction` existentes; el JSON nunca concede permisos.
Los alias, incluido Chica, sólo cambian vocativos permitidos, preservando nombres
y aclaraciones `person_name`. Contrato en [romeo-language.md](../arquitectura/romeo-language.md).

`command_normalization.py` aplica `gica_normalization.es.json` sólo a posiciones
gramaticales elegibles tras comprobar la petición original. Aliases, plurales e
inflexiones verbales revisadas preceden a la aproximación de nombres de destinos;
verbos/negaciones nunca reciben fuzzy matching. Candidato canónico único,
distancias/longitudes/contexto acotados y hasta tres pasadas a punto fijo evitan
cadenas de correcciones acumuladas. Distancia 2 sólo para calendario/directorio
largos con contexto fuerte; términos cortos mantienen límites menores o exactos.
La gramática y las múltiples acciones se revalidan después. Tokens conservan
offsets del texto NFC: el slot de persona no se corrige y la consulta sale del
original; sólo scopes de borde como «en los directorios» se canonicalizan.
La aclaración de tema reutiliza el intérprete con el prefijo fijo `Modo` cuando
corresponde y sólo permite las dos acciones de tema, sin otra tabla de respuestas.

La capa social pura `apps.assistant.social_language` carga el JSON independiente
`apps/assistant/data/gica_social.es.json`, versión `social-es-2026-11-15.4`.
Saludo, cómo estás, agradecimiento, saludo local a un nombre explícito y consulta
de hora devuelven `info` mediante el mismo contrato de cinco campos; no agregan
acciones, consultas de contactos, envíos, herramientas ni consumo de modelos.
La hora HH:MM se obtiene del reloj del servidor en `ZoneInfo("America/Lima")`.
Compone modales/cortesías, infinitivos, núcleo y persona mediante segmentos
declarativos; las guardas preceden a la poda, sin aceptar una parte de una frase
ambigua o negada. En `person_name` los nombres aislados, incluidos Chica o Buenos
Días, conservan prioridad; sólo una petición social explícita cambia de tema.
Una respuesta social en `theme` limpia ese contexto. Interpretación manual nueva
limpia la aclaración previa de la guía, evitando arrastrar un slot entre entradas.
Una cortesía o despedida completa también sale del slot de persona sin buscarla.
El JSON describe conceptos sociales con núcleos y lexemas gramaticales; gratitud
combina intensificadores, marco y contexto de ayuda/motivo sin enumerar oraciones.
Las pruebas contienen ejemplos y bordes adversariales. Repetición o distancia de
una edición con candidato único sólo pueden aproximar lexemas sociales elegibles
con apoyo contextual, nunca acciones, nombres, guardas o texto original. No es ML,
corrección difusa universal ni comprensión abierta del español. Una referencia
como «gracias por abrir calendario» sólo produce información, sin abrirlo o
acreditar ejecución; un segundo mandato no se absorbe como contexto de gratitud.
Las excepciones de cortesía no eliminan negaciones de órdenes.

Las dos entradas escritas, Conversar por texto y Ejecutar orden, muestran respuestas
sociales sin ejecutar controles. `interpret_for_owner` añade `info` al endpoint
`/romeo/interpret/` con sus seis claves: `status`, `action: null`, `query: ""`,
`message`, `options: []`, `catalog_version` social. El cliente finaliza información
sin runner ni recibos. El intérprete puro de acciones mantiene tres estados y
seis capacidades; la guía conserva sus cinco campos. Autoridad vigente, CSRF y
prohibición de administración/contexto de agente no cambian.

## Conversación guiada y navegación persistente

Abrir Gica mediante clic humano inicia saludo con el usuario SSR acotado y escucha
tras aviso guiado **v5** y permiso nativo. No se activa al cargar, por código ni
por restaurar una preferencia. Una orden clara se despacha tras **2000 ms desde el
último cambio del texto normalizado**, sin «¿Procedo?». Una orden sin saludo no
lleva preámbulo hablado. Un saludo explícito puede pronunciarse brevemente antes
de la orden mediante un prefijo literal revisado de `reply`; micrófono pausado,
sesión/ticket/borrador revalidados después y un solo envío al runner. Stop, edición
o navegación durante ese saludo invalidan la orden; el prefijo no concede autoridad.
Ruido sin palabras y resultados idénticos no reinician la espera. Un mapa RAM
acotado por ticket/índice conserva fragmentos; los parciales pendientes impiden
el despacho y una promoción idéntica a final no reinicia el plazo. El turno máximo
30 s empieza con texto. Las duraciones son estimadas del navegador, no una medida
de silencio físico. `X-Gica-Guide-Ms` mide procesamiento local.
Si el reconocedor termina con parciales pendientes, se descarta todo ese turno,
incluidos sus fragmentos definitivos. Se avisa y reconecta dentro de los límites
existentes; los parciales no sobreviven para bloquear el nuevo reconocedor.

`apps.assistant.local_commands` ofrece `/assistant/guide/`, guía sin modelos:
cinco campos `status`, `reply`, `draft`, `intent`, `follow_up`; las consultas y
órdenes ordinarias sólo leen; una enseñanza humana explícita válida puede guardar
un `LearnedAlias` por la ampliación posterior de conocimientos. Conserva
estados `ready/clarify/refused/info` y contextos vacío, `person_name` o `theme`.
Sólo `ready` produce borrador canónico e intención permitida. `readyOrder` inmutable
liga orden exacta, intención, generación de guía y sesión viva; el cliente usa el
formulario/runner normal que comprueba de nuevo permisos, CSRF, pestaña, TTL,
idempotencia y recibo. Las otras respuestas preguntan o informan sin actuar.
Edición, parada y callbacks obsoletos no pueden despachar. Texto guiado conserva
revisión y botón manual, sin iniciar micrófono ni síntesis. Planes y estados de
tareas siguen requiriendo aprobación humana por sus flujos propios.

`static/js/gica-navigation.js` mantiene cabecera, panel, cursor y controlador de
voz fuera del contenido sustituido. Sólo sirve SSR de `/`, `/calendar/` y
`/directory/`, con sus filtros GET manuales permitidos; no abre URLs arbitrarias.
Valida propietario, rol, destino, consulta, IDs y markup antes de importar el
contenido, sin scripts de la respuesta. Actualiza historial/URL y procesa el
fragmento con HTMX; el calendario se inicializa de forma idempotente.
Los eventos `sparkx:gica-navigation-start/complete`, ligados a un ID, pausan voz,
invalidan guía/turno parcial y retoman sólo al completar navegación, acción y TTS.
La transición de un clic se prepara y consume una vez, ligada a operación y ruta;
la llegada comprobada precede al cierre del recibo. Un fallo tras modificar el
contenido no afirma conservación de la página anterior ni repite el clic.

Contraer el panel no apaga la conversación; indicador y Stop siguen visibles y
una orden lista reabre el panel antes del runner. Stop/Terminar, ocultación,
recarga, navegación fuera de las tres vistas, logout, cambio de cuenta y errores
la detienen. No se persiste ni restaura una sesión de escucha. La guiada visible
no tiene TTL fijo de 300 s: admite máximo móvil de 20 inicios en 5 minutos y dos
reconexiones cortas consecutivas con backoff 500/1000 ms. Una escucha saludable de
30 s o un final válido restablece esa racha; errores no reintentan. Alcanzar el
límite exige nuevo inicio humano, sin prometer escucha ilimitada. El modo anterior
Voz rápida conserva 300 s por documento, 20 inicios totales, dos reconexiones sin
extender TTL y aviso command-session v2; no proporciona continuidad entre vistas.

`romeo-speech.js` usa exclusivamente voces compatibles con `localService === true`
y español para responder; no elige voz predeterminada/remota como alternativa.
Espera voces hasta 1 s y cada emisión hasta 8 s. No lee chat, consultas del
directorio ni contenido remoto: emite frases de aplicación, el saludo SSR y un
nombre aportado expresamente para recibir un saludo local. No busca a esa persona
ni envía mensajes; texto/control/HTML permanecen acotados y validados.
La voz invalida/aborta reconocimiento antes de hablar; tickets e identidad de
instancia impiden que callbacks viejos reabran micrófono. El indicador distingue
servicio iniciado, audio recibido, voz detectada, pausa y síntesis; `onend` sólo
acredita un evento del navegador, no volumen o audibilidad física. Los nombres
masculinos españoles identificados son una preferencia finita, no un atributo de
género de Web Speech. Sin voz elegida disponible se conserva respuesta textual.
El laboratorio temporal importa un módulo estático, detiene la sesión antes de
comparar y exige **Usar en Gica** para adoptar una voz española local. Guarda sólo
ID/ritmo por cuenta/navegador; si la elegida desaparece no la sustituye en silencio.
El reconocimiento puede usar un servicio remoto del navegador y requiere permiso;
voz local y lógica local no equivalen a reconocimiento offline.

## Memoria textual y patrones revisados

`InteractionRecord` registra texto final privado para mentor, separado de
`CommandPattern`. Su contrato conserva consentimiento v3 frente al aviso vocal v5:
POST JSON estricto, CSRF, humano activo y rol vigente; deniega contexto de agente,
recibos ajenos, campos/tipos/tamaños inválidos. Idempotencia por propietario y
request_id con huella de contenido; hasta 1000 filas sin purga automática. No crea
Jobs, AIUsage, acciones ni patrones. El estado declarado por cliente se distingue
del recibo del servidor. Lectura, revisión y borrado son del propietario; el CLI
`gica_memory` trata contenido como datos no confiables. Se ocultan formatos de
claves reconocibles, sin prometer detección universal.

El cliente recuerda sólo on/off por cuenta/v3, nunca texto ni cola en almacenamiento.
La cola RAM es acotada, sin reintentos; off, ocultación o salida descartan pendientes
e informan incertidumbre si un POST pudo llegar. La navegación parcial mantiene
el controlador, sin garantizar persistencia de todos los registros. Un fallo de
registro no bloquea ni repite la acción. No hay vigilancia permanente de Codex ni
entrenamiento automático. Hasta seis intercambios de interfaz quedan en RAM/DOM.

`CommandPattern` contiene frase revisada, intención de seis valores, clave única
normalizada por propietario y fecha. Sólo el humano activo con rol vigente puede
guardar/eliminar, con CSRF, revisión explícita, límite 200 y lock de propietario.
Una coincidencia exacta segura complementa una frase desconocida, sin reemplazar
rechazo, intención reconocida o banco inválido. Guardado y consulta conservan
negaciones, citas, condiciones y barreras administrativas. Una nota del mentor no
activa un patrón ni cambia permisos, modelos, presupuesto o estados del evento.
PostgreSQL sigue pendiente para acreditar concurrencia de locks.

## Gica-1: ejecución observada y piloto de USD 1

Autorización expresa del 15 de noviembre: OpenAI con máximo USD 1 de créditos,
eventos controlados y sin campañas exhaustivas. `apps.ai_management.pilot` aplica
un tope global permanente (cuentas/modelos/meses), reserva a tarifa Standard y
conserva consumos desconocidos. Un mutex migrado serializa reservas en PostgreSQL;
SQLite conserva un único coordinador de base de datos para el worker local;
no se afirma validación de locks entre procesos o servidores.
Sólo modelos de texto revisados y tarifas iguales o superiores a sus mínimos;
la comprobación se repite al preparar el snapshot, reservar y despachar. Un evento
debe conservar `is_synthetic=True` antes del envío. El tope no consulta ni modifica
la facturación del proveedor.

El worker congela también el payload OpenAI bajo los locks del evento/usuario;
incluye sólo historial y plan acreditados al mismo propietario/evento/proveedor/modelo.
Preflight y envío reutilizan el mismo cuerpo ligado a revisión, plan, prompt, acción
y límites; el envío no consulta ORM. Los helpers de compatibilidad del adaptador sin
Job no conceden autorización ni deben convertirse en otra ruta de envío.

`Job.execution_trace` registra únicamente códigos allowlist y marcas temporales:
cola, contexto preparado, conexión iniciada, respuesta recibida, validación y resultado.
Un observer ContextVar llama al registro antes de abrir HTTPS y tras leer la respuesta;
no contiene pensamientos del modelo, cuerpos remotos, claves o nuevos permisos.
Lease/claim protegen las observaciones. Cancelación, fallo y versión obsoleta se conservan;
el resultado siempre requiere aprobación humana. HTMX actualiza el monitor sin simular etapas.

Un indicador global consulta `jobs.live_status` con usuario/rol frescos y alcance
dueño+actor. Publica metadatos allowlist de hasta dos Jobs o una respuesta local
reciente, sin contenido privado del chat. El cursor SVG usa transformaciones de
presentación con coordenadas finitas, CSS externo y `pointer-events:none`; no
necesita `unsafe-inline`, bibliotecas nuevas ni privilegios de navegador/Windows.
El frontend rechaza etapas/URLs no permitidas y observaciones anteriores, pausa
en segundo plano, cancela al salir y detiene sondeo ante revocación 401/403.
El sondeo no genera clics, aprobaciones, pasos intermedios ni un heartbeat del worker.

Separadamente, `romeo-actions.js` acepta un catálogo de seis acciones humanas:
claro/oscuro, calendario, directorio, listado de eventos y buscar persona;
`jobs.ui_actions` registra la intención `UIAction` con TTL60s, CSRF, actor/rol
frescos, pestaña y huella HMAC de sesión. POST crea, inicia y recibe resultado;
reenvíos cambiados o transiciones terminales incompatibles se rechazan. Una
constraint parcial limita a una acción activa por actor/pestaña. El runner dispone
de pausa cancelable, `Detener`/Escape y cancelación al ocultarse; revalida antes
del clic sobre el selector constante del botón o enlace autorizado, comprueba el DOM y reporta.
Las etiquetas del cursor se invierten cerca del borde para mantener su punta
sobre el control real. Movimiento reducido mantiene el cursor acoplado.
No ejecuta selectores/acciones aportados por JSON, modelos, documentos o chat.
No reintenta clics si el recibo es desconocido. `completed` es declaración del
cliente, no observación del servidor ni evidencia de control del ratón. El contexto
de ejecución de agentes está denegado; no se amplían herramientas del LLM, permisos
administrativos, estados de tareas o aprobaciones. No crea Job/AIUsage.

La búsqueda guarda `UIAction.query` NFC acotada, sin controles y ligada a la
idempotencia; las otras acciones requieren vacío. Sólo navega a tres rutas propias
constantes y codifica q. La página destino valida ruta/consulta exactas y marcador
SSR antes de confirmar el recibo. Un handoff en sessionStorage se consume una
vez para ese acuse, nunca ejecuta navegación al cargar. No se confirma completed
en la página origen, ni se reintenta un clic al recargar. El hit-testing sigue
vigente tras desplazar un enlace fuera de vista. El toolbar de cuenta móvil ahora
ocupa espacio normal bajo la navegación, sin cubrir Directorio con Cerrar sesión.

El dictado compartido de `app.js` admite un destino y estado accesible por botón;
Gica reutiliza ese servicio para su campo de orden, sin una segunda integración
de voz. Sólo eventos finales escriben texto limitado; la identidad de instancia
y generación impide callbacks tardíos tras abortar. El runner no envía durante
la escucha ni ejecuta al recibir texto, y congela campo/micrófono al iniciar una
acción. En dictado normal, cierre de panel, Escape, ocultación y salida descartan
la escucha; la sesión rápida tiene la política acotada descrita arriba. La
aceptación explica el reconocimiento del navegador y el posible tratamiento
externo de audio. La ausencia de compatibilidad conserva el campo manual. Los
fixtures de reconocimiento prueban la interacción, no calidad de audio ni un
micrófono físico o la disponibilidad del servicio remoto del navegador.

`romeo_local` es una entrada del operador de confianza a las consultas locales
existentes: rol vigente, dueño, declaración sintética, UUID de idempotencia y
comando reconocido. No se expone al modelo ni crea un camino alternativo de IA.
Su respuesta se persiste como conversación local. Al detectarla en el evento
abierto, la UI refresca sólo el chat desde una vista GET propia, extrae etiquetas
y atributos permitidos y abre la conversación sin mover el foco de un editor.

`Iniciar SparkX.cmd` ejecuta `tools/start_sparkx.py` y `runromeo`: una web y un worker
en el mismo proceso, sin solicitar claves en consola. El worker está acotado a
adminjorge y eventos ficticios; reclama un Job específico elegible y se detiene
junto a la web. Revisa trabajos nuevos y pendientes, pero no crea solicitudes al
arrancar. Los leases vencidos se cierran sin repetir inferencia.

El coordinador admite hasta dos inferencias OpenAI/OpenCode independientes,
máximo una por evento y proveedor/modelo. Prepara contextos congelados, retransmite
observaciones y liquida resultados en su propio hilo; sólo inferencia corre en
el executor. Los hilos reciben namespaces sin ORM y ContextVars separados. Otros
adaptadores permanecen secuenciales. Los slots son locales al proceso; el apagado
espera ambos resultados. No duplica tareas ni agrega reintentos.

El superadministrador introduce la clave en **Gestión de IA → APIs y agentes**
(`/ai/control/`). `runtime_credentials` la conserva sólo en memoria por hasta dos
horas o hasta reiniciar, con referencia aleatoria ligada al propietario/proveedor,
versión y caducidad. El snapshot guarda la referencia, nunca la clave. Rotar,
desconectar, caducar o perder el registro invalida referencias anteriores sin
reutilizar una clave de entorno como alternativa silenciosa. Guardar no verifica
remotamente credenciales, saldo o cuota. Este almacén local no se comparte entre
procesos: un despliegue con workers separados requiere otra gestión de secretos.

`AgentGrant` asigna un único Gica-1 por cuenta, con modelo principal, versión y
tope monetario total de vida de hasta USD 1. Su resumen incluye el diario anterior
de la cuenta: cambiar nombre o recrear la asignación no reinicia consumo. El tope
global OpenAI de USD 1 sigue siendo independiente. La asignación activa preparada
usa GPT-5.4 mini y USD 1. El grupo gratuito se activa por decisión del humano,
después de autorizar individualmente los modelos y sus roles/políticas.

`AgentPoolEntry` permite los doce candidatos revisados con rol chat/plan/ambos,
prioridad, versión, límites internos diarios y huella de privacidad aprobada.
Con el grupo habilitado el chat lo usa desde el inicio, y los planes también si
se configura. Se selecciona por prioridad, trabajos de hoy e ID, omitiendo sin
llamadas los modelos sin capacidad interna. Agotar el grupo nunca escala a pago.
`FreeGatewayState` persiste una pausa local de diez minutos tras un 429 de alcance
desconocido, para todas las rutas OpenCode de la cuenta; no afirma reset del
proveedor. Cada Job mantiene un AIUsage y un solo modelo. Un consumo desconocido
retiene sus tokens aunque cambie el día UTC; la rotación no borra su recibo.

Sin grupo, una insuficiencia de presupuesto monetario del agente, mensual o del
piloto puede elegir la alternativa única heredada. El servidor liga la aprobación
del superadministrador a la política concreta y emite el recibo de la solicitud;
revalida perfil, política, permisos y evento ficticio. Cuotas de tokens, consumos
fuera de reserva o permisos insuficientes bloquean: no desencadenan otra IA.
No hay rotación, fallback o reintento después de un 429, error o timeout.

Las vistas y servicios administrativos reconsultan un superusuario activo;
`is_staff` o el rol Administrador del portal no conceden esa autoridad.
`agent_execution` impide el acceso administrativo durante la ejecución del agente,
aunque su actor sea superusuario. Las claves sólo viajan por HTTPS con Host válido
o por loopback directo de desarrollo, con POST/CSRF y redacción activa incluso en
DEBUG. No se devuelven en formularios, logs o respuestas. Son controles del
servidor y ContextVar, no un sandbox del sistema operativo ni una garantía frente
a código con acceso al proceso. El agente no dispone de herramientas administrativas.

Jorge comunicó haber introducido la clave privada; no se accedió a ella ni se
acreditó una inferencia OpenAI real durante esta actualización.
Las respuestas locales sintéticas de QA y los ensayos gratuitos históricos no
acreditan esta conexión ni su calidad real.

El apagado local conserva la confirmación POST/CSRF y la identidad de ejecución.
Su respuesta WSGI es autocontenida: primero envía la página de espera y después
un recibo de cierre. El comando espera al worker y a las solicitudes pendientes
y activas, excluyendo sólo los hilos que esperan ese recibo; cierra el listener,
señala el resultado y finalmente une esos hilos. Así no espera al propio stream
ni toma un error de red como prueba de apagado. El registro de streams se libera
también si el navegador abandona la respuesta antes de consumirla.
CSS y JS tienen nonce sólo en esta respuesta; no se permiten scripts inline
generales ni se necesitan recursos después de cerrar el puerto. Un fallo o la
ausencia del recibo durante cinco minutos muestran estado sin confirmar. El cierre
de pestaña respeta la política del navegador y conserva alternativa manual.
Este mecanismo pertenece exclusivamente al lanzador local, sin control de PID,
otros procesos, Windows o servidores desplegados.

Estado del primer incremento: [verificación y pendientes reales](../verification.md).

Decisión de arranque: 8 de noviembre de 2026, America/Lima. El usuario autorizó iniciar la construcción. Este documento define la dirección técnica; no acredita que todas las piezas estén implementadas, probadas o desplegadas. Consultar el plan de construcción y la evidencia de cada entrega para conocer el avance real.

## ADR-001: monolito modular con Django MTV y separación selectiva de responsabilidades

**Decisión.** Construir una sola aplicación desplegable, organizada por capacidades. El mismo proyecto proporciona el proceso web y un worker de trabajos persistidos. Django, HTMX y PostgreSQL mantienen la dirección de la propuesta aprobada. Las versiones exactas se fijan en dependencias después de comprobar compatibilidad y avisos vigentes.

**Motivo.** El prototipo requiere transacciones consistentes, control de permisos, generación de planes y una demostración completa, con presupuesto mínimo y un VPS existente de 4 vCPU/8 GB. Separar servicios y bases de datos antes de medir una necesidad ampliaría la operación y los puntos de fallo. No se ha verificado la capacidad libre del VPS.

MTV organiza la parte web: los modelos representan datos persistidos, las vistas reciben solicitudes y preparan respuestas, y los templates presentan contenido. Es una organización cercana a MVC, con la nomenclatura propia de Django; no compite con la decisión global de monolito modular. [FAQ oficial de Django](https://docs.djangoproject.com/en/5.2/faq/general/#django-appears-to-be-a-mvc-framework-but-you-call-the-controller-the-view-and-the-view-the-template-how-come-you-don-t-use-the-standard-names).

La separación en capas se aplica donde ayude:

| Responsabilidad | Ubicación y regla |
| --- | --- |
| Entrada HTTP y presentación | Vistas, formularios, templates y fragmentos HTMX. Validan formato de entrada, presentan errores y llaman operaciones de aplicación. |
| Casos de uso | Servicios de aplicación que verifican permisos, coordinan consultas, reglas, transacciones y trabajos. Pueden usar directamente el ORM de Django. |
| Reglas del problema | Funciones y estructuras Python para dependencias, restricciones, cambios, validación y transiciones, aisladas de HTTP y del proveedor IA cuando sea práctico. |
| Persistencia | Modelos, QuerySets y migraciones de Django; consultas autorizadas por evento. No duplicar el ORM mediante un repositorio genérico por tabla. |
| Integraciones | Adaptadores delimitados para IA, recuperación, solver y exportación cuando esas funciones se incorporen. Solo crear interfaces necesarias para sustituir o probar una dependencia real. |

Inspirarnos en arquitectura hexagonal o Clean Architecture significa proteger las reglas y aislar proveedores; no exige envolver cada operación del ORM. Las aplicaciones no necesitan todos los archivos o subdirectorios desde el primer día. Se añaden al introducir una responsabilidad concreta.

## Módulos del primer proyecto

| Paquete | Responsabilidad |
| --- | --- |
| config | Configuración por entorno, rutas raíz y puntos de entrada web. |
| apps.events | Propiedad y permisos del evento, ficha, datos confirmados/pendientes y operaciones básicas del organizador. |
| apps.directory | Contactos y organizaciones por propietario, participación por evento, versiones y consultas mecánicas con campos mínimos. Contactos separados de cuentas de acceso. |
| apps.planning | Candidatas, versiones aprobadas, diferencias, reglas, agenda y preparación ligada al plan. |
| apps.assistant | Conversación contextual, instrucciones versionadas, adaptador IA y recuperación autorizada. |
| apps.jobs | Trabajos durables, reclamo, intentos, lease, recuperación y cancelación. |
| apps.ai_management | Perfiles por propietario, autorización de pago, reservas USD/tokens y diario de consumo independiente de la publicación. |
| apps.project_checklist | Ayuda temporal exclusiva de adminjorge: guías, confirmaciones personales persistidas y observaciones locales sin red; separada de tareas, IA y pagos. |
| apps.accounts | Autenticación por correo/usuario, roles del portal, cambio inicial, sesiones revocables y acceso de revisores asignados. No concede privilegios técnicos o financieros. |
| apps.registration | Página pública por enlace opaco, inscripción mínima separada del directorio y aforo; apertura y cierre explícitos del propietario. |

Las inscripciones y la preparación con evidencia declarada tienen implementación acotada. Comentarios y reportes posteriores siguen pendientes. Esta tabla describe fronteras; no declara completas sus funciones ni su validación en producción.

### Directorio, catálogo y consultas mecánicas

`apps.directory` separa consultas autorizadas, servicios de escritura, formularios
y herramientas de lectura permitidas. Se normalizan nombres para buscar y correos
para evitar duplicados dentro del mismo propietario; no se fusionan homónimos.
Las mutaciones comprueban actor vigente, versión y relaciones bajo transacción.
La auditoría registra campos modificados sin copiar valores personales completos.
En participaciones y chat local el orden de bloqueo es Event → User. La semilla
se ejecuta con el servidor detenido durante mantenimiento.

`apps.events.catalog.find_events` comparte la población de listado, calendario y
herramienta: permisos antes de contar, filtros antes de limitar y fechas civiles
del evento o sesiones aprobadas. La proyección de eventos visibles sigue en memoria;
requiere medición antes de ampliarla a grandes volúmenes. El directorio pagina en
SQL y reutiliza el alcance autorizado al construir formularios de participación.

`apps.assistant.local_queries` reconoce comandos concretos y llama a tres consultas
locales de lectura. Persiste la pareja de mensajes con idempotencia, sin Job,
reservas ni AIUsage. No interpreta lenguaje libre ni incorpora todavía un ciclo
de herramientas de proveedores. Las restricciones explícitas de planificación ya
vinculan hasta tres expositores del directorio por identificador, nombre y versión;
tener un contacto no confirma por sí solo su disponibilidad.
Ver [modelo, permisos, referencia y límites](../arquitectura/directory-and-catalog.md).

### Restricciones y reparación mecánica acotadas

`Event.planning_constraints` y `planning_people` conservan una ventana horaria,
expositores habilitados y decisiones fijadas de un plan aprobado. El formulario
permite conservar inicio, expositor, recurso o duración por sesión; declarar la
ventana es una decisión del organizador. Guardar comprueba propietario, versión
de ficha y plan vigente, aumenta la revisión si cambió el contenido y conserva el
plan aprobado.

`planning.event_rules` contrasta la propuesta con el inicio de la ficha, la duración
confirmada de la entrevista y las restricciones configuradas. Revalida los contactos
versionados e incorpora reservas de otras agendas aprobadas del mismo propietario;
el alcance no consulta eventos ajenos ni disponibilidad externa. Estas reglas se
aplican al preparar candidatas y otra vez al aprobarlas.

`planning.constraints.repair_plan` busca una alternativa local con hasta doce
sesiones, tres expositores y tres recursos, ventana de hasta un día, inicios cada
quince minutos y un máximo de 50.000 pasos de búsqueda. Conserva identificadores,
contenido y decisiones fijadas; no ordena la agenda a partir de dependencias de
tareas. Produce una candidata pendiente de aprobación. Agotar la búsqueda no
demuestra inviabilidad ni optimalidad. Las carreras requieren PostgreSQL.

### Ciclo de ejecución local

`runlocal` es un punto de entrada de desarrollo con dirección fija `127.0.0.1`.
El comando comprueba las migraciones, registra en memoria únicamente su propio
controlador y atiende solicitudes hasta recibir el evento de cierre. No hay PID
introducido por el cliente, órdenes de shell ni terminación de otros procesos.
El registro desaparece al cerrar; `runserver` y los servidores de despliegue no lo
crean. Su extensión `runromeo` incorpora un worker controlado al mismo ciclo. El
lanzador único `Iniciar SparkX.cmd` reutiliza el entorno e inicia siempre web y
worker; las claves se gestionan después desde el panel privado, sin reiniciar.
El agente pertenece a la plataforma y no requiere otro lanzador.

La confirmación HTTP exige DEBUG, superusuario activo reconsultado en la base,
origen loopback, Host/puerto del servidor y ausencia de cabeceras de proxy. Requiere
POST, CSRF, casilla explícita y firma con caducidad de dos minutos ligada al usuario
y a la ejecución. Un GET no cambia el estado. Los roles del portal no conceden
control de procesos. Este mecanismo no debe exponerse mediante un proxy.

El servidor usa los hilos y cierre de conexiones de Django; espera las solicitudes
activas al cerrar. HTTP sin keep-alive y un timeout de sockets de diez segundos
evitan esperar indefinidamente conexiones ociosas. Una solicitud en ejecución puede
demorar el cierre. La respuesta confirma la solicitud de apagado, no certifica que
el proceso ya haya terminado antes de transmitirla. Los procesos de worker que se
inicien por separado conservan su ciclo independiente.

El resultado de apagado es HTML independiente sin descargas de recursos: un nonce
aleatorio por respuesta permite únicamente su estilo embebido mediante CSP. Las
demás pantallas conservan `style-src 'self'`; no se habilita `unsafe-inline`.

En Windows se reserva el puerto con `SO_EXCLUSIVEADDRUSE`: la reutilización normal
de direcciones allí permite binds simultáneos, por lo que el arranque duplicado
debe rechazarse explícitamente. Fuente: [documentación de sockets de Microsoft](https://learn.microsoft.com/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse).

### Cuentas y acceso de revisión

Se conserva el modelo User y la autenticación de Django. PortalAccount añade el rol
de portal sin utilizar `is_staff` para promociones. Las cuentas técnicas conservan
su autoridad previa y se protegen en la gestión del portal. El backend normaliza
correo/usuario, rechaza coincidencias ambiguas y no permite que otro backend elija
una identidad diferente; se mantiene el backend original para leer sesiones antiguas.
El alta comprueba ambos espacios de identificadores bajo el bloqueo del registro
administrativo. Las altas fuera de este módulo requieren respetar esa misma política.

Los comandos de cuentas vuelven a comprobar al actor, usan versión esperada y
serializan cambios con AdminRosterLock. No se permite autodesactivación ni retirar
el propio rol administrador; debe quedar un administrador activo. Los locks se
verifican en PostgreSQL, no mediante los resultados SQLite. La interfaz y sus vistas
leen un perfil por solicitud; los servicios no reutilizan ese snapshot para autorizar
cambios. La tabla de usuarios usa perfiles precargados para evitar consultas por fila.

`session_version` invalida sesiones tras cambios de contraseña o de acceso.
`access_version` invalida concesiones al cambiar rol/activación, pero no por cambiar
la contraseña. EventReviewAssignment fija el destinatario, versión de acceso y actor
que asignó. `Event.review_access_version` evita sobrescribir asignaciones simultáneas
sin alterar la revisión del contenido. Sólo el propietario organizador administra
esas concesiones; el rol Administrador no obtiene acceso a eventos ajenos.

El Revisor tiene una vista acotada de ficha, agenda aprobada y estados de tareas.
No recibe chat privado, candidatas, trabajos, formularios de edición o gestión de IA.
Middleware restringe rutas y servicios de evento mantienen la prohibición de escritura.
Los cambios de contraseña iniciales son obligatorios para cuentas nuevas y conservan
la sesión actual mediante el mecanismo nativo de Django; las otras sesiones caducan.

LoginAttemptWindow mantiene límites por origen y combinación origen/identificador,
con HMAC y purga de ventanas antiguas, sin contraseña, correo o IP en texto claro.
Se ignoran cabeceras de IP no confiables. La creación genera 20 caracteres en el
navegador con Web Crypto y rechazo uniforme; no usa `Math.random`, almacenamiento
del navegador ni servicios externos. El servidor exige 16–128 caracteres y aplica
los validadores y hashes de Django. No se han implementado MFA/SSO ni recuperación
por correo; no se afirma preparación para exposición pública sin validación adicional.

Fuentes de diseño consultadas el 13 de noviembre de 2026:
[autenticación Django](https://docs.djangoproject.com/en/5.2/topics/auth/default/),
[contraseñas](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/),
[backends](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/) y
[OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

## Flujo de una propuesta y su aprobación

1. El organizador autenticado describe o modifica su evento. El servidor identifica al actor y limita la consulta al evento autorizado.
2. Se comprueba el perfil seleccionado y se reserva su máximo USD/tokens mensuales junto con el Job, su base y clave idempotente. La web devuelve un estado consultable.
3. El worker reclama un intento válido y trabaja con esa instantánea. La llamada externa se realiza fuera de una transacción larga.
4. La IA propone contenido estructurado. Las reglas comprueban esquema, referencias, fechas, dependencias y restricciones del evento. La reparación mecánica acotada es otra vía explícita para preparar una candidata; no activa el plan.
5. Una operación breve y atómica comprueba intento, lease, cancelación y vigencia, y acepta el resultado como candidata revisable o lo marca inválido/obsoleto. Todavía no activa el plan.
6. La interfaz muestra propuesta, supuestos, validaciones y diferencias. El organizador aprueba una revisión inmutable exacta.
7. El servidor revalida permiso, contenido y revisiones esperadas en una transacción. Guarda la versión aprobada y cambia el único puntero al plan vigente, conservando el historial.

Política confirmada por el usuario el 12 de noviembre de 2026: el agente pregunta y prepara propuestas; el organizador confirma cambios del plan y estados de tareas. El chat no obtiene autoridad para escribir estados ni activar versiones. Se mantienen las exclusiones de acciones sobre terceros.

### Entrevista local y contexto revisable

`Event.interview_answers` conserva hasta siete respuestas estructuradas con estado
y texto acotado. Las reglas puras de `apps.events.interview` validan sus claves,
tipos, duración y estados: confirmado por el organizador, supuesto, pendiente,
referencia explícita a la ficha y No aplica donde corresponde. No interpretan texto
libre ni convierten datos del plan o del afiche en confirmaciones. Revisar siete
puntos puede dejar pendientes; ese recuento no es avance de tareas ni factibilidad.

La vista SSR permite guardar una respuesta y consultar un resumen editable sin
proveedor IA. El comando comprueba propietario y revisión esperada bajo el bloqueo
del evento. Un cambio incrementa `Event.revision`, conserva plan y progreso actuales
y deja obsoletas las candidatas/trabajos de bases anteriores. Un guardado idéntico
no incrementa la revisión. Si cambia la descripción, las referencias `in_brief`
vuelven a pendientes; las respuestas escritas explícitamente se conservan.

El contexto común del adaptador incluye las respuestas y su procedencia declarada
para planes y chat. No concede herramientas ni autoridad al modelo. La política
conservadora existente exige revisar de nuevo la preparación al aprobar un plan
después de cambiar requisitos; el progreso anterior sigue en su versión histórica.
El formulario lo advierte antes de guardar. Las restricciones textuales de la
entrevista no son un solver ni una comprobación automática de factibilidad.

Las operaciones que deben tener un único efecto local usan restricciones de base de datos, condiciones de versión y transacciones. Django ofrece atomic para agrupar cambios; on_commit permite posponer callbacks hasta después del commit, pero un callback fallido no revierte lo ya confirmado. [Transacciones de Django](https://docs.djangoproject.com/en/5.2/topics/db/transactions/).

## Gestión financiera de IA implementada

AIProfile conserva proveedor, modelo permitido, modalidad, máximos y tarifa revisada.
AIAccount controla selección y límites por propietario; AgentGrant añade la asignación
versionada y el tope total del agente, configurables sólo por superadministración humana.
Cada Job tiene un AIUsage con
instantánea inmutable de configuración, reserva y token de despacho persistente.
El orden de bloqueos es Event → User → AIAccount → Job → AIUsage. Las llamadas externas
quedan fuera de esas transacciones. La versión del perfil y el consentimiento se revisan
antes del despacho; una reserva de otro mes caduca sin llamar a la API.

El consumo se registra aunque un resultado sea inválido, obsoleto o cancelado. Un
consumo desconocido conserva la reserva y admite conciliación manual atribuida; el
uso real tardío prevalece manteniendo la auditoría. No se infiere saldo de créditos,
no hay fallback de pago y no se instala un LLM local automáticamente.
La disponibilidad real y las carreras PostgreSQL aún requieren verificación.
reporting.py implementa informes de sólo lectura: agregados SQL por evento/acción
y escenarios manuales o históricos comparados solicitud por solicitud. El costo
histórico se conserva; la comparación y PEN son proyecciones sin escrituras ni HTTP.
GPT-6 Luna usa caché explícita sin breakpoints para evitar escrituras no incluidas
en la reserva. GPT-5.4 mini usa caché automática, tarifa Standard y razonamiento
`none`; las reservas siguen siendo brutas y no presuponen incentivos externos.
Groq comprueba el contexto acotado antes de enviar.
Doce presets revisados incorporan un puente de chat a OpenCode local 2.2.7, con
proveedor remoto. Trece candidatos tienen políticas revisadas; Ultra, ausente en
el catálogo actual, queda excluido del producto. El modelo elegido queda fijado en la
instantánea del trabajo y se contrasta con la misma lista permitida en catálogo,
perfil, adaptador y proceso nativo. No hay descubrimiento o rotación automática:
la única selección por presupuesto es la alternativa exacta aprobada en AgentGrant,
antes de crear/despachar el trabajo. Exige evento ficticio al encolar,
preparar el trabajo y construir la llamada. El contexto es JSON cerrado; no se
seleccionan archivos del repositorio. El proceso usa entorno sin claves heredadas,
runtime desechable en `Temporal/`, un paso, herramientas denegadas y auxiliares
deshabilitados. Antes de inferir verifica configuración efectiva y precios cero
en el catálogo. Limita salida a 2.048 tokens y el trabajo a 90 segundos más la
gracia de terminación; no hay fallback ni reintentos propios de inferencia. OpenCode puede hacer
reintentos internos y se detiene al observar sus eventos de error/reintento.
Nueve modelos requieren aceptación específica por solicitud: token firmado ligado
a actor/evento/revisión/acción/UUID/perfil-versión/modelo/política, válido una hora.
Se registra en AIUsage.snapshot y se revalida antes de dispatch; el puente vuelve
a contrastar la huella. La configuración del perfil no acepta estas condiciones.
Para la alternativa de presupuesto, la aprobación humana exacta de AgentGrant
permite emitir ese recibo por solicitud; un cambio de política exige nueva aprobación.
La aplicación filtra historial y procedencia del plan por propietario, evento,
proveedor y modelo; omite textos sin origen acreditado o de otra IA. Las reglas y
la ficha declaradas del organizador son comunes. Cada ejecución usa estado nativo
privado y ContextVar para modelo/consumo; no constituye aislamiento del SO ni
garantiza ausencia de retención en el proveedor remoto.
Tres trabajos GLM de aceptación aislados fallaron sin contadores completos; el tercero
informó HTTP 429 y fallo de limpieza del runtime privado en Windows. No se realizan
más reintentos. La limpieza posterior retiró los tres runtimes residuales y no dejó
procesos OpenCode vivos. Se añadieron tres intentos de limpieza local con pausas
breves; no vuelven a llamar al modelo. Los dos ensayos posteriores, uno DeepSeek y
otro MiniMax, también devolvieron 429, con limpieza correcta y uso desconocido.
Dos agentes comprobaron el resto del recorrido con propuestas manuales sintéticas
en bases independientes; esa evidencia no acredita generación IA. La primera propuesta real del producto
sigue pendiente. La cuenta activa conserva perfil
sin seleccionar, pago deshabilitado y presupuesto USD 0.
[Contrato operativo y fuentes de tarifas](../guias/ai-management.md).

## Contratos y autoridad

Los nombres siguientes provienen del diseño previo. Su implementación puede distribuir campos entre modelos y objetos de intercambio sin crear una clase adicional por cada nombre.

| Contrato | Invariante principal |
| --- | --- |
| EventSpec / FieldClaim | Conservar entrada, procedencia y revisión; separar confirmado, supuesto, ambiguo y faltante. |
| InputSnapshot | Identificar la ficha, base de plan, restricciones y fuentes realmente utilizadas. |
| PlanCandidate | Guardar contenido revisable y su revisión; una edición produce otra revisión y nuevas comprobaciones. |
| PlanRevision | Historial aprobado inmutable; la vigencia pertenece al puntero del evento. |
| ChangeProposal | Explicar diferencias e impactos sobre una base identificada; simular no altera el plan activo. |
| ApprovalCommand | Identificar candidata y revisión exactas, base esperada y clave idempotente. El actor procede de la sesión. |
| Job | Persistir operación, entradas, solicitante, intentos y estado; el proceso worker no adquiere permiso para aprobar. |

No confiar en permisos, resultados del solver, marcas de verificación, costos o identidades porque aparezcan en una respuesta del modelo. Los genera o comprueba el servidor. Un JSON válido no acredita un plan válido.

## Seguimiento manual implementado

TaskProgress conserva el estado por pareja (PlanRevision, task_id), con versión,
último actor, fecha y nota. TaskProgressChange guarda cada transición con su actor,
nota y clave idempotente. Una tarea sin registro se presenta como «No iniciado».
El seguimiento se guarda aparte de los payloads inmutables de plan y candidata.

La operación de aplicación exige propietario, plan activo exacto, tarea existente
y versión esperada. Toma primero el bloqueo del evento y luego el del progreso,
dentro de una transacción; aprobación y seguimiento comparten ese orden. Una
recepción repetida del mismo comando no añade cambios ni restablece estados antiguos.
El servidor rechaza bases obsoletas. Las carreras se comprueban con pruebas de
PostgreSQL; SQLite no valida los bloqueos.

Al completar o reabrir se exige una nota. El historial muestra las últimas cinco
transiciones locales y, si corresponde, la versión y nota de origen heredadas.
Al aprobar una nueva versión, solo se arrastran registros de la versión activa
inmediatamente anterior cuando coinciden identificador, título, propósito y
requisitos, y sus antecesoras siguen iguales. Un cambio de ficha invalida ese
arrastre. Se preserva el actor/fecha reales y no se inventa una transición manual.

Las dependencias se informan; no bloquean automáticamente la transición. El avance
es una declaración manual del organizador. El contexto del chat incorpora una instantánea del
seguimiento y su porcentaje como declaración humana; la IA no tiene una operación
para cambiarlos.

`TaskPreparation` añade responsable del directorio con versión, plazo, nota o
enlace HTTPS y etapa: pendiente, preparado, aprobado o verificado por el organizador.
No modifica `TaskProgress` ni el payload del plan. Preparar, aprobar o verificar
requiere responsable activo y evidencia declarada; verificar además exige ejecución
completada y registra su versión exacta. El estado visible pasa a requerir revisión
si cambia el plan, responsable o ejecución. El historial conserva actor, campos
modificados e idempotencia con digest HMAC; no copia los textos de evidencia.
Los enlaces no se visitan, no hay adjuntos ni verificación independiente automática.

## Inscripción pública acotada

El propietario abre o cierra inscripciones por POST autenticado, CSRF, confirmación
y versiones esperadas. Abrir requiere un plan aprobado y crea un enlace aleatorio
de 256 bits. La página expone su agenda publicada y recibe nombre y correo;
`Registration` permanece separado de los contactos y las cuentas de acceso.
Un cambio de plan pausa la admisión hasta una republicación explícita.

La transacción de inscripción bloquea Event, valida el formulario firmado y su
versión, consume una clave idempotente y cuenta registros activos antes de ocupar
un cupo. El correo normalizado es único por evento. Aceptación, duplicado, cierre
y aforo completo devuelven el mismo acuse público; no se envía correo ni se verifica
su titularidad. Las tres carreras específicas de inscripción siguen sin ejecutar
en PostgreSQL. No se ha desplegado una página pública externa.

La aceptación independiente de interfaz pasó siete comprobaciones con un fixture
manual sintético, sin inferencia: aprobación/recuperación, conflicto y alternativa,
evidencia/reapertura e inscripción con duplicado y aforo dos. Se corrigió la política
referrer pública a `same-origin` para evitar `Origin: null` y rechazo CSRF; el flujo
corregido pasó en Edge de escritorio y móvil. Recibo: `Temporal/qa-closing/ui-acceptance.json`.
Este resultado no sustituye la generación real pendiente ni una prueba de carga.

## ADR-002: worker sobre trabajos persistidos, sin broker en el arranque

El primer worker será un comando de administración runjobs que reclama trabajos en la base de datos. Así, registrar la intención de trabajo y su entrada puede formar parte de una transacción local, sin introducir una segunda cola que deba sincronizarse con la base de datos.

El diseño completo necesita: reclamo atómico, identificador de intento, lease con vencimiento, recuperación acotada tras caídas y una comprobación final que impida publicar resultados de un intento que perdió autoridad. La caducidad de un lease no demuestra que la llamada remota se detuviera. Timeout, cancelación y reintentos no garantizan facturación remota exactamente una vez.

Separar tres ejes: ejecución del trabajo; utilidad del resultado (revisable, inválido, obsoleto o cancelado); y vigencia/aprobación del plan. La interfaz puede expresar estos estados con lenguaje sencillo.

PostgreSQL será el motor de referencia para la ejecución concurrente y las pruebas de reclamo/aprobación. SQLite puede facilitar un arranque individual, pero su select_for_update no establece los bloqueos de fila necesarios para validar este protocolo. [Diferencias del backend SQLite](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes).

Celery/Redis u otro transporte quedan condicionados a una necesidad real de operación o carga. Introducirlos no debe eliminar Job como registro autoritativo ni los controles de intentos y versiones.

## Seguridad que debe acompañar cada entrega

- Aislar por evento antes de consultar datos, recuperar documentos, llamar al modelo, exportar o mostrar un trabajo. El identificador de una URL no concede acceso.
- Mantener sesión, CSRF, método HTTP apropiado y autorización del servidor en cada escritura. Las vistas HTMX y descargas reciben el mismo control que las pantallas principales.
- Tratar mensajes, documentos y salidas del modelo como datos no confiables. No ejecutar código o herramientas arbitrarias ni convertirlos en templates de confianza.
- Escapar HTML; validar enlaces y recursos de exportación. No permitir que generar un PDF provoque acceso libre a redes internas o rutas del servidor.
- Mantener claves y configuración sensible fuera del repositorio, del almacenamiento persistente del navegador y de los registros. La entrada privada del panel no devuelve el valor. Registrar diagnósticos depurados y el mínimo de datos personales.
- Acotar entrada, salida, tiempo, reintentos, concurrencia y consumo por operación/evento. Una clave ausente no activa un simulador presentado como IA real.
- Registrar acciones relevantes y evidencia sin confundir borrador generado con tarea ejecutada o verificada.
- Revisar dependencias y configuración antes de exposición externa; probar restauración de datos y comportamiento ante fallos pertinentes.

Estos puntos son criterios de construcción, no un certificado de seguridad. El banco mantiene una matriz más detallada de amenazas y pruebas.

## Agente de trabajo y agente del producto

El mentor de construcción se utiliza en la sesión de ChatGPT Work/Codex cargando la configuración y el banco existentes. No es una instancia alojada nueva ni un modelo ajustado mediante entrenamiento.

El agente del producto tendrá conversación textual persistida dentro de cada evento, combinada con ficha, agenda y tareas editables. Sus permisos proceden del usuario y del caso de uso del servidor. La voz es una ampliación posterior: debe definir captura/transcripción, confirmación y privacidad, y no obliga a incorporar una plataforma de tiempo real en el primer recorrido.

## Despliegue, capacidad y límites

Desarrollar localmente y empaquetar para un servidor: proxy HTTPS, proceso web, PostgreSQL y worker, con volúmenes y secretos configurados por entorno. Contenedores no convierten esos procesos en microservicios. Antes de usar OVH deben verificarse servicios existentes, recursos libres, acceso, copias y configuración.

Objetivo inicial propuesto: 20 usuarios activos de operaciones web comunes, p95 inferior a 2 segundos, medido desde cliente con carga y errores documentados. Hasta 100 inscritos y explorar 50–100 concurrentes son capacidades diferentes. La generación pesada tendrá un límite propio, inicialmente 1–2 como hipótesis a ajustar a cuotas y mediciones. Ninguno de esos valores es un benchmark ejecutado.

El VPS no hospeda videollamadas ni se considera capaz de servir un LLM grande a muchos usuarios sobre CPU. Las rutas generales gratuitas conservan sus restricciones sintéticas. El piloto compacto dispone de la excepción de contexto público y de OpenAI explícito bajo el tope acumulado USD 1 descritos al principio; su disponibilidad se acredita mediante resultados reales. No contratar recursos o consumo adicional sin autorización.

## Alternativas consideradas y condiciones de revisión

| Alternativa | Decisión de arranque / motivo para reconsiderar |
| --- | --- |
| Microservicios y Kubernetes | Posponer; revisar solo ante equipos, despliegues o carga que exijan separación independiente. |
| SPA y API separadas para toda la UI | HTMX y renderizado servidor para el recorrido inicial; revisar ante una interacción que requiera estado complejo en cliente. |
| Clean/hexagonal completa, repositorio por modelo | Adoptar fronteras externas selectivas; ampliar si el acoplamiento causa un problema comprobado. |
| Event sourcing y CQRS con infraestructura propia | Versiones aprobadas y operaciones explícitas son suficientes por ahora; historial de planes no equivale a event sourcing. |
| Multiagentes con herramientas autónomas | Posponer hasta demostrar mejora medible con permisos y consumo delimitados. |
| RAG para todos los datos | Base canónica para agenda, registros y estados; recuperación documental solo para procedimientos y evidencia pertinente. |
| GraphRAG, base vectorial separada o entrenamiento propio | Condicionados a un fallo medido que no resuelva una solución menor. |
| Solver o código generado y ejecutado por IA | Constructores de restricciones desarrollados por nosotros, con tiempo acotado; no ejecución libre. |

## Referencias de continuidad

- [Plan de construcción](../construction-plan.md).
- [Mentor y reglas de contexto](../../.agents/skills/mentor-sparkx/SKILL.md).
- [Diseño de casos](../../.agents/skills/mentor-sparkx/references/diseno-y-casos.md).
- [Contratos y autonomía](../../.agents/skills/mentor-sparkx/references/contratos-y-autonomia.md).
- [Banco de investigación](../../.agents/skills/mentor-sparkx/references/banco-investigacion/indice.md).
- [Decisiones y brechas](../../.agents/skills/mentor-sparkx/references/banco-investigacion/decisiones-y-brechas.md).
- [Matriz de seguridad y pruebas propuestas](../../.agents/skills/mentor-sparkx/references/banco-investigacion/matriz-seguridad-y-pruebas.md).
## Conocimientos públicos y asociaciones automáticas — 15/11/2026

Decisión posterior de Jorge: incorporar conocimientos y asociaciones sin aprobación
previa, con revisión manual posterior. Esto sustituye la aprobación previa sólo
para esta memoria nueva; no cambia planes, estados, permisos, APIs o presupuestos.

`public_knowledge.py` consulta la API oficial de Wikipedia en español, no Google ni
un LLM. Origen fijo HTTPS, sin proxy heredado, redirecciones, URL arbitraria ni
reintentos; un GET, tres candidatos, máximo128KiB, socket4s y deadline8s. Dos slots
de transporte acotan DNS bloqueado. Texto externo siempre es dato; nunca pasa al
intérprete de órdenes, a herramientas o a un prompt. No equivale a búsqueda general
ni a una respuesta sintetizada/verificada por IA.

`knowledge_service.py` reconoce marcos explícitos de información pública. Una orden
ambigua o un slot de nombre/tema no dispara búsquedas. Descartar formatos conocidos
de credenciales, enlaces y datos privados no garantiza detectar toda información
personal: la interfaz pide consultar sólo temas públicos. Roles humanos vigentes,
CSRF y dueño se comprueban antes y después del transporte. Reserva durable por UUID,
huella de consulta, un pendiente por cuenta,20solicitudes externas/día local y5s entre
ellas; cachehits no consumen esta cuota. Un intento fallido no se reenvía por repetir
su UUID. Historial de reservas terminado con ventana de siete días, sin copia del
texto; la limpieza manual conserva las reservas de hoy para no reiniciar la cuota.
Locks y límites concurrentes requieren PostgreSQL para acreditarse; QA usó SQLite.

`KnowledgeEntry` conserva hasta200 entradas privadas con fuente, fecha, expiración
de24h y estado auto/reviewed/disabled. Se recupera por tema exacto normalizado,
no por similitud semántica. Caducado no se usa. Una corrección humana cambia la
atribución a memoria revisada; un refresco no sustituye decisiones humanas ni una
respuesta automática contradictoria. Biblioteca `/assistant/knowledge/` permite
filtrar, corregir, revisar, desactivar, reactivar tras revisión y eliminar.

`LearnedAlias` es independiente: hasta100 conceptos de1–3palabras que el humano
enseña explícitamente, por ejemplo «cuando diga programación, me refiero al
calendario». Validación local y activación automática, con revisión posterior.
Sólo cinco controles sin slots (temas, calendario, directorio, eventos); los nombres
y búsquedas de personas conservan prioridad. No extraer alias ni permisos de una
página. Los `CommandPattern` manuales revisados conservan su flujo y prioridad.
Una enseñanza válida escribe; consultas y órdenes normales mantienen SQL de lectura.

El panel pide primero la guía local de cinco campos. Sólo un resultado ambiguo sin
slot puede pasar al endpoint separado de conocimientos, que distingue información
pública de una orden no entendida. Checkbox permite apagar la consulta externa y
conservar lectura de caché. Respuesta textual íntegra y fuentes se insertan con
`textContent`; resumen breve se lee opcionalmente con voz local y captura pausada.
Se conservan tickets, cancelación, descarte de callbacks antiguos y seis acciones.
No hay ajuste de pesos ni aprendizaje de permisos. Migración `assistant.0005`.
