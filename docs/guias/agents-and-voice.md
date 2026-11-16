# Gica: guía, asistente de IA y voz

Actualización documental del 16 de noviembre de 2026. ArquiGica distingue la guía
local que acompaña al usuario, la inferencia remota que propone contenido y el
mentor usado durante el desarrollo.

## Gica en la aplicación

Gica es el bot arquitecto visible en la barra superior y en **Conoce a Gica**.
Puede acompañar por texto o voz, reconocer órdenes locales, buscar contactos,
abrir las vistas permitidas y guiar la creación de un evento. Estas funciones
usan reglas, diccionarios y servicios del servidor; no consumen tokens de un
modelo por interpretar cada turno.

La creación guiada pide los datos pendientes y muestra cómo se completa la ficha.
El directorio resuelve nombres y alias, ofrece coincidencias y pregunta antes de
registrar una identidad nueva. Después de crear el evento, la guía identifica
su estado y prepara los formularios para continuar. En el recorrido manual,
**guardar, generar y aprobar conservan sus controles humanos**. El acompañamiento
no concede acceso a Usuarios ni a Gestión de IA.

El asistente remoto se utiliza cuando se solicita contenido al proveedor
configurado. El worker procesa el trabajo, valida la respuesta y registra el
consumo. La generación compacta solicita agenda, preparación y comunicaciones
con un esquema cerrado; si faltan datos, admite preguntas breves. Configurar una
clave no demuestra que exista cuota ni que una llamada haya tenido éxito.
Si falta la clave OpenAI, la solicitud queda en **Guía en pausa**. El administrador
la guarda mediante el enlace que abre otra pestaña y vuelve a **Reanudar guía**;
Gica conserva ese paso y las respuestas ya elegidas. No se envía nada por guardar
la clave. Hay que mantener abierta la pestaña original para conservar el recorrido.
Consulta [gestión de IA](ai-management.md),
[lenguaje de Gica](../arquitectura/gica-language.md) y
[directorio y catálogo](../arquitectura/directory-and-catalog.md).

## Presentación narrada y revisión manual

**Mis eventos → Iniciar demo con OpenAI** inicia el piloto narrado autorizado.
Presenta el proyecto, recorre el registro de organización y expositor, crea la
ficha y muestra la solicitud al proveedor. Una respuesta válida permanece tres
segundos en **Respuesta recibida** antes de continuar. Después muestra el
calendario y un cambio de expositor. Este piloto tiene identidad, permisos y
presupuesto acotados; su autorización no se extiende a otros eventos.

**Recorrido completo** conserva las pausas de revisión y **Aprobar y continuar**.
La opción gratuita requiere selección explícita y cuota disponible. Ningún error
habilita un proveedor de pago por sí solo. La despedida explica cómo usar la guía
por voz o texto; no convierte la conversación en autorización para aprobar planes.
Los estados de tareas se confirman manualmente: una propuesta no acredita trabajo
realizado ni envía correos, reserva servicios o ejecuta código arbitrario.

## Voz dentro de ArquiGica

El navegador ofrece reconocimiento mediante `SpeechRecognition` y lectura mediante
`SpeechSynthesis` cuando son compatibles. Al abrir la conversación guiada, Gica
saluda y puede escuchar después del aviso y permiso correspondientes. Las órdenes
claras se procesan tras **1,5 segundos sin cambios en la transcripción**; los
pasos específicos de la entrevista pueden aplicar una espera distinta. Si no hay
palabras reconocidas, el silencio no envía una respuesta vacía ni termina la guía.
El dictado manual sigue permitiendo revisar el texto antes de enviarlo.

La conversación continúa en las vistas admitidas y pausa el micrófono mientras
Gica habla o ejecuta una acción. **Apagar mic** y **Terminar conversación** permiten
detenerla. Un cambio de cuenta, permiso, visibilidad o una navegación incompatible
puede terminar la sesión. El control de turnos y los límites de reinicio del
reconocedor están documentados en [la verificación](../verification.md).

Las voces dependen de las disponibles en ese navegador. El comparador permite
elegir una voz española y conservar la selección por cuenta y navegador. No se
incluyen modelos de voz externos ni una integración Realtime de pago en esta
función. El navegador puede procesar audio mediante su propio servicio remoto;
no se promete reconocimiento sin conexión ni soporte universal. Se requiere
localhost o HTTPS y permiso del navegador. La entrada por texto permanece
disponible. ArquiGica no guarda audio; la memoria textual opcional conserva los
registros autorizados y permite revisarlos o eliminarlos.

Referencias técnicas utilizadas para la implementación:
[SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)
y [SpeechSynthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis).
Los resultados medidos y el audio físico pendiente se distinguen en
[verificación](../verification.md).

## Mentor de desarrollo

El mentor acompaña diseño, código, validación y defensa dentro de Codex/ChatGPT.
Su skill y banco pertenecen al entorno privado de desarrollo: no se distribuyen
en el ZIP y no son una dependencia del producto. Constituyen instrucciones y
referencias consultables, no un modelo reentrenado. Las instancias colaboradoras
de una tarea no son contactos permanentes de la plataforma.

La voz para conversar con ese mentor depende del cliente y de la cuenta usada.
La skill no instala un control de voz ni activa permisos del dispositivo. Estas
condiciones son independientes de la voz implementada dentro de ArquiGica.
