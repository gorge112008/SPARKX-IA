# Plan de construcción y criterio de cierre

## Etapa vigente: piloto completo y preparación de entrega

El piloto local de Gicaingenieros recorre creación, siete campos de preparación,
propuesta, aprobación, calendario, sustitución de Robert por Jorge Gayoso Ugas,
reprogramación del 19 al 26 de noviembre y ajuste de horarios. Se conserva un
evento y tres versiones aprobadas con once tareas pendientes. Hay formulario
manual de horarios e historial visible; los pasos y aprobaciones del guion están
autorizados expresamente para este piloto. No se amplían permisos generales del agente.

La suite completa tiene 1.445 casos correctos y 14 omitidos de PostgreSQL.
El recorrido y las guardas tienen evidencia independiente en
[verificación](verification.md). Entrega: informe y manual, diapositivas ES/EN y
paquete de código instalable separado de los datos activos. Publicación del
repositorio y despliegue multiusuario requieren su destino y configuración.

Pendientes fuera de esta aceptación: audio físico en el navegador del usuario,
concurrencia y carga PostgreSQL, disponibilidad real de expositores y Zoom,
e inferencia remota con datos permitidos y cuota autorizada. No se declara
completa la totalidad de módulos de las bases por haber terminado este recorrido.

## Antecedentes de implementación — sustituidos por el corte vigente

Evidencia vigente: [verificación y pendientes reales](verification.md).

Mejora de presentación del 16 de noviembre: acceso en Mis eventos, cursor SVG con
movimiento y clic en Nuevo evento, cinco bloques compactos y título letra por
letra. La descripción se inserta completa. La demo narra el seminario de forma
natural sin abrir el panel manual y conserva el piloto existente. La burbuja
admite arrastre y posición manual, teclado y retorno a posición automática.
Las pruebas de esta mejora y sus límites se registran en el corte actual de
verificación; no cambian la aprobación pendiente del plan ni consumen modelos.

Estado actual del16de noviembre: Jorge autorizó eliminar sus eventos y borrador
y conservar sólo un piloto GICA para el jueves19a19:30. Respaldo, ensayo en copia
y transacción completados: cinco eventos/dos borradores anteriores eliminados;
piloto de19/11/2026,19:30–21:00 con cinco sesiones/once tareas propuestas. La
agenda requiere aprobación humana. Narrador muestra ese mismo evento sin
duplicarlo; arranque audible inmediato y diagnóstico visible.80pruebas backend,
cuatro escenarios finales de replay y siete contratos de proyección correctos.
Audio físico sigue sin comprobarse; ver límites y evidencia en verificación.

Primera demo narrada, ahora sustituida: botón en
Conoce a Gica y panel, guion breve que completa15campos, revisión y guardado
de un evento ficticio mediante el servicio actual, sin micrófono ni modelos.
Siete escenarios de navegador correctos con voz sintética. Audio físico
pendiente; no se creó un evento en la base activa durante estas pruebas.

Corrección del16de noviembre: confirmaciones del directorio separadas de nombres,
búsqueda por términos con sugerencias para elegir y recuperación del borrador
atascado por un fragmento de la pregunta. Preguntas más breves y2,5s de texto
estable sólo en ese paso.144pruebas integradas (142correctas,2PostgreSQLomitidas)
y6bloquesUI aislados correctos; runtime sano y datos conservados. No amplía el
alcance ni acredita audio físico o concurrencia PostgreSQL.

Arranque autorizado por el usuario el 8 de noviembre de 2026, America/Lima. Las fases siguientes ordenan entregas revisables; no son funcionalidades ya implementadas ni fechas garantizadas. El README y los resultados de comprobaciones deben describir el estado real de cada entrega.

## Punto actual — cierre del 15 de noviembre de 2026

Ampliación actual implementada y verificada con límites: fechas naturales múltiples con
retención de día/mes si falta el año, regla 20xx desde el año local actual y un
evento visible en cada día seleccionado. El formulario principal refleja la
entrevista y la transcripción provisional sin guardarla antes de terminar el
turno. Controles Gica espera/corrige/continúa y escucha anticipada opcional al
final estimado de preguntas de creación. No garantiza cinco segundos reales ni
ausencia de eco. La duración total de planes suma los tramos ocupados por jornada,
incluidos descansos; cada sesión debe respetar los días seleccionados. Migración
`events.0007` aplicada con respaldo y 43 tablas/columnas previas conservadas;
runtime reiniciado, salud200. La suite final tiene550casos:545correctos ycinco
omitidos de PostgreSQL;21bloques UI actuales correctos, sin sumar versiones
visuales sustituidas. Audio físico/eco real y concurrencia PostgreSQL pendientes.
Los resultados de la sección siguiente
corresponden a la creación guiada anterior, sin esta ampliación.

Ampliación vigente: creación conversacional de eventos solicitada expresamente
por Jorge. Gica ofrece crear al saludar y completa una ficha visible por voz o
texto, con 15 pasos y las siete preguntas de entrevista. Borrador privado de
24 horas, correcciones, atrás, cancelación y reanudación. Sólo el resumen completo
permite la orden final «crear evento» o el botón; «sí» aislado no crea nada.
La persistencia es transaccional, con UUID/revisión y datos literales separados
de navegación, conocimientos y alias. 307 pruebas correctas y 13 bloques UI
aislados con 32 turnos y cinco emisiones de voz adicionales. Incluye «Gica cancela»
con cancelación real del borrador y continuidad; cero modelos, llamadas externas, Jobs, AIUsage, planes o
UIActions en esa QA. Migración `assistant.0006` aplicada con respaldo y 42 tablas
previas conservadas; servicio normal reiniciado y salud 200. Audio físico y
concurrencia PostgreSQL siguen pendientes. Evidencia en [verificación](verification.md).

