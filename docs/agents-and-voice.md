# Mentor, agente del evento y voz

## Dos funciones distintas

El mentor del proyecto acompaña diseño, código, validación y defensa. Se usa en la
conversación de Codex/ChatGPT, cargando `$mentor-sparkx` desde la carpeta del proyecto.
Su banco es documentación consultable; no se han modificado pesos ni creado una
identidad de agente alojada. Las instancias internas que colaboran en una tarea no
constituyen contactos independientes permanentes a los que se pueda llamar.

El agente del producto vive en el panel de cada evento. Necesita el adaptador configurado
y el worker. Su historial está separado por evento y el servidor comprueba propietario
antes de acceder o encolar. No tiene herramientas para enviar correos, reservar servicios
o ejecutar código. Sus respuestas son texto escapado. La generación de planes usa un
esquema y validación semántica posterior. El organizador aprueba la versión exacta.

Los estados de preparación se registran manualmente en la vista de tareas. El chat
no los actualiza; su contexto incluye una instantánea calculada de estados y
porcentaje. Una propuesta del agente no marca trabajo como realizado. Los comandos
concretos de búsqueda de personas y eventos se responden localmente mediante
herramientas de lectura autorizadas, sin invocar un modelo. No constituyen todavía
un ciclo general de herramientas del LLM; ver [directorio y catálogo](directory-and-catalog.md).

## Voz para trabajar con el mentor

La documentación actual de ChatGPT describe voz en escritorio para conversaciones y
tareas Codex cuando esté disponible en el cliente/cuenta. Entra en la tarea y busca el
control de iniciar voz. La skill no habilita ese botón ni garantiza que exista en esta
instalación. Si el cliente no lo ofrece, el texto o el dictado del sistema siguen siendo
alternativas. No se ha probado el micrófono de Jorge ni activado permisos.

Fuente consultada el 8-11-2026:
https://learn.chatgpt.com/docs/features/voice

## Voz dentro de SparkX

El primer incremento implementa dictado opcional mediante SpeechRecognition y lectura
opcional mediante SpeechSynthesis del navegador. Se comprueba disponibilidad y se muestra
un aviso antes de activarlos. El micrófono no se inicia automáticamente. La transcripción
permanece editable y requiere pulsar Enviar; la lectura requiere acción expresa y puede
detenerse. No se guarda audio en nuestra aplicación.

El navegador puede depender de un servicio externo de voz. No se promete procesamiento
local, soporte universal ni gratuidad del servicio externo. Es necesario HTTPS o localhost
y permiso del navegador. Si no hay soporte o conexión, el texto se conserva.

Esto no implementa una conversación bidireccional Realtime continua. Realtime por API
implicaría otra integración, consumo y controles; se pospone hasta medir su utilidad y
presupuesto. El dictado no sustituye el coste de inferencia de las consultas de texto.

Fuentes técnicas:
https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis
