# Lenguaje y continuidad de Gica-1

## Respuestas que superan el límite

Cada turno mantiene el máximo de 300 caracteres, compartido con el servidor y
la memoria. NFC, bordes y espacios repetidos se normalizan antes de acumular,
incluido el texto conservado por «Gica espera». No se deduplican frases por su
contenido: responder «sí» en preguntas distintas es válido.

Superar ese máximo pone sólo la respuesta en revisión. Se conserva el texto
local, se mantiene la escucha para controles y se muestra **Volver a dictar**.
Ese botón o «Gica corrige» limpian sólo la respuesta pendiente y permiten dictar
un resumen; no cambian la ficha. «Gica continúa» no envía una respuesta excesiva.
No hay recorte con ejecución ni envío parcial. La vista de revisión tiene un
límite defensivo de 4096 caracteres y avisa si muestra sólo una vista del texto;
no se guarda el exceso como una interacción ni se envía al servidor.
Un turno abierto durante 30 segundos sin confirmación del navegador pasa a la
misma revisión sin apagar la conversación. Los errores de permiso/dispositivo
conservan sus reglas de detención.

## Palabras clave para iniciar una creación

`apps/assistant/data/gica_creation.es.json`, versión
`creation-keywords-es-2026-11-16.3`, contiene palabras individuales por concepto.
No tiene frases de petición, marcos, prefijos, sufijos ni una gramática de oración.
La regla es **palabra de acción AND palabra de tipo de evento**. Se tokeniza el
texto normalizando mayúsculas/tildes y se cruzan conjuntos; orden, separación y
relleno no condicionan la coincidencia, dentro del límite común de 300 caracteres.

Las variantes revisadas de crear/organizar/armar/preparar incluyen formas
conjugadas, gerundios y nombres de acción; los tipos tienen singular/plural.
Nuevo/nueva y sus plurales conservan el acceso abreviado anterior. La coincidencia
es de palabras completas: recrear, creativo o eventualidad no aportan los
conceptos crear/evento. No hay raíces abiertas, similitud difusa ni ML remoto.
La abreviatura q es relleno, no un marco que deba registrarse para reconocerla.

Se conservan guardas de negación, citas/relatos, condiciones, peticiones
administrativas y órdenes incompatibles. Sin presupuesto, sin duda, ya y las
cortesías repetidas no se rechazan por la gramática anterior. Dos conceptos de
evento dentro de una descripción no equivalen automáticamente a dos peticiones;
la coordinación explícita de otro objetivo requiere aclaración. Antes de quitar
tildes se distingue creé/creó de cree/creo. Un banco ausente o inválido deshabilita
la detección.

El reconocimiento sólo abre o retoma la entrevista; no guarda el evento final.
Una consulta local pendiente no lo omite, y las respuestas sin esa intención
vuelven a su contexto. Dentro de una ficha activa los campos siguen literales.
Se conserva la espera de 1500 ms desde el último cambio de texto reconocido,
los permisos y la confirmación final del servidor.

La continuidad distingue el cierre normal tras recibir audio y `no-speech` de
los errores: esas capturas saludables reanudan la escucha sin agotar el freno de
fallos rápidos. `network`, `aborted` o arranques cortos sin audio admiten como
máximo dos reintentos; permiso denegado, dispositivo, idioma/configuración y
código desconocido detienen la voz y muestran el código sin reintentar.
Los finales válidos sobreviven al cierre nativo antes o después de terminar
TTS, con un único envío y la espera de 1,5 segundos conservada. Un parcial
incompleto se conserva para revisión, sin promoverlo a respuesta final.

El título neutral **Ficha del evento** no indica que esté escuchando. Cuando se
detiene, **Mic apagado · borrador guardado** y **Borrador en pausa** lo muestran
por separado. La conversación guiada no tiene un TTL absoluto de cinco minutos:
20/40 inicios son un límite móvil de arranques en cinco minutos. Agotarlo en
modo guiado deja el micrófono en pausa visible y programa su reanudación al
liberarse capacidad; conserva la sesión, permite texto y respeta Apagar/segundo
plano. No crea reconocedores adicionales ni reintentos en bucle. El diagnóstico
local conserva hasta 40 eventos de estado/código/tiempo/contadores sólo en RAM,
sin texto transcrito ni audio y sin envío nuevo al servidor.

Una reproducción aislada confirmó que tres cierres normales cortos podían
agotar la reconexión anterior, y esa ruta quedó corregida y probada. No demuestra
la causa del episodio real del usuario: sus metadatos no incluían errorcodes.
El reinicio y la comprobación móvil quedaron verificados; los indicadores no se
solapan con el cambio de tema. Las pruebas de voz usan reconocimiento/síntesis
simulados: el micrófono físico sigue pendiente de validación por el usuario.

