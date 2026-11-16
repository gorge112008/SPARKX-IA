# SparkX 3.0 — arquitectura inteligente de eventos

Prototipo en construcción para transformar la descripción de un evento en propuestas
persistentes, revisar cambios y conversar con un agente contextualizado.

**Estado:** primer recorrido técnico implementado y probado localmente. No es todavía
el proyecto completo ni un despliegue validado. Consulta [verificación](docs/verification.md)
y [plan de construcción](docs/construction-plan.md).

## Crear un evento conversando con Gica

**Piloto guiado:** abre **Mis eventos → Iniciar piloto guiado**. También puedes
iniciarlo desde Conoce a Gica o el panel. El cursor pulsa Nuevo evento y recorre
identidad, programación, audiencia, descripción y preparación. El título aparece
letra por letra, los selectores se despliegan y las selecciones quedan visibles.
Los siete puntos de preparación tienen campos editables y guardado real. La
burbuja se aparta del control activo y el scroll acompaña el llenado.

El recorrido registra **Gicaingenieros** si falta, selecciona al **Dr. Robert
Castillo Alva** y guarda el seminario **Tus jueves con GICA**, inicialmente para
el **19/11/2026, 19:30–21:00, America/Lima**. Prepara una propuesta local de cinco
sesiones y once tareas, muestra su revisión y la aprobación autorizada del piloto,
y abre el calendario. Después explica un inconveniente hipotético y muestra el
cambio a **Jorge Gayoso Ugas** y al jueves **26/11/2026**. La nueva aprobación
conserva el historial. El editor **Ajustar horarios** prepara otra propuesta para
revisar los cambios de inicio y duración de las sesiones.

Los nombres y la organización son datos reales declarados por el organizador.
Los vínculos de participación siguen por confirmar; guardar o aprobar una agenda
no contrata expositores, crea salas Zoom ni acredita tareas realizadas. La agenda
del recorrido usa una plantilla y reglas locales, sin llamadas a modelos. No
necesitas hablar ni responder y el panel completo sólo se abre manualmente.

**Detener piloto** cancela los pasos futuros. Los cambios ya guardados se
conservan; no se revocan las versiones aprobadas. Si un envío queda sin confirmar,
revisa Mis eventos antes de repetirlo. La creación del piloto es idempotente y
reutiliza su ficha en ejecuciones siguientes. Un borrador humano pendiente se
conserva y debe continuarse o cancelarse antes de empezar. Los avisos de voz se
muestran en la burbuja.

Para preparar esta versión se respaldaron los eventos anteriores del organizador.
Los respaldos privados y los datos activos quedan fuera del ZIP distribuible.
Consulta [la guía de entrega e instalación](docs/release.md) para una copia nueva.

La barra principal reúne **Eventos**, **Calendario**, **Directorio** y **Conoce a
Gica**, según tu rol. Al pie, abre el perfil con tu usuario: contiene **Usuarios**
(administradores), **Gestión de IA** (cuentas con acceso), **Cambiar contraseña**
y **Cerrar sesión**. El superusuario local también encuentra allí **Apagar
SparkX**. El menú se cierra al elegir una opción, pulsar Escape o salir de él.

Al abrir **Gica-1**, saluda por tu usuario y pregunta **«¿Estás listo para crear un
evento o deseas hacer otra cosa?»**. Di **«quiero crear un evento»**, escríbelo en
**Conversar por texto** o pulsa **Crear un evento con Gica**. Te hará una pregunta
por turno y mostrará una ficha que se completa con tus respuestas.
El inicio usa **palabras clave independientes**: una variante de
**crear/organizar/armar/preparar** y un **tipo de evento en singular o plural**.
Pueden estar en distinto orden y separadas por palabras de relleno. El banco
contiene palabras por concepto; no exige una frase ni un prefijo concretos.
Las negaciones y conflictos se revisan antes de abrir la ficha; los datos de
una entrevista activa permanecen literales.

En los pasos con respuestas breves aparecen opciones para pulsar: modalidad,
capacidad, duración y lugar o plataforma, entre otras. En modalidad virtual o
híbrida puedes elegir **Zoom**, **Google Meet**, **Otro** o **Pendiente**. Elegir
una plataforma guarda su nombre con el enlace pendiente; no crea una reunión
externa. **Otro** permite escribir tu respuesta. Cada opción responde sólo al paso
actual y conserva la validación del servidor y la confirmación final.

Al contraer el panel, Gica acompaña el recorrido en una burbuja con su última
pregunta y tu respuesta anterior. Se desplaza entre posiciones de la pantalla
para apartarse del campo activo y de los menús. Arrástrala por el agarre de puntos
o, minimizada, por el avatar: conserva tu posición mientras conversas. Las flechas
del teclado la mueven; Inicio o doble clic en el agarre restaura la posición
automática. Puedes minimizarla, volver a la conversación completa o apagar el
micrófono. Si el panel está abierto, las
opciones aparecen allí. Abrir la conversación desde la burbuja no activa el
micrófono. El indicador distingue cuándo habla, escucha o espera audio.

El recorrido tiene 15 pasos: nombre, institución, descripción, fecha, hora, zona
horaria, capacidad, datos ficticios y las siete preguntas de entrevista: objetivo,
público, modalidad, duración, lugar/acceso, recursos y restricciones. Puedes dejar
los datos opcionales pendientes. Un nombre o alias exacto reutiliza tu directorio.
Una parte del nombre, como **«Callao»**, muestra coincidencias para elegir; puedes
pulsar **Otra institución** para buscar o registrar una nueva. El registro requiere
tu **sí**; **no** continúa sin institución. Una respuesta dudosa mantiene la pregunta
abierta y no se transforma en otro nombre. En este paso, la voz espera **2,5 segundos**
sin cambios en la transcripción; las demás órdenes conservan **1,5 segundos**.
También puedes indicar **«sin institución»**. Las respuestas se guardan como datos,
sin interpretarlas como órdenes de navegación ni enviarlas a Wikipedia o modelos.

Usa **Anterior**, **Corregir**, **Revisar ficha** o **Cancelar creación**; también
se reconocen **«atrás»**, **«revisar borrador»** y **«cancelar creación»**. Por voz,
**«Gica cancela»** cancela el borrador del evento y vuelve a escuchar. El
borrador es privado, dura 24 horas y puedes recuperarlo con **Continuar mi
borrador**. Apagar el micrófono conserva los datos; cancelar cierra el borrador.