Ampliación posterior autorizada: conocimientos públicos y asociaciones de lenguaje
con incorporación automática y revisión posterior. `/assistant/knowledge/` ofrece
biblioteca privada con fuentes/fecha, caducidad24h y corrección/desactivación/borrado.
Wikipedia es la primera fuente sin clave ni tokens;20consultas externas/día y
cachehits reutilizados. No es búsqueda general de Google ni razonamiento por LLM.
Enseñar conceptos mediante «cuando diga programación, me refiero al calendario»
activa una asociación acotada a controles existentes. No modifica planes ni tareas.
Esta decisión sustituye la aprobación previa de la memoria nueva, no la del
`CommandPattern` histórico ni la de cambios de negocio. Ver evidencia vigente.

Actualización vigente de Gica: diccionario local composicional y modular
`es-2026-11-15.6`, con vocabulario, intenciones/slot de persona, diálogos/saludos y
normalización como cuatro módulos fijos. Compone conceptos y expresiones
reutilizables. «Hola chica, abre eventos» reconoce el vocativo sin reescribir
«Busca a Chica» ni nombres de aclaraciones. No se entrenan modelos ni se consumen
tokens de LLM; el banco inválido falla cerrado. Sinónimos no agregan capacidades:
siguen exactamente dos temas, abrir calendario/directorio/eventos y buscar personas.
Negaciones, citas, relatos, condiciones, administración y órdenes múltiples no
autorizan ejecuciones parciales. Detalle en [lenguaje de Gica](romeo-language.md).

La normalización selecciona spans gramaticales tras las guardas originales y
revalida la gramática canónica. Plurales/variantes nominales e inflexiones verbales
son revisados; el fuzzy de distancia acotada sólo compara destinos elegibles,
no verbos, negaciones o nombres. Candidato único, presupuesto contra cada token
original y punto fijo de máximo tres pasadas impiden corregir por cadenas abiertas.
«Abre caldenarios» puede abrir Calendario, pero «Busca a Caldenarios/Evento»
preserva el nombre y sus offsets Unicode NFC. Scopes como «en los directorios»
se normalizan sólo en bordes, no dentro de personas. La guía de tema reutiliza
el intérprete con `Modo` y sólo acepta claro/oscuro. Social `.4` y los contratos
de cinco/seis campos y seis acciones permanecen separados y sin permisos nuevos.

La capa social local usa parser puro y `apps/assistant/data/gica_social.es.json`
con versión independiente `social-es-2026-11-15.4`: buenos días, cómo estás,
gracias, saludo a un nombre explícito y hora de Perú HH:MM desde el reloj del
servidor en `America/Lima`. Responde `info` sin añadir acciones, envíos, consultas
de contactos, Jobs, AIUsage o tokens. Compone modales, infinitivos y segmentos
saludo/núcleo/persona, con guardas antes de retirar cortesías; no necesita enumerar
todas las frases. Conversar por texto y Ejecutar orden admiten información social:
el wrapper de `/romeo/interpret/` añade `info` con acción nula/consulta y opciones
vacías en seis claves, sin runner ni recibos. El intérprete puro sigue con tres
estados y la guía con cinco campos. Nombres aislados como Chica o Buenos Días
conservan prioridad en `person_name`; sólo una petición social explícita cambia
de tema. La respuesta social durante `theme` limpia la aclaración y la interpretación
manual nueva descarta el contexto previo, sin ejecutar una petición anterior.
Un saludo que acompaña una orden segura puede hablarse brevemente antes de ella,
con micrófono pausado y revalidación de ticket, borrador y parada; no introduce
«¿Procedo?» ni repite la ejecución. Una orden pura sigue sin preámbulo y texto
guiado permanece manual. El JSON no concede herramientas, permisos ni gastos.
La capa conceptual reconoce gratitud por núcleo, marco y contexto gramatical de
ayuda/motivo, con lexemas en JSON y ejemplos en pruebas, sin memorizar todas las
oraciones. Typos como «graccias» se aproximan sólo en lexemas sociales elegibles
con apoyo contextual, por repetición o una edición con candidato único; no corrige
nombres, acciones, guardas ni texto original. «Gracias por abrir calendario» es
información sin acción o afirmación de ejecución; «gracias y abre» no se absorbe
como gratitud. No entrena modelos ni promete todo el español. Cortesía/despedida
salen del slot de persona sin buscar esas palabras. Si termina el dictado con parciales pendientes, descarta
todo el turno, avisa y reconecta dentro de los límites; no arrastra el parcial.

Abrir Gica mediante clic humano inicia saludo y escucha tras aviso guiado v5 y
permiso del navegador. Las órdenes claras se ejecutan directamente tras 2 segundos
sin cambios en texto definitivo, sin «¿Procedo?»; ruido sin palabras/resultados
idénticos no reinician y parciales pendientes bloquean despacho. Ambigüedad/datos
ausentes preguntan mediante guía local de cinco campos. Texto guiado conserva su
botón manual y los planes/tareas su aprobación humana. El runner existente valida
usuario, rol, CSRF, pestaña, orden, TTL, idempotencia y resultado; no hay modelos,
creación de eventos ni cambios administrativos por estas órdenes.