## Fechas naturales y conversación mientras se completa el formulario

La creación muestra el formulario principal y va llenando sus campos e
entrevista. **Dictando** identifica una transcripción provisional: todavía no
está guardada. La ficha del panel y el formulario reflejan los datos aceptados;
usa **Corregir** para volver a un campo. La creación final sigue requiriendo el
resumen y la confirmación explícita, incluso desde el formulario principal.
Al comenzar por voz, el panel se contrae para descubrir el formulario; el cursor
señala el campo actual y la escucha continúa. Por texto se mantiene abierto.

Se admiten **«5 de septiembre de 2026»**, **«cinco de setiembre del año dos mil
veintiséis»**, **«5, 6 y 7 de septiembre de 2026»**, **«del 5 al 9 de septiembre
de 2026»** y **«25 de octubre y 10 de septiembre de 2026»**. La selección se
ordena y deduplica, hasta 366 fechas. Es un evento con varias jornadas; aparece
en cada fecha del calendario y puede filtrarse por un día intermedio.

Los días van antes del mes; fechas numéricas completas usan ISO o DD/MM/AAAA.
El año debe estar entre el año local actual del servidor y 2099. Si falta, está
incompleto como **203** o es anterior como **2021**, Gica conserva días y meses
y pregunta sólo por el año: responde **2026**, si ese sigue siendo el año actual,
sin dictar de nuevo toda la selección. Los días pasados del mismo año están
permitidos. No se ignoran números extra ni se corrige un mes desconocido por
suposición. Los rangos inversos y los días imposibles se rechazan. Tras aceptar,
Gica repite una fecha con día de semana, mes y año, y cuenta las restantes.

**«Gica espera»** pausa el envío y conserva lo dictado. Mientras espera, sólo
acepta los controles de continuar/corregir o apagar voz; no guarda palabras del
ambiente como respuestas. **«Gica corrige»** limpia el texto pendiente para
dictarlo otra vez; **«Gica continúa»** lo retoma. Para modificar una respuesta ya
guardada usa **Corregir** en la ficha. **«Gica silencio»** apaga el micrófono.

La opción visible **Empezar a responder al final de la pregunta** intenta activar
la escucha cuando resten cinco segundos estimados de una pregunta de creación.
Está limitada a ese diálogo y puede desactivarse. Sólo funciona mientras se
completan datos (`collecting`), nunca en el resumen de confirmación (`review`).
Un fallo del navegador vuelve al mecanismo de responder después de la lectura.
Se descarta eco parecido a la pregunta.
No se garantiza detección acústica perfecta ni cinco segundos exactos. Aun si
ya empezaste a responder, se espera al fin de la lectura y después 1,5 segundos
de texto estable antes de enviar. La aceptación física de esta ventana sigue
pendiente; no interpretar voz simulada como evidencia de audio real.
Un borrador activo admite hasta 40 inicios de micrófono en cinco minutos;
fuera de la creación se mantienen 20. Siguen vigentes dos reconexiones cortas
consecutivas y el botón para apagar el micrófono.

## Creación conversacional del evento

Después de la confirmación final, una respuesta válida `created` anuncia el
guardado y abre automáticamente **Tus eventos** (`/`, sin filtros). Es un GET
fijo que refresca la lista incluso si ya estaba abierta; no vuelve a confirmar
ni a enviar el POST de creación. La respuesta hablada termina antes de navegar,
el panel se contrae para descubrir la lista y la conversación vuelve a escuchar
con su indicador y botón Apagar visibles. El recibo borrador/enlace limita la
navegación a un intento, comprobando sesión y generación; Apagar durante la
respuesta cancela la navegación pendiente. Revisar, cancelar o fallar la
confirmación no activa este regreso. Si falla el GET, el evento creado y su
enlace se conservan y el aviso distingue el guardado del fallo de navegación;
no pide crearlo otra vez. No genera ni aprueba un plan.

Al abrir la conversación, Gica saluda por el usuario y ofrece **«¿Estás listo para
crear un evento o deseas hacer otra cosa?»**. **«Hola Gica, quiero crear un
evento»**, **«organicemos un evento»** o **Crear un evento con Gica** inician la
entrevista local, por voz o texto. La detección cruza palabras de acción y tipo
sin exigir un marco; no basta encontrarlas dentro de cualquier cita, negación,
condición o petición múltiple. Una descripción inicial abre el flujo, pero no
se convierte automáticamente en datos de la ficha.

