# Gestión de IA, tokens y presupuesto

Guía operativa del prototipo local de ArquiGica. El acceso está en el menú del
perfil → **Gestión de IA**; las conexiones y asignaciones se administran en
**APIs y agentes** (`/ai/control/`). Configurar una conexión no realiza inferencias.

## Responsabilidades y permisos

- El **superadministrador humano** configura perfiles, conexiones, autorizaciones
  de pago, asignaciones, políticas del grupo gratuito y conciliaciones manuales.
- El organizador trabaja sobre sus eventos y revisa las propuestas del asistente.
  Las consultas de historial respetan la cuenta, el actor y el evento propietario.
- **Gica-1** interpreta órdenes y acompaña el recorrido; no administra usuarios,
  credenciales, límites ni autorizaciones, aunque actúe para un superadministrador.
- La IA propone contenido. El servidor valida estructura, tiempos, dependencias,
  permisos, versiones y presupuesto antes de preparar o aplicar una propuesta.

## Configuración privada de la conexión

1. Inicia ArquiGica con `iniciar.cmd` e ingresa con una cuenta autorizada.
2. En **Gestión de IA → Proveedores**, prepara el perfil: proveedor, modalidad,
   modelo permitido, límites de entrada/salida y tarifas de referencia.
3. En **Presupuesto**, selecciona el perfil y fija los límites mensuales de USD
   y tokens. El uso de pago requiere habilitación expresa y presupuesto positivo.
4. En **APIs y agentes**, selecciona el proveedor, introduce la clave en el campo
   privado y pulsa **Guardar conexión privada**. Nunca la pegues en el chat.
5. Configura la asignación de Gica: perfil principal, tope acumulado del agente
   y, si corresponde, grupo gratuito y funciones autorizadas. Guarda los cambios.
6. Revisa el estado de la conexión y los límites antes de iniciar una solicitud.
   «Disponible en esta ejecución» acredita una referencia local, no una prueba remota.

La clave introducida en el panel dura **hasta dos horas o hasta cerrar/reiniciar
el proceso**. No se devuelve al navegador ni se persiste en la base, documentos
o repositorio. Para reemplazarla, abre de nuevo el editor privado; desconectarla
revoca futuras referencias, pero no puede retirar una llamada ya despachada.

El panel exige HTTPS o acceso local directo de desarrollo, además de sesión y
protección CSRF. Las claves gestionadas son privadas de la cuenta y versión;
una referencia caducada o revocada falla sin probar otra clave del entorno.
La compatibilidad heredada con variables del servidor sólo se usa sin referencia
gestionada; ArquiGica no carga automáticamente archivos `.env`.

El arranque local comparte web y worker en un proceso; no abras workers adicionales
para este piloto SQLite. Varios procesos requieren custodia compartida de secretos
y verificación de concurrencia en PostgreSQL.

## Gica local y asistencia remota

| Función | Tratamiento |
| --- | --- |
| Navegación, tema, búsquedas y preguntas guiadas | Reglas locales y permisos del servidor; no requieren un LLM remoto. |
| Horarios, porcentajes, dependencias y conflictos | Cálculo y validación deterministas; el modelo no concede permisos. |
| Agenda, preparación y borradores de comunicación | Solicitud remota explícita mediante el contrato admitido. |
| Lectura y dictado | Síntesis local disponible y reconocimiento del navegador con consentimiento; este último puede usar su propio servicio. |

Consulta [el banco de lenguaje de Gica](../arquitectura/gica-language.md) para sus reglas y patrones.

## Generación compacta del seminario

El contrato actual está acotado al **seminario virtual de mantenimiento de
90 minutos** y su ficha confirmada. No es una exportación libre de cualquier
formulario. Los nombres, institución, fecha, contacto e historial permanecen
locales; la solicitud utiliza el tema público cerrado, opciones permitidas y
las referencias `p1` y `r1`. El servidor completa horarios y asignaciones reales.

El proveedor se elige expresamente: **OpenAI** o **ruta gratuita autorizada**.
El recorrido compacto OpenAI está restringido al modelo permitido por
`compact_planning.py`, actualmente `gpt-5.4-mini`; otro preset no amplía el contrato.
Un fallo gratuito no activa OpenAI y un fallo OpenAI no inicia una cadena de modelos.