La navegación local mantiene cabecera, panel, cursor y sesión humana entre
Eventos `/`, Calendario `/calendar/` y Directorio `/directory/`, incluidos sus
filtros GET manuales. Valida HTML SSR, identidad y destino; pausa micrófono durante
navegación, acción y respuesta hablada, y retoma al comprobarlos. Contraer el panel
no apaga la sesión; Stop/Terminar siguen disponibles. Ocultar, recargar, salir de
esas vistas, logout, cambio de cuenta, error o resultado incierto la detienen;
no se restaura escucha desde almacenamiento. La guiada visible no tiene TTL fijo
de 300 s: máximo móvil de 20 inicios/5 minutos y dos reconexiones cortas consecutivas
con backoff 500/1000 ms, renovadas por escucha saludable de 30 s o final válido.
No se reintentan errores ni se promete disponibilidad ilimitada. El modo anterior
Voz rápida conserva 300 s por documento y sus límites de compatibilidad.

La memoria privada del mentor conserva registro textual opcional con contrato v3,
preferencia off recordada, hasta 1000 registros, revisión y borrado; sin audio,
parciales ni entrenamiento. Hasta seis intercambios permanecen en RAM/DOM. Los
patrones ejecutables son una memoria separada de hasta 200 frases, editables y
revisadas explícitamente: anotar una revisión no los activa. La síntesis usa voz
local; el reconocimiento puede enviar audio al servicio del navegador y exige
su permiso. El laboratorio detiene la sesión antes de comparar voces. La prioridad
sigue siendo prototipo y evidencia antes de los documentos finales. Resultados
medidos y pendientes vigentes en [verification.md](verification.md); no inferir
aceptación real de modelos o audibilidad a partir de pruebas simuladas.

Los párrafos siguientes conservan cortes históricos de la construcción y de las
integraciones IA. No sustituyen el comportamiento vigente de voz descrito arriba.

Última entrega: cursor visual global y seguimiento privado de Gica-1, con orden
local autorizada desde el chat. `buscar eventos: UNAC` dejó la respuesta local ID 2
en la demo, con cero llamadas y consumo de IA. La conversación abierta puede
actualizar esa respuesta mediante lectura sin clics ni cambio de foco. El cursor
señala observaciones reales y no opera el ratón del sistema. QA de interfaz:
12/12 bloques con datos aislados; la herramienta de control de la pestaña personal
sigue sin conexión. SparkX se encontró detenido y se inició con el lanzador
normal: el motor Python nuevo ya está cargado y la salud responde 200. Falta
confirmar privadamente la credencial si se usará OpenAI y autorizar los modelos
gratuitos elegidos; no se realizaron inferencias. Ver el primer apartado de
verification.md para evidencia y límites vigentes; los párrafos siguientes
conservan los cortes anteriores.

Ampliación posterior: grupo de doce modelos gratuitos autorizables por función,
prioridad y límites internos; chat gratuito desde el inicio, propuestas gratuitas
opcionales y principal OpenAI bajo USD 1. Rotación sólo anterior al despacho,
pausa persistente de pasarela tras 429 desconocido, reservas inciertas intactas.
Un coordinador y dos inferencias independientes con contexto congelado; slots
locales, no despliegue distribuido. Migración respaldada y aplicada sin modificar
eventos, usuarios ni consumos. No se activaron modelos ni realizaron llamadas.
La instancia abierta debe reiniciarse y la clave volver a introducirse; después
Jorge autoriza las políticas exactas de los modelos que habilitará. Evidencia y
límites en verification.md y ai-management.md.

Actualización posterior: Jorge autorizó iniciar **Gica-1 con OpenAI mini y un tope
global de USD 1**, sólo eventos controlados. Se implementaron guardas de gasto,
contexto aislado/congelado, monitor y un único arranque **Iniciar SparkX.cmd**, con
web y worker local, sin pedir claves en consola. El superadministrador activo las
configura para su propia cuenta en `/ai/control/`, **Gestión de IA → APIs y agentes**:
memoria efímera de hasta dos horas, sin persistencia, revocable y perdida al reiniciar.
La interfaz administra una asignación Gica-1 por cuenta, con tope vitalicio ≤USD 1,
principal y una alternativa OpenCode gratuita opcional. El cap global OpenAI USD 1
no se eleva desde el panel. La asignación instalada está habilitada, con presupuesto
USD 1, principal GPT-5.4 mini y **sin alternativa seleccionada** hasta su elección
y aprobación expresas. En ese corte la base activa tenía cero Jobs y cero AIUsage.

La alternativa se elige antes de encolar/despachar, sólo si la reserva USD del
principal no cabe en el presupuesto de agente, cuenta o piloto global. Requiere
evento ficticio y huella exacta de privacidad aprobada por el superadministrador.
Tokens insuficientes, overrun, revocación, políticas o credenciales inválidas, errores,
timeout y HTTP 429 no disparan otra ruta; no hay cadenas de modelos ni garantía de
cuota. Contexto y resultados mantienen procedencia por propietario, evento, proveedor
y modelo, sin enviar claves o facultades administrativas al LLM. El agente no puede
administrar conexiones, permisos, asignaciones o conciliaciones. Son controles de
aplicación, no un sandbox del sistema operativo; planes y estados requieren aprobación humana.

La demo nueva está preparada y los planes anteriores se conservan. Las comprobaciones
locales utilizan recibos y bases QA sintéticos identificados. Este cierre no efectuó
nuevas llamadas reales a proveedores: la primera inferencia OpenAI queda pendiente
de conectar la clave privada y pedir una operación controlada. Las simulaciones no
acreditan aceptación de IA real. Los párrafos de espera de cuota, OpenAI deshabilitado
y baselines que siguen son historia previa a esta autorización; el estado y las
comprobaciones vigentes están en [verificación](verification.md) y el contrato en
[Gestión de IA](ai-management.md). La prioridad sigue siendo prototipo y evidencia
antes del informe y los demás documentos finales.

El usuario confirmó entrega el **15 de noviembre de 2026 a las 12:00, America/Lima**.
La prioridad autorizada es terminar el prototipo y su evidencia, y después preparar
los documentos finales en español e inglés. El turno del 25–26 de noviembre sigue
pendiente. No se ha enviado ni publicado el proyecto.

Se implementaron restricciones explícitas con ventana, expositores versionados,
reservas de agendas aprobadas del mismo propietario y decisiones fijadas; reparación
mecánica limitada que propone otra candidata sin activar el plan; responsable,
plazo y evidencia humana separados de ejecución; página/agenda pública por enlace
opaco, inscripción persistida, unicidad de correo y aforo. Un cambio de plan pausa
admisiones hasta republicar. No hay correos, pagos, verificación externa o despliegue.

La integración gratuita permite elegir doce modelos de chat revisados por OpenCode instalado,
contexto ficticio cerrado, configuración verificada y precio cero antes de llamar.
Tres trabajos de aceptación aislados fallaron sin contadores completos; el tercero
informó HTTP 429 y fallo de limpieza privada en Windows. Se suspendieron nuevos
reintentos. Falta demostrar brief → IA real → candidata válida → aprobación →
recuperación. Una propuesta manual etiquetada puede comprobar el resto del flujo, pero
no satisface esa puerta de inferencia. Posteriormente se probó una vez DeepSeek y
una vez MiniMax mediante los dos agentes solicitados: ambos devolvieron 429, sin
contadores ni fallback. Elegir un modelo distinto requiere selección explícita.

El baseline anterior tuvo 816 pruebas: 804 correctas y doce PostgreSQL omitidas.
Las comprobaciones posteriores de seguridad, contexto y limpieza forman parte de
la suite final vigente descrita abajo; no se suman como ejecuciones independientes.
PostgreSQL y carga siguen pendientes.

Las migraciones se aplicaron con copia previa
`var/backups/pre-prototype-closing-20261115.sqlite3`.
`Temporal/qa-closing/local-integration.json` verifica conservación de filas y
columnas anteriores de las 29 tablas existentes. No aprobó planes ni activó perfiles.
La cuenta activa mantiene perfil sin seleccionar, pago deshabilitado y presupuesto
USD 0; los trabajos de aceptación usan una base sintética independiente.

La suite final posterior ejecutó **873 pruebas: 861 correctas y doce PostgreSQL omitidas**, sin fallos/errores, en 69,032 s. Sustituye los baselines anteriores como recuento vigente; no se suman ejecuciones. Los dos agentes completaron once bloques funcionales cada uno con fixture manual identificado; la ampliación posterior pasó diez comprobaciones de consentimiento en navegador. Se corrigió el cruce de historial/planes entre modelos; el contexto se acredita por propietario/evento/modelo. Nueve perfiles requieren aceptación por solicitud. No se hicieron inferencias nuevas y se conserva la elección de esperar cuota. Los datos activos permanecen fuera de las bases QA.

### Evidencia real pendiente de cierre