La pregunta actual y la ficha aparecen antes de los ajustes de micrófono y
memoria. Gica recoge 15 pasos: nombre, institución, descripción, fecha, hora,
zona, capacidad, demostración ficticia y siete preguntas de entrevista. Cada
respuesta válida se conserva y avanza; una fecha, hora o cantidad inválida
mantiene el paso y ofrece un ejemplo. Puede entender «diecinueve de noviembre de
2026», «siete y media de la noche» y «una hora y media»; pregunta si falta la
franja horaria. La institución se reutiliza del directorio propio o se registra
después de una aceptación explícita; también puede quedar **sin institución**.
Los datos opcionales admiten **pendiente**; no se deducen
objetivos o recursos a partir de otros campos.

Mientras pregunta por un campo, lo que respondes es **dato**, no una orden: un
título como «abre calendario» se conserva literalmente. No se interpreta como
navegación, consulta externa o enseñanza de un alias. Están disponibles controles
del flujo: **«atrás»**, **«revisar borrador»**, **«cancelar creación»**, y botones
**Anterior**, **Revisar ficha**, **Corregir** y **Cancelar creación**. El borrador
es privado y dura 24 horas; **Continuar mi borrador** lo recupera. Apagar el
micrófono detiene la voz y conserva la ficha. **«Gica cancela»**, mientras existe
un borrador activo por voz, cancela la creación y vuelve a escuchar para otra
petición. Sin borrador conserva la cancelación local anterior y no abre ni
modifica una ficha de evento.

Al completar la entrevista, se muestra el resumen. Sólo entonces **«crear
evento»**, **«sí, crear evento»** o el botón final **Crear evento** guardan la
ficha. Un **«sí»** aislado no crea nada. UUID y revisiones evitan reaplicar
entregas repetidas; un conflicto recupera los datos actuales para revisión.
Después aparece **Abrir evento creado**. El flujo no genera ni aprueba planes,
no cambia estados de tareas, no usa `UIAction` y no consulta modelos o Wikipedia.
Conserva los límites y permisos del organizador; no es una séptima acción del
runner ni aprendizaje de nuevas capacidades.

### Aclarar coincidencias del directorio

Un nombre o alias exacto y único enlaza un registro propio activo. Una búsqueda
parcial tokeniza y normaliza los términos relevantes, combina sus condiciones
sobre nombre/alias y devuelve hasta tres candidatos propios activos. **Callao**
puede sugerir **Universidad Nacional del Callao - UNAC**: una sugerencia, aunque
sea única, espera selección por botón, número o un sí inequívoco. Varias
coincidencias requieren elegir una. Nunca se amplía a otros propietarios.

La respuesta publica `directory_resolution` separado de los campos del evento:
`choose`, `register` o `new_name`, con consulta, candidatos y posibilidad de omitir.
Las opciones de la burbuja y del panel son los mismos controles, protegidos por
usuario, borrador, revisión y paso. **Otra institución/persona** solicita primero
otro nombre; no registra automáticamente ni usa respuestas de confirmación como
nombres. En confirmación, sí/no se reconocen por conceptos y cortesías; señales
contradictorias, incertidumbre o fragmentos de la pregunta mantienen la aclaración.
Un borrador que tenía un fragmento de la pregunta como nombre vuelve a pedirlo al
reanudar, sin borrar registros ni crear uno con ese texto.

La voz espera 2500 ms sin cambios para institución o aclaración de personas;
el resto conserva 1500 ms. Texto vacío/provisional no envía una respuesta. En
directorio se suspende la escucha anticipada mientras habla Gica; tras terminar
hay una pausa breve y un filtro acotado de fragmentos de la pregunta reciente.
No acredita cancelación acústica ni sustituye una prueba física del micrófono.
La conversación continúa y una respuesta ambigua no cierra la sesión.

## Ampliación: conocimientos y asociaciones automáticas

Jorge autorizó incorporación automática y revisión posterior. En **Gica → Tu orden
→ Conversar por texto**, «qué es mantenimiento predictivo» puede consultar Wikipedia
si no hay una referencia vigente en la memoria privada. El checkbox **Consultar
Wikipedia si falta información** controla la salida a esa fuente; apagado permite
reutilizar la memoria. Sólo marcos de pregunta pública, no cualquier frase desconocida.
Una orden ambigua sigue aclarando. Hasta20consultas externas/día, separadas5s;
memoria200entradas con fuente/fecha y vigencia24h. No usa tokens de modelos.

«Cuando diga programación, me refiero al calendario» enseña un concepto de1–3palabras
y responde información sin pulsar nada. Después «abre programación» produce el
comando canónico del calendario. Hasta100asociaciones por cuenta, sin ampliar las
seis acciones; no aprende nombres ni datos de búsquedas de personas. No se enseñan
órdenes desde una página. La biblioteca **Gica → Conocimientos** permite corregir,
revisar, desactivar o eliminar lo aprendido. `CommandPattern` manual sigue separado.

La referencia íntegra y su enlace aparecen como texto, con un resumen breve de voz
local y micrófono pausado. No sintetiza respuestas complejas ni verifica una
afirmación por haberla guardado. Búsqueda general de Google queda pendiente de
proveedor, cuotas y configuración. Aprender significa persistir información y
asociaciones acotadas, no entrenar pesos ni conceder permisos.

Gica interpreta **Tu orden** mediante un diccionario composicional y reglas
locales: saludo o vocativo, verbo, destino y datos necesarios. El banco vigente es
`es-2026-11-15.6`. No es un modelo entrenado, no usa búsqueda difusa general ni
consume tokens de LLM. Las expresiones y respuestas son datos revisados; los
permisos, validación y ejecución pertenecen al servidor y al runner existente.

Las respuestas usan un tono cercano y una pregunta concreta: desconocido →
«Disculpa, no entendí bien tu petición…»; dato ausente → «Claro, ¿cómo se llama
la persona que quieres buscar?». Una negación se reconoce como tal: «De acuerdo,
no haré ese cambio». Los rechazos conservan su motivo y estado sin presentar
una acción fuera del alcance como si sólo necesitara reformularse.

## Intenciones y datos permitidos

El catálogo conserva exactamente seis acciones: `theme_light`, `theme_dark`,
`calendar_open`, `directory_open`, `people_search` y `events_open`.

| Petición | Tratamiento |
| --- | --- |
| «Hola chica, abre eventos» | Normalizar el vocativo y abrir Eventos |
| «Hola Gica, muéstrame el calendario por favor» | Abrir Calendario |
| «Entra al directorio» o «haz clic en contactos» | Abrir Directorio mediante el mismo enlace permitido |
| «Busca a Jorge en el directorio» | Buscar ese nombre en el directorio propio |
| «Pon el modo oscuro» | Aplicar ese tema |
| «Hola» | Saludo local; no crear una acción |
| «Buenos días», «cómo estás» o «gracias» | Respuesta social local, sin crear una acción |
| «Manda un saludo a Ana» | Saludo en pantalla/voz local, sin enviar mensajes ni consultar contactos |
| «Qué hora es» | Reloj del servidor en hora de Perú, HH:MM |
| «Abre», «busca» o «cambia el tema» | Preguntar por el destino, nombre o tema ausente |
| Negación, cita, condición, relato o varias órdenes | Aclarar o rechazar; no ejecutar una parte |
| Filtros de eventos/calendario por lenguaje natural | Explicar el alcance y ofrecer abrir la sección; no fingir filtros aplicados |
| Crear eventos | Entrevista separada descrita arriba; fuera de las seis acciones del runner |
| Modificar planes/tareas o administrar cuentas y claves | Fuera de estas seis acciones; conservan sus flujos y autorizaciones existentes |

Las palabras clave son pistas, no autoridad: mencionar «calendario» en una frase
negada o informativa no autoriza a abrirlo. Los vocabularios de negación, citas,
reporte, condiciones, instrucciones administrativas y órdenes múltiples se
comprueban antes de retirar saludos o muletillas. Los datos ausentes no se inventan.

Los alias Gica/Jica/Yica/Yika/Llica/Ilica/Chica sólo se normalizan a **Gica** como
vocativos en posiciones permitidas. «Busca a Chica», «Busca a Yika» y el nombre
«Jica» en una aclaración `person_name` conservan la persona; no hay reemplazo global.
Los nombres mantienen Unicode NFC y espacios, hasta 100 caracteres. No se usan
como código, URL o selector. El buscador conserva los permisos del directorio.

## Normalización gramatical acotada

`apps/jobs/command_normalization.py` usa el módulo fijo
`apps/jobs/data/gica_normalization.es.json`, con la misma versión `.6` que el
banco de acciones. Define conceptos de destino y tema, singular/plural/género
revisados, determinantes de ámbito e inflexiones verbales explícitas. No es un
corrector universal ni añade acciones. Una inflexión revisada se reconoce por
coincidencia exacta; no se corrigen verbos o negaciones mediante distancia.

Se comprueba primero la petición original: controles, URLs/código, citas,
relatos, condiciones, restricciones y negaciones. Después sólo se seleccionan
posiciones gramaticales elegibles. Destinos y temas se canonicalizan sin modificar
las posiciones originales de cada token; la gramática y la detección de varias
acciones se vuelven a comprobar sobre esa representación. Mencionar un destino
en un relato o junto a texto no entendido no equivale a una orden válida.