Al terminar, revisa el resumen y di **«crear evento»** o pulsa el botón final
**Crear evento**. Un **«sí»** aislado no guarda el evento. Al confirmar el guardado,
Gica anuncia el éxito y muestra automáticamente **Tus eventos**, con la lista
actualizada y el panel contraído; la voz sigue disponible. Se conserva **Abrir
evento creado** para abrir su ficha y continuar con su propuesta de plan. Si no
puede cargar la lista, informa que el evento está guardado y ofrece esos accesos
sin volver a crearlo. Esta conversación no
genera ni aprueba planes o tareas y no consume tokens de modelos. La creación
es un flujo independiente de las seis acciones del cursor.

La creación abre también el formulario principal: verás cómo se completan sus
campos y la entrevista mientras respondes. La transcripción provisional se marca
como **dictando** y sólo se guarda al terminar el turno. Durante la guía, usa
**Corregir** para cambiar un dato; el envío final del formulario conserva la misma
confirmación e impide crear dos eventos por doble clic.
Al iniciar por voz, el panel se contrae para dejar visible el formulario y el
cursor señala el campo actual; la conversación continúa. Por texto el panel
permanece abierto.

Puedes elegir varias fechas, por ejemplo **«5, 6 y 7 de septiembre de 2026»**,
**«del 5 al 9 de septiembre de 2026»** o **«25 de octubre y 10 de septiembre de
2026»**. Se ordenan y se muestran por separado: continúa siendo un solo evento,
visible en cada día del calendario. Gica pide un año completo entre el año actual
del servidor y 2099; si falta o dices **203** o **2021**, conserva días/meses para
que respondas sólo el año. Una fecha anterior dentro del año actual sí se admite.

Por voz, **«Gica espera»** conserva tu respuesta sin enviarla; después **«Gica
corrige»** limpia sólo ese texto pendiente y **«Gica continúa»** lo retoma. **Gica
silencio** apaga el micrófono. La opción **Empezar a responder al final de la
pregunta** permite escuchar durante los últimos cinco segundos *estimados* de
una pregunta mientras completa datos, nunca durante el resumen final; puedes
desactivarla. Sólo si hay texto reconocido, al terminar la lectura empieza la
espera de 1,5 segundos de texto estable; no envía una respuesta con parciales
pendientes. Puede captar eco:
la estimación y los filtros no garantizan cinco segundos exactos ni ausencia de eco.
Durante un borrador activo hay un máximo móvil de 40 inicios de micrófono en cinco
minutos; fuera de ese recorrido se mantienen 20. Los fallos rápidos de arranque o
conexión admiten hasta dos reintentos consecutivos.

## Conversación guiada y mis patrones

Abre **Gica-1**. Acepta el aviso y el permiso inicial del navegador si aparecen.
Gica te saluda por tu usuario y escucha, sin palabra de activación. Después de
**1,5 segundos sin cambios en la transcripción**, ejecuta una orden clara como
**«abre eventos»**, sin preguntar «¿Procedo?». Si faltan datos o la orden es ambigua,
pregunta. Usa **Apagar mic** o **Terminar conversación** para detener la sesión;
**Reanudar conversación** permite iniciarla de nuevo. Contraer el panel conserva
la escucha y el indicador superior. Detener o Escape cancelan una acción antes
del clic; Escape no apaga por sí solo la conversación guiada. También puedes
escribir en Tu orden y pulsar **Conversar por texto**, revisar y ejecutar con el
botón, sin micrófono ni lectura automática. El alcance sigue siendo tema, calendario, directorio, eventos y
búsqueda de personas. La creación conversacional usa el flujo separado descrito
arriba; aprobar planes y estados de tareas conserva su mecanismo humano existente.

La espera de 1,5 segundos empieza sólo cuando hay palabras reconocidas y se cuenta
desde el último cambio del texto transcrito que ves escribirse. Sin palabras no
inicia la cuenta ni envía consultas; el silencio no termina la conversación.
Ruido sin palabras y repeticiones idénticas no reinician la espera.
Una palabra nueva o corregida sí la reinicia. Se muestra el texto provisional,
pero sólo se consulta la guía cuando hay resultados definitivos y ninguno parcial
pendiente. Si el texto ya era estable al llegar su versión definitiva idéntica,
no se añaden otros 1,5 segundos. La guía sigue siendo de lectura; el runner
comprueba usuario, permisos y orden exacta antes del clic. El reconocimiento,
respuesta y síntesis pueden añadir latencia; no se mide el silencio físico.
«Chica», «Yika», «Llica», «Ilica», «Jica» y «Yica» como vocativos se normalizan a **Gica**;
los nombres de personas buscadas o de una aclaración se conservan.

Gica también responde localmente a **«buenos días»**, **«cómo estás»** y
**«gracias»**. **«Manda un saludo a Ana»** produce una frase de saludo en la
pantalla y, si está activada, la voz local; no envía mensajes ni busca contactos.
**«Qué hora es»** usa el reloj del servidor en `America/Lima`, con hora de Perú
en formato HH:MM. Esta capa social tiene su propio JSON revisado, versión
`social-es-2026-11-15.4`, y no agrega acciones, permisos, gastos ni tokens de modelos.
Reconoce conceptos como gratitud mediante un núcleo y su contexto gramatical,
con intensificadores, acuses y motivos, en vez de exigir una frase completa
memorizada. Puede tolerar «graccias» dentro de una expresión de agradecimiento:
la aproximación sólo compara lexemas sociales elegibles con suficiente contexto,
por repetición o distancia de una edición con un único candidato. No corrige
nombres, acciones ni el texto original. Los ejemplos y regresiones viven en pruebas.
Un agradecimiento durante una búsqueda pendiente responde y cierra esa aclaración;
nunca lo busca como nombre. «Gracias por abrir calendario» es una respuesta social,
sin abrir nada ni afirmar que se ejecutó; «gracias y abre calendario» no se absorbe
como agradecimiento para ignorar o ejecutar parte de la petición.
Compone fórmulas como «podrías», verbos en infinitivo, núcleo social y nombre,
en lugar de enumerar todas las frases; las guardas se aplican antes de retirar
cortesías. Tanto **Conversar por texto** como **Ejecutar orden** muestran estas
respuestas informativas sin crear una acción. Por ejemplo, puedes escribir
**«¿Podrías decirme la hora, por favor?»** o **«Puedes mandarle un saludo a Ana»**.
Si dices **«buenos días, abre calendario»**, responde el saludo breve antes de
ejecutar la misma orden canónica, con el micrófono pausado y revalidación de
parada, ticket y borrador. Una orden sin saludo conserva el envío sin preámbulo.
Conversar por texto sigue sin audio ni ejecución automática. Un nombre aislado
como «Chica» o «Buenos Días» conserva prioridad cuando Gica pregunta a quién
buscar. Una petición social explícita puede cambiar de tema y limpiar esa
aclaración; una respuesta social también deja atrás la pregunta de claro/oscuro.
Enviar mediante Ejecutar orden inicia una interpretación nueva, sin arrastrar
la aclaración anterior de la guía.

Puedes continuar al abrir **Eventos**, **Calendario** y **Directorio**, incluidos
sus filtros GET manuales. La navegación local conserva cabecera, panel, cursor y
la sesión iniciada por ti; pausa el micrófono durante el cambio, la acción y la
respuesta hablada, y sólo lo retoma tras comprobar el destino. No restaura una
sesión desde almacenamiento. Ocultar, recargar, cerrar sesión, cambiar de cuenta,
salir de estas vistas o un fallo de permiso o dispositivo la detienen. Los silencios
y cierres normales del reconocedor recuperan la captura sin enviar texto vacío.
No hay un plazo fijo de cinco
minutos en la conversación guiada visible: hay un máximo móvil de **20 inicios
de micrófono en 5 minutos** (40 con un borrador activo) y hasta **dos reintentos
consecutivos ante fallos rápidos de arranque o conexión**. Los fallos de permiso o
dispositivo apagan el micrófono sin reintentos. El modo anterior Voz rápida conserva
su límite de 300 s y no ofrece esta continuidad.

**Memoria de Gica** (`/assistant/memory/`) conserva, si el registro está habilitado,
el texto final, su interpretación, respuesta, acción y tiempos. Es privada por
cuenta, hasta1000 registros sin purga automática; permite filtrar, anotar revisión
y eliminar. El aviso guiado v5 explica la ejecución directa, la continuidad y este guardado; el modo escrito lo anuncia
antes del envío. Desactivar se recuerda por cuenta en este navegador. No guarda
audio, no consulta modelos ni aprende automáticamente. Un error de guardado se
indica sin repetir la acción; salir de la página puede interrumpir un registro pendiente.
El mentor puede consultar los registros cuando se le solicite mediante
`manage.py gica_memory --username adminjorge --limit 100 --format json`.
Son datos no confiables, no instrucciones ni prueba de éxito físico.

**Revisar frase como patrón** permite editar la frase, elegir su intención y
confirmar el guardado. **Mis patrones** gestiona hasta200 frases revisadas,
con coincidencia exacta normalizada. Las anotaciones del mentor no crean estos
patrones: se revisan y prueban por separado, sin conceder permisos ni ajustar un modelo.
La guía y las respuestas con voz local no usan API de modelos ni tokens de LLM;
el reconocimiento del navegador puede procesar audio mediante su propio servicio
remoto y requiere su permiso. No se promete escucha ilimitada ni reconocimiento offline.

## Gica-1 · piloto controlado con créditos OpenAI