El ciclo recursivo vigente está en `Temporal/qa-two-users/` y
[verificación](verification.md#ciclos-de-dos-organizadores-ficticios--15-de-noviembre).
Dos organizadores sintéticos independientes probaron creación/entrevista,
aprobación, cruce de ponentes y alternativa mecánica, tareas/evidencia, inscripciones,
roles, versiones obsoletas y navegación de escritorio/móvil. Los 11/11 bloques de
cada uno verifican el recorrido local después del fallo de cuota; no prueban una
respuesta válida de IA. No se repiten llamadas sin disponibilidad confirmada.
Los párrafos siguientes conservan la evidencia del ciclo manual anterior.

Los fallos de `Temporal/qa-closing/acceptance.json` conservan consumo desconocido y
reserva por conciliar. La limpieza posterior de las tres carpetas privadas quedó
completada y CIM no encontró procesos OpenCode vivos; el error original permanece
en el recibo. El adaptador reintenta sólo limpieza local hasta tres veces, sin modelo.

La QA con fixture manual sintético pasó **7/7 comprobaciones**, sin inferencia,
en `Temporal/qa-closing/ui-acceptance.json`: aprobación y recuperación, conflicto y
alternativa mecánica, evidencia y reapertura, apertura de inscripción y dos registros
únicos pese al correo repetido, aforo dos y navegación. Edge de escritorio
1440×1000 claro y móvil 390×844 oscuro, sin errores inesperados; tres PNG finales.
Se corrigió `no-referrer` a `same-origin` en la página pública porque el envío llevaba
`Origin: null` y recibía 403 CSRF; el paso corregido se repitió correctamente.
La inferencia real sigue pendiente; la suite final ya terminó correctamente. No se declara éxito de IA
ni cero tokens por esta simulación. El usuario aún no tiene claves Groq/Google;
la [guía opcional de Groq Free](ai-management.md#guía-opcional-preparar-groq-free-en-privado)
prepara el entorno privado sin activar perfiles o pago.

Comentarios, reporte posterior, materiales más amplios, recomendaciones,
comunicaciones y otras funciones del anexo siguen pendientes. No se asigna un
porcentaje global ni se afirma una exención formal de módulos del concurso.

## Producto que construiremos primero

Un organizador prepara un seminario virtual: describe el evento, corrige datos, genera y revisa un plan, aprueba una versión, solicita un cambio y comprende sus impactos. La preparación conserva responsables, bloqueos y evidencia. Una cobertura básica conecta la agenda y las inscripciones de participantes con comentarios y un resumen posterior exportable.

La conversación acompaña acciones visibles y editables; no reemplaza la ficha, la agenda o la revisión de cambios. El 12 de noviembre el usuario eligió voz por turnos con texto revisable. Se mantiene el recorrido persistido como prioridad; la voz continua no forma parte de la siguiente entrega.

Supuestos de arranque, modificables expresamente por el equipo:

- Confirmado el 12 de noviembre: el agente pregunta y prepara propuestas; el organizador confirma cambios del plan y estados de tareas.
- Caso principal de seminario virtual y datos sintéticos identificados para la demostración inicial.
- Hasta 100 inscritos; validar primero 20 usuarios web activos. La concurrencia de IA se mide y limita aparte.
- Un servidor y una base de datos; desarrollo local antes de un ensayo de despliegue.
- IA gratuita autorizada sólo para datos ficticios mediante el puente acotado.
  OpenAI y gasto permanecen deshabilitados; el beneficio mostrado anteriormente
  no constituye autorización de consumo. Disponibilidad y consumo real pendientes.

## Fases y puertas de aceptación

| Fase | Estado contrastado al 15 de noviembre | Entrega concreta y puerta de cierre |
| --- | --- | --- |
| 0. Base ejecutable | Operativa local con demo reproducible; cierre pendiente. | Estructura, entorno, autenticación, salud y navegación implementados. El comando seed_demo_event carga el caso GICA y repetirlo conserva los cambios. Falta completar el ensayo de instalación y arranque desde una copia nueva siguiendo el README. Las rutas privadas deben exigir sesión. |
| 1. Evento persistido | Recorrido local verificado el 12 de noviembre. | Crear, consultar, editar, validar datos y aislar por propietario funciona. El calendario permite consultar eventos y agendas aprobadas. La edición navegable conserva plan y tareas y rechaza una revisión obsoleta con comparación explícita antes de reenviar. Pruebas de servidor y navegador sobre SQLite; la concurrencia multiusuario requiere PostgreSQL y sigue en la fase 6. |
| 2. Primera propuesta con IA | Integrada, aceptación real pendiente. | Entrevista, chat, Job, worker, adaptadores, reservas, validación y aprobación implementados. Doce modelos gratuitos revisados de OpenCode para eventos ficticios, contexto aislado y consentimiento específico cuando corresponde. Cinco Jobs anteriores fallidos; 429 en GLM, DeepSeek y MiniMax, consumo desconocido. Usuario eligió esperar cuota, sin nuevas inferencias. Falta brief → IA real → revisión → plan aprobado recuperable. Respuestas controladas no cierran la fase. |
| 3. Adaptación verificable | Reparación mecánica acotada implementada. | Restricciones, contraste con ficha/entrevista, contactos versionados, reservas del propietario y decisiones fijadas. Búsqueda local que conserva contenido y propone una candidata: doce sesiones, tres expositores/recursos, cuadrícula de quince minutos y 50.000 pasos. Aceptación local con fixture manual comprobada; falta evaluación general; agotamiento no demuestra inviabilidad u optimalidad. |
| 4. Preparación y conocimiento | Seguimiento y evidencia humana implementados; parcial. | Ejecución manual con historial/herencia; responsable versionado, plazo, evidencia y etapas separadas. Verificar exige ejecución completada y pierde vigencia ante cambios relevantes. No hay validación externa automática, adjuntos, materiales generales ni recuperación de procedimientos. |
| 5. Participante y cierre básicos | Inscripción básica verificada con fixture; cierre parcial. | Página/agenda, apertura/cierre explícitos, datos persistidos, duplicados y aforo comprobados en la QA manual. Cambiar plan pausa admisiones hasta republicar. Tres carreras requieren PostgreSQL. Comentarios y resumen posterior/PDF siguen pendientes. |
| 6. Validación y paquete | Suite final y QA locales comprobadas; IA real y paquete pendientes. | Suite final 873: 861 correctas y doce PostgreSQL omitidas, sin fallos/errores ni inferencia. Dos agentes: once bloques funcionales cada uno con fixture manual; después diez comprobaciones de consentimiento y capturas desktop/móvil. Faltan IA real, PostgreSQL, carga, instalación nueva y despliegue si procede. Después del prototipo: documentos finales bilingües, código, vídeo y contribuciones. |

Cada entrega debe ser navegable o comprobable antes de ampliar alcance. El primer arranque de hoy no tiene que completar todas las fases: debe dejar una base honesta y verificable, sin botones que aparenten operaciones inexistentes.

## Orden inmediato de trabajo

El usuario confirmó el 12 de noviembre la prioridad del recorrido describir evento → plan con IA → revisar y aprobar → adaptar y seguir tareas. Estos incrementos desarrollan las fases existentes; no añaden otra numeración de etapas.

| Incremento | Trabajo concreto y dependencias | Evidencia para avanzar |
| --- | --- | --- |
| Base recuperable, fases 0 y 6 | Revisar el inventario antes de preparar el primer commit local, preservando datos activos e ignorados. Ensayar instalación y demo en una copia y base aisladas dentro de Temporal. No publicar. | Arranque siguiendo README, repetición de demo sin reiniciar cambios, lista revisada de archivos versionables y configuración sin secretos. |
| Ficha y conversación coherentes, fases 1 y 2 | Edición navegable, contexto del avance y entrevista guiada local implementados. Siete preguntas, estados, pendientes y resumen editable sin IA; las respuestas alimentan el contexto común. Falta verificar las respuestas con IA real. | Corrección recuperable desde la interfaz y acceso ajeno rechazado comprobados. El contexto distingue declaraciones del organizador, supuestos, plan aprobado y preparación humana. La respuesta real debe respetarlo; el chat no modifica tareas ni activa planes. |
| Concurrencia comprobada, fases 0 y 6 | Ejecutar las doce pruebas omitidas en PostgreSQL aislado, incluidas las tres carreras de inscripción. No prometer capacidad multiusuario antes de esos resultados y de la carga. | Bloqueos, carreras e idempotencia medidos; fallos corregidos o límites explícitos. |
| Primera propuesta real, fase 2 | Resolver disponibilidad por una vía gratuita autorizada sin activar pago ni repetir intentos con cuota agotada. Conservar recibos fallidos y comprobar el resto con fixture manual etiquetado si es necesario. | Propuesta y consumo reales sólo cuando existan; error conserva evento y plan. La simulación no cierra IA. |
| Adaptación y preparación, fases 3 y 4 | Verificar restricciones, decisiones fijadas, reparación pendiente y preparación humana ya implementadas. | Cambio factible y bloqueo, diferencias, aprobación explícita y pérdida de vigencia de evidencia al reabrir; distinguir simulación de interpretación por IA. |
| Participante y cierre acotados, fase 5 | Verificar página/agenda e inscripción existentes con datos ficticios; mantener comentarios y reporte posterior como pendientes. | Duplicados y cupos controlados; carreras pendientes identificadas, sin inventar usuarios o indicadores. |
| Entrega revisada, fase 6 | Después del prototipo y su evidencia, preparar informe, manual y PPT finales en español e inglés, vídeo y contribuciones. Ensayar antes de las 12:00 America/Lima del 15/11. | Paquete coherente con funciones y límites observados. Publicación/envío requieren instrucción correspondiente. |

La autorización gratuita del 15 de noviembre no habilita OpenAI ni pago. La clave
anterior sigue siendo privada y no se solicita de nuevo para este puente. Un error
de cuota no autoriza fallback ni reintentos automáticos.
El trabajo sin inferencia puede continuar sin solicitar que comparta una clave.

## Cómo incorporar las herramientas investigadas

Se conserva Django/HTMX, servicios de aplicación, reglas de dominio, base de datos y worker del mismo monolito. La investigación disponible está en [proveedores, voz y memoria](../.agents/skills/mentor-sparkx/references/banco-investigacion/ia-y-calidad/proveedores-y-voz.md). Haber investigado una herramienta no implica instalarla, contratarla ni habilitar sus llamadas.

| Necesidad | Primera implementación recomendada | Ampliación condicionada |
| --- | --- | --- |
| Guiar al organizador | Entrevista local de siete puntos con respuestas persistidas y resumen editable. Consultar la ficha y remitir a ella sin repetirla; las respuestas pendientes no se inventan. Reglas para datos exactos; la interpretación de ambigüedad por IA sigue pendiente. | Conversación más abierta cuando el recorrido y sus costos estén medidos. |
| Memoria coherente | Datos de negocio en Django; recuperar ficha, revisión vigente y avance real con permisos. Separar preferencias de hechos y conservar procedencia. | Evaluar Letta u otra memoria externa solo ante una necesidad que esta recuperación no cubra. Persistencia no demuestra exactitud. |
| Ejecución del agente o harness | Aprovechar trabajos durables, validación, presupuestos y aprobación existentes. Exponer solo operaciones concretas permitidas por el servidor, con límites de pasos, tiempo y consumo. | Evaluar Hermes u otro runtime mediante un caso aislado y una revisión de seguridad; no convertirlo en dependencia del producto por defecto. |
| Voz | Por turnos, según decisión del usuario: pulsar para hablar, revisar texto y enviar; respuesta en texto con lectura opcional. Jorge confirmó que funciona el dictado. Faltan la experiencia completa de lectura/respuesta y otros dispositivos. | Conversación continua, ElevenLabs o Realtime quedan para una ampliación con condiciones, presupuesto y latencia medidos. |
| Proveedores y ahorro | Reutilizar Gestión de IA y sus adaptadores; evitar llamadas para fechas, porcentajes, permisos o consultas exactas. Persistir resultados y contar fallos. | Comparar proveedores sobre tareas equivalentes antes de activar otra ruta. Una cuota gratuita agotada no autoriza gasto. |
| Apoyo al desarrollo | Usar el mentor canónico y encargos acotados con criterios de aceptación. Aprovechar revisiones manuales en herramientas ya disponibles. | OpenCode, Claude u otro asistente son opciones de desarrollo, separadas del backend de SparkX. Los beneficios exactos de Gemini Workspace siguen pendientes de edición/licencia; no atribuir beneficios de planes personales. |

## Decisiones confirmadas el 12 y el 15 de noviembre

| Decisión | Respuesta del usuario y consecuencia |
| --- | --- |
| Plazo | Entrega el 15 de noviembre de 2026 a las 12:00 America/Lima, confirmada por el usuario el 15. Turno y duración de exposición siguen pendientes. |
| Prioridad | Cerrar describir evento → plan con IA → revisar/aprobar → adaptar/seguir tareas. Conservar esta prioridad al evaluar extras. |
| Autonomía | El agente pregunta y prepara propuestas; Jorge confirma cambios del plan y estados de tareas. No habilitar escritura autónoma de estados desde el chat. |
| Voz inicial | Por turnos, con texto revisable. No incorporar voz continua para cerrar este recorrido. |
| Créditos API | Capturas anteriores: Personal / SparkX-Pruebas, USD 61 con vencimiento 22/11 y límites de Mini; sin acceso efectivo verificado. OpenAI y pago siguen sólo preparados, sin autorización de llamadas. El puente gratuito sintético del 15/11 tiene autorización separada; guía en [Gestión de IA](ai-management.md). |

No se vuelve a preguntar por la propuesta, inscripción, aprobación, stack, paletas, hora de cierre o estas preferencias sin una razón nueva. El gasto adicional autorizado permanece en cero; el piloto de USD 5 descrito en la investigación sigue siendo una propuesta. Cualquier credencial alternativa se configura sólo en privado y con autorización concreta.

## Secuencia histórica propuesta y ajuste de cierre

Las fechas 12–14 recogen prioridades propuestas anteriormente, no resultados
ejecutados. El ajuste confirmado del 15 mantiene prototipo y evidencia antes de los
documentos finales bilingües.

| Fecha de noviembre, America/Lima | Prioridad y condición para avanzar |
| --- | --- |
| 12 | Completar edición navegable y contexto real de preparación; dejar plan y permisos coherentes. Preparar base recuperable y revisar entorno PostgreSQL. Jorge comprueba el beneficio API en paralelo. |
| 13 | Cerrar primera inferencia con configuración y presupuesto verificados. Demostrar cambio factible y conflicto conservando decisiones y avance; corregir fallos del recorrido antes de extras. |
| 14 | Validar el recorrido acordado y su cobertura básica de participante/cierre; medir lo ejecutable en el entorno real. Cerrar informe, manual, PPT y guion; grabar respaldo. No ampliar el producto para compensar una falta de evidencia. |
| 15 | Cerrar prototipo y evidencia con límites reales; después preparar documentos finales en español e inglés y ensayar antes de las 12:00 America/Lima. No iniciar módulos nuevos ni enviar sin instrucción. |

Esta secuencia propone prioridades, no garantiza cerrar todas las brechas en tres días ni supone disponibilidad continua del equipo. Si una puerta no se alcanza, informar el límite y ajustar explícitamente el alcance; reservar tiempo para evidencia y entrega. Se mantienen fuera de este cierre voz continua, nuevos frameworks, nuevas suscripciones y refinamientos visuales adicionales.

## Prioridad y límites de esfuerzo

El núcleo diferencial es la adaptación del plan persistente con impactos explicados, decisiones preservadas y preparación sustentada en evidencia. La cobertura básica de participante y cierre conserva las salidas esperadas del desafío; su profundidad se mantiene acotada.

Después de ese núcleo y de la cobertura básica solo se añade una función si resuelve un defecto crítico, una obligación aplicable o un criterio de aceptación fallido. Se registra su coste y qué actividad desplaza. Se posponen más modalidades de evento, personalización avanzada, recomendaciones complejas, grandes paneles, herramientas externas y voz completa si compiten con validación y entregables.

No entran por defecto: pagos, mensajes masivos, configuración de Zoom/Meet/Teams, ejecución autónoma en terceros, videollamadas propias, microservicios, Kubernetes, un LLM propio o un motor distribuido de datos sin necesidad medida.

Las doce fichas y sus 60 criterios del mentor son un catálogo para priorizar y verificar. No obligan a construir doce módulos con igual profundidad ni acreditan pruebas ya ejecutadas.

## Comprobaciones que protegen el recorrido

Elegir pruebas por riesgo y comportamiento, no por cantidad. Los fallos de proveedor pueden simularse en pruebas para repetir escenarios; una simulación nunca sustituye la evidencia de inferencia real de la demostración.

| Riesgo | Evidencia necesaria al llegar a la fase correspondiente |
| --- | --- |
| Acceso a otro evento | Intentos de lectura y escritura en página, fragmento HTMX, conversación, Job y exportación son rechazados sin filtrar contenido. |
| Contenido IA inválido | Esquema incorrecto, referencias ajenas, fechas ambiguas, duraciones inválidas o ciclos no sustituyen el plan vigente. |
| Aprobación equivocada | Revisión o base diferentes de las mostradas obligan a revisar otra vez; solicitudes repetidas no crean otra versión aprobada. |
| Trabajo tardío o perdido | Reclamo, recuperación por lease y resultado de intento obsoleto mantienen un único efecto local. Cancelación efectiva y aceptación se arbitran sobre el estado persistido. |
| Doble inscripción o último cupo | La concurrencia no excede aforo ni duplica una inscripción válida. |
| Salida activa | Texto malicioso en entrada o respuesta no ejecuta HTML/script ni hace que exportar acceda libremente a recursos internos. |
| Estado engañoso | Borrador, aprobación, ejecución y verificación permanecen distinguibles y atribuibles. |
| Fallo operativo | Reinicio y restauración preservan datos; errores, cuota agotada o configuración ausente no producen una aprobación parcial. |

Las pruebas de bloqueos, carreras y transacciones concurrentes requieren PostgreSQL. Un arranque o suite sobre SQLite no permite afirmar que esas propiedades funcionan. Los controles del worker se implementan junto al protocolo durable, no se deducen de que el comando arranque.

## Evaluación del aporte

Antes de medir, fijar instancias pequeñas anotadas, variantes comparables y reglas de cálculo:

- Interpretación: campos esperados, ambigüedades, restricciones y preguntas de aclaración en español e inglés según el corpus.
- Planificación: violaciones duras, compromisos conservados, sesiones movidas, desplazamiento y reasignaciones, frente a una regeneración bajo las mismas condiciones.
- Recuperación: documentos canónicos autorizados y revisiones; consultas separadas entre ajuste y evaluación. Deduplicar antes del corte de cinco documentos y separar consultas sin respuesta.
- Respuestas: afirmaciones respaldadas y ausencia de datos inventados; una cita por sí sola no demuestra respaldo.
- Preparación: coherencia de estados y evidencia afectada por un cambio material.

Guardar también resultados negativos. No atribuir al prototipo porcentajes publicados por otros autores ni presentar un objetivo como mejora alcanzada.

## Capacidad, latencia y presupuesto

Meta inicial propuesta: p95 inferior a 2 segundos en operaciones web comunes con 20 usuarios activos, desde cliente, excluyendo generación IA. Antes del ensayo deben fijarse duración, ritmo, mezcla de operaciones, errores permitidos y hardware real. Informar p50/p95, tasa de errores, CPU/RAM y corrección, además del volumen de usuarios.

Para IA registrar por separado espera en cola, generación, tokens/solicitudes observados, fallos y consumo. El límite inicial de 1–2 trabajos pesados es una hipótesis operativa; se ajusta a cuotas y pruebas. No afirmar 100 generaciones simultáneas ni capacidad garantizada del VPS.

Antes de invocar un proveedor real se necesita saldo/cuota verificados, clave configurada por un mecanismo seguro, límites por operación y control de reintentos. No pegar la clave en chat ni en archivos versionados. El uso incluido y la ausencia de recargas automáticas deben comprobarse en la cuenta; una estimación local no es un tope contractual del proveedor.

## Experiencia y accesibilidad

Validar las tareas principales: describir evento, detectar un dato pendiente, comprender una propuesta, aprobar una revisión concreta, identificar un bloqueo y consultar agenda/inscribirse. Revisar teclado, foco visible, etiquetas, errores asociados, contraste y adaptación a móvil. Los estados incluyen texto además de color.

Usar estados verdaderos como En cola, Preparando propuesta, Revisando restricciones y Listo para revisar cuando correspondan al trabajo observado; no inventar porcentajes de progreso. Conservar entradas al fallar y ofrecer una siguiente acción útil.

La primera interfaz es una base para validar recorridos. La calidad visual y la facilidad de uso requieren inspección de la pantalla y observación del flujo; una colección de recomendaciones no las demuestra.

## Preparación de despliegue y entrega

El usuario confirmó entrega el **15 de noviembre de 2026 a las 12:00, America/Lima**. El comunicado conserva clausura el **25–26 de noviembre**; el turno sigue pendiente. Primero cerrar prototipo y evidencia, después preparar los documentos finales en español e inglés. Reducir extras si compiten con seguridad, validación y entregables.

Antes de OVH: verificar uso compartido, recursos libres, acceso, configuración, volúmenes y restauración; no reinstalar por la etiqueta de una imagen. Antes de datos personales reales: completar revisión normativa oficial, finalidades, datos mínimos, retención, derechos y tratamiento por proveedores. La demostración sintética no acredita cumplimiento normativo.

Preparar:

- Informe con problema, objetivos, método, arquitectura, implementación real, evaluación, resultados, límites y contribuciones.
- Presentación centrada en problema, adaptación demostrable, decisiones técnicas y evidencia.
- Código y manual con configuración, instalación, pruebas y límites conocidos, sin secretos.
- Vídeo de respaldo claramente identificado como grabación y datos reales del equipo.
- Guion con caso principal, cambio y conflicto, fallo recuperable y conclusión sustentada.

Un despliegue, envío o publicación externa requiere la instrucción correspondiente. Disponer de una URL o de una regla en un documento de concurso no autoriza por sí solo una acción externa.

## Definición de suficiente

El prototipo queda listo para entregar cuando se demuestra el recorrido acordado con datos persistidos, IA real e integridad del plan; las pruebas críticas del alcance pasan; se documentan carga y límites reales; la instalación es reproducible; y el paquete de entregables está revisado. No exige resolver todas las variantes de una plataforma comercial.

Si queda un fallo crítico de aislamiento, permisos, corrupción del plan o secreto expuesto, se corrige antes de ampliar funciones. Si una capacidad no se alcanzó, se reduce honestamente el alcance y se declara; no se presenta como implementada mediante una pantalla o una respuesta prefabricada.

## Dependencias de participación del usuario

La construcción local y la vía gratuita ya están autorizadas. Una credencial alternativa sólo se configura en privado con autorización concreta, nunca pegándola en la conversación. El acceso al VPS, los datos/contribuciones del equipo y el envío requieren intervención cuando corresponda. La hora de cierre ya fue confirmada; no se vuelve a preguntar.

## Continuidad

- [Arquitectura](architecture.md).
- [Mentor del proyecto](../.agents/skills/mentor-sparkx/SKILL.md).
- [Estado y plan previo](../.agents/skills/mentor-sparkx/references/estado.json).
- [Diseño de casos](../.agents/skills/mentor-sparkx/references/diseno-y-casos.md).
- [Matriz de amenazas y pruebas propuestas](../.agents/skills/mentor-sparkx/references/banco-investigacion/matriz-seguridad-y-pruebas.md).

Actualizar el estado del mentor al cerrar una entrega sustantiva. Distinguir hechos del usuario, supuestos de implementación, tareas pendientes y comprobaciones realizadas.