Los aliases/plurales exactos tienen prioridad. La aproximación usa distancia
Damerau acotada —incluye transposición adyacente— con el mejor candidato único
entre canónicas revisadas. Distancia 1 exige al menos 5 caracteres; distancia 2
sólo corresponde a calendario/directorio largos, con al menos 9 caracteres y
contexto fuerte. Tema/modo no reciben corrección difusa. Cada comparación parte
del token original; las pasadas no suman cambios por una cadena de aproximaciones.
Los límites del esquema son 80 tokens, longitud 32 para comparar y hasta 3 pasadas
para alcanzar un punto fijo idempotente. Empates entre canónicas no se resuelven
por el orden del JSON: requieren aclaración.

El slot de persona se separa antes de corregir. «Busca a Caldenarios», «Busca a
Evento» y «Busca a Calendario» conservan esos nombres: el introductor explícito
identifica una persona, sin abrir el módulo homónimo. «Buscar calendario» sin ese
introductor pide aclaración, igual que un ámbito no admitido «en el calendario».
La consulta se extrae del texto Unicode NFC mediante offsets originales, no de
una cadena reescrita. En «Busca a Ana en los directorios» sólo cambia el ámbito
gramatical de borde; palabras interiores de un nombre no se singularizan. El JSON
no puede aportar selectores, URLs o permisos.
Esta normalización `.6` es independiente de los conceptos sociales `.4`.

## Capa social local

`apps/assistant/social_language.py` interpreta expresiones sociales con el banco
de datos revisado `apps/assistant/data/gica_social.es.json`, versión independiente
`social-es-2026-11-15.4`. Contiene saludos, respuestas amables y vocabulario para
agradecer, preguntar cómo está Gica, solicitar un saludo o consultar la hora.
No entrena modelos ni consume tokens; no habilita herramientas ni modifica permisos.

Compone segmentos revisados: saludo/vocativo, fórmula modal («puedes», «podrías»),
verbo o infinitivo, núcleo y persona, con cortesías finales permitidas. El banco
separa wrappers, verbos/objetivos de hora e introductores/nombres de saludo; no
necesita guardar cada combinación como una frase nueva. Las guardas de negación,
citas, condiciones, relato y varias órdenes se aplican antes de podar cortesías.
No se recorta una parte peligrosa para convertir el resto en petición válida.

Gratitud y acuses se reconocen por **concepto y contexto gramatical**, no por
coincidir con una lista de oraciones completas. El JSON aporta lexemas funcionales:
núcleos, intensificadores, evaluadores, marcos de agradecimiento y complementos.
El parser comprueba cómo se relacionan y consume un contexto acotado de ayuda o
motivo; no basta con encontrar «gracias» dentro de cualquier texto. Las variantes
y ejemplos de desarrollo/regresión residen en `test_social_language.py`, no son
una base de frases privadas ni un aprendizaje automático del banco.

La tolerancia ortográfica tiene sólo dos destinos elegibles: `gracias` y
`agradezco`; `Gracia` está excluido. Una repetición interna inequívoca puede
reconocer «graccias» por sí sola; las otras aproximaciones de una edición exigen
un marco gramatical y candidato único. No convierte nombres o verbos de acciones
en otras palabras. Es una coincidencia interna; no reescribe `original_text`,
nombres, consultas, borradores ni guardas. Un candidato ambiguo no se acepta.
No hay corrección difusa general ni promesa de comprender todo el español.

Las excepciones de cortesía como «no, gracias» o «no hay de qué» no eliminan
negaciones de órdenes. «Gracias por abrir calendario» puede responder `info`
porque describe un motivo: no abre el calendario, no consulta su estado ni afirma
que alguien lo haya abierto. «Gracias y abre calendario», una cita, «se llama
Gracias» o «no digas gracias» no se convierten en gratitud por su palabra clave.
Un mandato independiente no puede ocultarse en el complemento de agradecimiento.
Un infinitivo de lectura en el motivo requiere `por` y objeto compatible: «abrir
calendario gracias» no se trata como información social para ocultar una orden;
su interpretación sigue correspondiendo al catálogo de acciones.

Tanto **Conversar por texto** como **Ejecutar orden** responden a una petición
social completa. La guía devuelve `status: info`, `reply` de la aplicación y los
otros tres campos vacíos; la interpretación manual usa `message` y su sobre de
seis claves descrito abajo. Ninguna crea UIAction, Job o AIUsage ni consulta contactos.
«Manda un saludo a Ana» significa decir un saludo local: no hay envío a Ana ni
conexión a correo/mensajería. El nombre procede de la petición explícita, conserva
Unicode NFC y admite hasta 80 caracteres validados; sólo se usa en esa respuesta
acotada. La hora se construye en el servidor con
`timezone.now()` y `ZoneInfo("America/Lima")`, en HH:MM; no se infiere de un modelo
ni de la zona del dispositivo. Las pruebas pueden fijar ese reloj.