| Elemento | Contrato de nuevas generaciones |
| --- | --- |
| Entrada | Hasta 12.000 tokens, limitada además por el perfil seleccionado. |
| Salida | Hasta 1.800 tokens; sólo JSON del contrato, sin explicación adicional. |
| Agenda | Entre 2 y 6 sesiones; suma exacta de 90 minutos. |
| Preparación | Entre 8 y 10 tareas concretas con entregables o comprobaciones observables. |
| Dependencias | Hasta 5 índices de tareas anteriores por tarea; sin ciclos ni referencias futuras. |
| Comunicaciones | Exactamente 3: `invitation`, `description` e `instructions`. |
| Textos | Títulos de hasta 90 caracteres; comunicaciones de hasta 320, preferentemente breves. |
| Aclaraciones | Hasta 4 preguntas, con opciones cerradas del catálogo de preferencias. |

La respuesta usa `v` y `state`. Con `state=questions` contiene `questions`;
con `state=proposal`, contiene `agenda`, `preparation` y `communications`.
OpenAI transporta ese objeto dentro de `result`, con esquema estricto. El
servidor valida el resultado antes de transformarlo en una propuesta del evento.

Hay **dos rondas normales**: solicitud inicial y aclaraciones. Gica espera las
elecciones y las envía juntas; la segunda ronda debe producir una propuesta.
Una aclaración OpenAI fallida reciente admite un único reintento humano explícito,
que reutiliza respuestas y reserva de nuevo. No hay un bucle de reintentos.

Las respuestas históricas más pequeñas siguen legibles, sin tareas inventadas.
Las tareas usan **No iniciado**, **En proceso** y **Completado**; su avance es
`floor(completadas × 100 / total)` cuando hay tareas. Generar una propuesta no
completa trabajo ni envía los tres borradores o crea una sala virtual.

## Cambio acotado de una agenda aprobada

**Pedir cambio a la IA** admite `more_case_time`: solicitar cinco minutos más
para el caso práctico. Antes de reservar, exige un plan aprobado de 90 minutos,
un caso y un bloque de preguntas separados y tiempo que pueda redistribuirse.

Se exportan sólo las funciones y minutos de las sesiones; no salen títulos
editados, nombres, fechas, identificadores, evidencias ni estados de tareas.
La respuesta debe conservar el número y orden de funciones de la agenda,
aumentar el caso **al menos cinco minutos**, mantener **90 minutos en total**
y dejar **al menos diez minutos para preguntas**. No admite preguntas nuevas.

El servidor conserva localmente tareas y avances. El plan vigente permanece
hasta revisar y aprobar la alternativa. Este cambio requiere **aprobación humana**,
también en la demo; una respuesta válida no significa que ya se haya aplicado.
Si la ficha o el plan base cambiaron, se rechaza la alternativa obsoleta.

## Ejecución visible y pausa por clave

Si falta la conexión, la guía queda en **pausa** en el mismo paso:

1. Abre **Configurar conexión** y guarda la clave desde el panel privado.
2. Regresa a la guía y pulsa **Reanudar guía**.
3. El servidor comprueba de nuevo permiso, referencia y presupuesto antes de enviar.

Esperar por una clave no despacha inferencias ni consume tokens del proveedor.
Reanudar no repite la ficha ni autoriza pagos adicionales. Si la clave vuelve a
caducar o la referencia deja de ser válida, debe revisarse la conexión.
**Detener recorrido** impide pasos futuros; una solicitud ya enviada puede
terminar y conservar consumo aunque su resultado no se publique.

El recorrido con revisión espera la aprobación del organizador. Las modalidades
de demo que aplican la propuesta inicial del escenario fijo requieren su
autorización específica; no conceden autonomía general al bot.

## Presupuestos y reserva previa

Los controles son distintos y se comprueban antes de despachar:

| Control | Ámbito |
| --- | --- |
| Presupuesto y tokens mensuales | Cuenta propietaria; mes contable en `America/Lima`. |
| Tope acumulado del agente | Consumo y reservas históricos de su cuenta; no se reinicia al cambiar perfil o mes. |
| Tope global del piloto OpenAI | **USD 1 acumulado**, compartido entre cuentas, modelos y meses. |

Crear un perfil, renombrar al agente o archivar un evento no borra su gasto.
La reserva usa máximos de entrada/salida y tarifas capturadas; para entrada toma
la mayor tarifa aplicable, sin asumir promociones ni caché. Los tokens de caché
ya están incluidos en la entrada. Los importes usan `Decimal`, con redondeo
hacia arriba a seis decimales.

**Disponible = límite − consumo liquidado − reservas abiertas**, con suelo cero.
Cada `AIUsage` conserva la instantánea de perfil, versión y tarifas del intento.
Un cambio posterior del catálogo no reescribe el coste histórico. La cota previa
basada en bytes y margen de protocolo es conservadora; no es tokenización exacta.

Los importes son **consumo bruto estimado, no factura ni saldo del proveedor**.
Los créditos declarados sólo sirven para escenarios de calculadora; no amplían
las reservas ni se descuentan del tope local. ArquiGica no consulta suscripciones,
beneficios, saldos externos ni el uso de una clave fuera de esta aplicación.