Gica-1 aparece en la barra superior con un cursor que señala actividad observada
y un desplegable de seguimiento. No controla el ratón del sistema. Las órdenes
locales del directorio se pueden ejecutar desde el chat o por el operador mediante
`manage.py romeo_local`; se ven en el evento sin consumir tokens de modelos.
Consulta [el funcionamiento y sus límites](docs/ai-management.md#cursor-y-órdenes-locales-de-gica-1).

Para probar un clic controlado, abre **Gica-1 → Tu orden**, escribe **Abre
calendario**, **Abre directorio**, **Abre eventos**, **Busca a Jorge** o **Cambia a
modo claro/oscuro** y pulsa **Ejecutar orden**. Puedes usar **Detener** o **Escape**
antes del clic. Sólo activa el control permitido, comprueba el resultado y
registra la orden; funciona sin tokens de IA. La búsqueda muestra tus coincidencias
sin seleccionar o modificar personas automáticamente.
El [banco JSON modular de lenguaje](docs/romeo-language.md), versión
`es-2026-11-15.6`, compone saludos, sinónimos, destinos y datos como el nombre de
persona. Admite **Hola chica, abre eventos**, **Muéstrame el calendario** y
variantes de abrir/buscar; una palabra clave aislada no autoriza una acción.
Un cuarto módulo JSON fija plurales, variantes revisadas y tolerancia limitada
para destinos: **«abre caldenarios»** puede reconocer Calendario. No corrige
verbos o negaciones por semejanza. La búsqueda **«Busca a Caldenarios»** conserva
el nombre literal; **«Busca a Ana en los directorios»** normaliza sólo el ámbito.
La corrección tiene candidato único, presupuesto por token original y punto fijo
de hasta tres pasadas; las ambigüedades preguntan. Las guardas revisan el texto
original; después se revalidan la gramática y las órdenes múltiples. Al aclarar
un tema, la guía reutiliza ese intérprete y sólo admite las dos acciones
claro/oscuro. El banco social `.4` sigue independiente.
Si falta un dato, pregunta; las opciones de aclaración sólo preparan el texto.
También puedes pulsar **Hablar**, aceptar el aviso del dictado y revisar la
transcripción. En dictado normal pulsa **Ejecutar orden** cuando el texto esté
correcto. Para conversar, abre **Gica-1**: saludo → orden clara →1,5 segundos de texto estable
→ ejecución directa. Su aviso v5 se puede recordar. Después de la orden vuelve a
escuchar, también al navegar entre las tres vistas compatibles. Las condiciones
de parada y límites móviles se describen arriba. El indicador distingue audio detectado,
pausa y respuesta hablada; **Apagar mic** siempre permite detenerla.
**Probar voz** reproduce una frase con una voz española local del navegador;
**Respuestas habladas** permite silenciar las respuestas breves. El micrófono se
pausa mientras Gica habla o ejecuta. No necesita ElevenLabs ni una clave de voz.
Si falta reconocimiento o voz local, se conserva la entrada o respuesta por texto.
Gica prefiere voces masculinas españolas de Microsoft identificadas, como Pablo
o Raúl. El panel muestra el nombre seleccionado y avisa si sólo encuentra otra
voz local. El ritmo es ligeramente más ágil, con el tono original de la voz.
**Gica-1 → Comparar voces (temporal)** abre un laboratorio con las voces que
ofrece el navegador. Escucha la misma muestra, ajusta el ritmo y pulsa **Usar en
Gica** para recordar una voz española local en esta cuenta/navegador. Comparar
no cambia la selección. Puedes restablecer la automática; las voces externas
se identifican y no se reproducen. Abrir el laboratorio apaga el micrófono.

Autorizado el 15 de noviembre: máximo global de **USD 1 estimado a tarifa normal**,
incluyendo reservas y consumos desconocidos, entre todas las cuentas/modelos/meses.
El piloto sólo admite eventos marcados como ficticios y conserva aprobación humana.
Perfil preparado: GPT-5.4 mini, máximo 24.000 entrada / 2.500 salida por solicitud.

1. Si SparkX está abierto, guarda tu trabajo y usa **Apagar SparkX**.
2. Ejecuta **Iniciar SparkX.cmd** desde esta carpeta y mantén abierta su ventana.
   Inicia la web y el coordinador local; no solicita una clave en consola.
3. Entra como superadministrador en **Gestión de IA → APIs y agentes**,
   `http://127.0.0.1:8000/ai/control/`. Introduce la clave en el formulario privado.
   Guardarla no realiza una llamada ni comprueba validez, cuota o saldo.
4. Revisa el acceso de Gica-1 y abre
   **UNAC · Claves para desarrollar Tesis I, II y III · Demo Gica-1**.
5. Pulsa **Crear propuesta → Generar propuesta** una vez. El panel derecho ofrece
   **Seguimiento** y **Conversación**, etapas observadas, tokens y presupuesto.
   Revisa el resultado antes de aprobarlo.

Este único lanzador incluye a Gica-1 y un worker en el mismo proceso local.
La clave se conserva sólo en memoria durante un máximo de dos horas y se pierde
al reiniciar. No vuelve a mostrarse ni se guarda en archivos o en la base de datos.
Su desconexión bloquea próximas solicitudes; no retira una llamada ya iniciada.
El worker procesa solicitudes nuevas y pendientes elegibles de eventos ficticios.

Cada cuenta tiene una única asignación de Gica-1, con un tope total de vida de
hasta USD 1; el piloto OpenAI mantiene además su tope global de USD 1. En
**APIs y agentes → Modelos gratuitos de Gica-1** hay doce candidatos que debes
autorizar individualmente con su política, tareas, prioridad y límites internos.
Activa **Usar primero los modelos gratuitos autorizados** para que atiendan chat
desde el inicio; las propuestas pueden asignarse también al grupo. Se rota antes
del envío por capacidad interna, sin duplicar tareas. El grupo agotado nunca
escala a pago automáticamente. La alternativa única sigue como compatibilidad
con el grupo deshabilitado. Un 429 de alcance desconocido pausa todas las rutas
OpenCode de esa cuenta diez minutos, sin garantizar restablecimiento remoto ni
reintentar esa inferencia. Los límites generales siguen vigentes.

El coordinador admite hasta dos llamadas independientes OpenAI/OpenCode de
eventos y modelos distintos: sólo inferencia corre en paralelo, con contextos
congelados y sin ORM. Preparación, seguimiento y publicación quedan serializados.
Son slots de un proceso local, no capacidad distribuida validada en SQLite.
Los permisos pertenecen al servidor: el agente no administra claves, accesos ni
presupuestos. La comprobación de superusuario vigente y el contexto de ejecución
del agente son controles lógicos, no un sandbox del sistema operativo.

Para preparar nuevamente una instalación, con las migraciones aplicadas:
`.venv\Scripts\python.exe -B manage.py prepare_romeo --username adminjorge`.
Preparar no llama al proveedor ni aprueba planes.

La verificación visual previa usa una respuesta local sintética identificada.
Jorge comunicó haber añadido su clave; esta actualización no verificó una
inferencia OpenAI real ni accedió a la credencial.
Falta ejecutar la primera solicitud autorizada y contrastar Usage en OpenAI. La cifra
del panel es estimación local; no consulta el saldo promocional ni configura un
límite contractual de facturación. Ver [verificación de Gica-1](docs/verification.md#romeo-1--piloto-openai-controlado).

## Arquitectura

Monolito modular Django MTV, servicios de aplicación, reglas de dominio puras y adaptador
de IA intercambiable. HTMX actualiza fragmentos HTML. Web y worker son procesos del mismo
proyecto. PostgreSQL será la base del prototipo desplegado; SQLite permite este primer
arranque local acotado. No se requieren microservicios, Kubernetes ni entrenar un LLM.

- `apps/events`: contexto y permisos del organizador.
- `apps/planning`: reglas, propuestas inmutables, aprobación y revisiones.
- `apps/jobs`: trabajos durables, idempotencia, cuotas, lease y cancelación.
- `apps/assistant`: conversación y adaptadores OpenAI, Groq, Gemini y Ollama local.
- `apps/ai_management`: perfiles, presupuesto USD/tokens, reservas y consumo auditado.
- `apps/accounts`: acceso, cuentas, roles y asignaciones de revisión.
- `apps/directory`: personas, organizaciones, participaciones y consultas locales autorizadas.
- `templates` y `static`: interfaz adaptable, dictado y lectura opcionales.

[Decisiones y límites de arquitectura](docs/architecture.md).

## Directorio y búsqueda de eventos

Abre **Directorio** para administrar expositores, participantes, invitados y empresas.
Los contactos pertenecen a cada organizador y no crean cuentas de acceso. Se pueden
buscar, editar y archivar; una edición obsoleta conserva el borrador y exige revisar
el conflicto. Cada evento ofrece **Personas del evento** para vincularlas con rol y
estado. Un vínculo no acredita inscripción, disponibilidad o asistencia.

**Eventos** y **Calendario** comparten filtros de texto, empresa, fechas y plan
aprobado/pendiente. La base local incluye 45 personas ficticias y seis eventos de
demostración UNAC/GICA del 16 al 21 de noviembre de 2026, con propuestas manuales
pendientes de aprobación. La carga repetida conserva los registros anteriores.

En el chat del evento escribe `buscar expositores`, `buscar eventos: UNAC` o
`personas de este evento`. Son consultas mecánicas, identificadas como locales:
no invocan modelos ni consumen tokens de proveedor. Otros mensajes conservan los
controles de perfil, asignación del agente y presupuesto; la conexión OpenAI real
sigue pendiente de introducir la clave privada.

[Diseño, auditoría de la referencia, permisos, carga y límites](docs/directory-and-catalog.md).

## Ayudante de desarrollo OpenCode

Abre **Ayudante OpenCode.cmd** para preparar una revisión o un borrador con un modelo
gratuito. Su catálogo revisa trece candidatos; diez requieren datos ficticios y
aceptación de sus condiciones. Recibe copias de archivos seleccionados y deja el resultado en
`Temporal/opencode/`; incorporar cambios requiere revisión. Es independiente del
agente de eventos y de los créditos API de SparkX. La instalación y los permisos están
verificados localmente. Tras autorización específica, una prueba remota sintética
generó un borrador con coste cero reportado; después pasó siete casos locales.
Este ensayo histórico no habilitó la API de SparkX. El piloto actual se configura
por separado en **APIs y agentes**. Revisa los datos antes de cada envío manual.
Cada resultado incluye consumo observado y escenarios de coste con tarifas pagadas,
calculados localmente y separados del gasto reportado. Comparar no invoca modelos.

[Instalación, uso, límites, privacidad y reparto de tareas](docs/opencode.md).

Se completó un [ensayo de seis eventos UNAC/GICA](docs/event-benchmark.md), con
seis agentes acotados, tres expositores ficticios y 42 pruebas principales sobre
los siete modelos. Incluye conflictos, sustituciones, cambios de horario y bloqueos
que requieren aprobación. Es evidencia separada de la demo y de la IA del producto.

## Acceso y usuarios

El login acepta **correo o usuario**, incluido `adminjorge`, y ofrece tema claro u
oscuro y mostrar/ocultar contraseña. Desde **Usuarios**, un administrador del portal
puede crear cuentas, cambiar roles y activar o desactivar accesos. Las cuentas técnicas
existentes quedan protegidas; tampoco se permite desactivar o destituir la propia
cuenta administradora. No se borran cuentas desde esta pantalla.

| Rol | Alcance |
| --- | --- |
| Administrador | Gestiona cuentas del portal y organiza sus propios eventos. No recibe automáticamente permisos técnicos ni de gasto de IA. |
| Organizador | Crea y administra sus propios eventos y asigna sus revisores. |
| Revisor | Consulta ficha, agenda aprobada y estados de preparación únicamente de sus eventos asignados. No edita, aprueba ni utiliza el agente. |

En un evento propio, **Acceso de revisores** permite conceder o retirar consultas.
Los cambios de acceso tienen una versión independiente y no alteran el plan. El
primer cambio de contraseña conserva las asignaciones; cambiar rol o activación
revoca sesiones y concesiones anteriores. Reactivar una cuenta no restaura esos
accesos automáticamente: el propietario debe asignarlos otra vez.

El formulario de alta incluye un generador criptográfico local de **20 caracteres**,
mostrar/ocultar y copia explícita. La contraseña manual admite 16–128 caracteres y
se valida en el servidor. Los usuarios nuevos deben cambiar la inicial al ingresar.
Los existentes conservan sus credenciales. La aplicación guarda hashes de Django,
no contraseñas en texto claro, y no envía invitaciones por correo. Comparte la inicial
por un canal privado; el portapapeles del sistema puede conservar lo copiado.

El login limita intentos mediante ventanas persistidas con identificadores HMAC:
5 por combinación de dirección de origen e identificador y 50 por dirección en
300 segundos. No se confía en un `X-Forwarded-For` enviado por el cliente. Si se
despliega detrás de proxy, debe configurarse y verificarse la dirección de origen
confiable; de lo contrario varios usuarios compartirían el límite de ese proxy.
No sustituye MFA, monitoreo o pruebas de exposición pública. No se incorporaron
registro público, SSO ni recuperación por email sin un servicio de correo acordado.

Las pantallas públicas y de contraseña usan respuestas sin caché; las operaciones
requieren sesión, permisos y CSRF. La revocación se comprueba en cada solicitud.
La concurrencia de privilegios sigue pendiente de PostgreSQL. Ver
[resultados y límites](docs/verification.md).

## Entrevista guiada sin IA

Desde el evento, abre **Entrevista guiada** (`/events/<id>/interview/`). La guía
presenta una pregunta a la vez sobre objetivo, público, modalidad, duración,
lugar/acceso, recursos y restricciones. La ficha existente permanece consultable.
Puedes declarar un dato confirmado por ti, supuesto o pendiente, remitir a la ficha
cuando corresponda o marcar una condición como No aplica. No se extraen ni confirman
hechos automáticamente; la duración confirmada se indica en minutos.

**Guardar y continuar** persiste la respuesta y pasa al primer punto no revisado;
**Guardar y ver resumen** abre las respuestas y sus estados con enlaces de edición.
Lo que dejes pendiente no se inventa. La guía funciona sin JavaScript, perfil IA,
worker o consumo de créditos. Las próximas solicitudes de IA reciben este contexto
cuando se configuren y autoricen; la entrevista no inicia solicitudes.

Guardar cambios conserva el plan vigente y su avance, e invalida las propuestas
preparadas con requisitos anteriores. Con la política conservadora actual, al aprobar
un plan posterior a esos cambios sus tareas comienzan pendientes; el historial del
plan anterior se conserva. Una edición obsoleta muestra los datos actuales y retiene
tu respuesta para que compares antes de guardar de nuevo.

Si la web se inició con `--noreload`, reiníciala desde su misma terminal después de
actualizar el código y aplicar migraciones. Esto conserva las variables privadas de
esa terminal; no pegues la clave de API en el código o en la conversación.

## Organización del proyecto

El código vive en apps/, config/, templates/ y static/; las pruebas se mantienen junto
a sus módulos. docs/ contiene sólo documentación vigente. El mentor y su banco tienen
una única copia canónica en .agents/skills/mentor-sparkx/.

Todo material auxiliar se crea desde el inicio dentro de **Temporal/** y se elimina
cuando pierde utilidad. Las referencias visuales actuales están en
Temporal/referencias/; las evidencias útiles de navegador se enumeran en
[verificación](docs/verification.md). Temporal/ no se versiona ni es necesaria para
ejecutar la aplicación. Las reglas permanentes
están en [AGENTS.md](AGENTS.md#organización-y-limpieza).

El entorno .venv/ y los datos activos de var/ mantienen sus ubicaciones e ignorado
de Git; no son copias auxiliares. No se acumulan exportaciones del mentor, capturas
antiguas ni registros de intentos sustituidos.

## Arranque local en Windows

**En la instalación actual:** abre **Iniciar SparkX.cmd** con doble clic desde esta
carpeta, mantén su ventana abierta y entra en http://127.0.0.1:8000/. Usa tu cuenta
existente; no necesitas volver a crearla ni instalar dependencias cada vez.

También puedes iniciarlo desde PowerShell situado en esta carpeta:

```powershell
.\.venv\Scripts\python.exe -B tools\start_sparkx.py
```

**Para detenerlo:** tu superusuario local (`adminjorge`) verá **Apagar SparkX** dentro
de su menú de perfil al pie de la barra lateral. Abre la confirmación, guarda lo que estés editando, marca la
casilla y confirma. Deja de aceptar nuevas conexiones y espera las solicitudes en
curso antes de cerrar. Los datos guardados permanecen. También admite `Ctrl+C`
desde su terminal. Para volver a usarlo, ejecuta otra vez el mismo archivo.

La página muestra **Apagando SparkX…** mientras terminan Gica-1 y las solicitudes
en curso. Después recibe una confirmación del servicio y muestra **SparkX apagado**.
Intenta cerrar esa pestaña automáticamente; si el navegador lo bloquea, conserva
el resultado y permite cerrarla manualmente. Sin confirmación no anuncia éxito.
La ventana abierta con doble clic en el lanzador termina al salir el proceso;
una terminal que ya tenías abierta permanece disponible.

El botón pertenece a `runlocal` y a su extensión `runromeo`, en desarrollo, con sesión de un
superusuario técnico y conexión local directa. No se concede al crear administradores
del portal. Abrir la confirmación no apaga nada; confirmar requiere POST, CSRF y un
token de dos minutos ligado al usuario y a esa ejecución. No está disponible con
`runserver`, WSGI/ASGI de despliegue ni `DEBUG=False`. No uses `runlocal` detrás de
un proxy ni lo expongas a Internet. No hay recarga automática: reinicia tras editar
código. Si el puerto está ocupado, el arranque falla sin terminar otro proceso;
puedes usar `runlocal --port 8001` y su dirección correspondiente.

El archivo inicia web y un worker local, sin pedir claves en consola ni crear
solicitudes de inferencia. El worker sí revisa trabajos explícitos pendientes y
nuevos; sólo los envía si siguen autorizados y su conexión está disponible.
Administra las claves en **Gestión de IA → APIs y agentes**. El apagado detiene
también este worker y puede esperar una llamada en curso. No abras otro `runjobs`
junto al lanzador en SQLite. Un worker iniciado por separado conserva su propio
ciclo y se detiene desde su terminal.

### Preparar una copia nueva

Python 3.12 o superior. La instalación actual ya tiene un entorno aislado `.venv`.
En una copia nueva:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Desde esta carpeta:

```powershell
New-Item -ItemType Directory -Force -Path var
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe -B manage.py runlocal
```

El segundo comando solicita usuario y contraseña local. Inicia sesión en
http://127.0.0.1:8000/ y crea un evento. No hay contraseña predeterminada.

Los comandos anteriores describen una copia gestionada manualmente: `runlocal`
abre sólo la web. Para el arranque integrado de la instalación preparada usa
**Iniciar SparkX.cmd**. Sólo en un entorno manual distinto, con el consumo
autorizado y sin otro worker activo, puede ejecutarse por separado:

```powershell
.\.venv\Scripts\python.exe manage.py runjobs --poll-interval 2
```

SQLite no valida la seguridad de dos workers concurrentes; usa un solo worker en este
arranque. Las pruebas de concurrencia deben ejecutarse sobre PostgreSQL antes de exponer
la aplicación a varios usuarios.

## Demo GICA

El caso mantenido de demostración usa el afiche `EVENTO1.jpg` aportado por Jorge:
**Gestión estratégica del mantenimiento: de la planificación al rendimiento**,
de GICA Certification, con el Ing. Merling Daniel Rosales Infantes.

Después de migrar la base y crear tu usuario local, carga el caso con:

```powershell
.\.venv\Scripts\python.exe -B manage.py seed_demo_event --owner adminjorge
```

Sustituye `adminjorge` si tu usuario existente tiene otro nombre. El comando no crea
cuentas ni contraseñas. Repetirlo conserva el caso y los cambios que hayas realizado;
no reinicia datos ni duplica planes. Si pertenece a otro usuario, rechaza la operación.

La carga deja una ficha, un plan inicial aprobado de ejemplo y una alternativa
pendiente que amplía la exposición 15 minutos. Entra en **Tus eventos → Demo · GICA**:
consulta la agenda, abre **Ver ficha y afiche**, revisa los supuestos y cambia a
**Propuestas** para comparar antes de aprobar o descartar. El afiche se sirve localmente
sin modificaciones; el original en Descargas se conserva.

El afiche indica jueves 12 de noviembre a las 19:30, Zoom, ingreso libre y acceso VIP
opcional con certificado y PDF. No indica año, zona, duración, cupos ni URL de acceso.
La demo asume **2026, America/Lima, 90 minutos iniciales y 100 cupos**; la alternativa
termina 15 minutos después. Estos supuestos y los pendientes aparecen en la ficha.

Los planes se prepararon manualmente para explorar el producto: no son evidencia de
inferencia IA. Al cargar por primera vez, las once tareas empiezan como «No iniciado»;
repetir la carga no reinicia el avance registrado. No se crean reuniones, inscripciones,
pagos o certificados reales ni se contacta al ponente u organizador.

## Demo 2: recorrido guiado sin consumo de IA

**Demo · Taller de IA responsable para equipos** es un escenario ficticio distinto
de GICA: 20/11/2026 a las 18:00 en America/Lima, 30 personas de aforo supuesto,
cuatro sesiones y seis tareas. No hay asistentes, reservas o ejecución reales.

Para cargarla una sola vez para tu usuario existente:

```powershell
.\.venv\Scripts\python.exe -B manage.py seed_journey_demo --owner adminjorge
```

La carga crea ficha, entrevista con supuestos y **una propuesta pendiente**. No
aprueba el plan, marca tareas ni utiliza proveedores. Repetirla conserva cualquier
edición, descarte, aprobación y avance posterior; tampoco modifica GICA. Reinicia
la web si estaba ejecutando una versión anterior del código.

La instancia actualizada el 15/11 está en **http://127.0.0.1:8000/**. Se identificó
y reinició el proceso anterior que conservaba rutas antiguas y fallaba al abrir
eventos con la plantilla nueva. `runlocal` no recarga código Python: tras actualizar,
guarda tus cambios, detén la instancia conocida y vuelve a iniciarla. Abrir un puerto
ocupado no garantiza que ejecute la versión actual. Si eliges un puerto alternativo,
utiliza la dirección que indique ese arranque:

```powershell
.\.venv\Scripts\python.exe -B manage.py runlocal --port 8001
```

Desde **Eventos → Abrir demo guiada**, o
`/events/88d44566-fc5c-5cce-9695-13eb7c027786/demo/`:

1. Revisa la ficha y la propuesta base de 90 minutos, de 18:00 a 19:30.
2. Pulsa **Aprobar esta propuesta** cuando quieras activar ese contenido exacto.
3. Abre **Actualizar tareas** y ensaya los estados con notas que indiquen que son
   datos ficticios. El porcentaje procede de tus registros; seis completadas dan 100%.
4. Vuelve a la guía y pulsa **Proponer 15 minutos más de práctica**. La práctica
   pasa de 40 a 55 minutos; preguntas empieza a las 19:25 y el cierre es a las 19:45.
   Revisa las diferencias y aprueba la alternativa si la aceptas.
5. En el recorrido original sin editar la ficha, cuatro tareas mantienen su avance.
   El ensayo cambia y su cierre dependiente vuelve a pendiente: si estaban todas
   completadas, el porcentaje pasa a 66%. Revisa esas dos tareas para volver a 100%.
6. **Comprobar conflicto** intenta solapar práctica y preguntas. El validador lo
   rechaza sin crear otra propuesta ni alterar el plan vigente o el avance.

El descarte se conserva. Preparar de nuevo una propuesta requiere un POST explícito;
reintentar el mismo escenario pendiente no lo duplica. Si editas ficha o entrevista,
la guía conserva tu personalización y desactiva sus ejemplos fijos para no sustituir
tus nuevos requisitos; puedes seguir trabajando desde el evento normal.

Esta demo valida un recorrido persistido con contenido manual. **No acredita
inferencia de IA**, decisiones fijadas, un solver, inscripciones, asistencia o cierre
de un evento real. No se habilitan presupuesto, perfil ni worker con la carga.

## Seguimiento de tareas

En **Preparación**, elige un estado y pulsa **Guardar estado**. El editor se cierra
solo después de que el servidor confirme el guardado. Al completar una tarea también
se cierran sus instrucciones y se abre la siguiente pendiente, conservando cualquier
borrador que ya tuviera. El estado de la siguiente tarea no cambia automáticamente.
Sin JavaScript, el guardado lleva a esa misma tarea mediante navegación normal.

Una completada ofrece **Reabrir tarea**: indica el motivo, elige **En proceso** o
**No iniciado** y pulsa **Confirmar reapertura**. Abrir o cancelar el formulario no
cambia su estado ni borra su historial. Los errores conservan el editor y el texto
para corregirlos. Al completar todas aparece **Preparación completada** y **Volver
al plan**; el porcentaje corresponde a registros manuales, no a ejecución verificada
del evento.

## Conexión de IA y presupuesto

Abre tu perfil al pie de la barra lateral → **Gestión de IA**, o http://127.0.0.1:8000/ai/.
El módulo incluye perfiles, comparador simultáneo manual o histórico por evento/acción,
calculadora individual, presupuesto mensual e historial filtrable con subtotales.
La conversión opcional a soles utiliza tasa, fecha y fuente declaradas; no cambia
la contabilidad en USD. Comparar no llama a una IA ni activa un perfil.
Las cuentas nuevas empiezan sin proveedor, con USD 0 y pago desactivado. No se simulan
respuestas cuando falta configuración. [Guía de uso y límites](docs/ai-management.md).

Un superadministrador prepara un perfil de Groq/Gemini gratuito, OpenAI/Groq/Gemini de pago
o un Ollama local opcional; luego lo elige en **Configurar presupuesto**. La cuota gratuita
se confirma en la cuenta del proveedor. La app no consulta elegibilidad ni saldo.
En la instalación local, el superadministrador introduce las claves en el formulario
privado **APIs y agentes**: sólo memoria, máximo dos horas y sin persistencia al
reiniciar. Para otros entornos siguen existiendo las variables privadas del servidor
y del worker `OPENAI_API_KEY`, `GROQ_API_KEY` o `GEMINI_API_KEY`; `.env.example`
documenta sus nombres y **no se carga automáticamente**. No pegues claves en el
chat, formularios de eventos o archivos versionados. Ollama requiere instalación aparte
antes de habilitar `OLLAMA_ENABLED=1`; no está instalado ni medido aquí.

Las nuevas solicitudes exigen un perfil guardado: `OPENAI_MODEL` por sí solo no activa
el worker. El catálogo del servidor fija modelos, destinos y tarifas verificadas.
Antes de una conexión real revisa saldo, facturación, cuotas y acceso en el proveedor.
Guardar en el panel local no requiere reiniciar; un despliegue con procesos separados
necesita su propia gestión de secretos. No se ha hecho una inferencia OpenAI real.

El catálogo incluye **GPT-5.4 mini** como alternativa de OpenAI para el proyecto
SparkX-Pruebas. Su tarifa normal y caché automática se distinguen de Luna; la oferta
por compartir datos se verifica en la cuenta externa y no se presume gratuita en la
contabilidad. [Preparación privada y estado de la conexión](docs/ai-management.md#preparación-de-gpt-54-mini-del-12-de-noviembre).
**Antecedente del 12 de noviembre:** Jorge eligió sólo preparar la conexión, sin
llamadas. La autorización posterior del 15 de noviembre habilita el piloto de USD 1
descrito al inicio: perfil, asignación y worker preparados, con clave aún pendiente.

Se reserva el máximo de entrada/salida y su costo bruto estimado antes de encolar.
USD y tokens mensuales se aplican por propietario, además de 20 solicitudes/día y
3 trabajos pendientes/evento. El perfil inicia con 24 000 tokens de entrada y 2500
de salida, ajustables. Caché está incluida en entrada y razonamiento en salida;
no se suman dos veces. Luna usa caché desactivada para evitar escrituras fuera
de la reserva y se simula su entrada a tarifa normal; Mini aplica caché automática
según el desglose observado. Reservas no despachadas caducan al cambiar el mes de Lima.

El diario conserva tokens observados, tarifas de cada solicitud y costo estimado;
no equivale a una factura ni al límite agregado de una organización API compartida.
Los créditos sólo se usan como escenario manual en la calculadora. Un fallo sin
contadores mantiene la reserva para conciliar; cancelar o descartar no borra consumo
remoto. No hay reintentos ni cambio automático de gratuito a pago.

## Conoce a Gica

El checklist personal fue retirado de la navegación y está deshabilitado en el
servidor. Sus datos históricos permanecen separados de los eventos.

**Conoce a Gica** reúne su avatar, apariencia, tono del saludo y ajustes de voz,
memoria, patrones y conocimientos. Cada organizador configura su propio bot;
estas preferencias no conceden permisos ni modifican claves o presupuesto.
Las opciones de personalidad y apariencia se guardan en la cuenta; las opciones
de voz y registro se recuerdan por cuenta en este navegador.

Al abrir Gica se muestran la conversación y los accesos rápidos. **Modo manual**
reúne Tu orden, Hablar, Ejecutar orden y Conversar por texto. El borrador y su
confirmación permanecen visibles fuera de ese apartado.

## Calendario y apariencia

La navegación incluye **Calendario**: vista mensual de lunes a domingo, anterior /
siguiente / Hoy, selección del día y detalle de las sesiones del plan aprobado.
Muestra eventos propios y, para revisores, únicamente los asignados; las candidatas
pendientes no publican agenda. Cada evento conserva su zona horaria. Los eventos sin fecha se
listan aparte; una fecha derivada del plan se identifica como tal.

El botón de **sol/luna**, arriba a la derecha, cambia toda la aplicación entre la
paleta clara inspirada en FIME y el grafito de SparkX. La preferencia se guarda
localmente en el navegador; inicialmente se usa la del sistema. Si el almacenamiento
está bloqueado, el cambio funciona durante la página. Sin JavaScript se conserva
el tema del sistema y la navegación normal del calendario.

Segoe UI/Arial del sistema, cuerpo de 14 px y títulos de 26/17/14 px, sidebar de
218 px y barra superior de 53 px. No se descargan fuentes ni se añaden plugins.
En móvil la cuadrícula muestra días con marcas de eventos y el detalle se lee
debajo, con controles táctiles de 44 px. [Sistema vigente](docs/design-system.md).

Las vistas Agenda / Preparación / Propuestas / Actividad y el agente ampliable
conservan sus operaciones y utilizan la misma escala y temas.

## Seguimiento de tareas

En el evento, abre **Preparación → Actualizar estado** en la tarea, elige el estado
y pulsa **Guardar estado**. Los indicadores llevan siempre texto:

- Gris: **No iniciado**.
- Ámbar: **En proceso**.
- Verde: **Completado**.

Puedes completarla directamente o reabrirla; en ambos casos se exige una nota breve.
Se guardan el usuario, la fecha y la nota de cada transición, y **Ver historial**
muestra los últimos cinco cambios de esa versión. El resumen cuenta los tres estados
y muestra el porcentaje entero de avance (completadas × 100 / total, truncado hacia
abajo). Una de once tareas equivale a 9 %; «En proceso» todavía no suma. Sin tareas
se muestra 0 % y el 100 % exige completar todas. Es avance declarado por el organizador; una nota
no acredita verificación independiente ni ejecución por IA.

Al aprobar otro plan, se conserva el avance de tareas con el mismo identificador,
título, instrucciones y requisitos previos, siempre que tampoco hayan cambiado sus
antecesoras ni la ficha del evento. Las tareas nuevas o afectadas empiezan como
«No iniciado»; el historial anterior sigue guardado. Una pestaña desactualizada debe
revisar el estado actual antes de guardar; no sobrescribe un cambio reciente.

El guardado funciona también sin JavaScript. Las propuestas pendientes se mantienen
como contenido para revisar y no permiten marcar ejecución.

## Movimiento y verificación

Motion 14.10.1 se sirve localmente con licencia MIT y SRI; origen e integridad
[revisados](docs/motion-dependency-review.md). Entradas, cambios de vista y control
para repetir la animación. El título principal entra como bloque tras una máscara;
los títulos de sección aparecen por palabras. Los rótulos de botones habilitados
se deslizan al pasar el cursor o darles foco con teclado; la pulsación tiene una
respuesta breve. Calendario comparte estos efectos. Se mantienen escala y paletas.
Movimiento reducido, fallback sin vendor y sin JS
conservan texto y navegación. No se animan chat, alertas ni polling.

La verificación de navegador utiliza Edge aislado con Playwright y prueba escritorio
y móvil, temas, navegación, permisos y recorridos principales. Herramientas de QA
opcionales en requirements-dev.txt. [Resultados y límites](docs/verification.md).

## Conversar con los agentes

Abre esta carpeta en Codex e invoca `$mentor-sparkx`. Su configuración y banco de
investigación viven en [.agents/skills/mentor-sparkx](.agents/skills/mentor-sparkx/SKILL.md).
Es un mentor con instrucciones y referencias, no un modelo reentrenado. Si no aparece,
pide a Codex leer ese archivo directamente.

El **agente del evento** es el panel de la aplicación. Consulta solo el contexto del
evento accesible al organizador; el chat no cambia el plan. Las propuestas se generan
por separado y requieren aprobación. Voz y límites: [agentes y voz](docs/agents-and-voice.md).

## Comprobaciones

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
```

Para probar PostgreSQL, define `DATABASE_URL` de una base local/de pruebas cuyo usuario
pueda crear la base temporal de Django. Nunca apuntes la suite a datos de producción.

## Antes de desplegar

[Preparación de despliegue](docs/deployment.md). Falta ensayo real sobre PostgreSQL,
contenedor/servidor, HTTPS y recursos libres del VPS. No se ha accedido a OVH, publicado
repositorio ni elegido la licencia del proyecto. No se incluyen secretos ni originales
privados del concurso. La licencia de HTMX se conserva en static/vendor.

Desde un evento están disponibles **Restricciones y alternativas**, **Responsables y
evidencias** e **Inscripciones**. Las restricciones declaran una ventana y hasta tres
expositores del directorio, conservan decisiones y permiten calcular una candidata
sin IA. Debe revisarse y aprobarse explícitamente. La preparación registra responsable,
plazo y evidencia humana; reabrir la ejecución invalida su verificación vigente.
Las inscripciones se publican mediante confirmación, respetan duplicados y aforo y
se pausan si cambia el plan aprobado. El enlace sólo será accesible desde otro equipo
cuando exista un despliegue autorizado; `127.0.0.1` es local.

El puente gratuito de demostración sólo admite eventos ficticios y permite elegir
entre doce modelos de chat revisados mediante sus presets de OpenCode. Cada solicitud conserva
el modelo elegido, sin sustitución automática. Los ensayos reales de los tres modelos
recibieron errores de cuota 429; no hay una propuesta real válida obtenida en esos ensayos.
Dos agentes QA verificaron once bloques funcionales cada uno con propuestas manuales
sintéticas, bases aisladas, navegador de escritorio/móvil y corrección/reprueba de fallos.
La alternativa Groq Free se prepara con la [guía privada](docs/ai-management.md#guía-opcional-preparar-groq-free-en-privado).
No se activa ningún proveedor ni gasto automáticamente.

Los nueve modelos con condiciones especiales muestran su política y requieren
aceptación por solicitud, ligada al modelo y a la revisión mostrada. Cada proceso
usa temporales/configuración/caché propios y cada modelo recibe únicamente historial
y planes de su procedencia acreditada. Se conservan la ficha y las restricciones
declaradas. No es un sandbox del sistema operativo ni elimina la retención remota.
Ultra queda excluido porque el catálogo actual no confirmó su presencia.
[Modelos, condiciones y aislamiento](docs/ai-management.md#aislamiento-y-modelos-ampliados).

Quedan pendientes materiales, comentarios y resumen posterior, inferencia real
integrada, PostgreSQL/carga y entregables del concurso. El usuario indicó terminar
el prototipo antes de redactar informe, PPT y manual finales bilingües.
Conocimientos de Gica: desde **Gica → Conocimientos** consulta referencias públicas
de Wikipedia, guardadas automáticamente con fuente/fecha y vigencia24h. Biblioteca
privada con revisión, corrección, desactivación y borrado;20consultas externas/día,
sin claves ni tokens de modelos. «Cuando diga programación, me refiero al calendario»
enseña una asociación utilizable y revisable después. No integra búsqueda general
de Google ni modifica permisos, planes o tareas. Detalles en
[lenguaje de Gica](docs/romeo-language.md) y [verificación](docs/verification.md).