Durante `person_name`, nombres aislados como «Chica» o «Buenos Días» se conservan:
no se convierten en saludo por suposición. Una petición social explícita —por
ejemplo una pregunta/modal de hora o un saludo dirigido a una persona— sí puede
abrir un tema nuevo y limpiar ese contexto. Durante `theme`, una petición social
completa responde y limpia la aclaración de claro/oscuro. Una cortesía/despedida
completa también sale del contexto de persona sin buscarla como nombre.
La respuesta contextual de tema reutiliza el intérprete y, cuando corresponde,
el prefijo fijo `Modo`; sólo acepta `theme_light` o `theme_dark`. No mantiene una
segunda lista de respuestas exactas ni permite otra acción desde ese slot.
No se convierten esas respuestas en datos del slot ni se ejecuta la orden anterior. Iniciar una
interpretación manual también limpia el contexto anterior de la guía.
Negaciones, citas, relatos, condiciones y peticiones mixtas no autorizan acciones.
Los JSON sociales son vocabulario/respuestas declarativas, no URLs, selectores,
código o esquemas para nuevas herramientas. El contrato de guía sigue teniendo
exactamente cinco campos y el catálogo ejecutable exactamente seis acciones.

## Banco modular mantenido

- `apps/jobs/data/romeo_intents.es.json`: manifiesto con versión, idioma, límites
  y los cuatro nombres de módulos fijos.
- `gica_vocabulary.es.json`: alias, verbos equivalentes, cortesías, muletillas,
  introductores y ámbitos de búsqueda, negaciones y barreras de seguridad.
- `gica_intents.es.json`: las seis intenciones, destinos equivalentes, órdenes
  canónicas y slot `person_name`; no registra herramientas nuevas.
- `gica_dialogues.es.json`: saludos y respuestas locales para aclarar o rechazar.
- `gica_normalization.es.json`: conceptos nominales, variantes, ámbitos,
  inflexiones exactas y límites de normalización revisados.
- `apps/jobs/data/romeo_intent_examples.es.json`: corpus sintético con resultados
  esperados, incluidos casos ambiguos y adversariales.
- `apps/jobs/command_language.py`: intérprete puro y compilación/validación del
  banco, sin red, base de datos, shell ni modelos.
- `apps/jobs/command_normalization.py`: candidatos únicos y punto fijo acotado,
  manteniendo los offsets del texto original.
- `apps/jobs/test_command_language.py` y `test_command_endpoint.py`: regresiones
  del lenguaje, autenticación, permisos y ausencia de ejecución al interpretar.
- `static/js/gica-language.js`: normalización finita de vocativos para la
  visualización; el servidor vuelve a interpretar y validar.
- `apps/assistant/social_language.py` y `data/gica_social.es.json`: parser puro
  y respuestas de la capa social, versionados por separado del banco de acciones.

El compilador sólo carga los cuatro archivos locales previstos, exige versiones y
esquemas compatibles y falla cerrado si falta un módulo o es inválido. El JSON
no admite regex o código dinámico, URLs de ejecución, selectores ni permisos.
Componer vocabulario permite reutilizar expresiones sin enumerar todas las frases,
pero no demuestra comprensión de todo el español ni aprende de usuarios.

## Interpretar y aclarar

`POST /romeo/interpret/` recibe una frase de hasta 300 caracteres y devuelve:

```json
{
  "status": "understood",
  "action": "calendar_open",
  "query": "",
  "message": "Abrir Calendario.",
  "options": [],
  "catalog_version": "es-2026-11-15.6"
}
```

El ejemplo ilustra el contrato; el mensaje y `catalog_version` corresponden al
banco vigente. El intérprete puro `apps.jobs.command_language.interpret` conserva
sólo `understood`, `clarify` y `refused`; los dos últimos llevan `action: null` y
consulta vacía. Una aclaración ofrece como máximo tres órdenes canónicas. Elegir
una opción sólo prepara texto para revisar y enviar; no inicia un clic.

El wrapper autorizado `interpret_for_owner` añade `info` sólo para respuestas
sociales completas. `/romeo/interpret/` conserva seis claves, por ejemplo:

```json
{
  "status": "info",
  "action": null,
  "query": "",
  "message": "Con gusto. Aquí estoy para ayudarte.",
  "options": [],
  "catalog_version": "social-es-2026-11-15.4"
}
```

Para `info`, acción nula, consulta vacía y opciones vacías son obligatorias. El
cliente muestra la respuesta y termina el seguimiento informativo sin llamar al
runner ni crear recibos. No interpreta la respuesta social como una séptima
acción. Sesión/rol vigentes, CSRF y rechazo del contexto de agente se mantienen.
Esto no modifica el contrato de cinco campos de `/assistant/guide/`.