## Fallos, consumo desconocido y conciliación

| Situación | Tratamiento |
| --- | --- |
| Cancelación o rechazo antes del despacho | Libera la reserva del intento que no se envió. |
| Respuesta con uso completo y coherente | Liquida el coste estimado y libera el sobrante. |
| Timeout, interrupción o uso incompleto tras despachar | Mantiene la reserva y muestra **Por conciliar**. |
| Resultado inválido, obsoleto o cancelado con uso informado | Registra el consumo aunque no aplique el contenido. |
| Uso observado superior a la reserva | Conserva el importe completo y bloquea nuevas solicitudes para revisión. |

La ausencia de contadores no se convierte en cero. El token del intento permite
liquidar una respuesta tardía sin repetir la petición. La idempotencia evita otra
reserva para la misma solicitud. Una reserva antigua en cola se rechaza antes del
envío; una llamada despachada conserva su mes. El worker revalida los límites.

Sólo el superadministrador humano propietario puede conciliar un intento terminado
**Por conciliar**, con cantidades y comprobante del proveedor. Se conservan fuente,
responsable, fecha y nota bajo **Conciliación manual**, diferenciada de lectura de API.
No sustituye un consumo ya confirmado ni permite al agente ajustar gastos.
Cero requiere una declaración documentada o un uso cero observado.

## Grupo gratuito, cuotas y aislamiento

El superadministrador autoriza modelos, función (`chat`, `plan` o ambas), prioridad
y límites diarios. La selección se realiza **antes del despacho**, por prioridad
y uso, entre entradas autorizadas con capacidad local. Las gratuitas pueden usarse
desde el inicio para tareas admitidas, sin esperar a agotar un proveedor de pago.

En las rutas generales, una insuficiencia de presupuesto USD puede seleccionar
un grupo o alternativa gratuita previamente autorizada. No lo hacen un fallo
remoto, tokens insuficientes, una clave inválida o un permiso retirado. El
recorrido compacto conserva su proveedor explícito y sus restricciones propias.
Una misma solicitud elige un modelo; no se duplica entre proveedores ni encadena
intentos tras un fallo. El coordinador admite dos solicitudes independientes.

El catálogo mantenido define los modelos permitidos y sus políticas. El puente
comprueba precio cero y límites antes de ejecutar; un modelo retirado o de pago
se rechaza. Estar en el catálogo o aparecer disponible localmente no acredita
cuota remota, gratuidad futura ni disponibilidad ilimitada.

Los límites internos diarios del grupo usan UTC y no representan la cuota real
del proveedor. Un HTTP 429 pausa la pasarela OpenCode de esa cuenta durante
diez minutos como espera local; no garantiza un restablecimiento ni dispara
la llamada al siguiente modelo. Los consumos desconocidos conservan su reserva.

Cada ejecución usa un entorno temporal separado, sin historial, repositorio ni
credenciales del desarrollador, y deniega herramientas del agente. No controla
la retención o entrenamiento del proveedor: requiere su política vigente y, cuando
corresponde, consentimiento vinculado a la solicitud. Los modelos sintéticos no
admiten datos reales; el contexto compacto minimizado es una excepción cerrada.

## Leer el historial y comparar escenarios

**Historial de uso** filtra por evento, acción y mes; distingue consumo conocido,
reservas y conciliaciones. No elimina intentos fallidos ni gasto de eventos archivados.

**Calculadora** y **Comparador** no llaman a una IA. Admiten cantidades manuales
o historial elegible y aplican las tarifas guardadas. Las comparaciones usan el
mismo volumen de tokens para cada alternativa: no garantizan igual calidad,
longitud, latencia o disponibilidad. Revisa cobertura, registros excluidos,
caché desconocida y procedencia antes de interpretar una cifra como ahorro.

Un coste cero de API no incluye infraestructura. La presentación en soles requiere
tasa, fecha y fuente declaradas; los límites siguen en USD, sin consultar saldos
ni una API de cambio.

## Referencias mantenidas

- [Arquitectura](../architecture.md) e [inicio local](inicio.md).
- [Operación de OpenCode](opencode.md) y [despliegue](deployment.md).
- [Contrato compacto](../../apps/assistant/compact_contract.py) y [cambio de agenda](../../apps/assistant/compact_changes.py).
- [Credenciales](../../apps/ai_management/runtime_credentials.py), [presupuestos](../../apps/ai_management/services.py) y [tope OpenAI](../../apps/ai_management/pilot.py).
- [Grupo gratuito](../../apps/ai_management/free_pool.py) y [consentimiento](../../apps/ai_management/model_policy.py).