Interpretar no crea UIAction, Job ni AIUsage. Los desconocidos no se remiten a
modelos, un banco inválido no activa una alternativa y el resultado no concede
permisos. El runner comprueba sesión, usuario/rol vigentes, CSRF, pestaña, orden y
consulta exactas, TTL e idempotencia del recibo `UIAction`, antes de iniciar el
control fijo. Detener o Escape cancelan antes del clic. Si ya se pulsó un control
y no se confirma su resultado, se informa incertidumbre sin repetirlo.

## Conversación guiada local vigente

Abrir **Gica-1** con un clic inicia el saludo con el usuario SSR de la cuenta,
tras aceptar el aviso guiado **v5** y el permiso del navegador si aparecen.
No se escucha al cargar, abrir por código ni restaurar preferencias. Habla sin
palabra de activación. Tras **1,5 segundos sin cambios en el texto transcrito**,
una orden clara se ejecuta directamente; no hay «¿Procedo?» ni turno sí/no.
Si faltan datos o hay ambigüedad, Gica pregunta. Los planes y estados de tareas
mantienen su aprobación humana por los flujos del evento.

Sólo una transcripción con letras o números inicia la cuenta: el último cambio
del texto normalizado fija `+1500 ms`. Silencio, ruido sin texto, resultados
vacíos o sólo puntuación no inician ni reinician la espera; tampoco cierran la
conversación. Los resultados idénticos no reinician la cuenta. El provisional se muestra, pero resultados
parciales pendientes bloquean el despacho. Promover las mismas palabras a texto
definitivo no añade otros 1,5 segundos. Retirar a vacío un provisional anterior
no lo confirma ni autoriza enviar únicamente el prefijo final. El turno admite
hasta 300 caracteres y 30 s desde el primer texto; al vencer pasa a revisión,
sin ejecutar parciales ni apagar la conversación. Sin texto no se arma ese
plazo. `text_change_to_dispatch_ms` es una duración estimada
del navegador, no una medida del silencio físico. Reconocimiento, guía, movimiento
del cursor y síntesis añaden sus propias demoras; el runner conserva sus pausas
controladas previas al clic.

`POST /assistant/guide/` sólo lee y devuelve cinco campos exactos: `status`,
`reply`, `draft`, `intent` y `follow_up`. Los estados son `ready`, `clarify`,
`refused` e `info`; sólo `ready` contiene borrador canónico y una de las seis
intenciones. Los contextos son vacío, `person_name` o `theme`: datos de aclaración,
no autoridad. La guía no consulta personas/calendarios ni crea UIAction/Job/AIUsage.
Una `readyOrder` inmutable liga borrador, intención, generación de guía y sesión;
únicamente entonces el cliente usa el runner normal. Edición, parada o resultado
obsoleto impiden el envío. Una orden sin saludo se envía sin preámbulo. Si la
petición empieza con un saludo explícito y la orden completa es segura, `reply`
incluye un prefijo canónico revisado, por ejemplo «Buenos días. Identifiqué la
orden.». El cliente sólo reconoce esos literales, habla el saludo breve con
micrófono pausado y vuelve a comprobar sesión, ticket y borrador exacto antes de
llamar al runner una sola vez. Stop, edición o navegación durante el saludo
impiden el clic; no es una segunda confirmación ni cambia la intención. Sin voz
local disponible se conserva el texto. La respuesta breve posterior a la acción
también mantiene el micrófono pausado para evitar eco.

**Conversar por texto** utiliza la misma guía sin activar micrófono ni síntesis;
prepara el texto y conserva el botón **Ejecutar orden**. El navegador mantiene
hasta seis intercambios en RAM/DOM. Una guía en vuelo es única, abortable y ligada
a cuenta, documento, ticket y borrador; los callbacks viejos no autorizan acciones.

## Continuidad entre vistas y parada

`static/js/gica-navigation.js` mantiene la cabecera, panel, cursor y controlador
humanamente iniciado al cambiar sólo el contenido SSR de **Eventos** (`/`),
**Calendario** (`/calendar/`) y **Directorio** (`/directory/`). Incluye filtros GET
manuales permitidos de esas vistas. No convierte el lenguaje natural en nuevos
filtros ni es un navegador general. Actualiza URL/historial y valida propietario,
rol, destino, consulta y formato del HTML, sin importar scripts de la respuesta.
El calendario se inicializa de forma idempotente en el contenido nuevo.

Los eventos `sparkx:gica-navigation-start/complete` comparten un ID de operación.
La voz invalida el turno parcial y pausa reconocimiento/síntesis durante el cambio.
Sólo retoma después de completar navegación, recibo de la acción y respuesta
hablada. El runner consume una transición nueva una sola vez, ligada a operación
y destino; comprueba llegada antes de cerrar el recibo. Un error posterior al
cambio no afirma que la página anterior se conservó ni repite el clic.

Contraer el panel conserva la conversación, con indicador y **Apagar mic** visibles;
una orden clara vuelve a mostrar el panel antes de ejecutar. **Apagar mic** o
**Terminar conversación** la detienen. Ocultar la pestaña, recargar, salir de las
tres vistas, cerrar sesión, cambiar de cuenta, error de reconocimiento/navegación
o resultado incierto la apagan. No se restaura una sesión mediante localStorage
o sessionStorage, ni se fuerza el permiso nativo. Escape puede cancelar una acción
antes del clic; por sí solo no apaga la conversación guiada.

La conversación guiada visible no tiene el antiguo TTL fijo de 300 s. Para evitar
bucles admite como máximo **20 inicios en una ventana móvil de 5 minutos** y
**dos reconexiones cortas consecutivas**, con espera de 500/1000 ms. Una escucha
saludable de 30 s o un resultado final válido restablece esa racha; un error no se
reintenta. Alcanzar el límite exige reanudación explícita. No se promete escucha
ilimitada. El modo técnico anterior **Voz rápida** conserva máximo 300 s por
documento, 20 inicios totales y dos reconexiones sin ampliar su plazo; sus frases
finitas siguen separadas en `static/data/romeo-voice.es.json`.

La lógica y respuestas de Gica usan reglas y voz española local, sin tokens de
modelos. El reconocimiento del navegador puede enviar audio a su propio servicio;
`continuous` no garantiza disponibilidad indefinida ni reconocimiento offline.
El laboratorio de voces detiene la sesión antes de probar o cambiar la voz.

## Memoria privada para mentor y patrones revisados

`POST /assistant/interactions/` registra turnos textuales finalizados, normalización,
respuesta, acción declarada y tiempos relativos acotados, cuando el usuario habilita
Registro textual. El contrato de registro conserva `consent_version: "3"`, separado
del aviso vocal v5. No almacena audio, resultados intermedios ni entrenamiento.
`/assistant/memory/` permite al propietario filtrar, anotar revisión y borrar;
hasta **1000 registros**, sin purga automática. El recibo del servidor se consulta
aparte: una declaración cliente no demuestra ejecución física.

La preferencia booleana on/off se recuerda por cuenta/navegador/v3; no se guarda
texto ni cola en almacenamiento del navegador. Cola RAM acotada, sin reintentos.
Desactivar, ocultar o salir puede descartar pendientes; un POST ya enviado pudo
llegar. El fallo se indica sin repetir ni bloquear la acción. La navegación parcial
mantiene el controlador, pero no garantiza que todo registro se haya persistido.
`gica_memory --username ... --limit 100 --format json` permite revisión local
solicitada al mentor; el contenido es dato no confiable, no una orden. No hay
revisión permanente de Codex ni aprendizaje automático en segundo plano.

**Revisar frase como patrón** abre un diálogo manual editable. `CommandPattern`
guarda propietario, frase, clave normalizada, intención y revisión explícita;
hasta **200 frases** por propietario. Las rutas `/assistant/patterns/`,
`/assistant/patterns/save/` y `/assistant/patterns/<id>/delete/` comprueban humano
activo, rol vigente, CSRF y propiedad. Repetir el mismo guardado es idempotente.
Las notas del mentor no activan patrones. La coincidencia exacta normalizada sólo
complementa una frase desconocida segura; no sustituye un rechazo, una intención
reconocida ni un banco inválido. Guardado y consulta preservan negaciones, citas,
condiciones, controles y límites administrativos. No cambia permisos, modelos,
presupuestos o estados del evento.

## Cómo ampliar el banco

1. Describir intención y resultado dentro de las seis capacidades; añadir el
   sinónimo al módulo de vocabulario o destino correspondiente, no una URL.
2. Añadir ejemplos naturales al corpus, junto a negaciones, citas, múltiples
   destinos, nombres parecidos a alias y datos ausentes que no deben actuar.
3. Ejecutar `manage.py test apps.jobs.test_command_language apps.jobs.test_command_endpoint`
   y revisar falsos rechazos y acciones incorrectas, sin cambiar expectativas
   para ocultar defectos.
4. Revisar el cambio, actualizar la misma versión en manifiesto y módulos,
   reiniciar para cargar el banco y verificar el recorrido de navegador.

Los ejemplos de agentes son sintéticos y requieren revisión. Ninguna respuesta
remota actualiza automáticamente el diccionario o registra una herramienta.
Pasar el corpus demuestra regresión de esos casos, no comprensión universal ni
precisión con usuarios reales. La evidencia medida y los límites están en
[verification.md](verification.md); las simulaciones no acreditan micrófono,
audibilidad o inferencia física real.
