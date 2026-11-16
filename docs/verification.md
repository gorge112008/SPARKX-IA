# Verificación local de ArquiGica — actualización del 16 de noviembre de 2026

## Informe del proyecto para la entrega

El usuario precisó que el entregable es un **Project Report** con descripción del
problema, objetivos, solución propuesta, metodología, tecnologías utilizadas,
implementación y resultados. El Word vigente se reorganiza en esos siete
apartados; el manual y las instrucciones técnicas dejan de dominar el cuerpo.
Los objetivos específicos se contrastan con resultados locales y pendientes.
Se conservan las copias técnicas anteriores como antecedente, y los enlaces
principales del README apuntan a los nuevos informes del proyecto ES/EN.
Cada versión tiene doce páginas, ocho figuras y el logo. Resultados añade cinco
figuras vinculadas a los objetivos: directorio, calendario, tramo de agenda,
cambio pendiente de aprobación y personalización de Gica. Los detalles de
identidad y preferencias proceden de dos áreas identificadas de la misma
pantalla; los recortes y sus hashes se registran en `outcome-figures.json`.
Se renderizaron las versiones finales con el flujo canónico. El cotejo
independiente comprobó secciones, cifras, alcance y ausencia de secretos.

El PPT mantiene catorce diapositivas por idioma y aclara problema y objetivo,
colaboración entre Gica y la IA, metodología iterativa y resultados. La etiqueta
de evidencia indica siete **grupos** UI. No se ejecutaron nuevas pruebas de la
aplicación ni inferencias para esta corrección documental. Recibos y renders:
`Temporal/arquigica-project-report/`.

## Preparación específica y cambio de agenda con IA

Las nuevas solicitudes piden entre ocho y diez tareas concretas del seminario de
mantenimiento, con entregables breves y dependencias entre contenido, materiales,
acceso, ensayo y moderación. OpenAI recibe un esquema con ese rango y tres
comunicaciones: invitación, descripción e indicaciones. Se mantienen los límites
de 12.000 tokens de entrada, 1.800 de salida y USD 1 acumulado. Los contratos
históricos con menos tareas o mensajes siguen siendo legibles.

El cambio cerrado `more_case_time` proyecta sólo minutos y funciones de sesiones,
sin exportar nombres, fechas o títulos privados del plan. La respuesta debe dar
al caso al menos cinco minutos adicionales, conservar 90 minutos en total y diez
como mínimo para preguntas. El servidor conserva títulos, tareas, fecha y
expositor; rechaza una ficha aún no sincronizada con su agenda. La propuesta se
aprueba mediante una confirmación humana, también en el recorrido automático.

La demo explica instrucciones y dependencias, ilustra estados y porcentaje en
una escena local sin guardar completados ficticios, lee las comunicaciones y
termina en Conoce a Gica. El perfil reutiliza los controles de voz ya vinculados
al navegar, sin abrir la conversación ni duplicar sus identificadores.

Validación de servidor: **99 pruebas correctas** en planificación compacta,
OpenAI, cambio acotado, piloto, compatibilidad y perfil, en 31,433 segundos.
Comprobación Django y sintaxis de cinco módulos JavaScript correctas. Proveedores
doblados localmente; ninguna llamada remota ni modificación de la base activa
durante estas pruebas. El registro está en
`Temporal/arquigica-final-artifacts/backend-checks.log`.

Comprobación visual con Edge aislado y SQLite descartable: tres grupos
principales correctos para instrucciones y desplazamiento, simulación de estados
al 10 % sin cambios persistidos y lectura de tres mensajes. Otros cuatro grupos
verificaron la aprobación humana del cambio de IA, la narración final de Conoce
a Gica y ambas vistas en móvil oscuro a 390 × 844 píxeles. Detener retira la
simulación; la revisión no deja el cursor sobre el cuadro de aprobación. Sin
errores JavaScript, avisos relevantes, peticiones externas ni POST de negocio.
La interfaz usa plantillas, CSS y cursor reales; contenido y voz son dobles
locales. Se repitieron los cuatro grupos de integración de la pausa por clave
con el narrador actualizado. Capturas y procedencia:
`Temporal/qa-gica-demo-content/screenshots.json`.

Antecedente técnico conservado: informes ArquiGica de 17 páginas en español y 15 en
inglés, cada uno con nueve capturas actuales y logo. Las presentaciones tienen
14 diapositivas por idioma. Se inspeccionaron las 32 páginas renderizadas con
LibreOffice y las 28 diapositivas renderizadas con Artifact Tool. Los PPTX
pasaron la comprobación de integridad, disposición y reimportación; no se
abrieron en PowerPoint nativo. Se conservaron los originales anteriores; este
material técnico sirve como antecedente del informe del proyecto vigente.
Recibos y hashes de ese corte en
`Temporal/arquigica-final-artifacts/`.

## Pausa por clave API ausente — corte vigente

El recorrido y la solicitud manual del piloto conservan su paso cuando OpenAI
devuelve el rechazo local `ai_not_configured`, sin crear el trabajo ni reservar
consumo. El aviso **Guía en pausa** permite al administrador abrir **Guardar
clave API** en otra pestaña y volver a **Reanudar guía**. Guardar una conexión
no envía la solicitud automáticamente; si sigue faltando, se mantiene la pausa.
Se conservan las respuestas de aclaración, el proveedor y la clave de idempotencia.

El cliente sólo reintenta esa operación local rechazada mediante un clic real.
No reenvía trabajos ante errores de cuota, permisos, proveedor o tiempos agotados.
Detener, salir de la página o cambiar de usuario/rol cancela la continuidad.
La pestaña oculta sólo se conserva durante esta pausa; recargar o cerrar la guía
termina el recorrido en memoria. Siguen vigentes las expiraciones de sesión.

Validación: **70 pruebas backend** correctas (49 de planificación compacta y
OpenAI, 21 de piloto y flujo), **12 grupos de pruebas UI** del cliente y **4 de
integración** con el narrador real. Se verificaron diez minutos virtuales de
pausa, reanudación, doble clic, respuestas conservadas, cambio de pestaña y
cancelación. Edge aislado mediante Playwright por ausencia de Browser; escritorio
y móvil sin recortes, sin errores de consola ni solicitudes externas.
Los proveedores, audio y navegación de prueba usan dobles locales, sin inferencia
ni modificaciones de la base activa. Evidencia en `Temporal/qa-gica-api-pause/`.

## Identidad definitiva azul y blanco — corte vigente

Por confirmación del usuario, el logo utiliza exclusivamente **#00437D y blanco**:
azul sobre blanco en tema claro y blanco sobre azul en oscuro. La misma geometría
se mantiene mediante máscara CSS; el icono del navegador también se invierte.
El turquesa **#087F8C** queda reservado a controles y estados de la interfaz.

Se completó la revisión de identidad visible de ArquiGica en pantallas, narración,
ayudas, administración Django, consola, prompts y guías vigentes. El nuevo
empaquetado identifica ArquiGica y sigue reconociendo el manifiesto anterior.
Se conservan identificadores de compatibilidad, rutas, claves locales, carpeta
técnica y referencias auténticas al concurso y al proyecto externo de OpenAI.

Validación de esta ampliación: **69 pruebas** de herramientas/lenguaje, **45** de
empaquetado/catálogo/instalación y **79** de acceso/conocimiento/lenguaje correctas
(hay once pruebas de lenguaje compartidas entre grupos). `manage.py check` sin
incidencias; **27 pruebas** adicionales del recorrido manual correctas tras
actualizar su descripción. Selección de **489 fuentes** válida. **26 comprobaciones UI** correctas
en Edge aislado, con SQLite sintético: login, marca, inversión de logo y favicon,
persistencia de tema y móvil a 390 y 360 píxeles sin desbordamientos. Sin errores
de consola, recursos fallidos ni peticiones externas.

No se modificaron la base activa, las conexiones ni los presupuestos, ni se
inició/reinició el servicio habitual. Las capturas y resultados vigentes están en
`Temporal/qa-arquigica-brand/`. Los Word, PPT y ZIP anteriores conservan su
identidad y alcance históricos hasta regenerarse.

## ArquiGica y acceso dividido — corte vigente

El nombre visible del producto es **ArquiGica**; SparkX 3.0 identifica el
concurso y `SPARKX3.0` sigue siendo la carpeta técnica existente. La marca AG,
los títulos, los mensajes y la narración utilizan la nueva identidad. Se
conservan rutas, cuentas, IDs, claves de almacenamiento y contratos técnicos.

Azul institucional **#00437D**, obtenido del PNG aportado, y turquesa de acciones
**#087F8C**. Las tintas para texto y controles se adaptan al fondo grafito del
tema oscuro. El acceso muestra marca a la izquierda y formulario real a la
derecha; en móvil se apila. El monograma generado con transparencia está en
`static/brand/`, con procedencia y prompt. Su máscara CSS mantiene colores
exactos sin rasterizar los campos ni los textos.

Comprobaciones de este cambio:

- **143 casos de acceso, vistas y apagado: 142 correctos, uno omitido** que
  requiere PostgreSQL; **146 casos** de contexto, contrato, proveedores con
  dobles y demo correctos; **11 casos** de arranque y empaquetado correctos.
- **21 comprobaciones UI** en Edge aislado mediante Playwright, al no estar
  disponible Browser. HTTP real sobre SQLite sintético: login válido e inválido,
  contraseña visible/oculta, tema persistente, branding del panel y móvil sin
  desbordamientos. Capturas a 1568×1003, 390×844 y 360×740; sin errores de
  consola, recursos fallidos o peticiones externas.
- Contraste de texto de botones claro **4,75:1**, oscuro **7,40:1**; identidad y
  navegación usan tintas accesibles. Esta comprobación no certifica todos los
  estados o componentes de la plataforma.

La base activa, sus cuentas, las conexiones privadas y el presupuesto no se
modificaron. No se inició ni reinició el servicio habitual ni se ejecutó una
inferencia del prototipo. Se revisó la referencia y el render final, con
comparación de layout, copia, tipografía, color y activo en
`Temporal/qa-arquigica-brand/`. Los Word, PPT y ZIP anteriores no se regeneraron
con esta identidad; conservan su fecha y alcance anteriores.

## Lanzador simplificado — corte vigente

El archivo raíz ahora es **`iniciar.cmd`**. El renombrado conserva su contenido
byte por byte, comprobado con SHA-256; siguen el mismo arranque, entorno y
coordinador. En PowerShell se ejecuta con `.\iniciar.cmd` sin comillas ni `&`.
Se actualizaron README, guías vigentes, arquitectura, plan de construcción,
mensajes de apagado y selección de archivos del empaquetador. Los registros
históricos posteriores conservan el nombre anterior como antecedente.

Comprobaciones: **11 pruebas del lanzador y empaquetado** y **41 pruebas de
apagado local** correctas; selección de **487 archivos de fuentes** correcta,
con `iniciar.cmd` incluido. No se arrancó ni reinició el servicio, ni se
ejecutaron llamadas de IA. Los accesos directos externos que apunten al nombre
anterior deben actualizarse. Los ZIP e informes de entregas anteriores no se
regeneraron. El guion se actualizó en `entrega/SparkX_Guion_Video_Actualizado.docx`
porque la versión anterior estaba abierta; conserva dos páginas revisadas.

## Organización formal del código y documentación — corte vigente

Se reorganizaron **90 archivos de pruebas** en `apps/<modulo>/tests/`, para las
nueve apps. Se ajustaron imports y la ruta del corpus dependiente de `__file__`;
el fixture compartido `valid_plan` quedó en `planning/tests/fixtures.py` con
exportación compatible. El descubrimiento conserva exactamente **1.540 casos
únicos**, sin pérdida ni duplicación después de renombrar módulos.

La portada README y la arquitectura presentan el código vigente, sus
responsabilidades, diagramas y arranque real. Once documentos se agruparon en
`docs/guias`, `docs/arquitectura`, `docs/decisiones` y `docs/validacion`.
Las notas largas anteriores de README y arquitectura se conservan en
`docs/historial` como antecedentes explícitos. `docs/architecture.md`,
`docs/construction-plan.md` y este registro mantienen entradas estables.

El workspace portátil `ArquiGica-presentacion.code-workspace` ordena el explorador
de VS Code y oculta entornos, datos y auxiliares de la vista de presentación.
No traslada esos archivos ni sustituye permisos o exclusiones de distribución.
El empaquetador admite el workspace y conserva las ocho excepciones de fixtures
de seguridad con los mismos hashes, vinculadas a sus nuevas rutas.

Comprobaciones tras la organización:

- Suite completa Django: **1.540 casos, 1.526 correctos y 14 omitidos** por
  bloqueos/concurrencia que requieren PostgreSQL, sobre el entorno SQLite local.
- Herramientas: **139 pruebas correctas**, incluidas las del lanzador,
  ayudante OpenCode y empaquetador. Sus conexiones están controladas en las pruebas.
- `check` correcto, `makemigrations --check --dry-run` sin cambios y paquete de
  fuentes aceptado por la selección y comprobación de credenciales.
- **237 enlaces locales** de documentación revisados, sin destinos ausentes.

No se movieron módulos ejecutables, plantillas, recursos de la aplicación,
migraciones, entorno o datos activos. No se reinició el servicio habitual;
al comprobar el puerto 8000 se encontraba detenido. Esta organización no
ejecutó inferencias reales ni actualizó los
Word/PPT/ZIP de entregas anteriores; deben regenerarse al preparar otra entrega.

Evidencia privada local: `Temporal/qa-code-structure/` contiene mapas de
movimientos, comparación de descubrimiento, suites y comprobación de enlaces.
La guía de inicio está en [Inicio e instalación](guias/inicio.md).

## Directorio antes del evento y confirmación visual — corte vigente

El recorrido actualizado presenta SparkX y a **Gica, bot arquitecto**; crea
Gicaingenieros, registra a **Jorge Gayoso** y después abre Nuevo evento. Mantiene
Robert como primer expositor y muestra posteriormente cómo sustituirlo por Jorge.
La despedida explica el acompañamiento por voz/texto. La inferencia y sus permisos
no se confunden con la guía: guardar, generar y aprobar manualmente mantienen
sus controles humanos habituales.

Una respuesta válida muestra **Respuesta recibida** durante 3.000 ms antes de
cerrarse y continuar. El recorrido integrado midió 3.004,7 y 3.005,9 ms en dos
respuestas; el reloj virtual comprobó los límites 2.999/3.000 ms, cancelación,
cambio de identidad, reemplazo de escena y movimiento reducido. Los errores
no presentan confirmación de éxito.

Verificación nueva, sin inferencias remotas ni consumo adicional:

- **163 casos backend: 161 correctos y dos omitidos de concurrencia PostgreSQL.**
  Incluyen retiro de fichas, piloto, contrato compacto, creación y límites de
  archivado. Los 18 de guía vigentes prueban estado, datos pendientes y modales:
  «gracias» no se convierte en nombre ni abandona la pregunta.
- **10 grupos del recorrido completo**, con formularios HTTP, cola, ledger,
  validación y dos aprobaciones humanas reales sobre SQLite desechable. El
  proveedor y el audio usan dobles declarados: dos respuestas sintéticas,
  preguntas A/B, dos POST de directorio y ningún error de JS/consola/red externa.
- **Ocho grupos de directorio/navegación, ocho de confirmación de espera y diez
  del controlador guiado**. Además, seis grupos integran JS, HTTP, CSRF y SSR
  reales para estado → calendario → agenda → pregunta de expositor → agradecimiento
  → continuación → prefill. Ocho tablas operativas quedan idénticas; sólo cambian
  metadatos privados de la guía.
- `check`, migraciones pendientes y sintaxis JS limpios. Servicio reiniciado en
  `127.0.0.1:8000`; cinco grupos de aceptación GET, diez assets actualizados y
  formularios de escritorio/móvil sin errores ni cambios de negocio.

La limpieza fue ensayada sobre copia y después aplicada. El evento previo y las
fichas antiguas de Gicaingenieros/Jorge quedan retirados de las vistas, conservando
sus referencias históricas. Permanecen visibles UNAC y Robert; la nueva demo
creará las otras fichas mediante formularios. **No se borró ninguna cuenta de
acceso, plan, Job o consumo**: 42 tablas ajenas al retiro idénticas, integridad y
claves foráneas correctas. UUID reservado:
`bcf52dbd-206b-4d22-a294-8c487c770c56`; todavía sin crear en la base activa.

El gasto conservado sigue en cuatro llamadas OpenAI, **4.344 tokens y
USD 0,006068 brutos estimados**, sin inferencia nueva en esta actualización.
El servicio confirma conexión efímera OpenAI no disponible después del reinicio:
para otra generación real se debe guardar de nuevo en Gestión de IA → APIs y
agentes. No se ha repetido automáticamente la demo pagada.

Límites: audio físico y concurrencia PostgreSQL no acreditados. Después de guardar
una ficha del directorio con recarga completa, se debe abrir de nuevo el evento
para retomar su guía; no se conserva contexto personal en localStorage. El
acompañamiento abre y prepara formularios; no equivale a autonomía para aprobar.

Evidencia local privada: `Temporal/qa-gica-flow-v4/` (`backend-final-checks.txt`,
`wait-complete-results.json`, `guided-client-results.json`,
`guided-integrated-results.json`, `reset-rehearse.json`, `reset-apply.json`,
`runtime-results.json`) y `Temporal/qa-gica-directory-v4/`
(`compact-journey-results.json`, `directory-results.json`).

## Antecedente: piloto real, prompt visible y archivado seguro

El 16 de noviembre a las 12:00 America/Lima terminó el recorrido real del piloto
`ebd54e40-752c-4f8a-9376-f2735e2c6a41`, con GPT-5.4 mini y voz Sabina nativa,
sin dobles de proveedor o contenido:

- **Una llamada nueva:** 1.023 tokens de entrada + 297 de salida = **1.320 tokens**;
  coste bruto Standard estimado **USD 0,002104**.
- **Acumulado conservado:** cuatro llamadas OpenAI, **4.344 tokens**, coste bruto
  estimado **USD 0,006068** y **USD 0,993932** restantes del tope autorizado USD 1.
  Incluye el intento rechazado anterior. El cobro neto tras créditos no está comprobado.
- **Cuatro sesiones de 90 minutos en total, tres tareas y tres comunicaciones**;
  copia local confirmada antes de aplicar. Dos planes aprobados, calendario
  inicial y actualizado y reemplazo Robert → Jorge sin otra llamada a la IA.
- **Un evento activo y uno archivado**. Los Jobs, AIUsage y planes del anterior
  coinciden exactamente con el respaldo; SQLite íntegro. Archivar no borra
  historial ni reinicia el presupuesto.
- **Cero rondas reales de preguntas** en esta ejecución. La IA entregó propuesta
  directamente. Las pruebas de opciones A/B, espera de elección, corrección y
  envío agrupado son locales con dobles identificados; no se presentan como
  aclaraciones remotas observadas en este recorrido.

El contexto y las instrucciones incluyen requisitos cerrados para caso aplicado,
preguntas con minutos propios, ensayo técnico y moderación. La revisión semántica
independiente considera la agenda **adecuada para el piloto**: marco 25 min,
caso 35 min, preguntas 20 min y cierre 10 min. Las tareas incluyen acceso/audio/
pantalla y moderación/material. Se cerraron las brechas principales de la agenda
anterior; profundidad y dependencias siguen siendo mejorables.
La valoración cubre un esquema: el nivel intermedio no está confirmado en el
contexto y los títulos no acreditan corrección técnica del caso o materiales.
Antes de difundir se deben elegir destinatarios y completar localmente datos
de acceso confirmados; las instrucciones recibidas están dirigidas al equipo.

Se observaron escritura progresiva del prompt exacto, clic del cursor en
**Ejecutar solicitud**, cierre del panel al recibir el Job y escena SVG de espera
durante la inferencia real. La captura `live-waiting-scene.png` acredita esa
presentación, no razonamiento interno del modelo ni porcentaje de avance.
La punta del cursor queda centrada verticalmente en el control, sin offset
vertical añadido; se aparta hacia el margen en botones/selectores para no tapar texto.
Las pistas originales vigentes son Órbita pop (124 BPM), Brisa groove (119 BPM)
y Chispa latina (128 BPM), sintetizadas localmente. Sabina informó fin de lectura;
**la audibilidad física no está acreditada**.

Pruebas focales, sin llamadas remotas de QA:

- **52 casos compactos**, incluidos cinco de requisitos y conservación del piloto,
  correctos; `check` y revisión de migraciones limpios.
- **66 casos de archivado y regresión**, incluidos seis nuevos: bloqueo de página
  y formulario público antiguo, republicación, roster, horarios y herramientas;
  agendas archivadas dejan de reservar expositores/recursos, conservando sus registros.
- UI: nueve grupos de recorrido, nueve de cliente, ocho de puntero y nueve de
  espera; tres comprobaciones de audio offline. Se usan dobles sólo en esa QA.

El reinicio final cargó las guardas de archivado en el servicio local. La clave
efímera quedó vacía: el plan guardado puede revisarse sin ella; otra generación
requiere introducirla de nuevo en **Gestión de IA → APIs y agentes**. No se hicieron
más llamadas después de este cierre.

Evidencia: [completion.json](../Temporal/qa-gica-polish-v3/completion.json),
[agenda-review.json](../Temporal/qa-gica-polish-v3/agenda-review.json),
`Temporal/qa-gica-polish-v3/live-result.json`, `live-waiting-scene.png`,
`compact-journey-results.json`, `polish-results.json`, `pointer-results.json`,
`wait-results.json` y `waiting-audio-results.json`. Copia original nueva:
`Temporal/gica-agenda-review/2/bba85265-3c46-420c-b80e-589ed120946e.json`.
Estos archivos son privados locales. No se acreditan disponibilidad externa de
expositores o Zoom, ejecución de tareas, envío de comunicaciones, carga o carreras
PostgreSQL ni capacidad para eventos generales por cerrar este piloto.

## Antecedente: primera aceptación OpenAI y recuperación

El botón principal **Mis eventos → Iniciar demo con OpenAI** selecciona
`agenda-openai` y el perfil principal configurado `gpt-5.4-mini`, por autorización
expresa de Jorge. Solicita una propuesta normal, guarda su copia con `saveCopy`
y sólo tras confirmar el recibo de `archive` continúa a la aprobación del
piloto fijo. Se mantienen los presupuestos mensual y del agente y el tope global
acumulado de USD 1, incluyendo reservas y consumos anteriores. La reserva máxima
12.000/1.800 equivale a USD 0,017100 por llamada a tarifa Standard; no es gasto medido.
`full` conserva la pausa de aprobación humana; el modo privado sigue siendo
opcional desde **Conoce a Gica → Guardar agenda para comparar**. La opción
**Demo con IA gratuita** permanece separada, sin cambio automático de proveedor.

Responses usa `store=false`, razonamiento `none`, servicio Standard y JSON
Schema estricto con envoltorio `result`. Preview y envío comparten sistema,
entrada y esquema; el servidor retira el envoltorio y valida el contrato compacto.

### Resultado real conciliado

El 16 de noviembre a las 11:39 America/Lima se completó la continuación visible
con OpenAI, sin dobles de proveedor, voz ni contenido:

- **Tres llamadas GPT-5.4 mini**, incluida una respuesta rechazada. Uso informado:
  **2.572 tokens de entrada + 452 de salida = 3.024 tokens**.
- Coste bruto Standard estimado agregado **USD 0,003964**, bajo el tope acumulado
  autorizado **USD 1**. El cobro neto después de créditos no se ha comprobado.
  Los intentos anteriores y su contabilidad se conservan; cero reintentos automáticos.
- Agenda validada: **cuatro sesiones, 90 minutos, cuatro tareas y tres borradores
  de comunicación**. El archivo local se confirmó antes de aplicar la propuesta.
- **Dos planes aprobados**: inicial con Robert y reemplazo por Jorge Gayoso Ugas.
  Temas, horarios y recursos se conservaron; el reemplazo no necesitó otra llamada
  a la IA. Calendario inicial y actualizado comprobados.
- Recorrido `retry-live-result.json` correcto, sin errores de aplicación,
  solicitudes denegadas ni errores de consola. Sabina nativa informó fin de
  lectura; esto no acredita audibilidad física. Integridad SQLite correcta.

Evidencia conciliada: `Temporal/qa-gica-openai/completion.json` y
`Temporal/qa-gica-openai/retry-live-result.json`. Copia de la respuesta validada:
`Temporal/gica-agenda-review/2/6a816058-9059-416b-b1e5-87607e491b35.json`.
Son archivos privados locales, no recursos publicados. La revisión semántica
independiente concluye **`needs_adjustments`**: progresión coherente durante 90
minutos, pero sin tiempo explícito para caso práctico ni preguntas que pedía la
ficha. El prompt real sólo exportó `focus=planning`; omitió nivel intermedio y
formato de caso. Es una limitación del contexto preparado por SparkX; no se
acredita incumplimiento literal de OpenAI de instrucciones que no recibió. La
agenda original se conserva para comparar, sin otra inferencia o ajuste silencioso.
Revisión independiente: [agenda-review.json](../Temporal/qa-gica-openai/agenda-review.json).
La aceptación operativa no acredita cumplimiento total de la ficha, disponibilidad
real de expositores/Zoom, ejecución de tareas ni envío de comunicaciones.

### Pruebas locales y recuperación

Validación focal de este corte:

- Backend: **76 casos, 75 correctos y uno omitido** por PostgreSQL. Once casos
  específicos de OpenAI usan HTTP simulado: payload estricto, prompt exacto,
  herencia de proveedor, archivo, uso informado, rechazo de salida incompleta,
  revocación y tope global acumulado en reserva y despacho. `check` y revisión
  de migraciones correctos; no se necesitan nuevas migraciones para OpenAI.
- Seis grupos del selector de modos: OpenAI sólo por modo explícito, copia
  antes de aplicar, ruta gratuita separada, pausa humana conservada y bloqueo
  si falta el recibo de copia. Las narraciones solicitan la voz femenina.
- Seis grupos de voz: Sabina local, elección femenina guardada, conservación
  de preferencias previas, catálogo tardío y fallo sin alternativa masculina o
  remota. Son dobles de síntesis, sin prueba de audibilidad física.
- Once grupos del cliente compacto: herencia OpenAI en aclaraciones, rechazo
  de proveedor distinto, prompt exacto, archivo anterior a aprobación, privacidad,
  preguntas agrupadas, cuota, cancelación, música/voz y móvil; con dobles identificados.
- Once grupos de espera: actividad indeterminada, fases y modelo admitido, tres pistas
  originales, pausa/cambio, consentimiento de voz, cancelación y ajuste visual.
  No muestra porcentajes inventados y sigue usable sin WebAudio.
- Formulario: corregidos estiramiento de bloques y alturas de controles;
  revisión visual en tres tamaños de ventana. La integración del cliente
  OpenAI se comprueba aparte de estas pruebas focales.
- Cinco grupos de sólo lectura sobre el runtime: acceso y recursos servidos,
  disposición de escritorio/móvil, Sabina local disponible y **46 tablas de
  negocio intactas**. La sesión temporal de comprobación se retiró.

Evidencia: `Temporal/qa-gica-compact/live-mode-results.json` y
`waiting-v2-results.json`, `Temporal/qa-gica-openai/voice-results.json` y las
pruebas mantenidas `apps/assistant/tests/test_compact_openai.py`. Estos resultados
**no acreditan por sí mismos una inferencia OpenAI real**. El usuario guardó la clave en el
panel privado después del último reinicio; el indicador del runtime confirmó
disponibilidad sin recuperar ni exponer su valor.

La ejecución real posterior recibió una pregunta válida de enfoque; se eligió
planificación. La segunda llamada terminó fallida, sin publicar candidato o
agenda. No se guardó su texto remoto: la causa concreta no está acreditada.
Ambas llamadas informaron **1.974 tokens** y coste Standard agregado estimado
**USD 0,001939**; sus recibos están liquidados. No se borraron esos Jobs ni consumos.

Corrección posterior: la ronda con respuestas usa esquema nativo e instrucciones
de propuesta únicamente. Un fallo de contrato conserva consumo e informa sólo
`compact_invalid`. El propietario puede recuperar esa aclaración una vez mediante
`retry`, incluso desde un nuevo recorrido vigente: mismas respuestas, proveedor,
ficha y plan, antigüedad máxima dos horas y nueva reserva bajo los topes existentes.
No hay reintento automático ni cadena de recuperaciones. **Continuar agenda con
OpenAI** usa `agenda-openai-continue`, retoma la ficha y conserva la copia previa
a aprobar. Las **47 pruebas focales
compactas** (16 OpenAI y 31 del contrato/flujo) pasaron con dobles; `check` y revisión
de migraciones correctos. Después del refuerzo de permisos del tag, pasaron 17
casos OpenAI y de saneamiento del worker; estas ejecuciones no se suman entre sí
ni sustituyen la evidencia real anterior. La recuperación remota ya terminó
correctamente; los 1.974 tokens y USD 0,001939 anteriores forman parte del total
conciliado de las tres llamadas, no son consumo adicional al mismo.

### Antecedente: ejecución gratuita desde Gica sin cuota

Se ejecutó el botón en Edge visible y aislado porque el control del navegador
personal respondió `The browser access host is unavailable`; se utilizó la
alternativa de pruebas autorizada. Sin dobles de voz, datos ni proveedor:
la ficha y sus siete respuestas quedaron guardadas, se mostró el prompt exacto
y el worker despachó **un trabajo GLM-5.3 Flash Free**. El proveedor devolvió
**429**. No hubo reintento, cambio de modelo ni llamada OpenAI.

En esa prueba, la base confirmó un evento, un trabajo fallido, cero candidatos,
cero planes y ningún archivo de agenda. El consumo remoto no trajo contadores: quedó
`uncertain`, tokens nulos y reserva monetaria cero; no se presenta como cero
tokens consumidos. Integridad y claves foráneas SQLite correctas. La comparación
de contenido era **no evaluable** hasta recibir una agenda real. Este antecedente
se conserva; no describe el estado después de la aceptación OpenAI anterior.

Se enumeraron cinco voces españolas locales y se observó la narración nativa;
el fin informado por el navegador no acredita audibilidad física. La UI no
mostró errores de aplicación ni excepciones JavaScript. El recolector tuvo un
error posterior a la captura final al consultar ORM desde el contexto de
Playwright; se corrigió con un hilo separado y se conciliaron los datos con
consultas de sólo lectura, sin repetir la solicitud.

Evidencia: `Temporal/qa-gica-visible-request/real-live-result.json`,
`real-prompt-prepared.png`, `real-prompt-waiting.png` y `real-final.png`.
En esa prueba se sirvieron los recursos `20261116-live1` en127.0.0.1:8000.

## Solicitud visible y agenda privada — aceptación anterior

El modo privado, ahora **Guardar agenda para comparar**, completa la ficha y muestra el prompt
íntegro antes de cada envío, colocado una vez en un campo de sólo lectura.
El constructor de preview comparte sistema/entrada con el adaptador real.
La pantalla sigue preparado → enviado → espera; el modelo se identifica después
de la admisión. El resultado privado no crea candidatos ni aprobaciones y no
entrega agenda/comunicaciones al navegador, tampoco después de recargar.
Se guarda JSON validado en `Temporal/gica-agenda-review/<owner>/<job>.json`
para comparar posteriormente. El recorrido completo permanece separado.

- Suite final congelada: **1.490 casos, 1.476 correctos y 14 omitidos** por
  PostgreSQL; 107,994 segundos y salida nativa 0. `check` y revisión de migraciones
  correctos. Migración aditiva `assistant.0010` aplicada con respaldo consistente.
- Cinco grupos E2E privados, ocho del cliente y tres de guardas correctos en
  Edge aislado con respuestas explícitamente simuladas. Cero candidatos/planes
  aprobados, prompt/archivo verificados, dos rondas agrupadas, contenido privado
  ausente del SSR y ninguna solicitud externa del navegador de QA.
- Cuatro grupos de aceptación de sólo lectura sobre el servicio real: escritorio,
  móvil390, recursos actuales y **46 tablas de negocio sin cambios**. Se corrigió
  el ajuste de los tres botones superiores para evitar desbordamiento en móvil.
- La instancia anterior se apagó mediante su recibo autenticado sin inferencias
  activas. La nueva instancia tiene acceso de red para el adaptador autorizado,
  sigue ligada a127.0.0.1:8000 y devuelve salud200. El catálogo público de OpenCode
  verificó GLM gratuito sin invocar el modelo. Esto no acredita cuota disponible.

Evidencia actual: `Temporal/qa-gica-visible-request/` y
`Temporal/qa-gica-compact/{private-journey-results.json,compact-client-results.json,review-guard-results.json}`.
Las pruebas usan dobles y no son la agenda real esperada por Jorge. No se envió
un prompt ni se consumieron créditos OpenAI desde las herramientas de Codex.
En este corte anterior aún no se había despachado inferencia. Audio físico y
concurrencia PostgreSQL continúan pendientes.

## Generación compacta, guion y cursor — aceptación anterior

El evento anterior fue eliminado por instrucción de Jorge, con respaldo SQLite,
ensayo en copia y transacción. Se retiraron un evento, seis planes y seis
candidatos; cuarenta tablas ajenas, personas, instituciones y doce UIActions
históricas quedaron intactas. La base activa queda sin eventos, trabajos ni
consumo nuevo, lista para **Mis eventos → Iniciar recorrido**.

La demo completa la ficha con escritura visible de campos cortos, selecciones
manuales y fecha del jueves 19/11/2026. Solicita agenda, preparación y mensajes
a un modelo del grupo gratuito. El contrato JSON v1 limita cada petición a
12.000 tokens de entrada y 1.800 de salida; son máximos de reserva, no tokens
consumidos. Admite una petición inicial y un lote de respuestas a hasta cuatro
preguntas cerradas. SparkX calcula horarios y asignaciones y valida la salida.
El usuario revisa y pulsa **Aprobar y continuar** antes de aplicar cada propuesta.

El caso de inconveniente mantiene la fecha: Robert no puede asistir y se
selecciona a Jorge. La nueva propuesta conserva contenido y horas sin otra
consulta a la IA. Los borradores de comunicación se muestran y no se envían.
La música se sintetiza localmente. Sólo un clic con consentimiento habilita
temporalmente los comandos de voz «detener» y «continuar» de la música; no abre
la conversación general. Al terminar o detenerse, cesa la escucha.

La exportación remota contiene exclusivamente el tema público predefinido,
audiencia genérica, duración, opciones de catálogo y referencias p1/r1. Identidad,
institución, fecha, contactos, UUID e historial permanecen locales. Sólo se
autorizaron tres modelos del catálogo con grupo gratuito para planes; no se
utilizan los perfiles OpenAI del usuario ni una alternativa pagada. Un 429
pausa la pasarela. Cancelar deja un recibo persistente incluso si el trabajo
todavía no se había encolado; no revierte inferencias ya despachadas.

Validación actual:

- Suite general: **1.482 casos, 1.468 correctos y 14 omitidos** por PostgreSQL,
  110,820 segundos. `check`, `pip check` y revisión de migraciones sin incidencias.
  Migraciones aditivas `assistant.0008` y `0009` aplicadas.
- Nueve grupos de cursor/burbuja: anclaje dentro del input, punto rojo sin clic,
  calendario despejado, arrastre/restauración, teclado, escritorio/móvil,
  movimiento reducido y cancelación.
- Siete grupos del cliente compacto: preguntas por turnos/lote, música/voz
  explícita, respuesta ajena, 429, cancelación tardía, móvil y consola limpia.
- Nueve grupos del recorrido completo con worker y proveedor simulado:
  creación, dos aclaraciones, respuestas agrupadas, dos aprobaciones humanas,
  calendario y reemplazo de expositor. Exactamente dos trabajos gratuitos;
  contenido y horas del plan anterior inmutables, comunicaciones visibles y
  escritura progresiva con cancelación. Los 1.800 tokens del fixture son
  sintéticos y no constituyen consumo remoto. Tres grupos adicionales permiten
  abrir instrucciones/recursos al revisar sin desbloquear formularios o estados.
- Servicio activo: salud HTTP200, once recursos servidos idénticos a las fuentes,
  UI del propietario en escritorio/móvil y **46 tablas de negocio sin cambios**
  durante la comprobación de sólo lectura. Sesión temporal retirada.

Evidencia: `Temporal/qa-gica-compact/`. Las pruebas de IA utilizan respuestas
simuladas identificadas; **no acreditan una inferencia real ni cuota disponible**.
No se hicieron llamadas remotas ni se consumieron créditos de OpenAI en esta
intervención. Audio físico y carreras/carga PostgreSQL siguen pendientes.
Los paquetes, informes y diapositivas publicados anteriormente describen el
guion local previo y no acreditan esta ampliación.

## Piloto completo de Gicaingenieros — corte anterior sustituido

El recorrido autorizado crea y guarda un único piloto con datos de identidad
declarados por Jorge. Registra Gicaingenieros, selecciona a Robert Castillo y
completa quince campos, incluidos siete controles editables de preparación.
Guarda la ficha del jueves 19/11/2026 a las 19:30, prepara una agenda local y
muestra su aprobación. A continuación selecciona a Jorge Gayoso Ugas y el jueves
26/11/2026, guarda el cambio, prepara otra propuesta y la aprueba. El editor
**Ajustar horarios** propone y aprueba la tercera versión, conservando las anteriores.

Estado activo comprobado: **un evento, tres versiones aprobadas, cinco sesiones
y once tareas pendientes**, 100 personas previstas, America/Lima, 26/11/2026 de
19:30 a 21:00. Duraciones finales: 5/25/30/20/10 minutos; el caso aplicado inicia
a las 20:00. Robert conserva su afiliación UNAC y su asignación anterior queda
cancelada; Jorge queda planificado para este evento. Ninguna tarea se marca
realizada ni se confirma disponibilidad, sala Zoom, difusión o asistencia externa.

El cursor muestra clics con ondas, apertura de opciones, elección de fecha y
capacidad, escritura del título y desplazamiento suave. La burbuja evita el
control activo, conserva arrastre y se minimiza al completar. El panel completo
sigue siendo manual. Detener cancela pasos futuros; los cambios ya guardados
permanecen. Repetir reutiliza evento e institución y puede añadir versiones
aprobadas: no es un replay de sólo lectura.

### Resultados de esta entrega

- Suite general: **1.459 casos; 1.445 correctos y 14 omitidos** por requerir
  PostgreSQL. `manage.py check` y `pip check` correctos; ocho pruebas del empaquetador correctas.
- Navegador aislado Edge/Playwright: siete grupos del recorrido completo en
  escritorio y móvil. Repetición: un piloto, una Gicaingenieros y seis versiones,
  sin duplicar eventos. Ocho grupos de guardas de permisos/cancelación,
  siete de proyección conversacional y cuatro de burbuja final correctos.
- Servicio activo: cinco bloques UI completos, trece capturas y aceptación
  independiente de sólo lectura de los datos finales. Cero errores inesperados
  JS/consola/CSP, cero micrófono y cero HTTP externo durante el recorrido.
- Cero Jobs y AIUsage; las doce UIActions históricas se conservan y no se
  generan nuevas. La agenda procede de una plantilla local, sin inferencia LLM.
- Antes de retirar el piloto sintético anterior se respaldó la base, se ensayó
  en copia y se comprobó la transacción: sólo evento/candidato eliminados;
  42 tablas ajenas conservadas y claves foráneas correctas.

La comprobación UI terminó los cinco bloques y guardó las tres aprobaciones;
su comprobador final intentó ORM dentro del contexto asíncrono de Playwright.
Ese fallo del harness se conserva en la evidencia y se resolvió verificando
los datos en otro proceso de sólo lectura, sin repetir las escrituras. La
sesión temporal se eliminó. Las nuevas lecturas de expositor y dos historiales
añaden tres consultas acotadas; la regresión mantiene el control contra N+1 y
un presupuesto máximo de 17 consultas independiente del número de tareas.

Evidencia actual: `Temporal/qa-gica-jury/` — `full-suite-final.log`,
`journey-results.json`, `journey-guards-results.json`,
`guided-projection-results.json`, `completion-bubble-results.json`,
`live-journey-results.json`, `live-acceptance.json` y `figures/01…13`.
El acceso al navegador personal no estuvo disponible; las capturas usan el
servicio real con una sesión de prueba temporal y síntesis nativa simulada.
**Audio físico y concurrencia PostgreSQL siguen pendientes**. La auditoría
crítica y sus límites están en [audit.md](validacion/audit.md); instalación y paquete
sin datos privados en [release.md](guias/release.md). Servicio local integrado
reiniciado en el puerto 8000 (sesión42254/PID8764), con salud HTTP200.

## Cursor visible, ficha por bloques y burbuja arrastrable — corte anterior sustituido

La demo se inicia en **Mis eventos → Ver demo narrada**. Si parte del perfil,
primero mueve su cursor SVG y activa el enlace de Mis eventos; después pulsa el
enlace visible de Nuevo evento. Completa quince campos agrupados en identidad,
programación, audiencia, descripción y preparación, con foco/borde del bloque
actual, título letra por letra y descripción pegada completa. La descripción
de presentación es un resumen editorial local; la descripción original y la
procedencia del piloto se conservan. Diecinueve locuciones presentan el seminario
sin mencionar el afiche. El panel completo permanece cerrado, incluso ante un
error de voz, y sólo se abre manualmente.

La ficha usa tres bloques superiores y dos inferiores en escritorio, dos
columnas intermedias y una en móvil. Capacidad 20/50/100 y Perú/Lima son atajos
manuales, bloqueados durante demo/entrevista. Se mantienen nombres POST, CSRF,
errores, revisión de edición y validación del servidor. El agarre de puntos y el
avatar minimizado permiten arrastrar la burbuja con ratón/touch; flechas, Inicio
y doble clic ofrecen movimiento y retorno al modo automático. La posición manual
se conserva en RAM y se limita al viewport.

**50 pruebas backend focales correctas** de vistas, edición, fechas y snapshot;
sintaxis de seis JS y `manage.py check` correctos. Edge instalado/Playwright,
sin Browser plugin disponible: **19 comprobaciones de arrastre**, **20 de cursor**,
**10 de formulario manual**, **6 escenarios integrados** y **1 revisión visual
oscura** correctos. Los escenarios integrados verifican título parcial y Stop con
restauración exacta, callbacks tardíos, clics reales de enlaces con cursor visible,
cinco bloques, descripción insertada completa, regreso a lista, inicio desde el
perfil y ausencia de voz sin abrir el panel. Sin errores inesperados de JS,
consola ni CSP; capturas claras/oscuras de 1440×1000 y móvil de 390×844
inspeccionadas. Evidencia en `Temporal/qa-gica-blocks/`, separada por componente;
las bases y servidores desechables de navegador quedaron retirados.

La QA usa síntesis nativa simulada: **no acredita audio físico**. Cero micrófono,
modelos o HTTP externo. En el recorrido sólo se envía `resume` y un GET privado
del piloto, además de la navegación GET; no hay creación ni confirmación. La
aceptación activa de sólo lectura mantiene un piloto/cero borradores, cinco
sesiones y once tareas pendientes, sin aprobación automática. Las **44 tablas de
datos siguen idénticas**; Jobs/AIUsage permanecen en cero.

Servicio normal reiniciado, sesión44269/PID31344 en8000, salud200 a03:39:24
America/Lima. Ocho activos servidos con caché `20261116-blocks1` idénticos a
fuente; `runtime-http.json`, `runtime-preserved.json` y `live-acceptance.json`.

## Único piloto GICA y narrador de su ficha — corte anterior

Por instrucción expresa de Jorge se guardó un respaldo SQLite íntegro, se ensayó
el cambio en una copia y se aplicó una transacción acotada a `adminjorge`.
Se eliminaron sus cinco eventos y dos registros de borrador, resolviendo las
referencias protegidas sin modificar contenido inmutable. Quedó un piloto
`9c1cb0ba-4025-49dc-b9e8-d0f6cf3e84aa` de Tus jueves con GICA: **19/11/2026,
19:30–21:00, America/Lima**,100personas previstas y datos del afiche aportado.
Se distingue la fecha publicada del12de la nueva programación local del19.
La propuesta manual tiene cinco sesiones y once tareas pendientes; no se copió
una tarea completada del evento anterior ni se aprobó automáticamente el plan.
Respaldo y resultados en `Temporal/qa-gica-pilot/before-reset.sqlite3` y
`reset-result.json`:38tablas ajenas idénticas y claves foráneas correctas.

Aceptación activa protegida contra escrituras: un evento/cero borradores,
siete respuestas, sesiones contiguas hasta21:00 y una ocurrencia en el
calendario del19. Índice, detalle, calendario y snapshot renderizan200.
`PRAGMA query_only` y un wrapper SQL impiden escrituras durante la comprobación;
las44tablas permanecieron iguales. Jobs y AIUsage continúan en cero.
Evidencia: `live-acceptance.json` y `verify_active.py`.

La voz ahora comienza dentro del clic, antes de esperar la consulta de borrador.
Se muestra el estado inmediatamente y se distinguen voz ausente, voz guardada
no disponible, navegador no compatible, error y timeout. El acceso al navegador
real no estuvo disponible: host de Browser inaccesible y pipe de Windows ausente.
No se atribuye la causa física del fallo de Jorge a partir de estas pruebas.

El narrador lee el piloto mediante un endpoint privado y sólo de lectura.
Proyecta sus quince campos y siete respuestas, anuncia que ya existe y abre
Eventos sin crear otra copia. Se retiró toda creación/confirmación de la demo.
**80 pruebas backend correctas**, incluidas ocho nuevas del snapshot; sintaxis
de ambos JS y `manage.py check` correctos. **Siete contratos DOM de proyección**
verifican validación, protección y restauración exacta de controles/nodos.
**Cinco pruebas de arranque** usan el módulo de síntesis real con sólo la API
nativa simulada: habla antes del primer HTTP, Stop y callbacks tardíos, borrador
preservado y mensajes específicos de voz. **Cuatro escenarios finales de replay**
correctos: Stop/restauración, recorrido completo, voz ausente y piloto ausente.
Diecinueve emisiones simuladas, un piloto inalterado, cero borradores nuevos,
POST únicamente de reanudación y GET del snapshot; cero micrófono, modelos,
red externa o errores inesperados JS/consola/CSP. Capturas de escritorio y móvil
inspeccionadas; `pilot-replay-results.json`, `preview-results.json` y
`narrator-start-results.json` conservan los resultados separados.

**Audio físico pendiente:** sin mocks, Edge headless enumeró cinco voces locales,
pero la síntesis nativa devolvió `synthesis-failed`. Ese resultado no demuestra
el comportamiento audible del navegador visible. Se conserva en
`native-speech-results.json`; no se oculta ni se presenta la simulación como audio
real. La concurrencia PostgreSQL y la contención de memoria opcional SQLite
siguen siendo pendientes separados.

Runtime normal34325/PID31876 en8000, salud200 a03:16:40 America/Lima; ambos JS
con caché `20261116-pilot2` idénticos a fuente y44tablas conservadas tras la
verificación final de servicio. `runtime-http.json` y `runtime-preserved.json`.

## Demostración narrada de creación — corte anterior, sustituido por piloto existente

Desde Conoce a Gica o el panel, **Ver demo narrada** explica el recorrido con un
guion local conciso y la voz elegida. El aviso anuncia que el clic autoriza crear
un evento ficticio. Completa los15campos mediante el servicio humano existente,
busca Callao y selecciona sólo la UNAC propia inequívoca, revisa la ficha marcada
sintética y confirma una vez. Sólo después de `created` anuncia éxito y abre
Eventos. No crea registros del directorio, reuniones ni planes. No usa modelos
ni micrófono. El panel conserva el guion visible y Detener demo.

**Siete escenarios UI correctos**, Edge/Playwright instalado, Browser plugin no
disponible, SQLite desechable,1440×1000 y390×844. Todos los inicios desde el acceso
de Conoce a Gica, sin abrir previamente voz: doble inicio y stop de introducción,
callbacks tardíos, borrador humano preservado, CSRF403/otro dueño404/revisión409,
stop con avance,15campos y siete respuestas de entrevista, selección de UNAC,
resumen todavía sin Event, una confirmación, lista actualizada y repetición
idéntica de entrega sin duplicado. Capturas de resumen inspeccionadas en ambos
tamaños, sin recorte horizontal ni errores inesperados JS/consola/CSP.

**19 emisiones de voz simuladas**, cero inicios de micrófono, modelos, HTTP
externo, registros opcionales de memoria, trabajos, contabilidad, planes o
UIActions. Se creó un evento sólo en la fixture eliminada después con su
servidor. No acredita audio físico ni que la voz elegida esté instalada en otro
navegador. Se conservan el pendiente SQLite de memoria y la concurrencia de
PostgreSQL como asuntos separados. Sintaxis de los cuatro JS,69 verificaciones
de contrato de opciones y `manage.py check` correctos. Evidencia actual en
`Temporal/qa-gica-narrated-demo/ui-results.json` y sus dos capturas de resumen.

Regresión focal adicional: **dos comprobaciones correctas**. Un borrador previo
y la ausencia de voz local muestran el aviso visible, abriendo el panel sin
activar micrófono. Sólo se consulta el estado; no se modifica el borrador ni se
crea un evento. Entorno aislado retirado; `terminal-feedback.json` conserva la
evidencia separada, sin repetir el recorrido completo.

Runtime normal reiniciado: salud200 a02:57:03 America/Lima, cinco activos con
caché `20261116-demo1` idénticos a fuente y44tablas de datos idénticas, incluidos
los cinco eventos. Ningún evento de demo añadido a la base activa por la QA.
Conservación y salud en `runtime-preserved.json` y `runtime-http.json` de la misma
carpeta.

## Directorio, confirmaciones y voz — corte anterior

Se separó la respuesta de confirmación del nombre de institución/persona. Sí/no
se interpreta por conceptos con cortesías; contradicción, incertidumbre o eco
mantienen la pregunta pendiente. Para cambiar el nombre se solicita explícitamente
otro registro. Un fragmento de la pregunta ya no se guarda como nombre; un
borrador con ese atasco vuelve a pedirlo al reanudar, sin borrar registros reales.

La búsqueda parcial combina términos normalizados sobre nombre/alias, limita a
registros propios activos y presenta hasta tres sugerencias sin enlazarlas.
Callao propone Universidad Nacional del Callao - UNAC para elegir. La burbuja y el
panel comparten los botones; también ofrecen otra institución/persona y omitir.
Las preguntas son más breves y conservan revisión, propietario e idempotencia.

**144 pruebas integradas:142 correctas y2 omitidas de PostgreSQL**, incluyendo
29 nuevas de directorio conversacional y la actualización de una expectativa
antigua que permitía reemplazar un nombre durante confirmación. Se mantienen
las pruebas de lenguaje, creación final, permisos y directorio. Sintaxis de los
tres JS, `manage.py check` y **69 comprobaciones sintéticas de opciones** correctas.

**Seis bloques UI correctos**, Edge/Playwright instalado porque Browser plugin
no está disponible, SQLite desechable,1440×1000 y390×844. Verificados Callao,
aislamiento de nombres ajenos/archivados, selección y doble clic único, alias,
sí/no compuesto y contradictorio, fragmento de pregunta, otro nombre y registro
explícito. La escucha anticipada queda suspendida durante preguntas del directorio.
El umbral de transcripción estable sube sólo allí a2500ms; provisional y vacío
no envían. En la prueba, el provisional permaneció2600ms sin POST y al finalizar
el mismo texto se envió una sola vez,a2623,4ms del último cambio. TTS ocupado y
eco reciente no enviaron; máximo un reconocedor y escucha continua reanudada.

Sin errores JS/consola/CSP/HTTP, modelos, HTTP externo, eventos, trabajos,
contabilidad, planes o acciones. Se creó sólo una institución ficticia tras
aceptación en la base efímera, después eliminada con el servidor de QA.
Memoria opcional desactivada sólo en la fixture; su pendiente SQLite se conserva.
Capturas de escritorio y móvil inspeccionadas; evidencia en
`Temporal/qa-gica-directory/ui-results.json`. Voz sintética: audio físico y
cancelación acústica real no probados.

Servicio normal reiniciado, salud200 a02:41:31 America/Lima; cuatro activos con
caché `20261116-directory1` idénticos a fuente. Las44tablas de datos idénticas,
incluidos cinco eventos y directorio real. Evidencia de conservación y salud en
`runtime-preserved.json` y `runtime-http.json` de la misma carpeta.

## Palabras clave independientes — corte anterior

Por corrección expresa de Jorge se sustituyó la gramática, no se amplió otra
lista de frases. `creation-keywords-es-2026-11-16.3` contiene sólo palabras por
concepto: variantes de acción AND tipo de evento. El reconocedor tokeniza y cruza
conjuntos sin exigir orden, distancia ni relleno específicos dentro de 300
caracteres. Se eliminaron frames, prefijos, sufijos y fullmatch de oración.
Guardas separadas conservan negación, citas/relatos, condiciones y conflictos.
Se mantienen campos activos literales, permisos y confirmación final.

**59 pruebas lenguaje/backend correctas**, con una matriz nueva de336 subcasos
de variantes×tipos×rellenos/inversión, Unicode, palabras completas y falta de
uno de los conceptos. Las expectativas antiguas que rechazaban sólo por relleno,
cortesías repetidas, sin presupuesto o posición fueron sustituidas por el nuevo
contrato. **Cuatro bloques UI correctos** en Edge/Playwright instalado, Browser
plugin no disponible, SQLite desechable y voz sintética. Una oración nueva con
palabras entre crear/seminario inició un único borrador/formulario mediante un
solo POST a1507,7ms del último cambio. Otra con evento antes de crear funcionó
por texto con micrófono apagado; título literal y negativas/palabras parecidas
también verificados.

Revisión estática y en navegador:287 entradas léxicas son palabras individuales,
sin registrar las oraciones probadas; AST del reconocedor sin gramática de
fullmatch. Cero errores JS/consola/CSP/HTTP, modelos, HTTP externo, eventos,
trabajos, contabilidad, planes o acciones; máximo un reconocedor. Memoria
opcional desactivada sólo en la fixture, sin afirmar resuelto su bloqueo SQLite.
Servidor/base efímeros retirados. Evidencia en
`Temporal/qa-gica-keywords/ui-results.json`. Runtime normal reiniciado y sano200,
44 tablas idénticas y cinco eventos conservados; audio físico no probado.

## Inicio con «hay que crear un evento» — corte anterior, sustituido por palabras clave

El fallo se reprodujo antes de corregir: `is_creation_request` devolvía `False`
para «hay que crear un evento». Faltaba ese marco en la gramática; no se acredita
un fallo del reconocimiento físico de voz. El banco `creation-es-2026-11-16.2`
combina hay que/tenemos que/debemos/necesitamos y otros auxiliares con una
progresión opcional, cuatro familias de acciones y los tipos de evento existentes.
`q → que` se aplica sólo a esa intención, conservando campos literales.
Se retiró además el filtro de cliente que omitía esta comprobación si quedaba una
aclaración local pendiente. El servidor conserva la detección y las validaciones.

**55 pruebas de lenguaje/backend correctas**, incluidas negaciones, citas,
relatos, acciones múltiples, campos literales y confirmación final explícita;
32 comprobaciones sintéticas del contrato de opciones y `node --check` correctos.
**Cuatro bloques UI correctos** en Edge/Playwright instalado, Browser plugin no
disponible, SQLite desechable, voz sintética y memoria opcional desactivada.
Los cuatro segmentos «hay / que / crear / un evento» enviaron una sola solicitud
a los 1516,4 ms del último cambio y abrieron nombre/formulario. El siguiente
título «hay q crear un evento» se conservó literal en la misma ficha. Cancelación,
negación/relato/multiorden y creación por texto tras aclaración real de tema
comprobados; este último caso mantuvo el micrófono apagado. Máximo un reconocedor,
cero errores JS/consola/CSP/HTTP, modelos, HTTP externo, eventos, trabajos, planes,
contabilidad o acciones. Servidor/base de prueba retirados. Evidencia en
`Temporal/qa-gica-obligation/ui-results.json`.

Runtime normal reiniciado y sano200; `gica-creation.js` servido idéntico a fuente
con caché `20261116-creation-modal1`, 44 tablas idénticas y cinco eventos
conservados. Prueba física de la frase pendiente de Jorge; no se usaron modelos.

## Respuestas rápidas y burbuja de Gica — corte anterior

La entrevista presenta hasta cuatro opciones revisadas en zona horaria,
capacidad, datos ficticios, modalidad, duración y lugar/acceso. En modalidad
virtual/híbrida ofrece Zoom, Google Meet, Otro y Pendiente. Las plataformas se
guardan con enlace pendiente; no se crean salas externas. Otro abre un campo
manual de 300 caracteres y sólo envía al pulsar Responder. No hay opciones que
confirmen automáticamente el evento en la revisión final.

La burbuja presenta la última pregunta y respuesta, distingue texto/habla/escucha,
permite minimizar, volver al panel y apagar el micrófono. Escoge entre ocho
posiciones según colisiones con campos/foco, navegación y menús. Usa las dos
paletas y respeta movimiento reducido, sin estilos inline, dependencias nuevas,
red ni almacenamiento propios. Con el panel completo abierto, los mismos nodos
de opciones pasan a la entrevista; al contraerlo vuelven a la burbuja. Se corrigió
el cierre exterior que cerraba inmediatamente Ver conversación y se notifican las
transiciones de cabecera/clic fuera/Escape para actualizar esa presentación.

**Diez bloques UI correctos** con Edge/Playwright instalado, Browser plugin no
disponible, 1440×1000 y 390×844 claro/oscuro. Tres cuentas/borradores sintéticos
sembrados mediante servicios locales en SQLite desechable, sin crear eventos.
Verificados campo real/avance de pregunta, doble clic único, revisión/paso/usuario
obsoletos, Zoom/Meet/Otro/Pendiente, mover opciones sin duplicarlas, foco/menús,
interrupción de TTS propio y callback tardío, máximo un reconocedor, Stop y
privacidad al ocultar/cambiar propietario. Audio sintético; no prueba física.
Cero errores JS/consola/CSP/HTTP en la aceptación final; cero modelos, HTTP
externo, planes, trabajos y acciones. Base efímera y servidor retirados.
Una regresión adicional con el activo de presencia final confirmó cerrar/abrir
cabecera, Escape y clic fuera: las mismas opciones cambian de ubicación
inmediatamente, sin iniciar micrófono ni hacer POST adicionales. Resultado en
`header-layout-results.json`.
`node --check` de los cuatro JS afectados, 32 verificaciones sintéticas del
contrato de opciones y `manage.py check` correctos. Evidencia/capturas en
`Temporal/qa-gica-companion/` y contrato en `Temporal/qa-gica-choice-contract/`.

**Límite separado:** una ejecución anterior con registro opcional de memoria
activo reprodujo HTTP500 por `database is locked` en
`save_interaction → InteractionRecord.objects.create`. No impidió avanzar la
creación, reanudar voz o detenerla, pero no se acredita el guardado de ese turno.
Diagnóstico sin contenido en `memory-lock-evidence.json`. La aceptación UI final
desactivó esa preferencia sólo para las cuentas sintéticas, sin filtrar errores
ni cambiar la configuración activa. La contención del registro en SQLite queda
pendiente; no se ha probado concurrencia PostgreSQL ni se alteraron transacciones
como parte de este cambio visual.

Servidor normal reiniciado: salud HTTP200, cinco activos estáticos idénticos a
fuente con caché `20261116-companion1` y las 44 tablas de datos idénticas, incluidos
los cinco eventos. Runtime en `estado.json` y `runtime-http.json` de esta carpeta.

## Herramientas comunes y menú de perfil — corte anterior

La barra principal separa cuatro accesos habituales: Eventos, Calendario,
Directorio y Conoce a Gica, con las condiciones por rol anteriores. El perfil
inferior muestra usuario y rol y despliega Usuarios/Gestión de IA, Cambiar
contraseña y Cerrar sesión. Apagar SparkX está allí cuando el servidor local lo
permite. Usuarios sigue limitado a administradores; Gestión de IA personal se
conserva para administradores y organizadores. El Revisor no recibe esas opciones.
No se amplían permisos ni el acceso de los agentes a módulos administrativos.

Es un `details` nativo que abre hacia arriba en escritorio y hacia abajo en
móvil, con dos secciones internas, ambas paletas, movimiento reducido y cierre
por Escape, foco/clic fuera, enlace o navegación SPA. El teclado conserva foco
en el disparador al cerrar con Escape. Se retiró la antigua cuadrícula móvil de
apagado que habría comprimido el perfil a media anchura.

**Siete bloques UI correctos** en Edge/Playwright instalado, Browser plugin no
disponible, a 1440×1000 y 390×844, claro/oscuro. Verificados Enter/Espacio/Tab,
Escape, foco, clic fuera, enlace GET a contraseña, rutas SPA de calendario,
directorio y eventos, un solo perfil persistente y visibilidad para los tres
roles. Para el CSS local se cargó su hoja y se añadió sólo su clase geométrica
en la fixture: pie y disparador midieron 358 px, sin habilitar Apagar ni crear
superusuarios. Logo/opciones y Gica/tema tras cerrar fueron accesibles; sin
recortes ni desbordamiento. No se ejecutaron logout, apagado, cambios de cuenta,
modelos, red externa o micrófono. Cero errores de consola/JS/CSP. Fixtures
retiradas; capturas y resultados en `Temporal/qa-gica-account-menu/`.

`node --check static/js/app.js` correcto. Reinicio normal, salud HTTP 200 y
CSS/JS servidos idénticos a fuente con caché `20261116-account-menu1`. Las 44
tablas de datos comparadas quedaron idénticas; siguen los cinco eventos.
Runtime final en `estado.json` y `Temporal/qa-gica-account-menu/runtime-http.json`.

## Catálogo reducido a cinco eventos — corte anterior

Por autorización expresa de Jorge, adminjorge pasó de once a cinco eventos.
Se conservaron las dos demos con planes aprobados y seguimiento, el evento
recién creado con Gica y dos ejemplos distintos de tesis con propuestas de
tres sesiones, tres tareas y sin errores de validación actuales. Los ejemplos
equivalentes se desempataron por variedad temática, no por una supuesta mejor
calidad de un modelo. Respaldo consistente previo en
`Temporal/event-cleanup-five/before.sqlite3`.

Se retiraron seis eventos, sus cuatro propuestas de ejemplo y dos mensajes
asociados. La colección de borrado se comprobó antes de ejecutar la transacción.
No se modificaron los cinco conservados, sus planes/progresos, usuarios,
directorio, presupuestos, contabilidad ni el recibo de creación de Gica.
Comparación de 46 tablas: sólo cambiaron `events_event`, `planning_plancandidate`
y `assistant_message`; 43 quedaron idénticas. Claves foráneas correctas, catálogo
con cinco filas, índice y cinco fichas renderizados con HTTP 200. Sin inferencias.

La revisión detectó una discrepancia anterior en GICA: sus cinco sesiones del
plan están antes del inicio actual de la ficha. Se conservó por su historial
aprobado y como demo original; no se alteraron sus fechas ni decisiones durante
la limpieza. Permanece registrado como ajuste pendiente. Selección, resultado
y respaldo en `Temporal/event-cleanup-five/`; servidor normal reiniciado y sano.

## Confirmación de creación y regreso a Tus eventos — corte anterior

Una lectura por propietario, sin modificar los datos activos, confirmó el
último evento de adminjorge y su vínculo con una ficha en estado `created`.
El resultado privado está en `Temporal/qa-gica-created-list/event-confirmation.json`.

Tras recibir un `created` válido, Gica anuncia el guardado y abre automáticamente
la lista de eventos con un GET fijo a `/`, sin filtros. Refresca incluso si esa
lista ya estaba abierta. El panel se contrae para mostrarla y la voz vuelve a
escuchar; el camino por texto conserva el micrófono apagado. Sólo se intenta
una navegación por recibo de borrador/enlace; nunca se repite el POST. Revisión,
cancelación y respuestas inválidas no disparan el salto. Un fallo del GET conserva
el evento y su enlace y explica que el guardado sí ocurrió. Apagar durante el
anuncio cancela el salto pendiente; apagar sólo el micrófono durante un GET ya
iniciado no cancela esa lectura, pero no reactiva la voz.

**Nueve bloques UI correctos**: siete del recorrido y dos del apagado aislado,
en Edge/Playwright instalado, Browser plugin no disponible, a 1440×1000 y
390×844. Reconocimiento/síntesis simulados con avance virtual del contador;
audio físico pendiente. Se verificaron 15 respuestas antes de confirmar,
doble clic con un solo evento y GET, título/enlace visibles, recibo repetido,
continuidad de voz, creación por texto, GET inválido y confirmación inválida.
El caso Apagar preparó una ficha en revisión mediante el servicio local de la
fixture y confirmó desde la UI: conservó un evento, cero GET finales y cero
micrófonos tras el callback tardío. Una aserción antigua y un panel contraído
interrumpieron el harness principal; se corrigieron sus comprobaciones y el
caso de apagado se verificó aisladamente sin repetir los recorridos ya aprobados.
No fueron defectos adicionales del producto.

Sin errores de JS/consola/CSP, modelos, HTTP externo, Jobs, UIActions, AIUsage o
planes; eventos ficticios sólo en fixtures efímeras, retiradas al terminar.
Evidencias y capturas en `Temporal/qa-gica-created-list/`, con procedencia de los
dos recorridos de QA. El reinicio preservó 44 tablas, salud HTTP 200 y tres JS
servidos idénticos al código local, con caché `20261116-created-list1`. Runtime
y comprobación finales en `estado.json` y `runtime-http.json` de esa carpeta.

## Creación con conectores y cortesía — corte anterior

Reproducido: **«y vamos a crear un evento»** llegaba completo a la creación,
pero el prefijo «y» impedía reconocerlo; no era una separación incorrecta del
audio. El banco `creation-es-2026-11-16.1` añade conectores iniciales revisados
(`y`, `pues`, `oye`) y cortesía (`por favor`, `porfa`) entre los componentes de
la intención. No enumera frases completas: combina marcos, familias de acción,
artículos y tipos de evento. Mantiene límites y guardas para negaciones, citas,
relatos, administración y órdenes múltiples. No cambia permisos ni datos.

**50 pruebas de lógica y backend correctas**, incluyendo validación/CSRF,
acceso, confirmación final y palabras de creación como título literal. Los
HTTP 400/403 de casos negativos son esperados. **Siete escenarios UI correctos**
en Edge aislado con voz sintética, escritorio 1440×1000 y móvil 390×844.
Browser plugin no disponible; se reutilizó Playwright/Edge instalado. Los cuatro
segmentos «y / vamos a / crear / un evento» generan una sola solicitud y ficha,
a 1507,3 ms del último cambio; la siguiente respuesta llena el título en ese
mismo borrador. También pasan saludo/cortesía por texto y los casos negativos.
Sin errores de JS/consola/CSP, modelos, HTTP externo, eventos, Jobs, UIActions,
AIUsage o planes. Sólo tres borradores sintéticos en una DB efímera eliminada;
fixture detenido. No demuestra captura acústica física.

Evidencias antes/después en `Temporal/qa-gica-creation-connectors/`. Servicio
normal reiniciado, salud HTTP 200 y 44 tablas preservadas sin cambios. Runtime y
hora finales registrados en `estado.json` y `runtime-http.json` de esa carpeta.

## Espera de 1,5 segundos sólo con palabras — corte anterior

El contador de voz guiada sólo se arma con texto reconocido que contiene letras
o números, desde su último cambio real. Silencio, audio sin palabras, resultados
vacíos/espacios/puntuación y repeticiones idénticas no inician ni reinician la
cuenta. Promover un provisional idéntico a final no añade otra espera. Retirar
un provisional a vacío no confirma esa respuesta ni permite enviar su prefijo.

El plazo de 30 segundos para una respuesta incompleta ahora conserva texto y
sesión en revisión: **Volver a dictar** o «Gica corrige» recuperan la pregunta.
El límite móvil de 20/40 arranques por cinco minutos deja pausa visible con
reanudación programada al liberarse capacidad, sin un bucle de arranques ni
reconocedores simultáneos. Apagar, segundo plano y errores fatales de dispositivo
o permisos mantienen su detención. No cambia backend, memoria ni permisos.

**14 escenarios correctos**, con reconocimiento/síntesis simulados en Edge
aislado, a 1440×1000 y 390×844. Browser plugin no disponible: se reutilizó
Playwright/Edge instalado, sin nuevas dependencias. Silencio virtual de 90 s:
un reconocedor, cero plazos y cero envíos. Texto provisional/final idéntico:
1500 ms hasta solicitud; cambio real: 1502 ms. Se verificaron vacíos,
puntuación, parciales, recuperación de 30 s, `no-speech` más cierre nativo,
exceso de 300 caracteres, pausa/reanudación al agotar arranques, Apagar y ocultar
la página. Cero errores de JS/consola/CSP, modelos, HTTP externo, eventos,
UIActions, Jobs, AIUsage o planes nuevos. La ficha de prueba quedó aislada;
servidor fixture detenido y DB eliminada. Audio físico pendiente.

Evidencias: `Temporal/qa-gica-silence15/ui-results.json` y capturas de escritorio
y móvil. Reinicio normal: 44 tablas preservadas, salud HTTP 200 y los recursos
`romeo-voice.js`/`app.js` servidos idénticos al código local; versión de caché
`20261116-silence15`. Hora y runtime finales en `estado.json` y
`Temporal/qa-gica-silence15/runtime-http.json`.

## Límite de voz sin apagar la conversación — corte anterior

El límite local de 300 caracteres por respuesta antes llamaba a `stop()`, lo que
apagaba todo el diálogo. Una reproducción aislada confirmó ese corte con dos
segmentos de 180 y 150 caracteres. La auditoría reprodujo además una diferencia
entre espacios comprimidos en la previsualización y espacios originales en el
acumulador; esperar y continuar también conserva un prefijo que cuenta para el
total. No se identificó cuál de estas rutas produjo el episodio físico del usuario.

Ahora el exceso conserva el texto para revisión, muestra **Volver a dictar** y
mantiene un reconocedor para controles. El botón o «Gica corrige» recuperan el
turno; continuar no envía el exceso. Se normalizan los espacios de forma común,
sin truncar/ejecutar ni enviar datos parciales. Backend, permisos y memoria no
cambian; el borrador aceptado se conserva. El plazo independiente de 30 segundos
detenía una frase abierta sin enviarla en ese corte; el corte actual lo sustituye
por revisión de la respuesta. Se aclaró el mensaje de espera
para que no sugiera continuar como vía para eludir la revisión.

**13 bloques de regresión correctos** en Edge aislado, a 1440×1000 y 390×844:
300 exactos, 301 final/provisional, varios segmentos/resultados, espacios repetidos,
espera/continuación, corrección por voz/botón y siguientes campos sin arrastre.
Máximo un reconocedor; cero errores de consola/CSP, modelos, HTTP externo,
eventos, Jobs, AIUsage, UIActions o planes nuevos. Fixtures retiradas. Evidencia
en `Temporal/qa-gica-overflow/fixed/ui-results.json`; voz sintética, no audio físico.
Comprobación inicial del reinicio: 44 tablas preservadas, salud HTTP 200 y JS
servido idéntico a fuente. El registro de estado contiene el runtime final.

## Directorio inicial y gestión de Gica — corte anterior

La limpieza autorizada de adminjorge dejó una organización, **Universidad Nacional
del Callao - UNAC**, y un expositor, **Dr. Robert Castillo Alva**, asociado a ella.
Retiró 45 personas, dos organizaciones y 60 participaciones del directorio;
desvinculó la organización anterior de seis eventos, sin borrar eventos, planes,
preparación, historial ni cuentas. Se creó un respaldo SQLite previo en
`Temporal/qa-gica-clean-profile/restore-before.sqlite3`. La comparación conserva
las columnas anteriores de 38 tablas fuera de los cambios autorizados; Django
añadió únicamente metadatos de permisos del nuevo modelo. El checklist personal
está deshabilitado en el servidor y retirado de la navegación; sus cinco registros
históricos se conservan.

Se aplicaron `directory.0002_alternate_names` y `assistant.0007_gicaprofile`.
Los alias son editables y se resuelven por coincidencia exacta normalizada, con
ámbito por propietario y elección si hay ambigüedad. El flujo conserva 15 pasos;
una institución o persona ausente requiere un sí explícito antes del alta.
También reconoce declaraciones de voz como «el expositor será Robert»; relatos,
negaciones y descripciones plurales no proponen altas por sí solos. Crear un
contacto no crea cuentas ni confirma el evento. `directory_people` es un campo
opcional validado estrictamente en el cliente; los nuevos registros de institución
pueden reflejarse en el formulario sin volver a cargar su lista.

**Conoce a Gica** reúne avatar SVG local, tres apariencias, tres tonos de saludo
y gestión de voz/memoria. El perfil es privado, se crea sólo al guardar y no
cambia permisos, modelos o presupuesto. La personalidad selecciona saludos
autoriales; no implica entrenamiento de un modelo. Las preferencias booleanas
de voz se recuerdan por cuenta en el navegador. El panel muestra cuatro accesos
rápidos, conversación y borrador; entrada, dictado y ejecución manual quedan en
**Modo manual** cerrado inicialmente. Los controles avanzados tienen un solo nodo
por documento y se conservan al pasar del perfil al formulario de creación.

**Pruebas:** 87 pruebas de backend correctas, incluyendo permisos/CSRF, alias,
registro sí/no, ambigüedad, repetición, limpieza idempotente y protección de
responsables/historial. Los HTTP 400/403/404 de esos casos negativos son esperados.
Siete bloques de aceptación integrada y cinco complementarios pasaron en Edge
aislado, a 1440×1000 y 390×844, con ambas paletas; sin errores de consola/CSP,
modelos ni HTTP externo. Voz y reconocimiento simulados: audio físico pendiente.
Evidencias en `Temporal/qa-gica-clean-profile/` y
`Temporal/qa-gica-clean-controls/`; los dos bloques visuales verificaron además
que el cursor en reposo no cubre el avatar. Un escenario adicional confirmó
crear desde Conoce a Gica, abrir el formulario, responder título/UNAC y cancelar
sin crear un evento: conservó los controles de preferencias y un solo reconocedor.
El runtime final está en sesión 58039, PID 19300, puerto 8000; salud HTTP 200
comprobada el 16 de noviembre a las 00:24:36 de Lima, y siete recursos HTTP
idénticos al código local por SHA256 (`runtime-http.json`). Los resultados de los cortes siguientes
son antecedentes y no se suman a estas cifras.

## Familias de creación y diagnóstico de continuidad — corte anterior

Ampliada la intención de inicio mediante `gica_creation.es.json`, versión
`creation-es-2026-11-15.1`: cuatro familias de acción, 12 tipos y 26 formas de objeto.
Infinitivos, imperativos, formas colectivas/futuras y nombres de acción comparten
marcos de cortesía y gramática; no se enumeran todas las oraciones. Se conservan
guardas de negación, citas, relatos, hipótesis, administración, secretos y órdenes
múltiples. Pasados acentuados se comprueban antes del plegado de tildes. El banco
inválido falla cerrado. Campos de un borrador activo siguen siendo datos, incluso
si dicen «quiero crearuna reunión»; sólo la petición inicial abre una entrevista.

**Backend:** 58/58 pruebas correctas, incluyendo 27 puras de lenguaje, 21 de servicio/
HTTP y 10 de fechas. Dentro de una prueba composicional hay 546 combinaciones de
21 verbos × 26 formas; no son 546 pruebas adicionales. Se comprueban nuevos tipos y nombres
de acción, futuro, unión verbo/artículo, rechazos, banco inválido y datos literales.
Sin modelos, red o base activa; no se genera evento, Job, AIUsage o UIAction al
reconocer la intención. Las cifras anteriores se solapan y no se suman.

**Diagnóstico de voz:** el usuario informa que se apaga al completar una parte
del recorrido. Una reproducción aislada confirmó que tres cierres normales
cortos agotaban la reconexión anterior. Los metadatos de la interacción real
no incluían el código de error; no se atribuye ese apagado a una causa concreta
del micrófono o el entorno. Se corrigió la ruta reproducible: cierre normal con
audio y `no-speech` saludable reanudan sin agotar la cuota de fallos cortos.
`network`, `aborted` o arranques sin audio mantienen dos reintentos; permisos,
dispositivo, idioma/configuración y errores desconocidos se detienen, muestran
código y no reintentan. Los finales sobreviven al cierre nativo antes/después
de TTS sin doble envío y conservan los dos segundos de texto estable.

**Voz aislada:** 8/8 bloques correctos en
`Temporal/qa-gica-continuity-v2/fixed/ui-results.json`; integración adicional de
cinco bloques/siete turnos en `integration/ui-results.json`. Máximo un reconocedor,
conservación de espera y borrador, códigos fatales y reintentos limitados; cero
Event/Job/AIUsage/UIAction/plan, modelos o llamadas externas. Servidores y bases
aisladas retirados. No se suman a las suites o versiones anteriores.
La traza local de 40 eventos sólo contiene metadatos, sin audio/transcripciones.
Se mantienen 20/40 inicios por ventana móvil de 5 minutos, sin TTL absoluto para la
conversación guiada. El rótulo **Ficha del evento** queda separado del indicador
de micrófono; apagado muestra **Mic apagado · borrador guardado** y
**Borrador en pausa**.

**Móvil:** un bloque/dos turnos adicionales correctos en
`integration/visual-results.json`, captura revisada. Indicador en dos líneas,
botón Gica y tema con 10 px de separación, sin solapamiento. El corte reúne ocho
bloques dirigidos, cinco de integración/siete turnos y uno visual/dos turnos;
son 14 bloques y no se suman versiones anteriores. Voz sintética; micrófono físico
y causa del episodio real permanecen sin acreditar.

**Runtime verificado:** 43 tablas activas exactamente preservadas mediante
`Temporal/qa-gica-continuity-v2/runtime-preserved.json`; sin migraciones ni
llamadas a modelos. Reinicio normal en sesión 6648, escucha en 127.0.0.1:8000/PID 11424;
salud HTTP 200 el 15 de noviembre a las 23:58:46 de Lima y 5/5 recursos idénticos por SHA256 a archivos
locales (`runtime-http.json`). Sintaxis de cuatro JavaScript y Django check
correctos; fixtures de QA retirados. El runtime 51237 corresponde al corte anterior.
No se guardaron audio ni transcripciones reales nuevas para este diagnóstico.

## Ampliación de fechas múltiples, formulario vivo y turno de voz

Implementación actual verificada con límites: `date_language.py` consume
fechas completas, listas/rangos, varios meses, números escritos y años hablados.
Pide año 20xx no anterior al actual del servidor y conserva días/meses en el
borrador privado cuando falta o es incompleto. Un año posterior como 2040 es
válido; días anteriores del año actual se admiten. Extra números, meses
desconocidos, rangos inversos y fechas inexistentes no se aceptan parcialmente.
La normalización final ordena/deduplica hasta 366 fechas en `Event.scheduled_dates`.

El formulario principal muestra datos e entrevista mientras Gica guía la creación;
las transcripciones parciales son sólo una previsualización. Calendario y filtros
consideran todos los días y meses seleccionados sin duplicar eventos. Los datos
históricos mantienen integridad sin caducar por el cambio de año. Los controles
espera/corrige/continúa preservan o limpian sólo el texto pendiente, sin cambiar
datos ya aceptados. La escucha anticipada opcional usa eventos de síntesis y una
estimación, no un reloj garantizado de audio. No se envía mientras habla Gica.

Los planes verifican que cada sesión ocupe días seleccionados y que la suma de
los tramos de cada jornada, incluidos descansos, respete la duración total
confirmada. Se conservan el inicio de ficha y el tratamiento de medianoche.
Se corrigieron dos bordes de edición: fechas históricas equivalentes reordenadas
siguen siendo las mismas; un inicio manual nuevo o modificado no elude la regla
del año actual dejando vacía la lista de fechas.

**Backend final:** 550 casos en 63,608s: **545 correctos y cinco omitidos**, estos
últimos de bloqueos/concurrencia PostgreSQL no acreditados con SQLite. La corrida
única incluye creación/fechas, lenguaje legado, eventos, planificación y trabajos;
no se suman las suites focales anteriores porque se solapan. Django check sin
incidencias, migraciones sin diferencias y sintaxis de todos los JavaScript correcta.

**Formulario/calendario:** diez bloques y 25 turnos (recorrido siete/20 más visual
tres/cinco), con formulario lleno, tres fechas, filtro del día intermedio,
confirmación doble sin duplicar, autocontracción por voz y cursor en el campo
actual tras3,3s de reposo. Capturas de escritorio/móvil inspeccionadas, sin
desbordamiento, errores JS/CSP ni llamadas externas o modelos. La QA funcional
creó un evento sólo en su base aislada; la visual canceló sin crear ninguno.
Bases y servidores de esas pruebas eliminados/cerrados.

**Voz dirigida:** once bloques correctos (siete de espera/corrección/anticipación,
dos de límites y dos de resumen final). Se conserva el texto en espera incluso
si falla la escucha anticipada; un único reconocedor y ninguna llamada externa,
error o creación de Event/Job/UIAction/plan en esas pruebas. La anticipación sólo
funciona en `collecting`, nunca en `review`; la confirmación final espera el fin
de la lectura. Fixtures y servidores retirados. Total UI actual: **21 bloques**
(diez de formulario/calendario más once dirigidos); se conservan los25turnos del
recorrido/visual por separado, sin sumar emisiones de ensayos distintos ni las
versiones visuales sustituidas.

Audio físico/eco real y concurrencia PostgreSQL siguen sin acreditarse. Las cifras
de la sección siguiente son evidencia histórica del recorrido anterior.
El ensayo de interfaz nuevo utiliza `Temporal/qa-gica-creation-live/`; no se
consultan modelos ni se prueba sobre la base activa.
La voz dirigida se conserva en `Temporal/qa-gica-creation/voice-turns/ui-results.json`,
`voice-limits/ui-results.json` y `review-voice/ui-results.json`. Las capturas
`Temporal/qa-gica-creation-live/live-desktop.png` y `live-mobile.png` muestran el
formulario visible, panel contraído y campo actual señalado.

**Activación:** migración `events.0007_event_scheduled_dates` aplicada con respaldo
privado `Temporal/qa-gica-creation-live/before-event-dates.sqlite3`. Se preservaron
exactamente 43 tablas y sus columnas anteriores, y el campo nuevo está vacío por
defecto en todos los eventos existentes. No se insertó QA en la base activa.
`runtime-preserved.json` registra la comprobación. Sin Jobs/UIAction activos al
parar; reinicio normal el 15/11 a las 23:37:24, sesión51237, launcherPID11472 y
enginePID3088; salud200 a las23:40:22. Siete recursos JS/CSS servidos por HTTP
coinciden por SHA256 con los archivos locales; sólo la pareja normal del servicio
permanece activa. Sin llamadas API ni lectura/reconstrucción
de credenciales.

## Creación conversacional de eventos con Gica

Solicitud expresa de Jorge: ofrecer crear al saludar, reconocer una petición de
creación y guiar el recorrido mientras completa la ficha con sus respuestas.
Implementados `creation_language.py`, `event_creation.py`, endpoint privado,
`EventCreationDraft`, migración `assistant.0006_eventcreationdraft` e interfaz de
pregunta/ficha visible con corrección, cancelación y reanudación.

Quince pasos: ocho datos de ficha y siete de entrevista. Borrador privado por
dueño, vigencia 24 horas, un activo por cuenta. Respuestas literales: un título
con forma de orden o HTML sigue siendo dato; no llega al runner, Wikipedia,
alias o modelos. Institución existente y propia o ninguna; campos opcionales
pendientes. Fecha, hora, zona, capacidad y duración tienen validación mecánica;
los formatos ambiguos preguntan. Revisor, contexto de agente, otro propietario,
campos extra/duplicados y falta de CSRF no conceden acceso. UUID, revisión y
transacción protegen el recorrido y la creación final. Sólo el estado `review`
admite «crear evento» o el botón final; un «sí» aislado no guarda el evento.

**Pruebas:** 307/307 correctas en la suite ampliada de este cambio. Incluye
regresiones de lenguaje, memoria, interacción, conocimientos y creación; validación,
permisos, TTL, un borrador activo, respuestas repetidas, revisión antigua y doble
confirmación sin duplicar el evento. Django check y migraciones sin diferencias.
Los ensayos no usaron modelos ni la base de datos activa.

**Interfaz:** 13 bloques correctos (siete del recorrido, dos visuales y cuatro de
cancelación por voz), 32 turnos (29 + 3) y cinco emisiones de voz adicionales en
Edge separado a 1440×1000 y 390×844. Browser plugin no
disponible; se reutilizó Playwright ya autorizado. El recorrido completó las
15 preguntas y siete respuestas de entrevista, mostró el resumen sin crear aún,
permitió corregir y creó exactamente un evento tras doble clic final. También
se probaron errores de fecha/hora/capacidad, atrás, recarga/reanudación, HTML
literal, cancelación, saludo con oferta y tres turnos de voz simulada. La
pregunta/ficha quedó por delante de los ajustes de voz; capturas inspeccionadas,
sin desbordamiento horizontal, errores JS/consola/CSP ni red externa.

Voz sintética: máximo un reconocedor activo y cero solapamientos; la captura se
pausa para TTS, descarta resultados antiguos y vuelve a escuchar. La QA funcional
terminó con un evento sintético, dos borradores y cero `UIAction`, `Job`, `AIUsage`
o planes; el ensayo visual canceló su propio borrador sin crear un evento.
El ensayo adicional comprobó que **«Gica cancela»** cancela el borrador persistido,
pronuncia la respuesta del servidor y vuelve a escuchar con un solo reconocedor,
sin crear un evento. Puede iniciar otro evento en la misma sesión. Sin un
borrador activo, la cancelación conserva el control local y no consulta el endpoint
de creación. No se midieron audio físico, precisión general del español ni locks concurrentes
de PostgreSQL. No se instalaron dependencias. Servidores y bases de QA retirados.

Evidencia: `Temporal/qa-gica-creation/ui-results.json`, `visual-results.json`,
`creation-desktop.png`, `creation-mobile.png`, `cancel-voice/ui-results.json` y
`cancel-voice/cancelled-voice.png`; reproducción del recorrido principal mediante
`.venv\Scripts\python.exe -B Temporal\qa-gica-creation\verify_ui.py --go`.

**Activación local:** migración `assistant.0006` aplicada con respaldo privado en
`Temporal/qa-gica-creation/before-creation-migration.sqlite3`. Las 42 tablas previas
conservaron exactamente sus filas; sólo se añadieron un tipo de contenido y cuatro
permisos Django esperados. Cero borradores nuevos o eventos de QA en la base activa.
Evidencia `runtime-preserved.json`. Reinicio normal el 15/11 a las 23:00:31,
sesión 61991, salud y activo nuevos 200; POST sin CSRF 403 como corresponde.
Sin llamadas a modelos ni reconstrucción de claves efímeras del proceso anterior.

## Conocimientos públicos, memoria automática y revisión posterior

Jorge autorizó consultar y conservar información y asociaciones sin aprobación
previa por entrada. Implementados `public_knowledge.py`, `knowledge_service.py`,
`knowledge_memory.py`, `learned_aliases.py`, vistas/biblioteca y migración0005.
Memoria y asociaciones privadas por dueño, independientes de permisos y planes.

- Wikipedia español: API oficial de origen fijo, un GET acotado, sin claves,
  redirecciones, proxy heredado, reintentos o LLM. Consulta real técnica pública
  «mantenimiento predictivo» satisfactoria en547ms en este ensayo. El adaptador
  inicialmente rechazó U+200B presente en extractos reales; se normaliza sólo ese
  separador y se conservan rechazo de bidi/controles, límites y pruebas de regresión.
  Evidencia en `Temporal/qa-gica-knowledge/wikipedia-live-validation.json`.
-20solicitudes externas/día local y5s entre ellas, un pendiente por dueño;
  caché no gasta esa cuota. UUID/huella y reserva durable evitan reenvío del mismo
  intento, incluidos cachehits; historia terminada de siete días. Timeout8s, sin
  reintentos, respuesta128KiB y máximo dos slots de transporte. SQLite no acredita
  carreras o límites concurrentes de PostgreSQL.
- Hasta200conocimientos con fuente/fecha y TTL24h. Una respuesta caducada o
  desactivada no se usa; un refresco no sustituye revisión humana ni contradicción
  previa. Corrección manual cambia la atribución a memoria revisada. Biblioteca
  permite filtrar, revisar, corregir, desactivar, reactivar tras revisar y borrar.
- Hasta100asociaciones explícitamente enseñadas de1–3palabras. Ejemplo «cuando
  diga programación, me refiero al calendario»: respuesta informativa, luego
  «abre programación» prepara calendario. Cinco controles sin slots; nombres,
  negaciones, múltiples órdenes, roles y seis acciones generales se conservan.
  Los `CommandPattern` revisados siguen separados. No entrenar pesos ni aprender
  permisos o instrucciones desde una página.

**Pruebas:**212/212 backend correctas (94 de conocimientos/asociaciones/transporte/
vistas y118 de lenguaje, memoria e interacción existentes). Se detectaron dos
regresiones de SQL de lectura por abrir transacciones para frases ordinarias;
corregidas sin modificar las pruebas previas. Después del ajuste de retención,
23/23pruebas del servicio repetidas correctamente. Django check y migraciones sin
diferencias. Ninguna prueba de backend consultó modelos o la base activa.

**Interfaz:**9/9bloques reales en Edge separado,1440×1000 y390×844. Browser plugin
not available; se utilizó Playwright existente con el permiso previo del usuario.
Flujo: Eventos → Gica por texto → referencia con fuentes/autoguardado → repetición
por caché → consulta externa apagada → enseñanza → biblioteca → revisión/corrección/
desactivación/reactivación/borrado. Voz sintética: pregunta →2s de texto definitivo
estable → caché → resumen TTS local con captura pausada → escucha reanudada; máximo
un reconocedor y cero solapamientos.0Jobs/AIUsage/UIActions,0inferencias y0HTTP
externos en esa QA; un extracto público real previamente capturado sirvió de fixture.
Página identificada, contenido visible, sin error de aplicación ni consola/CSP,
capturas inspeccionadas sin overflow. No acredita micrófono físico ni audibilidad.
Evidencia `Temporal/qa-gica-knowledge/ui-results.json`, `knowledge-desktop.png`,
`knowledge-mobile.png`; reproducción con
`.venv\Scripts\python.exe -B Temporal\qa-gica-knowledge\verify_ui.py`.
Base y servidor de QA eliminados/cerrados. No se instalaron dependencias nuevas.

**Runtime:**migración respaldada y aplicada sin trabajos/acciones en curso.
Las39tablas previas conservaron todas sus filas; se añadieron únicamente3tipos de
contenido y12permisos Django correspondientes a los tres modelos nuevos. Comprobación
hash/subconjuntos en `runtime-preserved.json`; respaldo privado de la migración
conservado en Temporal para reversión. Servicio normal reiniciado y salud200.
Las claves sólo mantenidas en RAM no se reconstruyen tras reiniciar.

**Alcance:**extractos de Wikipedia, no búsqueda general de Google ni respuesta
compleja sintetizada por IA. No se guardan pesos, audio ni nuevas capacidades.
Las preguntas públicas pueden enviarse a Wikimedia; controles de formatos privados
no garantizan identificar todos los datos personales. El usuario dispone del
checkbox para apagar la consulta y de la biblioteca para corregir lo aprendido.
Un resumen incorporado automáticamente no se etiqueta verificado por un humano.

## Normalización de órdenes por conceptos y punto fijo acotado

Banco vigente de acciones `es-2026-11-15.6`; social `.4` permanece independiente.
El manifiesto incluye un cuarto módulo fijo `gica_normalization.es.json`, compilado
por `apps/jobs/command_normalization.py`. Nueve familias principales y doce de
gramática auxiliar reúnen 46 formas nominales revisadas; hay ocho inflexiones
verbales explícitas adicionales. No se almacenan todas las oraciones posibles.
Normaliza singular/plural, género de claro/oscuro y errores de destinos como
«caldenarios», conservando las seis acciones actuales.

Primero comprueba el texto original y delimita gramática/datos. Después sólo
normaliza destinos y ámbitos en sus bordes: los nombres conservan NFC y offsets.
Hasta tres pasadas y 80 tokens; cada corrección se compara con el token original,
sin acumular saltos de errores. Una edición requiere lexema de longitud suficiente;
dos sólo para calendario/directorio largos en contexto fuerte, incluido un destino
aislado. El mejor candidato debe ser único. Verbos y negaciones no tienen corrección
difusa. La gramática completa y los múltiples destinos se revalidan después.
El tema pendiente reutiliza el intérprete y sólo admite claro/oscuro.

«Abre los caldenarios», «abre el evento», «pon temas claros» y los ámbitos plurales
preparan comandos canónicos. «Busca a Calendario», «Busca a Evento» y «Busca a
Caldenarios» preservan el nombre; buscar calendario sin introductor de persona o
buscar a alguien en el calendario siguen aclarando. Se cambió intencionalmente
una expectativa del corpus: `person_named_destination` pasa de aclaración a búsqueda
de la persona Calendario. Las otras expectativas del corpus se conservaron; los
dos archivos de ejemplos actualizaron su metadato a `.6`.

80/80 pruebas backend correctas, incluidas 21 de lenguaje/normalización, corpus
de 210 casos y matriz de 96 variantes morfológicas. QA aislada Django/SQLite/Edge:
cuatro bloques, 34 turnos (24 guía escrita, nueve ejecución escrita y uno de voz)
más seis interpretaciones y dos comprobaciones de permisos. Dos recibos completados:
Calendario por texto y Eventos por voz; 37 registros sintéticos. Cero Jobs, AIUsage,
patrones, errores JS/consola/CSP, peticiones externas o solapamientos de voz.
Stop dejó cero reconocedores activos. No acredita precisión general del español,
audio físico o aprendizaje autónomo de nuevos vocabularios.

Evidencia `Temporal/qa-gica-normalization/integration/results.json`; captura de
escritorio inspeccionada en el mismo directorio. Browser plugin no disponible;
Playwright/Edge separado ya autorizado. Servidor QA cerrado y base aislada eliminada.
SparkX reiniciado, salud 200 y 19 tablas activas preservadas
(`Temporal/qa-gica-normalization/runtime-preserved.json`), sin llamadas a modelos.
Las secciones de versiones anteriores siguientes son evidencia histórica.

## Reconocimiento por conceptos y contexto, con tolerancia ortográfica

Banco vigente `social-es-2026-11-15.4`. Las familias sociales se definen como
lexemas por función: núcleo, intensificadores, marco, motivo, vocativos y otras
palabras de contexto. Se retiraron las listas sociales de oraciones/expresiones
que sustituye este esquema; los ejemplos completos están en las pruebas, no en
el banco de reconocimiento. Las gramáticas de hora y saludo dirigido conservan
sus fragmentos y contratos. Esto no modifica el registro privado consentido de
conversaciones ni aprende patrones ejecutables automáticamente de ese historial.

«Graccias» se reconoce por repetición de letras; sólo `gracias` y `agradezco`
son candidatos revisados de corrección ortográfica. Otras aproximaciones de una
edición exigen candidato único y contexto gramatical; `Gracia` está excluida.
La corrección es interna: no reescribe nombres, consultas, órdenes, borradores
o texto original. La gratitud admite contexto antes/después del núcleo, como
«me has ayudado mucho gracias» o «por tu ayuda, muchísimas graccias».
No basta encontrar la clave en una cita, relato, mención de un nombre o mandato.
«Gracias por abrir calendario» responde información sin abrir nada ni afirmar
ejecución; «abrir calendario gracias» conserva la intención de abrir calendario.

71/71 pruebas backend correctas, incluidas 26 sociales y la matriz de 96 variantes
anteriores. QA aislada Django/SQLite/Edge: cuatro bloques, 33 turnos (16 guía
escrita, 10 ejecución escrita, 7 voz simulada) y cinco comprobaciones adicionales
de interpretación/permisos. Las tres oraciones extensas exigidas funcionaron sin
aparecer completas en el JSON. Conservados nombres Chica/Buenos Días/Graccias,
guardas, roles y Stop. Un recibo completado de Calendario, 34 registros sintéticos
y cero Jobs, AIUsage, patrones, errores JS/consola/CSP, peticiones externas o
solapamientos de reconocimiento/síntesis. No acredita comprensión ilimitada del
español, entrenamiento de pesos ni funcionamiento físico del micrófono.

Evidencia `Temporal/qa-gica-concepts/integration/results.json`; captura de escritorio
1440×1050 inspeccionada en el mismo directorio. Browser plugin no disponible;
Playwright/Edge separado ya autorizado, sin nuevas dependencias. Servidor QA
cerrado y base aislada eliminada. SparkX reiniciado, salud 200 y 19 tablas activas
preservadas (`Temporal/qa-gica-concepts/runtime-preserved.json`). No hubo llamadas
a modelos. Las secciones `.3`, `.2` y `.1` siguientes conservan evidencia histórica.

## Cortesías compuestas y recuperación de dictado incompleto

Banco vigente `social-es-2026-11-15.3`. La revisión privada de sólo lectura pasó
a 39 interacciones: el fallo nuevo correspondía a «O k muchas gracias». No se
copió el historial completo ni se aprobaron patrones personales automáticamente.
La gramática compone hasta tres segmentos sociales completos y hasta dos
intensificadores de agradecimiento: acuse, gracias/te agradezco, complementos
revisados, reciprocidad, disculpas, permisos o despedidas. Reconoce «O k muchas
gracias», «listo, gracias por tu ayuda» y «gracias, igualmente» desde ambas
entradas de texto y la voz guiada. «No, gracias» y «no hay de qué» son expresiones
completas; no se elimina la negación de una orden ni se admiten acciones en esa
rama. La QA detectó y permitió corregir la reciprocidad antes de esta entrega.

Cortesía/despedida completa termina una aclaración de persona sin buscarla como
nombre. «Busca a Gracias» conserva la búsqueda explícita; «Chica» y «Buenos Días»
siguen siendo nombres en un slot de persona. Si el reconocedor termina con
parciales pendientes, descarta todo el turno, incluidos sus fragmentos definitivos,
avisa y reconecta dentro de los límites existentes. No quedan parciales del
reconocedor anterior bloqueando la siguiente frase ni se ejecuta una suborden.
Los finales completos conservan la espera de 2 s; Stop y permisos no cambian.

65/65 pruebas backend correctas, incluidas 21 sociales y una matriz de 96 variantes.
QA aislada Django/SQLite/Edge: seis bloques y 39 turnos, cortesías por ambos botones,
agradecimientos repetidos por voz, búsqueda pendiente→agradecimiento→Calendario,
guardas y límites. Las carreras interim→onend→nuevo final y final+interim→onend
no enviaron los fragmentos descartados; un final completo abrió Calendario una
sola vez. Un recibo completado, 40 registros sintéticos y cero Jobs, AIUsage,
patrones, errores JS/consola/CSP, peticiones externas o solapamientos de audio.
Stop durante TTS impidió rearmado tardío. No mide audio físico ni todas las
variantes del español; no se invocaron modelos.

Evidencia `Temporal/qa-gica-courtesy/integration/results.json`; capturas de escritorio
y móvil inspeccionadas en el mismo directorio. La recaptura visual añadió un turno
aislado sin acciones, registrado aparte de los 39 de la suite principal.
Browser plugin no disponible: Playwright/Edge
separado ya autorizado. Servidor QA cerrado y SQLite aislado eliminado. SparkX
reiniciado, salud 200, activo de voz idéntico a disco y 19 tablas preservadas
(`Temporal/qa-gica-courtesy/served-assets.json`, `runtime-preserved.json`).
Recargar Ctrl+F5 para cargar el nuevo activo. Las secciones `.2` y `.1` siguientes
conservan evidencia histórica de versiones sustituidas.

## Generalización social y las dos entradas de texto

Revisión de sólo lectura de36 interacciones privadas: las peticiones con
«puedes mandarle» o «quiero saludar» no coincidían con las formas anteriores.
Además, «Ejecutar orden» no atendía respuestas sociales, aunque la guía sí las
atendía. No se han copiado conversaciones privadas a la documentación ni
convertido registros sin revisar en patrones aprobados.

Banco `social-es-2026-11-15.2`: composición de cortesías/modales, verbos,
conceptos y nombres. Reconoce preguntas como «¿Puedes decirme la hora?»,
saludos como «O buenas noches» y solicitudes de saludo con verbos en infinitivo.
Las guardas se aplican antes de retirar cortesías: negaciones, citas, condiciones
y órdenes mezcladas no se transforman parcialmente en una respuesta social.
Los saludos solicitados se dicen aquí; no envían mensajes externos.

Ambas entradas escritas responden localmente. El endpoint de interpretación
devuelve `info` en sus seis campos: `action:null`, `query:""`, `options:[]`;
el cliente rechaza información con una acción o alternativas adjuntas. No pasa
por el runner ni crea un UIAction. El parser puro conserva tres estados y seis
acciones; la guía mantiene cinco campos. La presencia y el historial distinguen
una respuesta informativa de una acción fallida.

Un turno social completo sale de una aclaración de tema; una petición social
explícita puede salir de la búsqueda de persona. Los nombres «Chica» y «Buenos
Días» se conservan como nombres cuando se está pidiendo una persona. La entrada
manual inicia un tema nuevo. La hora sigue usando el reloj real de America/Lima.

57/57 pruebas backend correctas, incluidas15 del resolver social. QA aislada en
Django/SQLite/Edge: seis bloques y33 turnos (19 guía escrita,8 ejecución escrita,
6 voz simulada), además de dos respuestas informativas manipuladas rechazadas.
Una única acción de Calendario completada; cero Jobs, AIUsage o patrones nuevos.
Sin errores JS/consola/CSP, red externa ni solapamiento de reconocimiento/síntesis.
Stop impide rearmado tardío. Esto no mide precisión general del español ni audio
físico. No se invocaron modelos.

Evidencia `Temporal/qa-gica-general/integration/results.json`; capturas de
escritorio1440×1050 y móvil390×844 inspeccionadas. Browser plugin no disponible;
se usó Playwright/Edge separado ya autorizado. Servidor QA cerrado y base aislada
eliminada. SparkX reiniciado, salud200, tres activos idénticos a disco y19 tablas
conservadas (`Temporal/qa-gica-general/runtime-preserved.json`, `served-assets.json`).
Recargar Ctrl+F5 para cargar esta versión. La sección social `.1` siguiente es
evidencia histórica sustituida por esta ampliación.

## Respuestas sociales rápidas, saludos y hora

Banco independiente `social-es-2026-11-15.1`:51 frases (14 saludos,17 cortesías,
cinco de bienestar, siete despedidas y ocho preguntas de hora), siete patrones
de saludo a una persona y siete alias. Resolver puro sin proveedores: turnos
sociales completos devuelven `info`, sin borrador, intención o UIAction. Saluda
según el saludo recibido, responde «Estoy bien, gracias por preguntar», agradece
y dice un saludo local para un nombre NFC validado de hasta80 caracteres. Nunca
envía mensajes ni consulta contactos. Si falta el nombre, invita a formular la
petición completa. Despedirse no afirma que se haya apagado el micrófono.

La hora se calcula con reloj del servidor y America/Lima, HH:MM con etiqueta de
Perú. Los contextos de nombre/tema conservan prioridad; «Chica» o «Buenos Días»
pueden seguir siendo nombres de búsquedas. Negaciones, citas, condiciones,
reportes y mezclas con órdenes no se resuelven parcialmente como un saludo.

«Buenos días, abre calendario» conserva el borrador/intención canónicos en los
cinco campos existentes. El cliente admite sólo cinco prefijos literales de
saludo, los dice con reconocimiento pausado y vuelve a comprobar sesión, ticket
y texto antes del mismo runner. Detener/edición/navegación durante el saludo
impiden ejecutar. Texto guiado conserva revisión manual. Una orden sin saludo
no recibe este preámbulo; capacidades, aviso v5 y memoria v3 no se amplían.

50/50 pruebas backend correctas, incluidas hora fijada a UTC para comprobar
conversión y singular a01:05;10/10 sociales puros se repitieron tras el ajuste
final de saludo compuesto. QA real aislada Django/SQLite/Edge: seis bloques,
saludos/cortesía/bienestar/persona/hora real, exclusión micrófono/TTS, un único
recibo de Calendario y Stop durante el saludo sin acción posterior ni rearmado.
Un POST aislado adicional verificó «Buenos días. ¡Hola, Ana!...» sin escrituras.
Cero errores JS/consola/CSP, peticiones externas, Jobs, AIUsage o patrones nuevos.
Reconocimiento/síntesis simulados: no acredita micrófono ni audibilidad físicos.

Evidencia `Temporal/qa-gica-social/integration/results.json` y capturas inspeccionadas
`social-calendar-desktop.png` (1440×1050) y `social-stopped-mobile.png` (390×844).
Browser plugin no disponible; Playwright/Edge separado ya autorizado. Servidor QA
cerrado y bases aisladas eliminadas. SparkX reiniciado, salud200, dos activos nuevos
idénticos a disco y19 tablas conservadas (`runtime-preserved.json`,
`served-assets.json`). Recargar Ctrl+F5 y abrir Gica para probar.

## Actualización de tono: mensajes más cercanos

Banco `es-2026-11-15.5`: respuestas amables y específicas. Petición desconocida
pide disculpa breve y ofrece opciones; nombre ausente pregunta por la persona;
negación se reconoce como entendida y función fuera del alcance se explica sin
prometer capacidades. La guía conserva el motivo del intérprete en vez de
convertir todos los rechazos en «No prepararé esa orden». Sólo cambia el texto:
seis acciones, estados, permisos, temporizadores, memoria y aviso v5 se conservan.

38/38 pruebas existentes de lenguaje, vocativos, endpoint y guía correctas.
QA breve real en Django/SQLite aislada y Edge: cinco turnos escritos, tres bloques
correctos; desconocido/negación/fuera de alcance distintos y nombre Chica
conservado en un borrador manual. Cero acciones, modelos, audio o errores de
consola/CSP. Evidencia `Temporal/qa-gica-tone/results.json`; captura inspeccionada
`tone-desktop.png`. Servidor de prueba cerrado y base temporal eliminada.
SparkX reiniciado, salud200 y19 tablas conservadas (`runtime-preserved.json`).
El recorrido de continuidad siguiente conserva su evidencia anterior; su banco
.4 queda sustituido por .5 únicamente en estos mensajes.

## Recorrido validado: diccionario modular y conversación continua entre tres vistas

Banco `es-2026-11-15.4`: seis intenciones,100 expresiones verbales,36 variantes
de destino, siete alias de vocativo,24 saludos/ayudas,15 mensajes y un slot de
persona. Manifiesto y tres módulos JSON locales validados;210 casos sintéticos
curados, incluidos negativos. Es composición de reglas, no entrenamiento de
pesos ni comprensión general del español. «Hola chica abre eventos» y «haz clic
en calendario» se interpretan; «busca a Chica Pérez» conserva el nombre. «Agenda»
pregunta a qué destino se refiere y «localizar a alguien» pide un nombre.

La conversación guiada con aviso **v5** conserva cabecera, panel, cursor y sesión
humana al abrir Eventos `/`, Calendario `/calendar/` y Directorio `/directory/`,
incluidos filtros GET y atrás/adelante. El contenido sigue renderizándose en el
servidor con sus permisos. No importa scripts del HTML recibido y rechaza identidad
o rol distinto, destinos/consultas incoherentes, scripts/HTMX automático, recursos
externos y atributos no admitidos. Una transición nueva se consume una vez y el
recibo sólo se completa tras verificar destino y URL. Un fallo posterior al cambio
informa incertidumbre sin fingir que se conservó la página ni repetir el clic.

Se mantienen2s de texto definitivo estable y ejecución directa de una orden clara;
ambigüedad pregunta y texto guiado conserva ejecución manual. Pausa micrófono
durante navegación/acción/TTS y retoma tras sus confirmaciones. Contraer el panel
no apaga la guiada; Detener/Apagar mic sí. Ocultar, recargar, salir de estas vistas,
errores o resultado incierto apagan sin restauración desde almacenamiento. Máximo
móvil20 inicios/5min y dos reconexiones cortas consecutivas, con renovación por
escucha saludable o final válido; no se promete escucha ilimitada. Legacy conserva
su TTL300s. Registro textual/preferenciaoff continúanv3, sin audio ni patrones nuevos.

Validación completada:

- **76/76 pruebas backend** de lenguaje, vocativos, endpoint, UIAction, guía y
  memoria; el corpus de210 casos se ejecuta en sus subpruebas. `manage.py check`
  y sintaxis de los scripts modificados correctos.
- **10/10 bloques frontend** con dobles: continuidad, eventos tardíos, pausa TTS,
  Stop/hidden/error, renovación y límite móvil; sin audio físico ni modelos.
- **8/8 bloques reales Django/SQLite aislada/Edge**: una sola apertura humana
  →«hola chica abre eventos»→«ahora calendario»→«directorio», misma instancia de
  documento y sesión, máximo un reconocedor. Estilos, teclado del calendario,
  filtros GET/atrás/adelante, nombre Chica propio, panel contraído, Stop y clic
  posterior cancelado sin reutilizar un resultado anterior comprobados.
- HTML adversarial con identidad distinta, script en main, HTMX al cargar o enlace
  externo se rechaza sin cambio ni falso éxito; scripts del head no se importan.
  Cero errores JS/consola/CSP, solicitudes externas o automáticas prohibidas.
- Diez recibos y27 registros sintéticos; cero Jobs, AIUsage o patrones creados.
  Servidor QA cerrado y base aislada eliminada. Capturas de memoria inspeccionadas
  a1440×1050 oscuro y390×844 claro, sin desbordamiento horizontal.

Evidencias: `Temporal/qa-gica-fluency/frontend/results.json` e
`integration/results.json`; capturas `integration/fluency-desktop.png` y
`fluency-mobile.png`. Browser plugin no disponible; se usó Edge separado con
Playwright ya instalado y reconocimiento/síntesis simulados. No acredita calidad
del reconocimiento, audibilidad o latencia física ni concurrencia PostgreSQL.
Ante fallo de navegación, la memoria puede conservar el estado previo y el recibo
fallido sin el mensaje terminal específico; el recibo visible evita afirmar éxito.

SparkX reiniciado con el lanzador normal: salud200 y siete activos servidos idénticos
a disco; **19 tablas preservadas** sin migraciones ni trabajos/acciones en curso al
reiniciar. Comprobantes `runtime-preserved.json` y `served-assets.json`. Recargar
Ctrl+F5, abrir Gica y aceptar aviso v5/permiso inicial si aparecen. El recorrido se
usa sin claves ni tokens de modelos. Los cortes siguientes son evidencia histórica.

## Corte anterior: orden clara, dos segundos y ejecución directa

La instrucción más reciente de Jorge sustituye el turno de confirmación: una
orden clara por voz se ejecuta tras2000ms sin cambios de texto, sin «¿Procedo?»
ni sí posterior. Ambigüedad/datos ausentes preguntan. Texto guiado sigue manual.
Aviso guiado v4 explica el cambio; registro/preferenciaoff conservan su contratov3.

Se retiró el estado de confirmación del flujo vocal principal. `readyOrder`
inmutable vincula borrador, intención permitida, generación y sesión; sólo el
resultado ready válido pasa al formulario/runner normal. El servidor reinterpreta
y autoriza, con actor vigente, CSRF, TTL, cancelación antes del clic y acuse del
destino. No amplía las seis acciones ni cambia aprobación de planes/tareas o APIs.
No hay preámbulo hablado antes del despacho; el feedback se habla al finalizar
con micrófono pausado. Una respuesta tardía, error o resultado incierto no reintenta.

Validación focal:33/33 pruebas backend (17 memoria+16 guía),9/9 bloques frontend
con dobles y7/7 integración Django/SQLite aislada/Edge. **«Jica, abre eventos»**
navegó a la lista real y confirmó un único recibo; recargar no repitió clic ni
reactivó micrófono. Tema claro→oscuro ejecutó un clic sin sí; consulta de guía
a2002ms del texto final, sin voz previa. Se probó aclaración de persona→Jica→
búsqueda real, negación sin acción, texto manual y memoria en escritorio/móvil.
Los9 focales cubren aviso viejo, edición/Stop/hidden, callbacks tardíos, exclusión
mic/TTS, no-ready, runnerrechazado e incertidumbre sin repetición.

Evidencia en `Temporal/qa-gica-autodirect/results.json` e `integration/results.json`,
con capturas en esa integración. Sin errores JS/consola/CSP, peticiones externas,
modelos ni audio/micrófono físicos; servidor QA cerrado y DB aislada eliminada.
SparkX reiniciado con lanzador normal: salud200, dos activos nuevos idénticos a disco
y19 tablas preservadas, sin migraciones. Comprobantes `served-assets.json` y
`runtime-preserved.json`. Recargar Ctrl+F5 y aceptar el aviso actualizado al abrir
Gica si corresponde. El cursor conserva su animación y cancelación del runner;
los2s miden el inicio del despacho, no toda la carga del destino o audio físico.

## Entrega anterior: tres segundos de texto estable

Jorge confirmó conservar «¿Procedo?» antes de ejecutar. La guía espera3000ms
desde el último cambio del texto transcrito normalizado, no desde speechend.
Se muestra escritura provisional; ruido sin texto y repeticiones idénticas no
inician ni reinician el plazo. Una palabra nueva/corregida sí lo reinicia. Mientras
haya parciales pendientes no se despacha un fragmento anterior. Promover texto
idéntico a definitivo conserva el plazo; el máximo30s sólo empieza cuando hay texto.
Ruido que produzca palabras nuevas sigue contando como cambio de transcripción.

Mapas RAM acotados por turno/ticket/índice se limpian entre turnos; los originales
y nombres propios se conservan. `text_change_to_dispatch_ms` se admite como
duración relativa0..120000ms, sin nueva migración ni autoridad. Se mantiene el
borrador exacto durante confirmación y sólo un sí inequívoco posterior ejecuta.

Validación actual:17/17 pruebas backend de memoria,8/8 bloques focales de texto
y ruido,10/10 integración real Django/SQLite aislada/Edge con dobles de voz.
La integración midió3012ms desde el último cambio estable aun con señal posterior
de ruido, y3010ms tras una corrección de texto. No acredita micrófono físico.
Focales probaron promoción idéntica sin otro3s, parciales pendientes, turnos nuevos,
nombre Jica como persona y ruido sin texto durante31s simulados. Sin errores
JS/consola/CSP, solicitudes externas, modelos o audio real; QA aislado cerrado.

Evidencia en `Temporal/qa-gica-textidle/results.json` e `integration/results.json`;
capturas de memoria de escritorio/móvil en esa integración. SparkX reiniciado:
salud200, dos activos nuevos idénticos a disco y19 tablas existentes conservadas,
incluida la memoria, sin trabajos/acciones en curso al reiniciar. Comprobantes
`runtime-preserved.json` y `served-assets.json`. Recargar con Ctrl+F5. El servicio
del navegador puede añadir latencia y transcribir ruido como palabras.

## Ajuste anterior: pausa de1,5 segundos y nombre visible Gica

Por solicitud de Jorge, `silenceMs=1500` sustituye3000ms. Conserva anclaje al fin
de voz observado, estabilidad150ms, bloqueo de intermedios y confirmación en otro
turno. Se actualizaron aviso, instrucciones y caché de activos. El reconocimiento
y la síntesis pueden añadir tiempo; no es una promesa de respuesta audible en1,5s.

El campo guiado, conversación y propuesta de patrón muestran el vocativo normalizado
**Gica**. Antes se enviaba correctamente normalizado, pero se mostraba texto crudo
como «Jica» en esas superficies. Búsquedas y slot person_name conservan personas
llamadas Jica. Memoria muestra primero el texto interpretado y ofrece la transcripción
original en un detalle desplegable; no se alteran los registros originales.

Validación:5/5 bloques visuales y10/10 bloques de integración real Django/SQLite
aislada/Edge con reconocimiento y síntesis simulados. Confirma Jica→Gica visible,
original preservado, nombres de persona intactos, confirmación separada, registro,
revisión y borrado. Escritorio1440×1050 oscuro y móvil390×844 claro sin desbordamiento,
errores JS/consola/CSP o solicitudes externas. No llamadas a modelos ni audio físico.
El harness espera el nuevo DOM tras la redirección de revisión antes de verificarlo.

Evidencia vigente en `Temporal/qa-gica-pause15/`: `visual-results.json`, capturas
`normalized-desktop.png`/`normalized-mobile.png` y `integration/results.json` con
mediciones. SparkX reiniciado con lanzador normal, salud200, cuatro activos servidos
idénticos a disco y19 tablas preservadas, incluida la memoria; sin migraciones.
Consultar `runtime-preserved.json` y `served-assets.json`. La latencia física sigue
pendiente de probar en el navegador del usuario.

## Silencio medido, variantes de Gica y memoria para el mentor

Cambio solicitado después del flujo de confirmación: la espera se ancla al fin
de voz observado por el navegador más3000ms. Transcripciones finales y audioend
tardíos no reinician otros tres segundos; si el final llega vencido el plazo,
exige150ms de estabilidad. Un intermedio pendiente impide despachar un fragmento
final anterior; el turno máximo sigue en30s. Sin speechend, los tiempos se marcan
estimados. Se muestran duraciones relativas de consulta/respuesta/síntesis, no
una medición del silencio físico. El movimiento del cursor conserva sus pausas
deliberadas500+1800ms, separadas de la espera vocal.

Normalización finita de Gica/Jica/Yica/Yika/Llica/Ilica como vocativos y controles.
No sustituye nombres dentro de búsquedas o del slot person_name: «Busca a Yika»
y la aclaración «Yika» conservan la persona. Confirmaciones con variantes mantienen
las guardas existentes, sin aceptar condiciones, citas, dudas ni órdenes mezcladas.

**Memoria de Gica**, `/assistant/memory/`, guarda interacciones textuales finalizadas
cuando el registro está habilitado: original, normalización, respuesta, borrador,
intención, resultado declarado y tiempos. Es del propietario, con CSRF, humano/rol
vigentes, agentes denegados, JSON estricto, idempotencia y hasta1000 registros sin
purga automática. El aviso guiado v3 explica el cambio; texto muestra el aviso antes
del envío. Desactivar se recuerda por cuenta/v3 en este navegador. Sin audio,
resultados intermedios, proveedores, Jobs, AIUsage o activación de patrones.
Se ocultan formatos reconocibles de claves; no es detección universal de secretos.
Notas de revisión y sugerencias se separan de los patrones ejecutables. El mentor
consulta registros al trabajar sobre ellos mediante `gica_memory`; no permanece
observando en segundo plano. Las declaraciones del cliente no dan autoridad ni
demuestran éxito físico. Un POST incierto no reintenta; cola RAM limitada/salida
pueden dejar registros sin guardar y se informa esa posibilidad.

| Comprobación focal actual | Resultado |
| --- | --- |
| Backend |51/51:16 memoria,3 vocativos,9 lenguaje,16 guía/patrones,7 endpoint |
| Lenguaje puro JS |88 normalizaciones y66 confirmaciones |
| Navegador con dobles locales |11/11 bloques de tiempos, intermedios, errores, controles, preferencias y nombre aclarado; repro manual adicional satisfactorio |
| Integración real Django + SQLite aislada + Edge |10/10 bloques: registro, revisión, eliminación, off persistente, error de guía, confirmación y orden manual |
| Identidad/contenido/overlay/consola/CSP/red |Página correcta y significativa; sin overlay, errores JS/consola/CSP ni solicitudes externas |
| Capturas |1440×1050 oscuro y390×844 claro, inspeccionadas, sin desbordamiento horizontal |
| Configuración/esquema/runtime |check y makemigrations sin incidencias;0004 aplicada con respaldo; salud200 y6 activos idénticos a disco |

En la integración final, el despacho se observó a **3004ms** de speechend con final
tardío; otro final recibido después del plazo se despachó a los **160ms** de
recibirlo (**3567ms** desde speechend). Son escenarios sintéticos medidos en Edge,
no latencia del micrófono del usuario ni una garantía general. Dos UIAction se
completaron en DB aislada, sin patrones/Jobs/AIUsage; servidor cerrado y DB eliminada.
El harness manual se corrigió para esperar el fin del runner antes de exigir
ambos registros, en vez de asumir que emitir el clic ya completaba el acuse.

Evidencia útil en `Temporal/qa-gica-mentor/`: `frontend/timing-results.json`,
`language-results.json` y `manual-results.json`; `integration/results.json` y
capturas `memory-desktop.png`/`memory-mobile.png`. Plugin Browser no disponible;
se usó Edge/Playwright separado previamente autorizado, sin micrófono/audio físicos.
Auditoría independiente cerró cuatro huecos: logs de errores/controles, aliases
en confirmación, preferencia off al navegar y nombre de persona con forma de alias.

SparkX quedó reiniciado con su lanzador normal. Antes del reinicio había cero
Jobs/UIAction en curso. `before-mentor.sqlite3` es respaldo anterior a0004;
`runtime-preserved.json` confirma18 tablas existentes idénticas en todos sus campos,
sin cambiar usuarios, planes, tareas o contabilidad. La nueva memoria activa empezó
vacía, sin fixtures de QA. `served-assets.json` acredita salud200, ruta privada302
sin sesión y seis activos nuevos servidos. Las conexiones API efímeras se descartan
al reiniciar; no se recuperaron claves ni se hicieron inferencias.

La comprobación física de reconocimiento, silencio percibido, volumen y voz en la
sesión del usuario sigue pendiente. PostgreSQL sigue siendo necesario para validar
locks/concurrencia distribuida; SQLite sólo acredita este recorrido local.

## Entrega anterior: Gica por clic, saludo y confirmación sí/no

Por solicitud posterior de Jorge, el flujo principal empieza al **abrir Gica
con un clic**: aviso guiado v2 y permiso si corresponden → saludo por el usuario
SSR («Hola, adminjorge») → escucha directa. Ya no exige Gica hablemos ni Gica
ejecuta. Un clic sintético, carga de página o restauración de preferencias no
inicia escucha. Reanudar conversación reemplaza el botón Activar voz rápida.

La actividad de habla/intermedios reinicia la espera de **3000ms**. La pausa
sólo consulta la guía local; si hay una orden lista, muestra el borrador y dice
«¿Procedo a ejecutarlo?». La respuesta se recoge con otro reconocedor/ticket
después de pausar micrófono durante la pregunta. Sí/si y no cuentan como palabras
completas con acompañantes naturales; ambas, dudas, citas, reporte, condición,
negación contradictoria u otra orden no ejecutan. El sí/no de la petición
inicial nunca autoriza. Confirmación ligada a borrador, intención, cuenta,
generación y ticket; al cambiar la petición debe obtenerse otra confirmación.
El runner y los seis permisos existentes siguen comprobándose en el servidor.

El clasificador puro `static/js/gica-confirmation.js` pasó **60/60 casos**:
acompañantes, acentos y fronteras Unicode; condiciones y cancelaciones mezcladas;
«así», «siguiente» y «sino» no son sí. **23/23 pruebas backend** focales pasan
para guía/memoria y endpoint. Node comprueba los cinco JS implicados; check y
makemigrations sin incidencias. La voz sigue local y el reconocimiento puede usar
el servicio del navegador. Sin modelos ni cambios de presupuesto.

El saludo sólo incorpora el username SSR validado de1–60 caracteres; no lee
personas buscadas ni contenido remoto. El inicio vocal nuevo limpia el slot de
otra conversación; el modo de texto conserva sus aclaraciones entre clics.
Se conservan300s,20 inicios/dos reconexiones normales y parada al cerrar/ocultar/
navegar/recargar/Escape/laboratorio. Un turno abierto más de30s termina sin
ejecutar. Se conserva revisión explícita para memoria, sin audio ni guardado
automático de conversaciones.

QA de interfaz: **14/14 bloques** con Django y runner reales en SQLite aislada,
reconocimiento/síntesis simulados. Un focal posterior de cuatro respuestas sobre
las guardas finales confirmó tres rechazos sin acción y «sí Gica, adelante» con
exactamente un UIAction/un clic; no se suma como otra campaña de14 bloques.
Identidad y contenido de página correctos; sin overlay, errores JS/consola/CSP
o solicitudes externas. Escritorio1440×1050 oscuro y móvil390×844 claro,
pregunta visible, sin desbordamiento. Se corrigió la clase que anulaba hidden en
el selector antiguo; Terminar conversación permanece visible como control de parada.

SparkX se reinició con el lanzador normal y salud200. Comparación de18 tablas
antes/después conserva todos los campos, incluidos patrones, usuarios, planes,
acciones y contabilidad; seis activos servidos coinciden con disco. Comprobante
`Temporal/qa-gica-confirmation/runtime-preserved.json`. Cero Jobs/UIAction en
curso antes del reinicio, sin cambios de esquema o recuperación de claves.
El reinicio descarta conexiones API efímeras; esta guía no necesita ninguna.

Evidencia actual en `Temporal/qa-gica-confirmation/`: pruebas puras en
`frontend/classifier-results.json`; interacción real Django/UIAction con voces
sintéticas y SQLite efímera en `qa/results.json`; capturas de escritorio oscuro
y móvil claro. El plugin Browser no está disponible: Edge/Playwright separado
ya autorizado. La instalación inicial tardía del reloj en el subcaso TTL del
harness se corrigió antes de continuar; no se cambió el producto para esa prueba.
El lector SQLite del harness se corrigió para cerrar explícitamente sus
conexiones antes de borrar la DB de prueba en Windows; servidor cerrado y DB
aislada eliminada al final. No hay fallos funcionales pendientes de este recorrido.
No se activaron micrófono/audio físicos ni modelos remotos. La prueba física de
reconocimiento, audibilidad y latencia depende de la sesión del usuario.

## Entrega anterior: conversación guiada y memoria revisada

Jorge eligió conversación guiada sin IA remota y guardar únicamente frases
revisadas e intención. Gica-1 ofrece **Conversación guiada local** y
**Conversar por texto**: pregunta por nombre o tema, prepara la orden canónica
visible y espera confirmación en otro turno o el botón ordinario. La pausa de
700ms sólo consulta reglas; nunca ejecuta. El modo guiado requiere inicio
explícito y permiso del navegador, conserva300s/20 inicios/dos reconexiones
normales y termina al cerrar el panel, ocultar, navegar o recargar. Micrófono
invalidado antes de síntesis o acción; respuestas tardías no rearman la sesión.

Sólo seis funciones: tema claro/oscuro, abrir calendario/directorio/eventos y
buscar personas. No crea eventos, cambia tareas/planes ni administra cuentas o
APIs. `/assistant/guide/` es de lectura: sobre estricto de cinco campos y dos
slots de aclaración; sin modelos, Jobs, UIAction, AIUsage o guardado de turnos.
Hasta seis intercambios permanecen sólo en RAM/DOM. El reconocimiento del
navegador puede usar un servicio remoto; local describe las reglas y la síntesis
seleccionada, no una garantía de transcripción offline ni escucha ilimitada.

**Revisar frase como patrón** abre un diálogo editable con intención de seis
valores y casilla inicialmente desmarcada. Sólo Guardar persiste, con CSRF y rol
humano vigente. **Mis patrones** gestiona hasta200 frases privadas por cuenta,
con eliminación e idempotencia. La alternativa exacta normalizada no reemplaza
una orden entendida ni un rechazo; se repiten las guardas al guardar y consultar.
Sin audio, transcripción completa, cambio de pesos o aprendizaje automático.
Cancelar no escribe; cerrar tras enviar informa honestamente que debe comprobarse
la lista, porque abortar el cliente no garantiza deshacer el POST.

Validación de esta entrega:

| Comprobación | Resultado |
| --- | --- |
| Backend focal |53/53:16 guía/memoria,9 lenguaje,7 endpoint,21 recibos de acciones |
| Navegador con dobles de voz/servidor |13/13 bloques: consentimiento, ejecución separada, carreras/abort, límites, errores, legado y memoria |
| Integración real Django + SQLite aislada + Edge |8/8 bloques, formularios CSRF HTML/JSON, aclaración y borrador, cancelar/guardar/eliminar y móvil |
| Identidad, contenido, errores y consola/CSP | Pasa; página significativa, sin overlay, errores JS/CSP o solicitudes externas |
| Escritorio y móvil |1440×1000 memoria clara; fixture oscuro y390×844 claro; capturas inspeccionadas, sin desbordamiento horizontal |
| Configuración/sintaxis | `check`, `makemigrations --check --dry-run`, tres JS `node --check` correctos |
| Estado real | Migración assistant0003 aplicada, salud/activos200 y17 tablas existentes preservadas |

Browser plugin no disponible; se usó Edge/Playwright separado ya autorizado.
La integración real verificó `/assistant/patterns/` → guardar revisión HTML →
Gica/búsqueda incompleta → nombre → borrador sin ejecutar → cancelar revisión →
revisar/editar/guardar por JSON → eliminar por formulario. La DB aislada se
eliminó y los servidores QA se cerraron. Las primeras iteraciones corrigieron el
harness de QA (ORM dentro del loop Playwright, cola del servidor y reapertura del
panel); no son fallos de inferencia ni datos reales. Se corrigió una carrera de
Probar voz durante debounce antes de cerrar los13 bloques frontend.

Evidencia útil en `Temporal/qa-gica-conversation/`: `integration-results.json`,
`frontend/results.json`, `served-assets.json`, capturas `memory-desktop.png`,
`memory-mobile.png`, `guide-review-desktop.png` y frontend guiado. Respaldo
`before-conversation.sqlite3`; `configuration-preserved.json` comprueba todos
los campos de17 tablas, incluidos presupuesto, políticas, usuarios, eventos y
tareas. El proceso propio anterior se detuvo con cero Jobs activos antes del
respaldo/migración; SparkX se reinició con su lanzador normal. Las claves efímeras
no se leyeron ni recuperaron. Jobs0, AIUsage0, recibos UIAction3 conservados,
memoria personal inicialmente vacía. No hubo llamadas a modelos, gasto API,
audio reproducido o micrófono físico en estas pruebas. PostgreSQL/concurrencia
distribuida, calidad perceptual y reconocimiento físico siguen pendientes.

Uso: **Ctrl+F5 → Gica-1 → Conversación guiada local → Iniciar conversación**.
Para usar sólo teclado, escribe en Tu orden y pulsa **Conversar por texto**.
**Mis patrones** abre la memoria. La guía local no necesita clave API.

## Nombre vigente: Gica-1

Por petición de Jorge, Romeo-1 pasa a llamarse **Gica-1**. Panel, cursor,
conversación, administración de IA, textos de ayuda, consentimiento, lanzador y
respuestas habladas usan el nombre nuevo. La documentación de uso se actualizó;
los apartados inferiores conservan la evidencia histórica. No se renombraron
personas, mensajes/peticiones, instantáneas financieras o títulos históricos de
eventos. Rutas, código durable `romeo-1`, nombres de módulos, IDs y claves de
preferencia/consentimiento siguen siendo compatibles.

Los comandos primarios son **Gica hablemos / Gica ejecuta / Gica cancela / Gica
silencio**. Las variantes precisas GICA/Jica/Yica y Gica uno/1/-1 comparten los
mismos controles acotados; los aliases antiguos exactos quedan internos. Banco
de intenciones .2 con120 ejemplos sintéticos; no se amplían las seis acciones,
permisos o límites de micrófono. Negaciones, citas y comandos mezclados no envían.

`ai_management.0006_gica_display_name` aplicada tras cerrar el proceso propio sin
Jobs activos y respaldar SQLite. Sólo cambia el default y etiquetas generadas
exactas. Fingerprints antes/después comprueban17 tablas: se conservaron todos los
campos fuera de los nombres permitidos, incluidos identidad, versiones, límites,
políticas, reservas, perfiles, planes/tareas, eventos, usuarios y mensajes. No se
ejecutó `prepare_romeo` para este cambio ni se creó otro presupuesto. Respaldo y
comprobantes en `Temporal/qa-gica-rename/`; copia previa útil para revisión.

Pruebas focales: **41 backend**, **3 del lanzador** y **9 bloques de navegador**
aprobados. Raíz repitió también los7 casos de `test_romeo` ya incluidos en41;
no contarlos como nuevos. Los3 tests de migración se revalidaron tras el ajuste
final de alias de BD. `check`, `makemigrations --check --dry-run` y sintaxis de
los6 JS cambiados correctos. Navegador Edge/Playwright separado, plugin Browser
no disponible: JS reales con reconocimiento/síntesis/media/runner simulados,
escritorio1440×1050 oscuro y móvil390×844 claro, capturas inspeccionadas y sin
errores JS/CSP ni desbordamientos. Servidor QA detenido y DB de tests destruida.

Se regeneró la muestra Davefx: «Hola, soy Gica. Vamos a organizar tu próximo
evento.», WAV170028B/3.855s, con nueva procedencia/hash y URL de caché `gica1`.
Una inferencia TTS local, sin audio reproducido/micrófono ni API. El servicio real
devuelve200 para salud/JS/CSS/WAV y Edge decodifica la metadata3.854512s sin
reproducir. Pruebas de calidad perceptual y reconocimiento físico pendientes.

SparkX reiniciado con el lanzador normal, web y worker en el mismo proceso;
salud200, cero Jobs y AIUsage. Las claves efímeras no se leyeron ni recuperaron:
volver a introducirlas privadamente si se necesita inferencia remota. **Ctrl+F5**
carga Gica-1 y los comandos nuevos, conservando la preferencia local de voz.

## Voces instaladas de Windows y muestra local Piper

Jorge autorizó intentar instalaciones oficiales y confirmó haber instalado
Jorge y Álvaro desde el Narrador. Se instalaron por DISM las capacidades
`Language.Basic~~~es-MX~0.0.1.0` y `Language.TextToSpeech~~~es-MX~0.0.1.0`
desde Windows Update: ambas finalizaron con código0; el registro final de DISM
indica **Reboot required=no**. No se cambió la política de ejecución ni se
editaron claves del registro para forzar exposición. El ayudante PS1 que no se
usó se eliminó; comprobantes útiles en `Temporal/voces-windows/`.

| Opción | Resultado real |
| --- | --- |
| Raúl y Sabina, español de México | Instalados y expuestos como locales por Edge y Chrome nuevos/aislados |
| Pablo, Laura y Helena, español de España | Siguen disponibles; ya existían antes de esta instalación |
| Jorge y Álvaro naturales | Instalación confirmada por el usuario; no expuestos en ninguno de los dos navegadores comprobados |
| Piper · Davefx | Una muestra WAV generada localmente y añadida al comparador; todavía no es una voz para las respuestas de Romeo |

Seguimiento posterior: Jorge indica que Raúl y Sabina no aparecen en su lista.
Un segundo inventario de Edge y Chrome nuevos vuelve a mostrar las cinco voces
locales. Los24 procesos personales de Edge observados arrancaron entre el14de
noviembre20:28:09 y22:16:27, antes de instalar las voces. Es coherente con un
catálogo nativo retenido, sin observar directamente su pestaña. Los activos
públicos del servicio coinciden con disco. Se indica guardar trabajo y reiniciar
Edge completo mediante `edge://restart`, [atajo documentado por Microsoft](https://learn.microsoft.com/en-us/ecdn/how-to/disable-mdns#solution),
y después Actualizar voces. No se cerró el navegador del usuario ni se reinició
SparkX. Confirmación en su sesión todavía pendiente; no se repitieron inferencias.

`browser-inventory.json` registra las cinco voces y selección automática Raúl en
una sesión sin preferencia guardada. No se cambió la elección de la cuenta real.
Cero llamadas a síntesis, micrófono o solicitudes de página durante ese inventario.
Una consulta alternativa a `SpeechSynthesizer.AllVoices` devolvió **Internal
Speech Error**: no acredita compatibilidad ni justifica añadir un puente nativo.
Las voces naturales se documentan también para Lupa; no afirmar que son exclusivas
de Narrador. Su instalación no demuestra que `getVoices()` las publique.

Se descargó Davefx desde una revisión fija del repositorio oficial de voces;
el SHA-256 del ONNX coincide con la metadata LFS. Su tarjeta actual identifica
dataset CC0 y base rdh CC0. Se descartó Ald para esta muestra al no acreditar
la cadena completa de su versión. Piper no concede una licencia general sobre modelos:
conservar la procedencia en `static/audio/romeo/NOTICE.txt`. El motor Piper1.8.0
(GPL-3.0-or-later), modelo y dependencias permanecen en un entorno de prueba
separado dentro de `Temporal/voces-piper/`; no se añadieron a Django ni a sus
dependencias. Siete wheels revisados contra origen/hash, versiones retiradas y
avisos publicados de PyPI, con versiones y hashes fijados; esa revisión no es
una garantía de ausencia de vulnerabilidades ni un sandbox del sistema operativo.

Una sola inferencia TTS local produjo la misma frase del comparador: WAV mono
22050Hz/16bit, **3.843s y169516bytes**. Medición de esa ejecución: carga fría6.894s,
síntesis5.554s, pico de memoria del proceso174.4MiB; CPU, dos hilos internos y uno
externo, sin GPU. No son garantías de latencia o capacidad. No hubo llamada a
modelos remotos, tokens API, servicios de pago, escucha ni reproducción física.

El laboratorio añade **Escuchar Davefx / Detener muestra**, ruta fija del mismo
origen, sin autoplay ni descarga al abrir. Distingue la muestra de la selección
nativa: no la guarda ni la adopta. Cancelación al cerrar/Escape/ocultar/salir,
cambiar de muestra, dictado o lectura; nodo/ticket por intento y límite15s.
**8/8 bloques Edge/Playwright aprobados**, con media/síntesis simuladas:13 intentos
media y1 preview nativo, cero micrófono/persistencia/errores JS/CSP/red externa.
Fixture estática sin Django/DB; escritorio1440×1100 oscuro y móvil390×844 claro,
capturas inspeccionadas, sin desbordamiento. Servidor QA detenido. Evidencia en
`Temporal/qa-romeo-piper-preview/`.

Verificación adicional del servicio real: salud, JS, CSS y WAV responden200;
hash del WAV servido coincide y Edge decodifica metadata3.842902s, silenciado y
pausado, sin `play()` ni incidencias CSP. Comprobante en
`Temporal/voces-piper/served-sample.json`; generación en `sample-receipt.json`.
Syntax check de los dos JS cambiados correcto. Sin cambios de modelo de datos,
backend o dependencias del servidor; sin reinicio de SparkX ni acceso a claves.

Para probar: cerrar y abrir el navegador si no recoge las voces nuevas,
**Ctrl+F5 → Romeo-1 → Comparar voces → Actualizar voces**. Las cinco voces
nativas admiten elegir/guardar; Davefx sólo admite escuchar la muestra. Falta
escucha humana para comprobar audibilidad y preferencia; no se acredita calidad
perceptual por un WAV válido. La primera inferencia LLM real del piloto sigue
pendiente y es independiente de esta prueba TTS.

## Romeo-1: laboratorio temporal para comparar y elegir voces

**Romeo-1 → Comparar voces (temporal)** permite comparar catálogo real del
navegador, filtro español/otros idiomas y ritmo85–120 %. Todas las muestras usan
«Hola, soy Romeo. Vamos a organizar tu próximo evento.» Probar o mover el rango
no cambia Romeo; **Usar en Romeo** guarda voz española local y ritmo por cuenta
en este navegador. Restablecer borra la preferencia inmediatamente. Las voces
externas se identifican y bloquean; otros idiomas locales sólo admiten preview.
No se eligió una voz nueva en la cuenta real del usuario.

**9/9 bloques de navegador aprobados**, ejecutados por continuación2+4+3 con
prefijos medidos conservados; no son tres campañas completas. Edge/Playwright
separado porque Browser plugin no está disponible. Sintetizador/reconocedor y
voces ficticios, sin audio real. Se verificaron apertura sin escucha/reproducción,
muestras idénticas, selección frente a guardado, persistencia/recarga/reset,
aislamiento por usuario/versión y almacenamiento inválido, voz ausente sin
sustitución, Stop/Escape/cierre/hidden/pagehide, callbacks viejos y exclusión del
micrófono. Un dictado nuevo o lectura cierra el laboratorio; ninguna muestra
reactiva voz rápida. Fallo de almacenamiento queda indicado como memoria de página.

| Comprobación | Resultado |
| --- | --- |
| Identidad, contenido y ausencia de overlay de error | Correctos |
| Interacción completa | Comparar → guardar → recargar conserva voz y ritmo; reset vuelve a automática |
| Escritorio1440×1000 oscuro y móvil390×844 claro/reducido | Modal y controles legibles, sin desbordamiento |
| Consola, CSP y red externa | Cero incidencias |
| Interpretaciones, UIAction, Jobs, AIUsage y modelos | Cero nuevos registros o llamadas |

Revisión independiente sin hallazgos materiales pendientes y **15/15 casos VM**
del adaptador (persistencia/memoria, IDs/rangos, voz ausente, preview local, remoto
rechazado, cancelación, identidad y límites1s/8s). Node syntax check correcto en
los tres JS. El helper corrigió assertions sobre clics sintéticos de botones
deshabilitados y contadores históricos; no se cambió el producto para ocultar
fallos. No se repitió la suite backend: sólo JS/CSS, sin modelos ni dependencias.

Evidencia: `Temporal/qa-romeo-voice-lab/results.json`, `verify_voice_lab.py`,
`test-speech-preference.cjs` y dos capturas finales `voice-lab-desktop.png` /
`voice-lab-mobile.png`, inspeccionadas. Servidor QA detenido y DB ficticia eliminada.
Principal en8000 con salud200 y assets nuevos servidos; sin reinicio ni lectura
de claves. Jobs0/AIUsage0 y tres UIAction existentes del usuario conservados. Esta evidencia
prueba lógica e interfaz; el usuario debe oír las voces y elegir. No acredita
audibilidad, volumen, permisos nativos o calidad perceptual. **Ctrl+F5** carga
los cambios estáticos; no necesita reiniciar SparkX.

## Romeo-1: preferencia de voz masculina

Por solicitud de Jorge se priorizan voces españolas masculinas Microsoft
identificadas por nombre y variante, manteniendo servicio local. El panel muestra
el nombre real y advierte si sólo hay otra voz local sin género identificado.
Ritmo1.04 y tono original1; no se acredita mayor naturalidad sin escucha humana.
La lista real de Edge aislado devolvió Helena, Laura y **Microsoft Pablo (es-ES)**;
el módulo seleccionó Pablo sin emitir audio ni iniciar el micrófono. El registro
de Windows también identifica Pablo como Male. No se instalaron voces ni se
modificó el registro. Fuente de nombres:
[Microsoft](https://support.microsoft.com/es-es/accessibility/windows/narrator/appendix-a-supported-languages-and-voices).

**6/6 pruebas focales** con síntesis/reconocimiento simulados: preferencia Pablo
frente a Helena, orden determinista, exclusión de remotas, fallback sin atribuir
género, voces tardías/timeout, parámetros, mute y relevo de micrófono. Capturas
1440×1000 oscuro y390×844 claro/reducido inspeccionadas, nombre legible y sin
desbordamiento. Cero errores JS/CSP, solicitudes externas, recibos UIAction,
Jobs/AIUsage o llamadas a modelos. Servidor QA detenido y base ficticia eliminada.
Evidencia en `Temporal/qa-romeo-male-voice/`: `results.json`, `actual-voices.json`,
helper y dos PNG finales. `node --check` correcto en ambos JS cambiados.
Sólo cambia código estático; no se reinició SparkX ni se descartaron claves.
**Ctrl+F5 → Romeo-1 → Probar voz**. Audibilidad y preferencia de ritmo pendientes.

## Romeo-1: sesión disponible y respuestas habladas

Actualización solicitada por Jorge: conservar Voz rápida y saber cuándo Romeo
recibe audio o habla. Esta entrega sustituye la política de apagado tras envío,
cierre de panel o primer fin normal del apartado histórico siguiente. Mantiene
inicio explícito por clic, aviso command-session **v2** y permiso del navegador.
No autoactiva el micrófono al cargar ni restaura sesiones desde almacenamiento.

- Tras una orden que termina en la misma página vuelve a espera. El panel puede
  cerrarse; indicador y **Apagar mic** siguen visibles. Un borrador oculto pierde
  autorización y necesita nueva activación del dictado.
- Sesión absoluta300s, hasta dos reconexiones por fin normal (500/1000ms) y20
  inicios totales. Error, apagado, edición, lectura manual, ocultación, navegación,
  recarga o expiración terminan la sesión. No se reintentan clics ni errores.
- SpeechSynthesis responde con frases fijas breves y una voz española explícita
  `localService === true`. **Probar voz** y **Respuestas habladas** permiten probar
  y silenciar. Sin voz local, sólo texto; espera voces1s y emisión8s como máximo.
- Se aborta e invalida reconocimiento antes de hablar/actuar. Sólo sesión y
  ticket vigentes pueden retomarlo; el runner avisa después de liberar su bloqueo.
  Se conservan las seis acciones, permisos, recibos y aprobación humana existentes.
- `onstart` del reconocedor muestra Esperando audio; eventos de audio/voz/resultados
  habilitan Escuchando/Dictando/Voz detectada. El indicador Romeo habla requiere
  `onstart` de la emisión. Son señales del navegador, no certificación del audio.

**14/14 bloques de navegador aprobados**, Edge/Playwright separado porque Browser
plugin no está disponible. SpeechRecognition y SpeechSynthesis **simulados**,
voces locales/remotas ficticias y reloj virtual para300s; ningún audio real.

| Comprobación | Resultado |
| --- | --- |
| Aviso v2 por usuario, recuerdo y recarga | Aceptación anterior v1/otro usuario no omite aviso; nunca autoescucha |
| Prueba de voz y selección local | No inicia micrófono ni elige voz remota/inglesa como alternativa |
| Indicadores y saludo antes del micrófono | Inicialización, audio, voz detectada y habla se distinguen por callbacks |
| Wake, eco, duplicados y callbacks viejos | Captura suspendida durante TTS; no escriben ni ejecutan resultados inválidos |
| Ejecutar tema y aclarar | Una UIAction real de tema en DB ficticia; respuesta y vuelta a espera tras ambas rutas |
| Cancelar, silencio, mute y sin voz local | Texto preservado/restaurado cuando corresponde; sin nuevas acciones o voz remota |
| Edición, Stop, error y reconexiones | Revocación efectiva; dos reconexiones totales, ningún reintento por error |
| Panel, ocultación, navegación y TTL | Borrador oculto invalidado; no reabre tras fin o resultado tardío |
| Dictado normal/chat y lectura manual | Consentimientos independientes y un dueño de micrófono |
| Móvil, movimiento reducido, APIs/config ausentes | Sin desbordamiento; escritura y voz de prueba disponibles según compatibilidad |
| JS, CSP y solicitudes externas | Cero incidencias |
| Modelos/Jobs/AIUsage | Cero llamadas o nuevos registros de consumo |

Revisión independiente corrigió dos carreras: prueba TTS autónoma aún activa al
iniciar otro dictado, y callbacks de `starting` restaurando dictado al cerrar el
panel. Se invalidan emisión/identidad antes del relevo y captura/borrador antes
de volver a espera. La reprueba incluye ambos casos. Inspección visual detectó
checkbox sobredimensionado por estilos genéricos; se fijó a16px con selector propio.
La comprobación visual focal posterior pasó en1440×1000 y390×844: checkbox16×16,
punta dentro de su anclaje y fuera del badge, controles superiores alcanzables
por hit-testing y sin desbordamiento. `latest_layout` conserva sus mediciones;
se sustituyeron las dos capturas y no se repitieron los14 bloques funcionales.

Evidencia: `Temporal/qa-romeo-speaking/results.json`, helper `verify_speaking.py`,
capturas `speaking-desktop.png` y `speaking-mobile.png`. Dos interpretaciones y
tres POST create/start/finish para una única UIAction, todo en datos aislados.
Servidor QA cerrado y base ficticia eliminada. `node --check` correcto para los
cinco JS implicados y `manage.py check` sin incidencias. No se repitió la suite
backend previa para cambios sin modelos, migraciones ni dependencias nuevas.

Runtime principal reiniciado sin Jobs activos; salud200 y nuevos assets servidos.
Base activa: Jobs0, AIUsage0, dos UIAction del usuario preservadas. No se leyeron
claves; el reinicio descarta las efímeras. La voz local no las necesita.

Documentación primaria consultada:
[SpeechSynthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis),
[localService](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService),
[voiceschanged](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/voiceschanged_event),
[SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).
No se probó micrófono, audibilidad/volumen, permisos nativos ni transcripción real;
`onend` de TTS no acredita que se haya oído. El reconocimiento puede usar un
servicio externo del navegador. Primera inferencia real de proveedor sigue pendiente.
Uso: **Ctrl+F5 → Romeo-1 → Probar voz → Activar voz rápida**.

## Romeo-1: avisos recordables y voz rápida

Jorge solicita evitar permisos/avisos repetitivos y usar «Romeo hablemos» y
«Rome ejecuta». Se conserva el dictado normal y se añade **Activar voz rápida**,
con aviso independiente que explica el envío explícito por voz. Ambos avisos
pueden recordarse por usuario, modalidad y versión en este navegador; sólo se
guarda `accepted`. Permisos del micrófono siguen perteneciendo al navegador.
Nunca se guarda una sesión activa, audio o transcripciones en ese almacenamiento.

Máquina de estados apagado → consentimiento → iniciando → espera → dictado.
Frase final exacta de activación, orden en otro turno y frase final exacta de
ejecución. Antes del envío se aborta el reconocimiento, invalida su generación y
se retira el bloqueo de escucha; sólo entonces se envía el borrador visible
idéntico por el formulario existente. El intérprete y los seis `UIAction` conservan
sus validaciones. No permite crear eventos, aprobar planes/tareas o administrar.
**Romeo cancela** restaura el texto previo si no fue editado; **Romeo silencio**
apaga la sesión. No hay escucha de palabra clave con micrófono apagado.

**14 bloques de QA aprobados**, tres iniciales y once de continuación; se conserva
el prefijo medido, no se presenta como dos campañas completas. Edge/Playwright
separado porque Browser plugin no está disponible. Viewports1440×1000 oscuro y
390×844 claro, con movimiento normal/reducido. Reconocimiento y eventos de
visibilidad simulados; expiración300s con reloj virtual, sin esperar cinco minutos.

| Comprobación | Resultado |
| --- | --- |
| Identidad, pantalla con contenido y aplicación sin overlay | Correctos |
| Aviso y recuerdo | Cancelar no inicia reconocimiento; checkbox opcional; claves de otra versión/usuario no omiten el aviso actual |
| Inicio y recarga | Nunca escucha sola; recuerdo del aviso no restaura sesión |
| Frases finales exactas | Intermedios, citas, negación y comandos mezclados no escriben ni ejecutan |
| Borrador y envío por voz | Cero POST antes de ejecutar; sólo borrador capturado idéntico llega al intérprete |
| Duplicados, callbacks tardíos y varios finales juntos | Sin repetición ni ejecución del lote |
| Cancelar, silencio, edición manual y borrador ausente | Sin acción; edición invalida la autorización capturada |
| Fin, error, ocultación, recarga y navegación | Micrófono apagado, sin reinicios automáticos |
| Dictado normal/chat y voz rápida | Un reconocedor activo; flag de escucha y submit bloqueado conservados |
| Sin API de reconocimiento/config inválida | Apagado y entrada manual disponible |
| Límite300s | Finaliza y no reabre con reloj virtual |
| JS, CSP y red externa | Cero errores y solicitudes externas en QA |
| Modelos, audio real, Jobs y AIUsage | Cero llamadas, audio real o nuevos registros |

Una revisión independiente encontró y corrigió una carrera de coexistencia: el
evento de relevo del micrófono se emitía después de marcar el dictado normal como
activo, y apagar voz rápida retiraba esa marca. Ahora se emite antes de marcar y
se revalida el estado antes de arrancar. QA confirmó mismo campo escuchando con
submit deshabilitado. Se notifica el cambio de tamaño del badge Mic activo/Dictando
al posicionador del cursor para que mantenga su anclaje tras el reflujo.

Evidencia en `Temporal/qa-romeo-handsfree/results.json`, helper reproducible
`verify_handsfree.py` y capturas finales `handsfree-desktop.png` y
`handsfree-mobile.png`. Un error de evaluación del helper se corrigió antes de
continuar; no se modificó el producto para acomodarlo. Bases ficticias eliminadas
y servidores de QA cerrados. `node --check` correcto para app/actions/voice y
`manage.py check` sin incidencias. No se repitió la suite Python anterior: cambio
de JavaScript/plantillas sin modelos, migraciones ni nuevas dependencias.

Documentación primaria consultada el15nov2026:
[permiso de Chrome](https://support.google.com/chrome/answer/2693767?hl=es),
[SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)
y [continuous](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/continuous).
La compatibilidad y duración nativa dependen del navegador; puede existir
reconocimiento remoto. La evidencia ficticia no prueba permisos nativos,
micrófono físico, precisión de transcripción ni duración real. Tampoco acredita
reconocimiento de hablantes, escucha offline/ilimitada o asistente del sistema.

Comprobación focal visual posterior correcta: la punta del cursor permanece
dentro de su anclaje y fuera del badge de voz en escritorio y móvil. Capturas
finales sustituidas; resultados en `latest_layout`, sin repetir los14 casos.
Runtime propio reiniciado sin Jobs activos; `/health/`200 y JS/configuración de
voz nuevos servidos. Jobs0/AIUsage0 y los dos UIAction existentes del usuario
preservados; ninguna escritura operativa de QA en la base activa. No se leyeron
claves y el reinicio descarta las efímeras. Para utilizarlo: **Ctrl+F5 → Romeo-1 →
Activar voz rápida**, con micrófono físico aún pendiente de comprobación.

## Romeo-1: banco JSON de lenguaje e intenciones

Por solicitud de Jorge se incorporó vocabulario declarativo y un intérprete local
en el servidor para frases naturales de **Tu orden**. Conserva las seis acciones
ya permitidas: no concede nuevas herramientas al modelo. Sinónimos, saludos,
cortesía, muletillas y destinos se separan de la consulta de persona. Por ejemplo,
`hola abre nose calendario` se interpreta como abrir Calendario; `búsqueda de
Jorge en mi directorio` busca Jorge conservando permisos. Los scopes del directorio
sólo se retiran de los bordes del nombre, no de su interior.

Banco `apps/jobs/data/romeo_intents.es.json`, versión `es-2026-11-15.1`, con
validación estricta como datos finitos. Corpus
`apps/jobs/data/romeo_intent_examples.es.json`: **108 casos sintéticos**, de los
cuales 51 deben entenderse, 30 aclararse y 27 rechazarse. No es ajuste de pesos,
aprendizaje automático de frases privadas ni una medición de todo el español.
Contrato y proceso de ampliación en [romeo-language.md](arquitectura/romeo-language.md).

| Comprobación | Resultado |
| --- | --- |
| Suite Django afectada | 616 casos: 611 correctos, 5 omitidos por PostgreSQL; cero fallos, 64,979 s |
| Regresión pura final | 8 pruebas, 108 ejemplos del corpus, correctas; 0,084 s |
| Endpoint local | 7 pruebas incluidas en la suite: sesión/rol vigentes, POST/CSRF, ContextVar y ninguna ejecución |
| Navegador aislado | 12 bloques consolidados en tres continuaciones de cuatro; no una segunda campaña única |
| Navegación y tema naturales | Interpretación antes del recibo y de un único clic autorizado |
| Aclaración | Pregunta sin UIAction; elegir opción sólo rellena texto y conserva foco/panel; Enter manual ejecuta |
| Búsqueda explícita en directorio | Query Jorge, dos personas propias ficticias, registro ajeno excluido |
| Negación, órdenes múltiples y administración | Rechazo o aclaración sin clic ni UIAction |
| JSON inválido, enum/query/controles inválidos | Sin despacho de acciones |
| Cancelar interpretación lenta | Respuesta tardía ignorada, ninguna acción |
| Dictado | Reconocimiento simulado sólo prepara borrador; sin audio real |
| Escritorio/móvil | 1440×1000 oscuro y 390×844 claro; opciones utilizables y sin desbordamiento horizontal; movimiento reducido navega una vez |
| JavaScript, CSP y red externa | Cero errores y solicitudes externas en QA |

Las pruebas puras finales incluyen una prueba añadida durante el descubrimiento
de la suite general; son evidencia focal con solapamiento, no otros ocho casos
independientes para sumar a 616. El alias `nose` se comprobó en corpus/smoke local;
la navegación de navegador utilizó la variante `no sé`. El corpus es diseñado por
el equipo, no un conjunto independiente de conversaciones reales.

Se corrigió un defecto de interfaz encontrado por QA: retirar el botón de opción
durante su clic hacía que el manejador global lo interpretase como un clic fuera
del panel. Ahora se detiene esa propagación y el campo conserva el foco. También
se corrigieron dos aserciones del helper de QA —conteo de interpretaciones tras
una aclaración y firma del callback Playwright—, sin modificar el producto para
acomodarlo a esas aserciones.

Evidencia en `Temporal/qa-romeo-language/`: `results.json`, `verify_language.py`,
`language-tests.txt`, `verification.txt` y las dos capturas finales
`language-desktop.png`/`language-mobile.png`, inspeccionadas. Browser plugin no
disponible; se empleó Edge/Playwright separado previamente autorizado. Servidores
de QA cerrados y bases ficticias eliminadas. No se probó micrófono físico,
inferencia remota, otros navegadores ni carreras distribuidas con PostgreSQL.

`POST /romeo/interpret/` es sólo lectura: no memoriza frases, consulta personas o
crea Jobs/AIUsage/UIAction. La acción inequívoca sigue pasando por los recibos y
autorizaciones ya existentes. El campo admite 300 caracteres y la consulta de
persona conserva su límite100. Las aclaraciones no guardan contexto oculto ni
se envían a modelos gratuitos o de pago; futuros ejemplos requieren revisión y
pruebas antes de ampliar el JSON. Filtros de calendario/eventos siguen manuales.

Sin dependencias ni migraciones nuevas. Runtime propio reiniciado sin Jobs
activos; salud200, ruta protegida y assets nuevos servidos. Datos conservados:
Jobs0, AIUsage0 y UIAction1 preexistente del usuario. No se leyeron claves y el
reinicio descarta las efímeras. **Cero llamadas a modelos y cero tokens de IA.**
Para probar: **Ctrl+F5 → Romeo-1 → Tu orden**, escribir o dictar, revisar y ejecutar.

## Romeo-1: calendario, directorio, eventos y búsqueda de personas

Ampliación vigente de **Tu orden** a seis acciones locales: modo claro, modo
oscuro, abrir Calendario, abrir Directorio, abrir Eventos y buscar personas por
nombre. Los apartados anteriores sobre dos acciones se conservan más abajo como
historial de sus entregas. Se muestran los ejemplos en **Ver órdenes disponibles**;
el dictado sigue creando un borrador que requiere **Ejecutar orden**.

Navegación mediante un único clic en el enlace existente, visible y sin controles
superpuestos. Los destinos son constantes e internos; la consulta se normaliza,
acota y codifica con URLSearchParams. El servidor vincula acción y consulta al
recibo, actor, sesión y pestaña, con TTL60s, CSRF e idempotencia. Revalida antes
del clic; Detener/Escape cancelan durante el movimiento. El mensaje de llegada
sólo se registra después de comprobar ruta, consulta y marcador SSR del destino.
El handoff se consume antes de confirmar y nunca vuelve a navegar al recargar.
La búsqueda muestra las coincidencias permitidas, sin elegir automáticamente una
persona. El recibo sigue siendo una declaración del cliente, no una observación
independiente de la pantalla por el servidor.

| Comprobación | Resultado |
| --- | --- |
| Suite Python afectada | 602 casos: 597 correctos, 5 omitidos por requerir PostgreSQL; cero fallos, 65,738 s |
| Contrato de UIAction | 21 pruebas focales correctas, incluidas en la suite anterior |
| Navegador aislado | 12 bloques consolidados: 10 iniciales y 2 focales; más comprobación final del movimiento en escritorio |
| Calendario, Directorio y Eventos | Un clic al enlace real, autorización previa y recibo tras llegar al destino |
| Búsqueda por nombre | Tres coincidencias propias ficticias, registro ajeno excluido, texto HTML escapado |
| Cancelación y repetición | Detener evita navegar; recargar y handoffs inválidos no repiten acciones |
| Dictado | Fixture SpeechRecognition: sólo borrador hasta envío humano; sin audio real |
| Móvil y movimiento reducido | Sin desbordamiento; enlace fuera de pantalla se revela antes del clic; movimiento reducido conserva navegación |
| JavaScript, CSP y red externa | Cero errores o solicitudes externas en QA |
| Modelos, Jobs y tokens | Cero llamadas, Jobs o AIUsage nuevos |

Se corrigió un defecto real en móvil: Cerrar sesión cubría parte de Directorio.
Los controles de cuenta ahora ocupan su propia fila. Se conservó la comprobación
de visibilidad/hit-testing. También se libera el estado ocupado si vence el
timeout con la pestaña oculta; no se repite el clic ante un resultado desconocido.
Las capturas finales de escritorio y móvil fueron inspeccionadas.

Evidencia útil en `Temporal/qa-romeo-navigation/`: `results.json`,
`verify_navigation.py`, comprobación focal `verify_desktop.py`,
`navigation-desktop.png`, `navigation-mobile.png`, `verification.txt` y
`migration.json`. Los diez resultados iniciales se conservaron al ejecutar los
dos casos restantes; no se presenta como una nueva campaña completa. Se utilizó
Edge/Playwright separado porque el control del navegador personal sigue sin
conexión disponible. Los servidores de QA se cerraron y sus bases ficticias se
eliminaron; esto no prueba el micrófono físico, inferencia real ni concurrencia
distribuida sobre PostgreSQL.

La migración `jobs.0004_uiaction_query_and_navigation` se aplicó con respaldo
`var/backups/pre-romeo-navigation-20261115-160018.sqlite3`, integridad SQLite y
claves foráneas correctas, conservando las filas de negocio y el UIAction ya
existente del usuario. Se reinició el runtime propio sin Jobs activos; salud200
y el catálogo nuevo servido. Verificación posterior: Jobs0, AIUsage0, UIAction1.
No se leyeron claves; el reinicio descarta credenciales efímeras. Estas acciones
locales no necesitan una API y consumen cero tokens del modelo. Para utilizarlas:
**Ctrl+F5 → Romeo-1 → Tu orden**, escribir o dictar, revisar y ejecutar.

## Dictado en «Tu orden» de Romeo-1

Conectado **Hablar** al mismo reconocimiento del navegador ya usado por el chat,
con estado propio, aviso de consentimiento y sin ejecución automática. La voz
rellena como máximo 100 caracteres; sólo resultados finales, sin duplicar índices.
Se admite puntuación terminal sin ampliar la lista de dos temas permitidos.
Mientras escucha se bloquean envío y Enter; tras detener, el usuario revisa y
pulsa Ejecutar. Campo/micrófono se congelan durante una acción. Escape, cerrar
el panel, ocultación o salida abortan la escucha; callbacks de instancias previas,
campos ocultos/desconectados o readonly no pueden cambiar la orden. Sin soporte
de reconocimiento, queda escritura manual y un mensaje local.

**13 comprobaciones consolidadas** con Edge/Playwright aislado: nueve del recorrido
principal y cuatro de continuación con assets finales. Se usó **SpeechRecognition
simulado**, sin capturar audio, invocar el servicio de reconocimiento real ni
conceder permisos en el navegador personal. Browser plugin ausente en esta sesión;
alternativa Playwright previamente autorizada. Viewports 1440×1000 oscuro y
390×844 claro. Revisión independiente de la lógica sin hallazgos materiales.

| Comprobación | Resultado |
| --- | --- |
| Identidad, contenido, pantalla vacía y overlay | Correctos, sin fallos de aplicación |
| Cancelar consentimiento | Ningún reconocimiento iniciado ni acción enviada |
| Dictar, revisar y ejecutar | Voz sólo crea borrador; ejecución manual produce un recibo y un clic |
| Escucha, límites y cancelación | Enter bloqueado, 100 caracteres, finales deduplicados y tardíos descartados |
| Permiso denegado y navegador sin soporte | Error local/entrada manual conservada |
| Regresión del chat | Su borrador/estado no se mezclan con los de Romeo; sin envíos automáticos |
| Móvil y recarga | Controles legibles, sin desbordamiento ni reinicio de escucha |
| JavaScript, CSP y red externa | Cero errores o solicitudes externas en QA |

Evidencia en `Temporal/qa-romeo-voice/results.json`, capturas inspeccionadas
`voice-desktop.png`/`voice-mobile.png` y script de comprobación `verify_voice.py`.
La continuación focal conserva los nueve resultados ya medidos; no representa
una segunda ejecución completa de esos casos. Los servidores y bases ficticias
se retiraron. `node --check` pasó para los tres scripts modificados. No se repitió
la suite Python al ser una modificación de interfaz; la cifra anterior de 563
casos sigue siendo evidencia de su entrega correspondiente.

El servicio propio se reinició sin Jobs activos para cargar la plantilla y volvió
a responder `/health/` 200. No hubo migraciones, dependencias ni cambios de negocio,
Jobs/AIUsage nuevos, acceso a claves o inferencias. El reinicio descarta claves
efímeras; dictado y tema no las necesitan. La prueba física de micrófono y calidad
de transcripción en este nuevo campo queda pendiente del usuario. No se afirma
reconocimiento offline, ilimitado o conversación continua; el navegador puede
enviar audio a su propio servicio externo según su configuración.

## Primer clic controlado: tema claro u oscuro

Por aceptación expresa de Jorge, **Romeo-1 → Tu orden** reconoce únicamente
órdenes exactas de tema claro/oscuro. El runner local registra la intención,
señala el campo, mueve el cursor al botón real y deja una ventana de cancelación
con **Detener** o **Escape**. Revalida autorización antes del clic, activa como
máximo una vez el botón existente y comprueba `data-theme`. Si ya tenía ese tema,
no pulsa. No interpreta frases con un modelo, navega, administra APIs/cuentas o
modifica planes/estados. No controla el puntero del sistema ni recibe órdenes
remotas de Codex: el usuario envía explícitamente el formulario de esta página.

`UIAction` guarda código de acción, actor, pestaña, huella HMAC de sesión, estado
y fechas. TTL60s; tres POST con CSRF, rol/usuario frescos y transiciones estrictas.
Una constraint parcial impide dos activas por actor/pestaña. Reenvíos cambiados,
actor/pestaña/sesión ajenos, expiración y contexto de ejecución del agente se
rechazan. `completed` registra una declaración del cliente tras comprobar el DOM;
el servidor no observa la pantalla independientemente. Un resultado desconocido
no vuelve a emitir el clic. Las carreras entre procesos siguen requiriendo
validación PostgreSQL; SQLite no acredita ese comportamiento distribuido.

Suite afectada: **563 casos, 560 correctos y 3 omitidos por PostgreSQL**, cero
fallos, 100,238 s. `manage.py test apps.jobs apps.assistant apps.accounts apps.events
--noinput --verbosity 0`; system check sin incidencias. Incluye 15 pruebas nuevas
de autorización, CSRF, sesión, pestaña, idempotencia, estados y caducidad. No sumar
esas 15 a las 563. Sintaxis de ambos scripts comprobada con `node --check`.

QA Edge/Playwright separado y ya autorizado: **13/13 bloques**, más prueba focal
de movimiento normal y recarga móvil. La conexión externa a la pestaña personal
no estaba disponible en la comprobación anterior; no se presenta este navegador
QA como control personal. Viewports 1440×1000 y 390×844. Resultado:

| Comprobación | Evidencia |
| --- | --- |
| Identidad, contenido y ausencia de pantalla vacía/overlay | Correctos |
| Claro/oscuro y persistencia | Un clic por orden necesaria, tema conservado al recargar |
| Cancelación y órdenes desconocidas/duplicadas | Sin clic adicional; Detener y Escape efectivos |
| Error de red y revocación real de permisos tras crear recibo | Inicio rechazado, cero clics |
| Cursor | Visible, sin interceptar controles; punta medida dentro del botón antes del clic |
| Movimiento reducido y foco | Cursor acoplado, misma ventana de cancelación y foco conservado |
| Móvil | Ambos temas, cancelación visible y sin desbordamiento; recarga sin repetición |
| JS/CSP/5xx inesperados y red externa | Cero; 403/503 esperados identificados aparte |

La ocultación se comprobó con un fixture explícito `visibilitychange`, no mediante
un cambio nativo de pestaña del usuario. El pase focal midió la punta `(1388,21)`
dentro del botón `(1380,8)-(1416,44)`. Se corrigieron el trazo SVG heredado que
tapaba la etiqueta, la posición tras ocultar Detener, la interferencia de errores
de sondeo y los mensajes que podían afirmar autorización/cambio aún sin confirmar.
Dos capturas inspeccionadas, `actions-desktop.png` y `actions-mobile.png`, junto con
`results.json`, `verify_actions.py`, `verify_mobile_reload.py` y `verification.txt`
en `Temporal/qa-romeo-actions`. Datos/servidores de QA eliminados/detenidos al cerrar.

Migración `jobs.0003_uiaction` aplicada con respaldo
`var/backups/pre-romeo-actions-20261115-151211.sqlite3`: integridad y FK correctas,
recuentos de negocio preservados, cero filas UIAction al activar. Se reinició la
instancia local propia, con cero Jobs activos antes del cierre, y el lanzador
normal volvió a responder `/health/` 200. Los scripts nuevos se sirven en el 8000;
el usuario debe recargar con Ctrl+F5. No se leyó ni recreó ninguna clave: el reinicio
descarta las claves efímeras, y esta función no las necesita. Cero inferencias,
Job/AIUsage creados o créditos consumidos. La primera inferencia real sigue pendiente.

## Cursor observado y orden local de Romeo-1

Romeo-1 aparece en la barra superior y su cursor SVG señala el paso registrado
o la respuesta local exacta. Puede ocultarse; respeta movimiento reducido y no
intercepta controles ni mueve el puntero del sistema. El estado privado consulta
usuario/rol vigentes, dueño y actor, sin exponer contenido del chat, claves o
presupuestos. El navegador consulta cada 2 s en ejecución y 12 s en reposo,
pausa al ocultarse y se detiene ante 401/403 hasta recargar. No inventa clics,
porcentajes, pensamientos ni confirmaciones de aprobación.

Jorge confirmó que veía Romeo-1 y pidió lanzar la búsqueda. Se ejecutó una vez
`buscar eventos: UNAC` mediante `romeo_local`, orden idempotente
`e4261464-0a92-483a-94b8-9aa244c661d8`, en la demo ficticia propia
`71a3850e-d858-509d-8bb2-0d9a00c449f9`. Resultado persistido: mensaje local ID 2,
dos mensajes de conversación, cero Jobs, cero AIUsage y cero llamadas de modelo.
No se accedió a claves ni se cambiaron planes, tareas o presupuestos. La respuesta
puede abrirse en el evento con `?romeo_result=2#agent-panel`. Una nueva respuesta
local del evento abierto se recupera mediante GET de sólo lectura, extrae sólo
etiquetas/atributos permitidos del chat y no roba el foco de un editor activo.

El control de la pestaña personal no estuvo disponible: la herramienta devolvió
`The browser access host is unavailable` y ausencia de conexión a la tubería nativa
de Windows. Se utilizó el navegador separado Playwright/Edge ya autorizado.
**12/12 bloques QA correctos** con base, usuarios y Jobs ficticios aislados, sin
worker ni proveedor: CSRF, consulta local real, actualización desde una orden
externa a la página, SVG realmente visible y desplazamiento a la respuesta exacta,
1440×1050/390×844, ambos temas, movimiento reducido, foco, JSON/URL/etapas inválidos,
observaciones antiguas, recuperación y revocación 403. Cero errores JS/CSP/5xx o
peticiones externas; el 403 inyectado esperado está separado. El servidor QA se
detuvo y su base fue eliminada. Capturas inspeccionadas y evidencia reproducible
en `Temporal/qa-romeo-cursor/`: `results.json`, `verify_cursor.py`,
`cursor-desktop.png` y `cursor-mobile-dark.png`. Las etapas de inferencia son
fixtures identificados, no prueba de llamadas ni calidad de modelos reales.

Se corrigieron el atributo SVG `hidden`, el desplegable móvil y la recuperación
tras pérdida de seguimiento. Las pruebas existentes ahora declaran explícitamente
sus eventos ficticios y exigen el enlace ligado al Job; se conserva el rechazo
de eventos no sintéticos y se añadió su regresión. Los timestamps de fixtures
son deterministas para evitar empates del reloj de Windows.

Suite final afectada: **548 casos, 545 correctos y 3 omitidos**, cero fallos,
56,665 s; `manage.py test apps.jobs apps.assistant apps.accounts apps.events
--noinput --verbosity 0`. Las omisiones requieren PostgreSQL. System check sin
incidencias. Registro vigente: `Temporal/qa-romeo-cursor/verification.txt`.
Las 40 pruebas focalizadas se solapan con esta suite y no se suman.

La instancia previa se encontró detenida. Se abrió el lanzador normal con web y
worker, cargando también el motor del grupo gratuito; `/health/` respondió 200.
No se leyó ni reconstruyó una clave de otro proceso. El reinicio pierde las claves
efímeras: su presencia/validez no se infiere. La aprobación individual de modelos
gratuitos y la primera inferencia real siguen pendientes. Esta demostración local
no consume el piloto OpenAI USD 1 ni acredita control autónomo del navegador.

## Grupo gratuito, asignación por tareas y dos inferencias independientes

Implementado en `free_pool.py`, `AgentPoolEntry`/`FreeGatewayState`, asignación y
panel humano; worker separado en preparación, inferencia congelada y publicación.
Doce candidatos autorizables individualmente; chat gratuito desde el inicio,
planes opcionales, prioridad y capacidad interna por modelo. Sin escalada a pago
al agotarse el grupo; USD 1 global/vitalicio intacto. Rotación sólo antes del
envío. Un 429 de alcance desconocido conserva su recibo y pausa diez minutos
todas las rutas OpenCode de la cuenta. El reloj UTC no borra holds antiguos.
Es backoff local persistente, sin garantía de reset ni sondas/reintentos.

Suite conjunta: **516 casos, 511 correctos y 5 omitidos**, cero fallos, 52,372 s.
Comando: `manage.py test apps.ai_management apps.jobs apps.assistant
apps.events.test_local_runtime tools.test_start_sparkx --noinput --verbosity 0`.
Las omisiones requieren capacidades de base distintas de SQLite; no acreditan
locks concurrentes en PostgreSQL. Incluye presupuesto/ledger, permisos actuales,
revocaciones, consentimiento por huella, límites, Jobs, apagado y lanzador.
Doce casos del grupo de concurrencia prueban solapamiento con barreras, prohíben
SQL en hilos remotos y comprueban contextos/contadores separados, exclusión de
evento/modelo, cancelación, lease vencido y apagado que espera ambas llamadas.
Son respuestas sintéticas de QA, no resultados ni rendimiento de modelos reales.
`makemigrations --check --dry-run` no detectó diferencias y `check` pasó.
Después del último guard para permitir revocar un perfil legacy retirado,
**27/27** pruebas de control pasaron (se solapan con la suite; no se suman).

QA Edge/Playwright existente (**Browser plugin not available**), base y credenciales
ficticias aisladas: **7/7 bloques**, 1440×1100 claro y 390×844 oscuro. Página y
título correctos, doce filas sin aprobación automática, políticas exactas,
aceptación desmarcada al cambiar modelo, guardado POST/CSRF, grupo/chat independiente
de plan pagado, revocación humana, presupuesto `1` y scroll móvil acotado.
Sin errores JS/console, overlays, solicitudes externas ni llamadas de proveedor.
Capturas inspeccionadas: `Temporal/qa-api-control/free-pool-desktop.png` y
`free-pool-mobile-dark.png`; resultados `free-pool-results.json`; prueba reproducible
`verify_free_pool.py`. Se retiró la base de QA al terminar.

Revisión cruzada corrigió dos fallos: saltarse cooldown por ruta legacy/primary,
y aceptar una política que cambió entre mostrarla y enviar. La pausa se consulta
antes de reservar/despachar en todas las rutas; ambos formularios y servicios
verifican huella exacta. Los agentes no pueden configurar el grupo.

Migración 0005 aplicada con respaldo
`var/backups/pre-free-pool-20261115-143415.sqlite3`. Integridad y FK correctas;
filas de negocio sin cambios; sólo Django añadió dos content types y ocho permisos
estándar. Cero modelos activados, cero inferencias y cero Jobs/AIUsage activos al
migrar. `/health/` respondió 200 después. No se reinició el proceso ni se accedió
a la clave real. Para usar el motor nuevo: apagar/reabrir, introducir otra vez la
clave si se usará OpenAI y autorizar cada modelo/política en APIs y agentes.
La cuota remota, calidad real por rol, latencia y ejecución distribuida no están
acreditadas por estas pruebas. No repetir campañas remotas bajo el piloto USD 1.

## Apagado con confirmación real y cierre de pestaña

La página pasa de **Apagando SparkX…** a **SparkX apagado** sólo al recibir la
confirmación del runtime: worker terminado, solicitudes pendientes/activas drenadas
y listener cerrado. El recibo viaja en la respuesta POST original, autocontenida;
no depende de sondear un puerto ya cerrado ni confunde errores de red con éxito.
Timeout/error o ausencia del recibo durante cinco minutos conservan el estado
sin confirmar. Se mantienen superusuario vigente, loopback directo, CSRF, token
por ejecución y nonce CSS/JS exclusivo de esa respuesta. No controla otros procesos.

Comprobación conjunta: **63/63**, cero fallos, 5,523 s, para runtime, Romeo, lanzador
y formulario de APIs (`Temporal/qa-api-control/shutdown-final.txt`). Incluye una
prueba HTTP real con solicitud pendiente, solicitud activa y stream de recibo:
el drenaje espera las dos primeras y excluye el último, evitando esperarse a sí mismo.
Los grupos anteriores de 40/41 pruebas se solapan y no se suman.

QA Edge/Playwright existente, Browser plugin not available: **6/6 bloques**,
1440×1000 y 390×844, dos runtimes reales de Romeo-1 con base SQLite independiente,
worker sin trabajos e inferencia bloqueada. Se retuvo temporalmente el cierre para
verificar que no apareciera éxito con el worker vivo. Después del recibo se
comprobó que terminaran los hilos y que ambos puertos rechazaran conexiones.
La pestaña normal conservó resultado/botón/manual al bloquear Edge `window.close`;
la ventana abierta por script se cerró automáticamente. Recibo fallido y pérdida
del recibo se comprobaron con fixtures explícitas y reloj virtual: nunca anuncian éxito.
Sin errores JS/CSP o solicitudes externas; la advertencia esperada de Edge sobre
cierre de pestañas es una restricción del navegador, no un fallo de apagado.

Resultados y capturas inspeccionadas en `Temporal/qa-api-control/`:
`shutdown-results.json`, `shutdown-stopping-desktop.png`, `shutdown-complete-desktop.png`
y `shutdown-complete-mobile.png`; script de regresión `verify_shutdown.py`.
No se modificaron datos activos ni se llamaron modelos. Las bases QA se eliminaron
tras cerrar conexiones y workers. SparkX estaba ya apagado y se conservó así;
el siguiente inicio con **Iniciar SparkX.cmd** carga este cambio y el formato monetario.
La prueba de navegador cubre Edge; no acredita otros navegadores o despliegue.
El cierre de ventana depende de [las reglas del navegador](https://developer.mozilla.org/en-US/docs/Web/API/Window/close);
el streaming sigue [el contrato WSGI de Django](https://docs.djangoproject.com/en/5.2/ref/request-response/#streaminghttpresponse-objects).

## APIs y agentes — configuración integrada vigente

El editor de claves ahora permanece cerrado y se abre por proveedor con **Añadir
clave** o **Cambiar clave**. Guardar conserva el POST/redirect privado y vuelve al
estado cerrado; Cancelar/Escape vacían el borrador sin cambiar la conexión actual.
Doce pruebas de controles API y seis bloques en Edge/Playwright pasan, con base
aislada, claves ficticias y cero inferencias. Escritorio claro 1440×1100 y móvil
oscuro 390×844 inspeccionados: sin errores JS/CSP, peticiones externas o desbordamiento.
Evidencia en `Temporal/qa-api-control/credential-editor-results.json`,
`credential-saved-desktop.png` y `credential-change-mobile-dark.png`.
La mejora usa los estáticos del servidor actual y funciona con su HTML en caché:
salud/JS/CSS 200, sin reinicio ni lectura o sustitución de la clave real. Ctrl+F5
carga el editor actualizado. Sin soporte de dialog nativo se conserva el formulario.

Ajuste posterior de presentación: enteros sin decimales (`USD 1`), fracciones
con precisión de seis decimales y moneda explícita en el resumen. No cambia
contabilidad ni límites. Las 32 pruebas HTTP del módulo y cuatro casos de formato
pasan. Render aislado en escritorio 1440×1000 y móvil 390×844, navegación Resumen,
sin desbordamiento, errores JS ni solicitudes externas. Evidencia en
`Temporal/qa-api-control/verify_decimals.py` y capturas `budget-decimals-*`.
La instancia local sin recarga automática requiere apagar/iniciar para vaciar la
caché de plantillas; se conservó encendida para no perder sus conexiones efímeras.

**Gestión de IA → APIs y agentes** (`/ai/control/`) centraliza conexiones privadas,
acceso de Romeo-1, presupuesto vitalicio y una alternativa gratuita aprobada.
`Iniciar SparkX.cmd` abre web y worker juntos, sin introducir claves en consola.
Las instrucciones de consola de la sección histórica siguiente quedan sustituidas.

La identidad activa de superadministrador se consulta de nuevo en cada operación.
Administrador del portal, organizador, revisor y contexto de ejecución del agente
no pueden gestionar estas funciones. La protección es de aplicación: no constituye
un sandbox del sistema operativo ni revoca una clave en la cuenta del proveedor.
Las claves se mantienen en memoria hasta dos horas o hasta cerrar el proceso;
rotarlas/desconectarlas invalida sus referencias anteriores. No hay almacenamiento
de secretos en BD/archivos/navegador ni verificación remota al guardar la conexión.
Se exige HTTPS o HTTP directo de loopback en desarrollo, CSRF y redacción también
en páginas de error de desarrollo.

Antes de despachar se comprueba reserva, permisos y versión del grant. Si falta
presupuesto monetario puede seleccionarse una sola alternativa OpenCode gratuita
revisada, con política exacta aprobada por el superadministrador. La falta de tokens,
excesos registrados, revocación, error remoto o 429 no activan esa alternativa.
No hay rotación ni reintento después del envío; su cuota real no está garantizada.
Plan y tareas conservan confirmación humana, con historial separado por modelo.

- Comprobación conjunta final: **96 descubiertas, 94 correctas y dos omitidas por
  requerir PostgreSQL**, cero fallos, 5,681 s (`Temporal/qa-api-control/final-checks.txt`).
  La última comprobación del formulario/credenciales pasó **12/12** después de
  añadir el estado booleano de conexiones heredadas del entorno. Los grupos se
  solapan y no se suman; no se declara una nueva suite completa.
- QA visual **8/8**, escritorio 1440×1100 claro y móvil 390×844 oscuro, Edge/Playwright
  existentes porque Browser plugin no estaba disponible. Flujo: superadmin guarda
  clave ficticia, fija presupuesto cero, autoriza Beam Free, solicita una propuesta
  sintética, observa selección gratuita previa al envío y desconecta la conexión.
  Cero errores JS/CSP y solicitudes externas. Capturas inspeccionadas en
  `Temporal/qa-api-control/`: `control-desktop-light.png`, `control-mobile-dark.png`
  y `fallback-desktop-light.png`; resultados en `results.json`.
- La respuesta de QA es un recibo local simulado. Los 1010 tokens y presupuesto
  cero de sus capturas pertenecen sólo a la base sintética; no prueban inferencia
  real, consumo del proveedor ni disponibilidad de modelos gratuitos.
- Migración `ai_management.0004` aplicada con copia
  `var/backups/pre-api-control-20261115-130107.sqlite3`. Eventos 10→10, planes 3→3,
  Jobs 0→0 y AIUsage 0→0, según `Temporal/qa-api-control/local-state.json`.
  Cuenta activa: Romeo-1 habilitado, principal mini, tope USD 1; alternativa
  **sin habilitar** hasta selección y aceptación expresa en el panel.
- SparkX responde en loopback con el arranque integrado. La clave privada y la
  primera solicitud real siguen pendientes. No se hicieron llamadas nuevas a
  proveedores, no se aprobaron planes ni cambiaron estados de tareas.

## Romeo-1 — piloto OpenAI controlado

Histórico anterior a la configuración web: **Iniciar SparkX.cmd** es el único acceso a la
plataforma y al agente integrado. Se retiró el lanzador duplicado y se renombró su
entrada a `tools/start_sparkx.py`. Con clave oculta inicia web + worker del piloto;
Enter sin clave abre la plataforma con consultas locales. No hay otra aplicación.
Arrancar con IA atiende también Jobs elegibles pendientes; no crea solicitudes nuevas.
Se bloquea el fallback de `getpass` a entrada visible. Las cinco comprobaciones
focalizadas pasan (clave privada, sin clave, clave heredada, puerto ocupado y consola
sin captura oculta), sin red ni cambios en la base. `manage.py check` correcto.

Usuario autorizó USD 1 máximo de créditos, eventos controlados y nombre Romeo-1.
Implementados: límite global persistente por contabilidad de todas las cuentas/meses/modelos,
reservas conservadoras y consumos desconocidos; eventos ficticios obligatorios; tarifas
mínimas verificadas; snapshot OpenAI aislado por identidad y congelado antes de preflight;
traza operacional con timestamps; panel con Seguimiento/Conversación, indicador cursor,
tokens y presupuesto; lanzador privado y un worker mini acotado a cuenta administradora.
Las acciones de aprobar y de estados de tareas siguen siendo humanas.

QA visual **9/9** en `Temporal/qa-romeo/results.json`: Edge/Playwright (Browser plugin
not available), escritorio 1440×1100 y móvil 390×844, claro/oscuro, teclado, cola,
conexión observada, respuesta/validación/resultado, conservación del plan y enlace
de revisión. Sin errores JS/CSP ni solicitudes externas. La respuesta HTTP es una
fixture local identificada: los 1720 tokens y USD 0,002865 mostrados pertenecen
exclusivamente a la base aislada QA; no representan inferencia ni gasto real.
Se corrigió el enlace de revisión para recargar la ficha y mostrar la candidata creada
después de cargar la página. Las capturas fueron inspeccionadas: texto compacto,
paleta existente, separación de etapas, scroll del rail, marcador y colapso móvil.
No se reprodujeron pensamientos internos ni se animaron etapas sin observación.

Pruebas focalizadas por componentes: presupuesto **76 (74 correctas/2 PG omitidas)**;
aislamiento/adaptador **80 correctas**; worker legacy **31 (29 correctas/2 PG omitidas)**;
arranque/apagado local **33 correctas**. Los grupos se solapan y no se suman.
La primera integración de 131 casos detectó un orden de fixture dependiente de UUID
cuando Windows asigna el mismo timestamp a dos Jobs. Se fijó el orden explícito del
fixture y se repitieron Romeo/launcher: **10/10**. No fue un fallo de publicación.
Comprobación final conjunta Romeo/launcher/apagado: **43/43** en 4,150 s,
sin red, en `Temporal/qa-romeo/final-checks.txt`.
`check` y `makemigrations --check --dry-run` correctos. La suite completa anterior
de 873 casos continúa como baseline histórico; no se declara una nueva suite completa.

Base activa: copia `var/backups/pre-romeo-1-20261115-122755.sqlite3`; migraciones
`ai_management.0003` y `jobs.0002` aplicadas. Antes/después en
`Temporal/qa-romeo/local-state.json`: eventos 9→10; planes 3→3; Jobs 0→0; AIUsage 0→0.
Perfil Romeo-1 mini seleccionado, pago por créditos habilitado con presupuesto USD 1.
La clave no está disponible en el proceso de herramientas; **cero inferencias nuevas**.
Falta que Jorge ejecute el lanzador e introduzca la clave en privado, y después una
solicitud real controlada con contraste de Usage. No se añadió tarjeta ni se aprobó
ningún plan existente. El presupuesto es estimación local, no un límite contractual
del proveedor. PostgreSQL, calidad/latencia real e inferencia siguen pendientes.

Última suite completa: **873 pruebas: 861 correctas y 12 omitidas por PostgreSQL**,
sin fallos ni errores, en 69,032 s. Base de pruebas SQLite aislada, sin modelos.
Ampliación a doce modelos gratuitos revisados, con consentimiento por solicitud,
contexto por modelo y diez comprobaciones de navegador correctas. Las llamadas
reales anteriores DeepSeek y MiniMax devolvieron 429; no se repitieron.
Servicio actualizado en http://127.0.0.1:8000/. Las secciones inferiores conservan
sus fechas y resultados históricos; no deben sumarse como pruebas independientes.

## Ampliación de modelos y aislamiento — 15 de noviembre

El usuario pidió ampliar modelos OpenCode y mantenerlos aislados. Se consultaron
las condiciones oficiales y el catálogo JSON público sin enviar datos del proyecto.
Trece modelos de chat tienen política revisada; doce confirmaron precio cero.
Nemotron 3 Ultra no apareció y quedó fuera de la aplicación. Jev usa System One,
otro contrato, y no se habilitó como chat. La presencia/precio no acredita cuota,
rendimiento ni respuesta válida. No se instalaron dependencias o binarios nuevos.

| Comprobación | Resultado y alcance |
| --- | --- |
| Catálogo y política | Doce presets con límites comunes, sin URLs/modelos arbitrarios ni fallback. Nueve con retención/entrenamiento/alojamiento especial exigen aceptación específica. Huella versionada de política, no auditoría del proveedor. |
| Enqueue y dispatch | Token firmado de una hora ligado a actor, evento/revisión, acción, UUID, perfil/versión y modelo/política. Sin aceptación no hay Job/reserva; cambio de política en cola libera reserva antes de dispatch. Repetir el mismo Job es idempotente; otro UUID requiere aceptación nueva. |
| Contexto | Historial por evento/propietario/proveedor/modelo y Job/AIUsage acreditados, antes de limitar a ocho. Omite local, desconocido u otra IA; plan/progreso sólo con procedencia del mismo modelo. Ficha, entrevista y restricciones declaradas siguen disponibles. Instante congelado ligado al modelo y cero ORM en el envío. |
| Ejecuciones simultáneas | Dos modelos con barreras y finalización intercalada verifican prompts, configuración, temporales, nueve rutas de entorno/caché y contadores independientes; un fallo 429 no afecta al otro. Son procesos nativos simulados para estas pruebas, sin inferencia externa. ContextVar real comprobado con dos hilos y reutilización del hilo después de un fallo. |
| Cadena de doce modelos | Prueba de Job/worker/ledger para cada modelo aprobado con bridge controlado: transmite sólo su aceptación, publica en su propio Job y conserva sus propios contadores. No acredita calidad remota. |
| Navegador | Flujo: detalle y condiciones → envío sin casilla rechazado → aceptación encola un Job → HTMX renueva UUID/token y desmarca → referencias antiguas/otro modelo rechazadas → consulta local sin permiso remoto. Diez comprobaciones correctas; un único Job reservado y ninguno enviado en la base QA. |
| Presentación y salud | Browser plugin not available; Edge/Playwright existentes, 1440×1000 y 390×844 en claro/oscuro, dos capturas inspeccionadas. Página/título/contenido correctos, sin overlay técnico, desbordamiento, errores JS/CSP ni HTTP 5xx finales. Sin peticiones externas del documento. |
| Suites | 873 descubiertas: 861 correctas y doce PostgreSQL omitidas, cero fallos/errores, 69,032 s. `check` y migraciones sin drift correctos. Dos revisores independientes; sin hallazgos bloqueantes. |
| Privacidad y límites | No es un sandbox del sistema operativo. El proveedor remoto conserva datos conforme a sus condiciones; no detecta texto que el organizador copie en ficha/prompt ni impide cambios directos de código/BD privilegiados. No hay prueba PostgreSQL ni cuota ilimitada. |
| Llamadas y datos | Cero nuevas inferencias, sin worker o pago. Se conserva la elección de esperar cuota OpenCode. QA usa otra base y no activa perfiles ni modifica eventos de Jorge. |

Evidencias vigentes: `Temporal/qa-model-isolation/catalog.json`, `server-tests.json`,
`ui/results.json`, `ui/beam-policy-desktop.png` y `ui/mimo-policy-mobile.png`.
Scripts/bases QA permanecen en Temporal sólo para una regresión concreta posterior;
servidor QA detenido. Un problema de codificación stdout del script se corrigió y
se continuó sin repetir el Job. Los cinco fallos reales anteriores siguen sin
contadores completos: no se reemplazan por resultados controlados ni consumo cero.
[Modelos y contrato operativo](guias/ai-management.md#aislamiento-y-modelos-ampliados).

## Ciclos de dos organizadores ficticios — 15 de noviembre

Recorrido bajo prueba: login → crear evento y confirmar entrevista → solicitar IA →
revisar/aprobar → restricciones y alternativa → preparación/evidencia → inscripción.
Cada agente usó su propia base SQLite y servidor loopback efímeros. No se añadieron
eventos ni se aprobaron planes o tareas de Jorge. Los ciclos corrigieron el producto
y el harness por separado; no hubo llamadas de pago ni nuevos reintentos de inferencia.
Las cuentas principales tenían rol de portal Organizador y marca técnica `is_staff`
para configurar su perfil financiero aislado. No acredita el alta de un organizador
sin ese privilegio; las cuentas ajenas y revisores se comprobaron por separado.

| Caso | Resultado observado |
| --- | --- |
| QA1 UNAC / DeepSeek | Un único Job real: HTTP 429, consumo desconocido. Después, fixture manual identificado; ronda final 11/11 bloques correctos y reprueba de cuatro rutas protegidas. |
| QA2 GICA / MiniMax | Un único Job real: HTTP 429, consumo desconocido. Después, fixture manual identificado; 11/11 bloques correctos, incluidas pausa/republicación, aforo y dos pestañas con rechazo 409. |
| Aprobación y restricciones | Aprobación humana en UI y recuperación tras recargar. Cruce entre eventos detectado; decisiones fijadas pueden bloquear. Liberar sólo el ponente permitió otra candidata manteniendo horario, sin alterar automáticamente el plan. |
| Preparación | Completar cierra el editor. Responsable/evidencia declarados, verificación y reapertura comprobados; reabrir conserva historial y exige nueva revisión de vigencia. |
| Inscripciones | Publicación explícita; duplicado no consume otro cupo ni expone correo. Aforo exacto dos; nueva versión del plan pausa admisiones y un formulario viejo no escribe. Republicación explícita comprobada. |
| Permisos | Otra cuenta no accede a evento/contactos/evidencia/inscritos. Revisor asignado consulta lo permitido y no puede escribir restricciones, evidencia o inscripciones. |
| Fallo de producto corregido | Django DEBUG mostraba su 404 técnica y estilos inline rechazados por CSP al pedir un evento ajeno. Ahora devuelve una 404 genérica, sin trazas, nombre ajeno o URLconf; CSS externo, no-store y CSP estricta. Ambos agentes repitieron el caso con éxito. JSON 404 conserva su contrato. |
| Robustez local | Una preconexión de navegador ociosa generaba un TimeoutError de hilo. Se cierra sólo ese socket al agotar la lectura inicial. Regresión TCP real y revisión independiente: no captura errores de aplicación/WSGI. |
| Fallos de harness corregidos | Navegación al mismo fragmento no recargaba la plantilla tras insertar el fixture; selector exigía “Correo” en vez de “Correo electrónico”; acceso ORM durante contexto async. Se corrigieron los scripts y se repitieron sin otra llamada IA. |
| Navegador | Browser plugin not available; Playwright/Edge existentes con perfiles aislados. Escritorio 1440×1000 y móvil 390×844, claro/oscuro, capturas inspeccionadas. Contenido, rutas, controles y estados persistidos correctos; cero errores JS/CSP inesperados y cero HTTP 5xx finales. 403/404/409 provocados se registran aparte. |
| Modelos | Tres presets permitidos: GLM, DeepSeek y MiniMax gratuitos por OpenCode. Lista compartida entre catálogo, perfil, adaptador y puente; modelo explícito fijado por solicitud. Comprobación de precio cero antes de enviar, sin herramientas ni claves heredadas. No existe rotación/fallback automático. |
| Suite final | 843 descubiertas; 831 correctas, cero fallos/errores, doce omitidas por PostgreSQL, 65,453 s. Sin modelos ni datos activos. Los controles `check`, migraciones sin drift y formato se verifican por separado. |

Evidencia vigente en `Temporal/qa-two-users/`: `server-tests.json`,
`catalog-check.json`, `deepseek/round-3.json`, `deepseek/model-receipt.json` y
`minimax/results.json`. Se conservan los recibos anteriores útiles para distinguir
errores del script, fallo remoto y corrección de producto; las bases/capturas
sustituidas se retiraron. Los dos servidores QA están detenidos y no quedaron
carpetas privadas del puente.

La comprobación final `final-local-state.json` confirma salud 200, CSS 200, rutas
privadas con redirección al login y 404 genérica con CSP/no-store. Filas originales
y tablas de negocio conservadas frente al respaldo previo; nueve eventos, cero
Jobs/AIUsage, perfil activo nulo, pago deshabilitado y USD 0. Servicio reiniciado con
el código final en 8000, sin worker. `check` y `makemigrations --check --dry-run`
correctos; no hubo nuevas migraciones ni dependencias en este ciclo.

Los tres modelos gratuitos ensayados entre este ciclo y el anterior respondieron
429. Los cinco Jobs lógicos de aceptación fallaron: tres GLM previos y uno por cada
agente actual. No equivale a cinco peticiones HTTP ni a cinco inferencias completas.
No hay nueva propuesta IA real aceptada ni medición de tokens completa: el coste es
desconocido, no cero. La cuota es un bloqueo externo; repetir indefinidamente el
mismo fallo no aporta validación. Se requiere restablecimiento del proveedor o
configuración privada de otra oferta gratuita elegida por el usuario. Jorge eligió
**esperar la cuota de OpenCode**; Groq queda aplazado, sin sondeos ni reintentos
automáticos. No se conoce una hora verificada de restablecimiento. Siguen
pendientes PostgreSQL/concurrencia, carga, instalación nueva y los módulos/entregables
de concurso descritos en el plan. Esta QA no acredita usuarios reales ni producción.

## Restricciones, evidencia e inscripciones — cierre local del 15 de noviembre

El usuario confirmó entrega hoy a las **12:00 America/Lima** y pidió terminar el
prototipo antes del informe, PPT y manual finales, que serán bilingües. No se
crearon esos documentos ni se publicó o desplegó el proyecto.

| Comprobación | Resultado y límite |
| --- | --- |
| Restricciones | Inicio/duración confirmados, ventana explícita, hasta tres expositores y recursos, doce sesiones, decisiones fijadas y reservas de agendas aprobadas del propietario. Se revalida al aprobar. Las referencias personales guardan versión; una ficha cambiada exige revisión. |
| Reparación | Cálculo mecánico en cuadrícula de 15 minutos y hasta 50.000 pasos. El caso de cruce produjo otra candidata y conservó el plan hasta aprobar explícitamente. No demuestra óptimo ni inviabilidad global. |
| Preparación | Responsable, plazo y nota/URL HTTPS; etapas separadas de ejecución. Completar y verificar exige declaración humana. Reabrir ejecución invalida la vigencia de la verificación; el historial permanece. No se descargan enlaces ni se acredita revisión independiente. |
| Inscripciones | Apertura explícita con sesión/CSRF/versiones; enlace opaco, agenda publicada, nombre/correo únicos por evento, aforo y recibo idempotente. Cambio de plan pausa admisión hasta republicar. Sin correos, pagos ni verificación de propiedad del correo. |
| Navegador | Browser plugin not available; Edge/Playwright existentes, 1440×1000 claro y 390×844 oscuro, movimiento reducido. Siete comprobaciones correctas, contenido y rutas esperados, cero errores inesperados de JS/consola y tres capturas inspeccionadas. Base y servidor QA aislados, detenidos al terminar. |
| Recorrido | Fixture manual → aprobar/recuperar → guardar restricciones → cruce con otra agenda → alternativa → aprobar → completar/verificar/reabrir tarea → publicar inscripción → correo repetido ignorado → dos registros únicos → aforo completo sin formulario. No acredita generación IA. |
| Corrección de navegador | `no-referrer` en la página pública provocaba `Origin: null` y rechazo CSRF 403. Se cambió a `same-origin`, manteniendo CSRF, y se repitió el envío correctamente. |
| Revisión de seguridad | Contexto remoto gratuito congelado antes de dispatch; filtrado sintético del directorio y exclusión de todos los mensajes de consultas locales del historial. Preflight y llamada reutilizan la instantánea; cero consultas ORM en envío comprobadas. Cancelar reconsulta al actor vigente, aunque el objeto autenticado esté obsoleto. |
| Suite final | 835 descubiertas: 823 correctas, cero fallos/errores y doce carreras/bloqueos PostgreSQL omitidos. `check`, migraciones sin drift y `git diff --check` correctos. No implica capacidad de 20–100 usuarios ni prueba de carga. |
| Base activa | Migraciones `events.0006`, `planning.0003`, `registration.0001` y `ai_management.0002`, con copia previa `var/backups/pre-prototype-closing-20261115.sqlite3`. Filas y columnas anteriores conservadas; se añaden metadatos de permisos/tipos por migración. Ningún plan o estado de tareas del usuario fue cambiado. |
| IA real | Tres trabajos gratuitos sintéticos en base aislada fallaron. Fase del primero no determinada; segundo `step_start → error`; tercero HTTP 429 confirmado. Sin propuesta válida ni contadores completos: tokens/costo desconocidos, no cero. Sin reintento automático o sustitución por pago. |
| Limpieza | Tres runtimes privados residuales retirados tras comprobar que no había procesos OpenCode. El puente tolera liberación tardía de handles con tres intentos de limpieza local; no repite inferencia. Conserva el fallo histórico del recibo. |
| Servicio y gasto | Web reiniciada en 8000, sin worker. Base activa con nueve eventos, cero Job/AIUsage, perfil sin seleccionar, pago deshabilitado y presupuesto USD 0. La guía de Groq Free prepara una alternativa; requiere acción privada del usuario. |

Evidencia local útil en `Temporal/qa-closing/`: `server-tests.json`,
`local-integration.json`, `final-local-state.json`, `acceptance.json` (fallos reales),
`ui-acceptance.json` (fixture manual), `preparation-desktop.png`,
`constraints-desktop.png` y `registration-mobile.png`. No hay evidencia de inferencia
real completada, concurrencia PostgreSQL, carga o despliegue en este incremento.

## Evento fallaba en la instancia antigua — 15 de noviembre

Jorge reportó `NoReverseMatch: 'directory' is not a registered namespace` al abrir
`/events/7183dc2f-dac0-58f9-a176-50712460e59b/#plan` en 8000. El código actual
registraba correctamente las rutas. La instancia antigua devolvía salud 200 pero
directorio 404; la nueva en 8001 devolvía la redirección de acceso esperada. Se
identificó el PID 21848, comando `python -B manage.py runlocal`, iniciado antes
del cambio. Conservaba el URLconf importado y leía la plantilla nueva del disco.

Tras verificar proceso, servicio y puerto se detuvo solo esa instancia y se inició
`runlocal --port 8000` con el código actual (sesión 56568). Se cerró la instancia
auxiliar 8001 de esta sesión para dejar una sola dirección. El arranque ahora advierte
que un puerto ocupado puede corresponder a una versión anterior; no detiene otros
procesos automáticamente. El README vuelve a identificar 8000 como dirección vigente.

Validación: **57/57 pruebas relacionadas correctas**, en 2,970 s. Edge/Playwright
existentes, Browser plugin not available: evento reportado 200, título/contenido
correctos, navegación a Personas del evento y al directorio, misma vista móvil
390×844 sin desbordamiento y cero errores de consola/JS. Capturas de escritorio
1440×1000 claro y móvil oscuro inspeccionadas. No se hicieron llamadas IA.

Se creó únicamente una sesión de QA propia de cinco minutos, retirada al terminar,
sin extraer contraseñas, modificar cuentas o reutilizar sesiones de Jorge. Cantidad
anterior de sesiones conservada; huellas de todas las tablas ajenas a sesiones
idénticas antes/después. Evidencia: `Temporal/qa-directory/event-runtime.json`,
`event-runtime-desktop.png` y `event-runtime-mobile.png`. Script temporal retirado.

## Directorio, calendario filtrable y consultas mecánicas — 15 de noviembre

Jorge pidió optimizar tareas repetitivas, crear datos de expositores/participantes/
invitados y un repositorio de eventos navegable por calendario, bajo usuarios y
administración. Se revisó estáticamente el ZIP UNAC 1.3.0 aportado, sin ejecutarlo,
extraerlo ni cambiar el original. [Hallazgos, adaptación y límites](arquitectura/directory-and-catalog.md).

| Comprobación | Resultado |
| --- | --- |
| Datos locales | Dos organizaciones, 45 personas ficticias: tres expositores, 30 participantes y 12 invitados; 60 vínculos por confirmar. Seis eventos, cinco UNAC/uno GICA, del 16 al 21/11/2026. |
| Propuestas | Seis ejemplos manuales pendientes; cero aprobaciones automáticas. No se importaron respuestas del benchmark ni se modificaron tareas anteriores. |
| Preservación | Copia SQLite consistente en `var/backups/pre-directory-20261115.sqlite3`; comprobación por huellas de filas y columnas originales en 25 tablas, todas conservadas. Segunda carga sin duplicados ni nuevas auditorías. |
| Permisos | Directorio por propietario incluso para administrador técnico/del portal; revisores bloqueados en directorio y herramientas. Catálogo de revisores limitado a eventos asignados. Sesión, CSRF, referencias cruzadas y versiones verificadas. |
| Algoritmos | Normalización compartida, correo único por propietario, archivado, versiones obligatorias y rechazo de edición obsoleta. Catálogo común filtra antes de contar/limitar. Se evitó reconsultar al actor por cada formulario de participación. |
| Revisión independiente | Se corrigió expansión Unicode de claves normalizadas antes de persistir y se añadió regresión. Auditoría estática del código de referencia y revisión de aislamiento; no pentest de un servicio externo. |
| Configuración | `check` y `makemigrations --check --dry-run` correctos. Migraciones `directory.0001` y `events.0005` aplicadas; sin dependencias nuevas. |
| Navegador | Python 3.12.14, Django 5.2.19, Playwright 1.64.1, Edge 157.0.4341.60 existentes. Browser plugin not available. SQLite y servidor loopback efímeros aislados. 14/14 recorridos correctos. |
| Recorridos | Filtros, paginación, alta/edición/archivado, conflicto 409 y recuperación, participaciones, cinco eventos UNAC/uno GICA y filtros conservados al navegar. |
| Chat local | `buscar expositores` devuelve tres nombres; se persisten dos mensajes sin Job, AIUsage, inferencias o solicitudes externas. Otros mensajes mantienen los controles de IA existentes. |
| Presentación | Escritorio 1440×1000 claro; móvil 390×844 oscuro con movimiento reducido. Se corrigió un desbordamiento del encabezado accesible: el scroll queda dentro de la tabla y documento/cuerpo miden 390 px. Tres capturas finales inspeccionadas. |
| Consola | Cero errores inesperados de JS, consola o CSP; conflicto 409 provocado documentado por separado. |
| Servicio final | `runlocal --port 8001`, sesión 15600, reiniciado tras los cambios finales. Salud 200; directorio/calendario anónimos redirigen al login; CSS 200. Puerto 8000 intacto. |
| Consumo activo | Job 0, AIUsage 0, mensajes reales 0, perfil activo nulo, pago desactivado y presupuesto USD 0. Sin worker ni lectura/transferencia de claves. |

Evidencias útiles: `Temporal/qa-directory/results.json`, `server-tests.json` y
`local-integration.json`; capturas `directory-desktop-light.png`,
`calendar-desktop-light.png` y `roster-mobile-dark.png`. Base, sesiones, cookies,
servidor y script de QA aislada retirados al cierre. Son datos de QA, no personas
reales ni mediciones de asistencia.

Nueve pruebas de la suite completa requieren PostgreSQL y no se ejecutaron con
SQLite. Tampoco se acredita carga multiusuario, importación masiva, disponibilidad
de ponentes conectada al plan, interpretación libre mediante tool calling, ahorro
porcentual de tokens o despliegue público. Las consultas mecánicas concretas evitan
una llamada a modelo; el ahorro de generación de agendas todavía exige evaluación A/B.

## Ensayo de seis eventos — 14 de noviembre de 2026

Seis agentes independientes y acotados prepararon cinco casos UNAC y uno GICA,
del lunes al sábado de una semana simulada, con tres expositores ficticios.
Se ejecutaron 42 celdas principales, seis por cada uno de los siete modelos.
Resultado: **19 correctas**, dos respuestas completas con fechas inválidas,
19 límites de salida y dos errores HTTP 429 por cuota gratuita agotada.
GLM completó 6/6 y su calendario compartido pasó en ambas fases: cuatro
adaptaciones factibles y dos bloqueos correctos pendientes de decisión humana.

Nueve intentos previos de piloto se excluyeron por recorte de líneas largas del
input. Se corrigió el formato antes de la matriz principal; dos pilotos quedaron
interrumpidos con contadores desconocidos. No se reutilizaron tareas reclamadas.
Los 51 intentos del ensayo no equivalen a 51 peticiones HTTP exactas.

**124/124 pruebas de herramientas correctas en 4,364 s**, incluidas 15 del evaluador
de agendas y preservación de recibos parciales. `manage.py check` correcto y salud
local HTTP 200. Lectura de base: Job=0, AIUsage=0, perfil activo nulo, pago False,
presupuesto USD 0. Sin modificación de la demo ni inferencia integrada de SparkX.
La suite de servidor citada arriba no se volvió a ejecutar para este cambio.

Método, tabla por modelo, revisión textual y costes hipotéticos en
[event-benchmark.md](validacion/event-benchmark.md). Evidencia completa en
`Temporal/opencode/event-benchmark/`, con recibos individuales referenciados por
`matrix.json`. Un fallo por 2.048 tokens mide este perfil, no la capacidad general
del modelo. No es una prueba de carga ni una validación de contenido académico.

## Ayudante OpenCode — 14 de noviembre de 2026

Se incorporó una herramienta de desarrollo separada de la IA del producto:
`Ayudante OpenCode.cmd`, broker Python, configuración restringida, instalador con
versión fija y comprobación del catálogo gratuito. No se editaron los servicios
de eventos, estados, presupuestos o proveedores de SparkX. Uso y fuentes en
[opencode.md](guias/opencode.md).

| Comprobación | Resultado |
| --- | --- |
| Instalación | OpenCode 2.2.7 Windows x64 baseline, ZIP oficial de 124.794.066 bytes y SHA-256 coincidentes; solo exe extraído y comprobante local. Sin PATH/npm global. |
| Pruebas mantenidas | 107/107 correctas en 3,465 s; 21 instalación, 12 catálogo, 12 configuración, 28 broker, 18 estimador y 16 consentimiento/comparación. Incluye exclusión concurrente, desconocidos, razonamiento/caché y prevalidación de datos ficticios. Sin modelo o red en estas pruebas. |
| Harness real | 31/31 comprobaciones sobre el binario, incluidas 16 decisiones de permisos. Solo configuración preparada, dos agentes de trabajo, mantenimiento con mismo modelo, proveedor `opencode` sin cuentas conectadas y contexto sin mensajes. |
| Restricciones reales | Lectura de inputs permitida; draft puede escribir outputs; review no escribe. `.env`, rutas ajenas, shell, Code Mode, subagentes, red y acciones desconocidas denegados. No es un sandbox del SO. |
| Salida | Preflight adicional con 2.048 tokens de salida ordinaria aceptado por el binario. Tiempo 180 s y salida de proceso 1 MiB comprobados con procesos Python propios; interrupción ante JSON de error/reintento/límite. No se promete un máximo exacto de peticiones HTTP. |
| Privacidad | Entorno hijo por lista permitida y directorios propios; instrucciones ancestrales deshabilitadas según fuente fijada. El harness sigue transmitiendo metadatos de plataforma y rutas cuando se autorice inferencia. |
| Regresión de aplicación | `check` correcto; `makemigrations --check --dry-run`: sin cambios. La suite de servidor de 636 pruebas corresponde a la modificación anterior, no se contó como ejecución nueva de esta herramienta. |
| Inferencia | Tras el rechazo automático inicial, Jorge autorizó expresamente la prueba gratuita con datos sintéticos. GLM-5.3 Flash completó el trabajo en 19,453 s, tres pasos, salida 0 y estado pendiente de revisión. Catálogo a precio cero y coste cero reportado; sin claves o cuenta de pago. No es verificación de facturación ni rendimiento general. |
| Revisión del borrador | Código inspeccionado antes de ejecución local aislada: siete casos correctos; 999/1000 → 99 y total cero → 0. Hashes de entradas intactos. Sin imports, llamadas o atributos en el AST del ejemplo. No se incorporó el archivo a SparkX. |
| Ampliación a siete modelos | Catálogo público confirma los tres originales y LongCat 2.5, Beam, MiMo V2.6 Flash y Nemotron 3.5 Lightning gratuitos. Los cuatro nuevos requieren datos ficticios declarados y aceptación de su política; las condiciones se muestran en español y se revalidan al ejecutar. Ninguna inferencia adicional. |
| Preflight adicional | Los cuatro nuevos pasaron la comprobación de configuración efectiva del ejecutable real en 2,765 / 2,032 / 1,875 / 2,063 s; evidencia `Temporal/opencode/model-preflight.json`. Sus carpetas de prueba se retiraron. No acredita calidad de generación. |
| Comparación económica | `compare` funciona sin red/modelos y conserva intacto `result.json`. Muestra coste reportado USD 0 separado de tres escenarios pagados con tarifa/fecha/fuente. La muestra suma 6.683 tokens disjuntos: 5.627 entrada y 1.056 salida con razonamiento. Referencias por muestra GLM USD 0,00111093; DeepSeek 0,002315556; MiniMax M3 0,00243306. Hipótesis con mismos contadores, no facturas, equivalencia entre modelos o prueba de ahorro. |
| Revisión independiente | Detectó que añadir el ejemplo no declaraba ficticios otros archivos seleccionados. Se corrigió: demo más archivos requiere `--synthetic` explícito en modelos restringidos; prueba mantenida añadida. Sin otros bloqueos concretos en el flujo revisado. |

Evidencia del harness en `Temporal/opencode/qa-policy-results.json`. Los procesos
privados, sesiones, scripts y tareas desechables de QA se cerraron o retiraron.
La tarea sintética de 80 bytes está en
`Temporal/opencode/tasks/20261115T024003-a63dd261ee/`, con resultado del modelo y
`review.json`. Por categoría, OpenCode informó 3.451 tokens de entrada sin caché,
799 de salida visible, 257 de razonamiento y 2.176 de lectura de caché entre los
tres pasos. Según la fuente fijada de 2.2.7 son categorías disjuntas: total 6.683;
el contador no sustituye una factura auditada. La tarea está reclamada y no puede
volver a ejecutarse. No quedaron procesos OpenCode activos. La base de SparkX
conserva Job=0, AIUsage=0, perfil activo nulo, pago deshabilitado y presupuesto USD 0.
No se habilitó la API de SparkX ni se modificaron sus créditos o presupuesto.
`cost-comparison.md` y JSON se añadieron a esa tarea mediante cálculo local; no se
ejecutó de nuevo ni se cambió su recibo original. Las tarifas de referencia son
instantáneas del 14 de noviembre, revisables antes de decidir un gasto. El lanzador
permite elegir los siete modelos, sin cambio automático entre ellos.

## Completar, continuar y reabrir tareas — 14 de noviembre de 2026

Jorge pidió que el agente hiciera las pruebas y corrigiera el editor que seguía
abierto al completar. La causa era que cualquier mensaje de respuesta abría el
editor, incluido el guardado correcto. Ahora se cierra únicamente tras confirmación
del servidor; completar también cierra las instrucciones y abre/enfoca la siguiente
tarea pendiente, sin cambiar su estado ni borrar su borrador. Si no quedan tareas
posteriores, busca desde el inicio y omite completadas. Un enlace permite continuar
y la navegación normal mantiene el recorrido sin JavaScript.

Las completadas ofrecen **Reabrir tarea**, motivo y confirmación explícita; cancelar
no guarda ni reinicia el borrador. El 100% muestra **Preparación completada** y
**Volver al plan**. Los errores de validación, concurrencia, red y timeout mantienen
el formulario y el texto. No cambian las reglas de permisos, aprobación o estados.

La lectura de la base activa encontró la demo 2 **ya en su plan v2, revisión 3, con
las seis tareas completadas y 100%**. Cada registro conserva versión 1. Son acciones
previas del organizador, no resultados de estas pruebas. El render del propietario
con RequestFactory devuelve 200, muestra el cierre y seis controles de reapertura;
no se creó sesión, reabrió, reinició ni completó ninguna tarea real. Job y AIUsage
siguen en cero.

| Comprobación | Resultado |
| --- | --- |
| Pruebas específicas | 46/46 correctas en 4,527 s: 18 nuevas y 28 existentes; cierre, siguiente pendiente, reapertura, errores, reintentos, permisos, CSP y límite de consultas. |
| Suite completa final | 636 pruebas; 629 correctas y siete PostgreSQL omitidas; 52,883 s, salida 0. |
| Configuración | `check`, `makemigrations --check --dry-run` y sintaxis de ambos JS correctos. Sin migraciones o dependencias nuevas. |
| Entorno de navegador | 127/127 con Edge headless y Python Playwright existentes; Browser plugin not available. SQLite desechable y puerto loopback efímero. Sin datos activos ni puertos 8000/8001. |
| Identidad y presentación | Página y contenido correctos, sin pantalla vacía u overlay. Escritorio 1440×1000 claro; móvil 390×844 oscuro y movimiento reducido; sin desbordamiento horizontal. Tres capturas inspeccionadas. |
| Recorrido | Completar seis → cierre/autoavance/foco → 100%; reapertura con nota, cancelar, repetir, saltar completadas y continuar desde el inicio. También navegación sin JS. |
| Recuperación | Nota obligatoria, versión obsoleta, fallo de conexión y timeout conservan el editor/borrador. Sin escrituras al abrir, cancelar o navegar. |
| Demo de adaptación | 100% → 66% → 100%; conflicto HTTP 400 con las dos restricciones esperadas. Plan vigente, avance e historial preservados. GICA aislado intacto. |
| Consola y seguridad | Cero errores inesperados y cero infracciones CSP en ejecución final. Errores de red, timeout y 400 provocados separados en el JSON. |
| Consumo | Cero solicitudes a proveedores, trabajos, consumos y mensajes IA en QA. Sin worker. |
| Servicio actualizado | `runlocal --port 8001`, PID 20592, sesión 28310. Salud 200; acceso anónimo redirige al login; JS/CSS 200. Sin detener 8000 ni transferir claves de otra terminal. |

El navegador detectó que HTMX intentaba restaurar el atributo `style` al sustituir
filas y el resumen. Se excluyó de `attributesToSettle`, manteniendo `class`, `width`
y `height`; no se modificó el vendor ni se relajó CSP. Una prueba mantenida comprueba
la configuración y las cabeceras reales de GET/POST sin estilos inline o eval.

Evidencia en `Temporal/qa-task-flow/results.json` y tres capturas:
`next-task-desktop-light.png`, `all-completed-desktop-light.png` y
`all-completed-mobile-dark.png`. Son imágenes de QA aislada. El script, base temporal,
servidor de pruebas e imagen sustituida se retiraron. La instancia 8001 permanece
disponible para Jorge. Siguen pendientes las siete pruebas PostgreSQL, la inferencia
autorizada y la validación de carga/despliegue; esta mejora no acredita ejecución
real de tareas o del evento.

## Demo 2: recorrido guiado manual — 14 de noviembre de 2026

Jorge pidió completar el recorrido con otra demo. Se implementó un taller ficticio
de IA responsable para equipos: 20/11/2026 18:00, America/Lima, aforo supuesto de 30,
cuatro sesiones y seis tareas. La ficha y entrevista identifican sus datos como
supuestos ficticios. La carga real deja **una propuesta pendiente, sin plan aprobado
ni estados de tareas**. Las aprobaciones y los estados requieren acciones explícitas
del organizador; la carga no representa ejecución ni inferencia.

El recorrido permite revisión y descarte/recreación idempotente, aprobación exacta,
seguimiento con notas y porcentaje, ampliación de práctica de 40 a 55 minutos y
desplazamiento de preguntas/cierre. En una base consecutiva sin editar la ficha,
cuatro tareas mantienen su avance; cambia el ensayo y su cierre dependiente vuelve
a pendiente. Se comprobó **100% → 66% → 100%** preservando actor, fecha, notas e
historial de las tareas anteriores. El solapamiento de ejemplo se rechaza sin crear
otra candidata ni alterar el plan. No se implementó un solver o interpretación IA.

| Comprobación | Resultado |
| --- | --- |
| Pruebas mantenidas de la demo | 27/27 correctas; carga, permisos, CAS, CSRF, ausencia de llamadas y ejecución, descartes, herencia selectiva y recuperación. |
| Suite completa | 618 pruebas; 611 correctas y siete PostgreSQL omitidas; 50,687 s, salida 0. |
| Configuración | `check` y `makemigrations --check --dry-run` correctos, sin migraciones. |
| Navegador | 60/60 con Edge headless y Python Playwright existentes; Browser plugin not available. SQLite y puerto efímero aislados, sin usar datos reales o 8000. |
| Identidad y contenido | Índice, guía, candidata, plan y porcentaje visibles; sin página vacía ni overlay. |
| Interacción | Descartar → recrear/reusar → aprobar → tareas 100% → cambio → 66% → revisar dos tareas → 100%. Otro contexto recibe 409; conflicto recibe 400; recuperación tras recargar. |
| Consola y red | Cero errores JS/relevantes; cuatro respuestas HTTP deliberadas de prueba separadas. Sin llamadas a proveedores o tráfico externo. |
| Presentación | 1440×1000 claro, 390×844 oscuro y formularios sin JavaScript. Sin desbordamientos ni controles recortados; tres capturas inspeccionadas. |
| Conservación de GICA | Huella idéntica antes/después del recorrido aislado. |
| Personalizaciones | Editar ficha o entrevista bloquea los ejemplos fijos y conserva la edición. Repetir la carga no reinicia decisiones, descartes o tareas. |
| Base real | Se creó sólo el nuevo evento y su candidata pendiente. Once modelos previos conservados por huellas; segunda carga con huellas idénticas. Tres eventos en total; nuevo evento sin plan y cero tareas registradas. Presupuesto USD 0, pago deshabilitado, perfil activo nulo, Job 0 y AIUsage 0. Checklist conservado. |

Evidencia en `Temporal/qa-journey-demo/results.json` y tres imágenes:
`guide-desktop-light.png`, `change-review-desktop-light.png` y
`complete-mobile-dark.png`. La captura de 100% corresponde exclusivamente a la base
aislada de QA, no al progreso de Jorge. Script auxiliar, base temporal y servidor de
pruebas retirados. No se instalaron dependencias ni se modificaron credenciales.

La revisión de permisos rechazó detener el PID 1756 que ocupaba 8000: el ejecutable
estaba asociado al runtime principal de Codex y no estaba inequívocamente identificado
como servidor independiente. El intento normal recibió acceso denegado; la elevación
fue rechazada por riesgo de finalizar la sesión. Se conservó ese proceso y se abrió
una instancia independiente, **127.0.0.1:8001**, con `runlocal --port 8001`: PID 24368,
sesión de herramienta 41154. Salud 200, nueva ruta anónima 302 al login y CSS 200.
El render del propietario con RequestFactory es 200, sin crear una sesión o cambiar
registros. La instancia nueva no extrae la clave privada de otra terminal y no
inicia worker. No se intentó terminar el proceso rechazado por otro mecanismo.

Límites: esta demo completa un ensayo manual del núcleo de planificación. Siguen
pendientes IA real autorizada, decisiones fijadas, conservación selectiva tras
edición material de requisitos, participantes/cierre, PostgreSQL, carga y paquete
de entrega. No se marcan estas fases como completas por haber añadido ejemplos.

## Arranque y apagado local — 13 de noviembre de 2026

Jorge pidió cómo ejecutar su software y un botón que detenga su ejecución. Se añadió
`Iniciar SparkX.cmd`, que llama al comando `runlocal` con el Python existente. El
comando sirve web y archivos estáticos únicamente en 127.0.0.1, sin reloader, worker,
instalaciones, migraciones automáticas o inferencia. Las migraciones pendientes
impiden el inicio y se explican en consola; un segundo arranque no toma el puerto
ocupado ni termina el proceso anterior.

**Apagar SparkX** aparece al superusuario técnico local activo; no se concede a
Administradores del portal, Organizadores o Revisores. GET abre la confirmación;
POST necesita sesión, CSRF, checkbox y firma de dos minutos por usuario/ejecución,
además de origen loopback, Host/puerto correctos y ausencia de cabeceras de proxy.
Fuera de `runlocal` o con DEBUG desactivado la operación no está disponible. No se
usa PID, shell o apagado de Windows. La web deja de aceptar solicitudes nuevas y
espera las activas; el tiempo de inactividad de sockets no es un plazo total de cierre.
Los datos guardados permanecen y los workers externos, si se iniciaran, son independientes.

| Comprobación | Resultado |
| --- | --- |
| Pruebas específicas mantenidas | 32/32 correctas; permisos, CSRF real, token/caducidad/reinicio, revocación en DB, origen/Host/proxy, arranque y cierre. |
| Suite completa | 591 pruebas: 584 correctas y siete PostgreSQL omitidas, 97,019 s, salida 0. `check` y `makemigrations --check --dry-run` sin incidencias. |
| Socket real | HTTP/1.0 y cierre anunciado, hilos no daemon, puerto exclusivo en Windows, timeout de socket y limpieza del controlador. |
| Navegador | 50/50 comprobaciones en 33,244 s con Edge headless y Python Playwright existentes. Browser plugin not available; mismo fallback autorizado previamente. |
| Identidad, contenido y errores visuales | Eventos y confirmación correctos, contenido legible, sin página vacía u overlay de error. |
| Consola y red | Cero errores de consola, excepciones de página, solicitudes fallidas o tráfico externo en la ejecución final. |
| Interacción | Eventos → Apagar → Cancelar conserva servicio; casilla obligatoria → confirmar devuelve HTML completo → listener cerrado → reinicio en el mismo puerto con identidad nueva. También sin JavaScript. |
| Responsive y temas | 1440×900 claro y 390×844 oscuro; sin overflow ni solapamiento de controles; capturas inspeccionadas. |
| Estado de datos real | adminjorge activo y superusuario; presupuesto USD 0, pago deshabilitado, perfil activo nulo; cero Job y AIUsage. No se alteró el checklist ni se crearon usuarios reales. |

La prueba real detectó que un resultado basado en la plantilla general intentaba
descargar recursos después de cerrar el listener. Se corrigió con un resultado
independiente, sin solicitudes de recursos y CSS autorizado mediante un nonce nuevo
generado por el servidor; sin `unsafe-inline` ni scripts. También se corrigió la
versión del responder WSGI para que cierre la conexión de forma coherente. La revisión
independiente posterior no encontró bloqueantes en el alcance leído; no es un pentest.

Evidencia final en `Temporal/qa-local-runtime/results.json` y tres capturas:
`confirm-desktop-light.png`, `confirm-mobile-dark.png` y
`shutdown-requested-desktop.png`. Script auxiliar y base de pruebas eliminados;
ningún dato ni puerto del servicio habitual se usó en esa QA.

Se detuvo únicamente el servicio anterior de esta sesión (runserver PID 17764) y se
inició el nuevo mediante el propio lanzador: PID 17024, sesión de herramienta 47906,
127.0.0.1:8000. Salud y login 200; apagado anónimo 302 al login; respuesta HTTP/1.0.
La clave privada de otra terminal no se extrajo ni transfirió. No se inició worker
ni se realizaron llamadas API. Uso público, servidor de producción, dispositivos
físicos y otros navegadores quedan fuera de esta comprobación local.

## Login, usuarios y roles — 13 de noviembre de 2026

Solicitud de Jorge: login profesional, gestión de usuarios inspirada en las capturas
de su portal de revisión y generador aleatorio de contraseñas. Confirmó expresamente
Administrador, Organizador y Revisor con eventos asignados, y acceso por correo o
usuario. La URL de referencia no fue accesible desde la herramienta web; la comparación
visual usa sus dos capturas y el sistema visual existente, sin inventar una inspección
de ese portal autenticado. No se generaron imágenes ni cambiaron las paletas aprobadas.

- Login independiente de la navegación privada, claro/oscuro y mostrar/ocultar
  contraseña. Conserva `adminjorge` y las credenciales existentes. Rechaza aliases
  ambiguos y mantiene mensajes de autenticación genéricos y redirecciones seguras.
- Usuarios: tabla de nombre/correo, rol, estado y acceso; crear cuenta en diálogo
  con foco/Escape y formulario sin JavaScript. Roles y activación usan POST, CSRF
  y versión esperada; no se pueden desactivar/destituir la propia cuenta ni alterar
  las cuentas técnicas protegidas. El Administrador de portal no recibe staff,
  superusuario ni permisos de gasto. Se mantiene al menos un administrador activo.
- Generador de 20 caracteres con Web Crypto y rechazo uniforme; mostrar/copiar
  explícitos, sin `Math.random`, red, logs o almacenamiento del navegador. Alta
  manual de 16–128 caracteres con validadores y hash de Django. No se reimprime la
  contraseña ante errores; se limpia al cerrar el diálogo o salir de la página.
- Cuentas nuevas con cambio inicial obligatorio. Versiones separadas para revocar
  sesiones y concesiones; cambiar contraseña conserva asignaciones de revisión,
  mientras cambiar rol o activación invalida sesiones y concesiones anteriores.
- Organizador/Administrador asignan revisores únicamente a sus eventos propios.
  Revisor consulta ficha, agenda aprobada y estados; no accede al chat privado,
  candidatas, edición o gestión de IA. Revocar el acceso devuelve 404 al consultar
  un evento ya no asignado. Los comandos de evento también rechazan su escritura.
- Límite de intentos persistido con HMAC, sin identificador ni dirección en claro:
  cinco por origen/identificador y cincuenta por origen en 300 segundos. No confía
  en cabeceras arbitrarias de IP. Detrás de proxy debe validarse la IP confiable.

| Comprobación | Resultado |
| --- | --- |
| Suite completa con runner Django | 559 pruebas; 552 correctas, siete PostgreSQL omitidas; 92,439 s; salida 0. |
| Servicios nuevos | 23 correctas y una carrera de administradores omitida por requerir PostgreSQL. |
| HTTP y autenticación nuevos | 52 correctas con migraciones, SQLite en memoria y sin red. |
| Cuentas y seguimiento tras optimización | 104 pruebas; 103 correctas, una PostgreSQL omitida. Se mantiene el tope anterior de consultas sin aumentar el límite de la prueba. |
| `check`, `makemigrations --check --dry-run` | Sin incidencias y sin cambios de modelo pendientes. |
| Migraciones | events.0004, accounts.0001 y accounts.0002 aplicadas. Huellas de once modelos de negocio y metadatos de User iguales, excluyendo la columna nueva. Trece usuarios conservados; trece perfiles y un lock creados; cero asignaciones e intentos de login reales nuevos. La migración no escribe contraseñas. |
| Render actual | Usuarios privado y login HTTP 200 con RequestFactory, sin mutaciones de negocio. |
| Identidad, contenido y estado visual | Login y módulo correctos; sin página vacía ni overlay de error. |
| Consola y red | Cero errores de aplicación y solicitudes externas. HTTP 400, 404 y 409 deliberados se registraron aparte. |
| Flujo e interacción | Usuario/correo → Usuarios → modal → generar/copiar → alta → cambio inicial → asignación → consulta Revisor → revocación. También roles, activación, CAS y error sin contraseña reimpresa. |
| Escritorio y móvil | Claro 1440×900 y oscuro 390×844; sin desbordamiento del documento o controles recortados. Tabla móvil con desplazamiento interno; login, lista y alta también sin JavaScript. |

**Browser plugin not available**; fallback autorizado con Playwright Python/Edge
headless existentes, contexto separado, SQLite en memoria configurada antes de
Django y servidor de pruebas en puerto aleatorio. **51/51 comprobaciones** en
15,339 s. Cinco capturas inspeccionadas en `Temporal/qa-accounts`: login-desktop.png,
users-desktop.png, create-modal-desktop.png, login-mobile-dark.png y
create-modal-mobile-dark.png; resultados, comparación de seis puntos y diferencias
intencionales en results.json. Referencia conservada: tabla de cuatro columnas,
orden de campos, tipografía compacta, blanco/teal y espaciado. Variantes explícitas:
marca SparkX, tres roles aprobados, generador y modo oscuro. No se afirma clon exacto
de una ventana completa a partir de capturas parciales. Script temporal retirado.

Revisión independiente de autoridad, login, sesiones, onboarding y backfill sin
hallazgos materiales pendientes en el alcance leído. Se separaron las versiones de
sesión y acceso para conservar asignaciones tras cambiar contraseña. La suite detectó
consultas repetidas en los permisos de presentación; se corrigieron con un snapshot
por solicitud y perfiles precargados, manteniendo comprobaciones frescas en servicios.
Esto no equivale a pentest, carga, MFA o validación de concurrencia en SQLite.

La web habitual estaba detenida. Se inició `runserver --noreload` en 127.0.0.1:8000:
health 200, login nuevo 200 con no-store y Usuarios anónimo 302. PID observado 17764,
sesión de herramienta 9727. Este proceso no hereda la OPENAI_API_KEY de la terminal
privada anterior; no se extrajo ni transfirió. Cuenta IA conservada sin perfil activo,
pago deshabilitado, USD 0 y cero trabajos/consumos. No se inició worker, no se enviaron
correos ni se crearon cuentas reales desde la nueva interfaz. El checklist manual se
conserva; cambiar la contraseña de Jorge antes de acceso público sigue siendo manual.

Límites pendientes: siete pruebas PostgreSQL, dispositivo móvil físico, otros
navegadores, carga y exposición pública con HTTPS/DEBUG=False/IP confiable. QA usa
movimiento reducido; no mide animaciones. No hay SSO, MFA, registro público ni
recuperación de contraseña por correo. Fuentes: [Django](https://docs.djangoproject.com/en/5.2/topics/auth/default/),
[contraseñas](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/) y
[OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

## Entrevista guiada local — 12 de noviembre de 2026

Recorrido: evento → **Entrevista guiada** → guardar una respuesta → siguiente punto
no revisado → resumen editable → corregir y recargar. Ruta
`/events/<id>/interview/`; no necesita perfil, presupuesto o worker.

- Siete preguntas sobre objetivo, público, modalidad, duración, lugar/acceso,
  recursos y restricciones. Los datos básicos y la descripción se consultan desde
  la ficha; no se extraen hechos ni se promueve automáticamente un supuesto.
- Estado y texto persistidos: Confirmado por mí, Supuesto de trabajo, Pendiente,
  referencia a la ficha y No aplica donde corresponde. Duración confirmada o
  supuesta entre 1 y 1440 minutos; texto por respuesta acotado a 1000 caracteres.
  El recuento de puntos revisados no acredita tareas ejecutadas ni factibilidad.
- Guardado explícito con propiedad, CSRF, validación y revisión esperada. Un
  conflicto HTTP 409 conserva los campos y muestra la respuesta y ficha actuales;
  requiere comparar y volver a guardar. Un guardado idéntico no crea otra revisión.
- Las respuestas alimentan el contexto común de planes y chat. El plan y progreso
  vigentes se conservan. Cambiar requisitos invalida candidatas anteriores; con la
  política conservadora existente, al aprobar un plan posterior sus tareas vuelven
  a pendientes y el historial anterior permanece. El formulario advierte este límite.
- Si cambia la descripción, las respuestas que remitían a ella vuelven a pendientes.
  Las respuestas escritas explícitamente se conservan. No hay solver ni validación
  automática de las restricciones textuales.

| Comprobación | Resultado |
| --- | --- |
| Suite completa con el runner Django | 483 pruebas; 477 correctas, seis PostgreSQL omitidas; 44,348 s; salida 0. |
| Reglas, vistas de entrevista, edición y contexto de tareas | 49 correctas; incluye 14 reglas y 17 pruebas nuevas de vistas. |
| Adaptadores actualizados al nuevo campo del evento | 49 correctas, con respuestas HTTP controladas. Las fixtures de eventos sintéticos incluyen la entrevista vacía. |
| Vistas después del ajuste final móvil y de duración | 17 correctas; 0,759 s. |
| `check` y `makemigrations --check --dry-run` | Sin incidencias ni cambios de modelo pendientes. |
| Migración `events.0003_event_interview_answers` | Aplicada. Huellas y recuentos de once modelos conservados, excluyendo la columna añadida; dos eventos con respuestas inicialmente vacías. |
| Render privado con los datos actuales | Pregunta y resumen HTTP 200 con RequestFactory; sin cambios en datos de negocio. |
| Identidad, pantalla y errores de interfaz | Contenido correcto y ningún overlay de error. |
| Consola y red | Cero errores de aplicación, advertencias, excepciones de página o tráfico externo. El diagnóstico HTTP 409 deliberado se registra aparte. |
| Interacción y persistencia | Guardado, resumen, edición, recarga, duración inválida, conflicto y reenvío explícito correctos. También guardado y resumen sin JavaScript. |
| Escritorio y móvil | Claro 1440×900, oscuro 390×844; sin desbordamiento ni solapamiento. Corregido el orden móvil para mostrar la pregunta antes de la navegación; título visible sin scroll entre y710 y762. |

**Browser plugin not available**; fallback Playwright Python existente con Edge
headless separado, autorizado previamente. `StaticLiveServerTestCase`, SQLite en
memoria y puerto aleatorio, configurados antes de inicializar Django. Último ensayo
17,786 s: **50 comprobaciones automáticas y una inspección visual correctas**.
Evidencia vigente: `Temporal/qa-event-interview/results.json`, `question-desktop.png`,
`summary-desktop.png`, `question-mobile.png` y `conflict-mobile.png`. Cuatro capturas
inspeccionadas; retirado el script de una sola ejecución y sustituidas las capturas
anteriores. Sin dependencias nuevas ni fixtures sobre la base activa.

La revisión independiente detectó las fixtures que requerían el campo nuevo y el
límite de conservación de estados en aprobaciones futuras; ambos quedaron cubiertos
por cambios, pruebas y documentación. No equivale a una auditoría de seguridad ni a
una prueba de concurrencia. Siguen pendientes PostgreSQL, carga, inferencia real,
otros navegadores y móvil físico. QA usó movimiento reducido; no midió animaciones.

Cuenta de Jorge conservada: sin perfil activo, pago deshabilitado y presupuesto
USD 0; cero trabajos y consumos. No se recibió ni extrajo la clave ni se inició worker.
La web habitual respondió `/health/` HTTP 200 y la ruta nueva HTTP 404 porque aún
carga el código anterior con `--noreload`. No se detuvo ese proceso: debe reiniciarse
desde su misma terminal para conservar la variable privada. El checklist personal
no se completó por construir esta función; todavía falta su revisión por Jorge.

## Reinicio y actualización del checklist — 12 de noviembre, 14:35 Lima

Por instrucción de Jorge se reinició únicamente la web local. Se verificó
`/health/` como SparkX antes de detener el proceso que escuchaba en 127.0.0.1:8000
y el proceso nuevo respondió HTTP 200 con `service: sparkx, status: ok`.
No se inició worker. La comprobación de presencia confirmó que el entorno de este
arranque no contiene OPENAI_API_KEY; la clave que Jorge cargó permanece en su
terminal privada y no se leyó ni transfirió.

Se actualizaron los datos de Checklist SparkX mediante `update_progress` con
versión esperada y una transacción, sin cambiar código ni crear migraciones:

| Punto | Estado y confirmaciones |
| --- | --- |
| Créditos y cuota | Completado, conservado íntegramente como ya estaba registrado; tres confirmaciones. |
| Credencial privada | En proceso; confirmada únicamente la creación dedicada. Acceso desde web/worker e indicador siguen pendientes. |
| Presupuesto | En proceso; confirmada ausencia de autorización de gastos adicionales. Sin cifra ni límites locales nuevos. |
| Recorrido real y resto | Conservados sin nuevas marcas; no se acredita inferencia real. |

Lectura posterior independiente y render de la vista privada HTTP 200: **1/15
completado, 2 en proceso, 6%**; cero puntos antiguos por revisar. Es porcentaje del
checklist personal, no del desarrollo del proyecto. Los recuentos de otros nueve
modelos y los valores de AIAccount permanecieron iguales: perfil activo nulo,
pago deshabilitado, presupuesto USD 0 y límite mensual 200 000 tokens.
No hubo solicitudes a proveedores. Sigue vigente «solo preparar, todavía sin llamadas».

Relevo posterior para configuración privada: Jorge confirmó la creación del perfil
Mini. La lectura de la base mostró perfil 1 desactivado, versión 2; al releerlo ya
estaba así y no fue necesario escribirlo. Cuenta sin perfil activo, pago deshabilitado
y USD 0, sin nuevos trabajos o consumos. Se detuvo la web propia verificada y se
comprobó libre el puerto 8000 para que Jorge inicie `runserver --noreload` desde su
terminal con la clave. **El arranque privado todavía no se ha observado**; no hay
worker ni inferencia. El estado vigente de este relevo se registra en estado.json.

Confirmación posterior del relevo: Jorge indicó «Ya aparece ok» y una consulta
independiente a `/health/` devolvió HTTP 200 con servicio SparkX. La presencia de la
clave en ese proceso todavía requiere revisar el indicador local del perfil; la
salud de la web no demuestra validez o acceso a OpenAI. La lectura de configuración
mantiene perfil Mini desactivado, ningún perfil seleccionado, pago deshabilitado y
presupuesto USD 0. No se inició worker ni se hizo una llamada al proveedor.

Confirmación del indicador: Jorge comunicó «Referencia de conexión disponible ·
límite 24000 entrada / 2500 salida». La base muestra el perfil Mini habilitado,
versión 3, sin perfil seleccionado y con pago deshabilitado y presupuesto USD 0.
Se registró únicamente `credencial_privada_indicador` junto a la credencial dedicada
ya confirmada, mediante versión esperada; el punto sigue En proceso porque falta
el acceso privado del worker. Se conservaron cuenta y recuentos de trabajos/consumo.
El indicador acredita presencia local según la interfaz reportada, no validez de la
clave o acceso al proveedor. Sigue vigente la instrucción de no realizar llamadas.

Revisión manual posterior de la demo: Jorge declaró «ya revise todo y esta ok»
después de recorrer ficha/afiche, supuestos, agenda y preparación. Se registraron
`supuestos_gica_afiche` y `supuestos_gica_separados`; el punto sigue En proceso
porque la confirmación sobre cómo presentará el caso no se dio expresamente.
Esto no acredita el recorrido con IA real ni una prueba física de voz. Lectura
posterior: **1/15 completado, 3 en proceso, 6%** y render privado HTTP 200.
Los demás puntos, configuración de cuenta/perfiles y recuentos de los modelos de
negocio permanecieron iguales; cero trabajos y cero consumos. No se inició worker
ni se hicieron llamadas. La entrevista guiada sigue pendiente de construcción.

Prueba física declarada de dictado: Jorge confirmó «si funciona bien el dictado»
tras las instrucciones de probar el micrófono sin enviar el texto. Se registró
`demo_voz_microfono`; voz por turnos permanece En proceso. La corrección del texto,
lectura/detención de respuestas y conversación con IA no se dan por verificadas.
Checklist: **1/15 completado, 4 en proceso, 6%**; render privado HTTP 200. Los demás
puntos y la cuenta IA se conservaron; siguen cero trabajos y cero consumos.

## Preparación de GPT-5.4 mini del 12 de noviembre

Se añade `openai_54_mini` al catálogo con tarifa Standard 0,75 / 0,075 / 4,50 USD
por millón de tokens, fecha propia 12/11 y modalidad `paid`. El modelo usa Responses
con JSON estricto en planes, `store: false`, `service_tier: default` y razonamiento
`none`. Su caché automática se diferencia de la política explícita de Luna.
Fuentes: [modelo](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[caché](https://developers.openai.com/api/docs/guides/prompt-caching) y
[Responses](https://developers.openai.com/api/reference/resources/responses/methods/create).

El servidor conserva autorización y presupuesto positivo antes de despachar. No
infiere gratuidad, saldo ni activación de incentivos. Con máximos 24 000 / 2500,
reserva USD 0,029250 sin anticipar descuento. El comparador muestra siete opciones;
calculadora e historial conservan caché incluida en entrada y tarifas por solicitud.
Se mantiene la fecha de los presets anteriores. La revisión independiente estática
no detectó hallazgos materiales; no equivale a una certificación de seguridad.

Comprobaciones ejecutadas:

| Comprobación | Resultado |
| --- | --- |
| Suite completa `python -B manage.py test --verbosity 1` | 452 pruebas; 446 correctas, seis PostgreSQL omitidas; 44,716 s; salida 0. |
| Adaptadores `apps.assistant.test_providers apps.assistant.tests` | 49 correctas, incluidas cuatro nuevas de Mini y rechazo de modalidad gratuita. |
| Gestión IA `apps.ai_management` | 140 pruebas, 139 correctas y una PostgreSQL omitida; seis nuevas de tarifas, fechas, caché, reserva bruta y consentimiento. Es parte de la suite completa. |
| `makemigrations --check --dry-run` | Sin cambios detectados; ninguna migración aplicada. |
| Identidad, contenido y overlay del navegador | Rutas `/ai/providers/`, `/ai/profiles/new/`, `/ai/calculator/` y `/ai/compare/` correctas, contenido visible y sin overlay de error. |
| Interacciones | Catálogo → preparar Mini → guardar perfil sintético → calcular caché → comparar siete opciones, con resultado persistido solo en la base desechable. |
| Consola y red | Cero errores, advertencias, pageerrors, tráfico externo y llamadas API. |
| Evidencia visual | Cinco capturas inspeccionadas en Edge headless separado; 1440×900 claro y 390×844 oscuro. Sin desbordamiento del documento; tabla móvil con scroll contenido. |

Navegador: **34/34** comprobaciones. Browser plugin not available; fallback existente
Playwright/Edge autorizado, sin instalar dependencias. `StaticLiveServerTestCase`
usa SQLite en memoria configurada antes de inicializar Django y un usuario QA
sintético. El perfil guardado no queda seleccionado ni habilita pago; cero trabajos
o consumos creados. Escenario de cálculo: 1000 entrada, 400 incluidos en caché y 300
salida da USD 0,001830 por solicitud y USD 0,045750 por 25. Es simulación, no gasto.
El navegador de QA usa movimiento reducido para capturas estables; no se evaluaron
animaciones ni voz en este incremento.

Jorge aportó capturas de Personal / SparkX-Pruebas, saldo USD 61, vencimiento 22/11
y límites de Mini 2 000 000 TPM / 5000 RPM. Declara sharing activado y confirmó
`True` para la presencia de la clave en su propia terminal. No se recibió o leyó el
secreto ni se comprobó acceso real. La cuenta, presupuesto y perfiles activos no se
modificaron; no se inició worker ni se reinició el servicio habitual. El catálogo
nuevo estará disponible en ese proceso tras reiniciarlo. Las pruebas aislaron sus
datos; no acreditan configuración del proceso habitual ni condiciones contractuales
de la oferta. Sigue pendiente la validación PostgreSQL y cualquier llamada real
requiere una nueva instrucción que revoque «solo preparar, todavía sin llamadas».

Evidencia: [34 comprobaciones](../Temporal/qa-openai-mini/results.json),
[proveedores escritorio](../Temporal/qa-openai-mini/providers-desktop.png),
[calculadora](../Temporal/qa-openai-mini/calculator-desktop.png),
[comparador escritorio](../Temporal/qa-openai-mini/comparison-desktop.png),
[comparador móvil](../Temporal/qa-openai-mini/comparison-mobile.png) y
[proveedores móvil](../Temporal/qa-openai-mini/providers-mobile.png).
El script de una sola vez se retiró; solo se retienen resultados y cinco capturas
en Temporal. [Guía y preparación privada](guias/ai-management.md#preparación-de-gpt-54-mini-del-12-de-noviembre).

## Checklist temporal del proyecto — incremento del 9 de noviembre

Disponible para administradores en [Checklist SparkX](http://127.0.0.1:8000/project-checklist/).
Los 15 puntos del checklist manual se organizan en cuatro etapas. Cada usuario guarda
su propio avance: No iniciado, En proceso, Completado y, en cinco puntos condicionales,
No aplica. El porcentaje considera únicamente los puntos aplicables. La declaración
manual no configura servicios, acredita inferencia, autoriza pagos ni realiza envíos.
No se reciben notas ni secretos; las tareas de eventos y el diario IA están separados.

**Suite de este incremento del 9 de noviembre: 389 pruebas, 383 correctas y 6 omitidas por requerir PostgreSQL**,
salida 0, 51.099 segundos. El incremento aporta 30 pruebas de permisos, CSRF,
propiedad, GET sin escrituras, catálogo, validación, porcentaje, restricciones de DB,
versiones e idempotencia. Formularios inválidos responden 400 y pestañas obsoletas,
409 con datos actuales. Django check y makemigrations --check --dry-run correctos.
La migración aditiva project_checklist.0001_initial fue aplicada a la base local.

**Navegador: 67/67 comprobaciones correctas** con Playwright 1.61.0 / Edge existente.
Browser plugin ausente; fallback aislado autorizado. Escritorio 1663×946 claro y
móvil emulado 390×844 oscuro, teclado y formulario sin JavaScript. Se verificaron
guardado, PRG con etapa abierta, recarga persistente, porcentaje, No aplica, aislamiento
de usuarios, acceso staff, CSRF y versiones. Cero errores JS/CSP, advertencias, recursos
fallidos, peticiones externas o desbordamientos. Las dos capturas se inspeccionaron
visualmente y muestran únicamente **datos sintéticos QA**, no avances de Jorge.

La prueba de integración local devuelve 200 con 15 puntos; GET no crea registros.
Las huellas de los modelos existentes de eventos, planes, asistente, trabajos y
Gestión IA coinciden antes/después. No hubo llamadas reales a proveedores, gastos
API ni dependencias nuevas. No se probaron credenciales reales, voz, OVH, carga ni
concurrencia PostgreSQL. Las seis omisiones concurrentes previas siguen pendientes.

La herramienta está activa por defecto sólo en desarrollo. SPARKX_CHECKLIST_ENABLED=0
oculta el enlace y deshabilita las rutas conservando el progreso. El proceso local
se inició en segundo plano con ventana oculta en 127.0.0.1:8000; /health/ respondió
200 y el checklist anónimo redirigió al acceso. La base, sesiones, scripts, estáticos
y servidor 8001 de QA fueron retirados. Sólo se conservan dos capturas y su resultado;
el script de integración utilizado también se eliminó.

Evidencia: [pruebas de servidor](../Temporal/project-checklist/server-tests.json),
[integración y preservación local](../Temporal/project-checklist/local-integration.json),
[67 comprobaciones de navegador](../Temporal/qa-project-checklist/results.json),
[escritorio claro](../Temporal/qa-project-checklist/checklist-light-desktop.png) y
[móvil oscuro](../Temporal/qa-project-checklist/checklist-dark-mobile.png).
[Uso y desactivación del módulo](../README.md#checklist-temporal-del-proyecto).


## Comparador y consumo por evento — incremento del 9 de noviembre

Disponible en [Comparador](http://127.0.0.1:8000/ai/compare/) y
[Historial de uso](http://127.0.0.1:8000/ai/usage/). Se comparan seis presets con
un escenario manual o con el historial filtrado por evento, acción y mes. PEN es
una conversión declarada con tasa/fecha/fuente; los créditos siguen en la calculadora
individual y la contabilidad permanece en USD. [Guía vigente](guias/ai-management.md).

**Servidor: 359 pruebas, 353 correctas y 6 omitidas por PostgreSQL**, salida 0.
Incluye 22 pruebas de informes, 33 HTTP nuevos, 32 regresiones de Gestión IA y
45 de adaptadores. Se comprueban propiedad, CSRF, GET/POST inválidos, cobertura,
cero/desconocido, redondeo por llamada, subtotales, filtros/paginación,
rango de contexto, conversión PEN y ausencia de cambios en presupuesto/diario.
Las seis omisiones concurrentes siguen pendientes; SQLite no acredita esos locks.

Django check, makemigrations --check --dry-run y node --check de
ai-comparison.js correctos. No se necesita otra migración. Estáticos recopilados
y servidor de uso actualizado en 127.0.0.1:8000. Nueve rutas y los POST de escenario
manual, PEN e historial respondieron 200 con CSRF. Nueve hashes de ficha, planes,
candidatas, progreso, auditoría, cuenta IA, perfiles, consumo y trabajos coinciden
antes/después; la sesión de verificación se retiró.

La verificación oficial de tarifas detectó escrituras implícitas de caché OpenAI.
La conexión ahora usa modo explícito sin breakpoints; el comparador aplica entrada
normal sin descuento para ese perfil. Escrituras inesperadas impiden liquidar
automáticamente el costo. Groq valida entrada acotada más salida reservada antes de
HTTP. Compatibilidad real con la cuenta/proveedor todavía requiere una inferencia
acotada; este incremento no realizó ninguna.

### Navegador: 153 comprobaciones correctas

Flujo: escenario manual → seis opciones → PEN → historial por evento/acción/mes →
cobertura y comparación → navegación al evento y calculadora individual.
Playwright 1.61.0 / Edge 157.0.4341.42 existentes, escritorio 1663×946 y móvil táctil
emulado 390×844, temas claro/oscuro, teclado y formulario sin JavaScript.
Browser plugin ausente; navegador aislado autorizado.

| Comprobación | Resultado |
| --- | --- |
| Identidad, contenido y pantalla de error | Rutas correctas, contenido útil y sin overlay |
| Cálculos | Redondeo por solicitud, seis importes, caché, PEN y créditos separados |
| Historial | Filtros y páginas preservados; conocidos, excluidos y pendientes explícitos |
| Permisos y persistencia | Evento ajeno rechazado; comparar no cambia cuenta, perfil, diario, evento ni trabajos |
| Apariencia | Dos capturas inspeccionadas; desplazamiento local de tablas, sin desborde del documento |
| Salud final | Cero errores JavaScript/CSP, recursos fallidos o solicitudes externas; 15 rechazos HTTP esperados |
| Limpieza | Navegador/servidor 8001 cerrados; DB, sesiones, scripts y estáticos QA eliminados |

La corrida final aislada usa DEBUG=False para comprobar las páginas de error públicas.
La exploración con DEBUG=True detectó tres bloqueos CSP de estilos de la página
técnica 404 de Django; se clasificaron como diagnóstico de desarrollo y no se relajó
la política. El mes deliberadamente inválido produjo una advertencia nativa esperada.
La configuración local de QA no acredita un despliegue de producción.

Las capturas usan **datos sintéticos QA**, no consumo real ni saldo de Jorge.
No se probaron otros navegadores, dispositivos físicos, carga, PostgreSQL ni APIs
reales. El PDF/DOCX sigue como una entrega posterior.

Evidencia: [resultados de navegador](../Temporal/qa-ai-comparison/results.json),
[comparador claro de escritorio](../Temporal/qa-ai-comparison/ai-comparison-light-desktop.png),
[historial oscuro móvil](../Temporal/qa-ai-comparison/ai-history-dark-mobile.png),
[pruebas de servidor](../Temporal/ai-management/server-tests.json) y
[integración sin cambios de datos](../Temporal/ai-management/local-integration.json).
Las dos capturas anteriores de Gestión IA se retiraron al quedar sustituidas;
su resultado de 94 comprobaciones se conserva como antecedente.

## Gestión de IA: incremento precedente del 8 de noviembre

El módulo está disponible en [Gestión de IA](http://127.0.0.1:8000/ai/) y en la
navegación principal. Añade perfiles de OpenAI, Groq, Gemini y Ollama local optativo;
calculadora, límites mensuales USD/tokens, reservas por solicitud e historial con
conciliación manual atribuida. [Funcionamiento y fuentes](guias/ai-management.md).

**Servidor: 299 pruebas, 293 correctas y 6 omitidas por PostgreSQL.** Ejecución final
con código de salida 0; 32 pruebas HTTP del módulo también correctas. Las nuevas
pruebas cubren precios del catálogo, caché/razonamiento sin doble conteo, permisos,
CSRF, propiedad, versiones, límites, idempotencia, consumo desconocido/tardío,
cancelación, mes vencido y enteros compatibles con PostgreSQL. Las tarifas quedan
capturadas por trabajo. La comparación y liquidación no dependen de que se publique
una respuesta válida.

Las seis omisiones son aprobación concurrente, salto de filas bloqueadas del worker,
cuota concurrente, cambios competidores de una tarea, repetición concurrente de
su clave y reservas simultáneas entre eventos del mismo propietario. No se presentan
como pruebas superadas. SQLite no valida esos bloqueos.

Django check y makemigrations --check --dry-run correctos. Migración
ai_management.0001_initial aplicada a la base local; estilos recopilados y servidor
reiniciado en 127.0.0.1:8000. La cuenta existente adminjorge conserva pago desactivado,
USD 0 y ningún perfil seleccionado. Ocho rutas locales respondieron 200. No se crearon
perfiles ni consumos reales; la sesión de comprobación fue retirada. Cinco hashes
de ficha, planes, candidatas, progreso y auditoría GICA coinciden antes y después.

La revisión independiente detectó y corrigió el despacho con una reserva de un mes
vencido. También se acotó el total de tokens al rango PostgreSQL y se alineó la
configuración con el bloqueo User antes de AIAccount. Las claves sólo se cargan
desde el entorno; destinos/modelos cerrados, sin redirecciones, proxies heredados,
reintentos ni cambio automático de gratuito a pago.

GicaTesis se analizó sólo en lectura: recibe AIResult y genera documentos. Su propia
documentación atribuye proveedores y presupuesto a GicaGen, otro repositorio no
aportado. No se afirma haber trasladado una calculadora inexistente en la carpeta
recibida. No hubo inferencia real, consulta de saldo, instalación de Ollama, uso del
VPS ni generación DOCX/PDF. La configuración real del proveedor y su cuota siguen
pendientes.

## Referencia corregida: revisión estática posterior

El usuario aportó Proyecto2TesisAI-main y confirmó que era la referencia buscada.
La copia interior contiene GicaGen con simulador de presupuesto y comparación sobre
tokens históricos. La [comparación documentada](guias/ai-management.md#referencia-corregida-gicagen-y-su-presupuesto)
distingue ideas reutilizables y límites del cálculo. Esta revisión no ejecutó GicaGen
ni sus tests, no accedió a secretos y no modificó código ni interfaz de SparkX.
Las mejoras del comparador/PEN permanecen propuestas; los resultados de servidor
e interfaz siguientes corresponden al módulo construido en el incremento anterior.

## Navegador del módulo: 94 comprobaciones correctas

Flujo: /ai/ → crear/editar un perfil → seleccionar presupuesto → simular consumo →
consultar historial → conciliar un registro desconocido. Se comprobaron persistencia,
dos pestañas con versión obsoleta, propiedad, permisos, confirmación gratuita,
pago desactivado por defecto, caché/razonamiento y nota HTML escapada. La calculadora
mostró USD 0,000600 por 1000 tokens de entrada + 1000 de salida con Luna, USD 0,060000
por cien solicitudes y los créditos como escenario independiente.

Entorno aislado: 127.0.0.1:8001, SQLite nueva en Temporal, claves vacías, Ollama
desactivado y sin worker. Edge 157.0.4341.42 / Playwright 1.61.0 existentes.
Browser plugin ausente; fallback de navegador separado autorizado. Escritorio
1663×946 y móvil 390×844 táctil emulado, temas claro/oscuro, teclado y navegación
sin JavaScript. Identidad de página, contenido útil y ausencia de pantalla de error
comprobados en cinco rutas. No se instaló dependencia adicional.

| Comprobación | Resultado |
| --- | --- |
| Páginas, formularios y persistencia | Correctos; perfiles y cuenta propios, conflictos rechazados |
| Tokens desconocidos frente a cero | Diferenciados en UI y sin liberar un consumo desconocido |
| Conciliación manual | Fuente/actor/nota/contadores originales visibles; efecto único |
| Apariencia | Ambas paletas, tamaños y capturas inspeccionadas con view_image |
| Móvil | Tabla reciente corregida: región 324 px, tabla 720 px con scroll local y documento 390 px sin desborde |
| Consola/CSP/red | Sin errores de aplicación, CSP, recursos fallidos o solicitudes externas; ocho HTTP 400 esperados de validaciones |
| Limpieza | Servidor 8001 detenido; SQLite, scripts y sesiones eliminados; quedan sólo dos PNG y results.json |

Las capturas de este antecedente, ahora sustituidas por el incremento actual,
mostraban datos sintéticos QA y un presupuesto de ejemplo de USD 10; no eran
consumo real ni saldo de la cuenta de Jorge. El servidor de uso continúa
en 8000 con los valores iniciales de pago y presupuesto descritos arriba. No se probaron
Safari, Firefox, dispositivo físico, cuotas/saldo reales, carga ni bloqueos PostgreSQL.

Evidencias: [resultados del navegador](../Temporal/qa-ai-management/results.json),
[pruebas del servidor](../Temporal/ai-management/server-tests.json) y
[preservación de datos locales](../Temporal/ai-management/local-integration.json).
Los enlaces a Temporal son evidencias locales ignoradas por Git.

## Interfaz vigente y evidencia precedente

Seguimiento manual de tareas implementado en Preparación: tres estados con color y
texto, nota, actor/fecha, historial, porcentaje y resumen. Se mantienen calendario, paletas
sol/luna y escala FIME: Segoe UI, cuerpo 14 px, títulos 26/17/14, sidebar 218 y barra 53.
Referencia canónica: [sistema visual](arquitectura/design-system.md).

Evidencia actual en Temporal/qa-motion-progress/ (porcentaje/movimiento), resultado
anterior en Temporal/qa-task-progress/, Temporal/qa-plan-scroll/ (agenda) y
Temporal/qa-calendar/ (calendario/formularios). Conceptos y mediciones en
Temporal/referencias/. No se añadieron bibliotecas, fuentes remotas ni CDN.

## Porcentaje y movimiento: 48 comprobaciones actuales correctas

Flujo comprobado: evento de prueba → Preparación → completar → 9 % → reabrir →
0 % → volver a completar → 9 %; recarga y DB coinciden. Hover, foco por Tab/Shift+Tab,
pulsación, replay, cambio de sección y calendario activan los efectos previstos.
No se modificaron los datos del evento original.

Entorno: Edge 157.0.4341.42, Playwright 1.61.0,
http://127.0.0.1:8000/, escritorio 1663×946 y móvil 390×844 con isMobile/hasTouch y
puntero coarse comprobados. Browser plugin ausente; Playwright aislado autorizado.

| Comprobación actual | Resultado |
| --- | --- |
| Identidad, contenido y pantalla de error | Título/ruta correctos, contenido útil y sin overlay |
| H1 | Un bloque se mueve en múltiples frames; texto y nombre accesible únicos, sin máscaras al terminar |
| H2 | Palabras con transformaciones escalonadas; texto original restaurado |
| Botón | Rótulo none → −8,77 → −18,19 px; retorno observado; duración 400 ms |
| Teclado y presión | Foco visible con roller, elevación −2 px y escala .98 al pulsar |
| Deshabilitados y comunicación | Sin efecto en botones disabled, chat, alertas o estado de trabajos |
| HTMX | Botón nuevo animado, sin repetir encabezados; scroll al POST, instrucciones y borradores conservados |
| Porcentaje | 0→9→0 y persistencia; denominador y aria-live/aria-valuetext correctos |
| Reducción de movimiento | Inicial y dinámica cancelan y limpian títulos; controles estáticos y replay deshabilitado |
| Fallback | Vendor bloqueado usa API nativa; excepción exacta de recurso esperada registrada aparte |
| Sin JS e impresión | Contenido/porcentaje utilizables; impresión durante entrada restaura título y conserva estados |
| Móvil táctil y tema oscuro | Sin overflow horizontal ni hover persistente tras tocar |
| Salud | Cero errores/warnings, HTTP inesperados, violaciones CSP o solicitudes externas |
| Datos | Copia/usuario/sesión retirados; cinco hashes originales GICA coinciden |

Evidencia vigente: Temporal/qa-motion-progress/results.json y dos PNG,
motion-progress-light-desktop.png y motion-progress-dark-mobile.png. Inspección con
view_image de ambas referencias Hyrup y ambas capturas de SparkX. Capturas finales
con caret:initial después de las mutaciones; los números corresponden a una copia QA.
No se grabó vídeo: el grabador no estaba instalado y no se añadieron dependencias.

La investigación midió [Hyrup About](https://www.hyrup.de/about-us) y
[Hyrup Home](https://www.hyrup.de/?ref=land-book.com) en 1440×1000 y contrastó
parámetros en módulos públicos. H1 entero detrás de máscara y roller de CTA/nav:
400 ms, curva [.4,0,.4,1]. SparkX acorta la espera del H1 y adapta H2 por palabras,
foco, elevación y presión. [Mediciones](../Temporal/referencias/motion-current/results.json)
y [decisiones visuales](arquitectura/design-system.md#movimiento-de-títulos-y-controles).

| Comparación de referencia y resultado | Decisión verificada |
| --- | --- |
| Copy y navegación | Se conserva el texto del producto; sólo se añade porcentaje y «x de y» solicitados |
| Tipografía | FIME conserva familia y escala 26/17/14; no se copia el H1 de 64 px del sitio |
| Paleta | Blanco/teal y grafito/azul conservados; sin nuevos fondos o gradientes |
| Distribución | Misma barra de secciones, columnas, formularios y scroll; no se añade un hero |
| Iconos y control | SVG existentes y tamaño táctil conservados; el elemento interactivo no se reemplaza |
| Movimiento | Máscara y curva del rótulo contrastadas; tiempos H1/H2 son adaptaciones explícitas |

Se corrigió la reinicialización tras outerHTML: se utiliza el elemento actualizado
de afterSwap, no el target retirado. El primer aviso CSP fue causado por el método
de captura (estilos vacíos del caret que el siguiente swap HTMX copiaba); la prueba
final evita esa interferencia y conserva intacta style-src 'self'. Se retiran
atributos de estilo vacíos al limpiar animaciones y nodos observados desconectados.
No quedan desajustes materiales observados dentro del recorrido comprobado.

## Seguimiento: base anterior de 47 comprobaciones correctas

Edge 157 y Playwright 1.62.1 existentes, contextos separados del perfil personal.
Browser plugin no disponible; fallback autorizado. Entorno http://127.0.0.1:8000/,
viewports 1663×946 y 390×844. Se omite --hide-scrollbars para capturar barras nativas
reales; no se altera el CSS para las imágenes.

Las transiciones se probaron en una copia identificada como «Demo seguimiento QA».
Las capturas contienen datos de prueba; no acreditan ejecución de tareas GICA reales.
La cuenta QA tenía contraseña inutilizable y sesión efímera marcada.

| Área | Resultado observado |
| --- | --- |
| Inicio | Once tareas «No iniciado»; GET no crea registros de progreso |
| Guardado | Formulario real → estado, actor/fecha e historial persistidos |
| Resumen | Contadores y barra coinciden con DB; caso final sintético 8/2/1 |
| Semáforo | Gris/ámbar/verde medidos, siempre acompañados por texto |
| Completar/reabrir | Admitidos; nota obligatoria, errores locales y entrada conservada |
| Texto seguro | Nota con marcado mostrada literalmente, sin ejecución ni recursos externos |
| Dos pestañas | Cambio obsoleto rechazado; estado actual y nota conservados, sin sobrescritura |
| Continuidad | Reemplazo HTMX conserva instrucciones abiertas, scroll 161→161 y borrador |
| Recarga y sin JS | Estado recuperable; POST nativo guarda y redirige a Preparación |
| Nueva aprobación | Tres registros heredados de tareas iguales sin auditoría manual inventada |
| Nota heredada | Texto de origen intacto tras reabrir y completar en la versión nueva |
| Plan anterior | Escritura rechazada y enlace para recargar el vigente |
| Impresión | Once estados sin recorte; edición e historial ocultos |
| Temas/móvil | Estados conservados; sin desbordamiento horizontal observado |
| Salud | Cero errores/warnings, HTTP inesperados, violaciones CSP o solicitudes externas |
| Limpieza | Copia, usuario, sesión, progreso y auditoría de QA retirados; GICA intacto |

Resultado anterior conservado en Temporal/qa-task-progress/results.json. Sus dos
capturas se retiran al quedar sustituidas por porcentaje/movimiento actuales.

## Servidor precedente: porcentaje y movimiento (190 pruebas)

La suite completa pasó después de incorporar el porcentaje y el marcado de
animaciones. Las 29 pruebas focalizadas (28 HTTP y una de cálculo) también pasaron.
Django check no detectó problemas y makemigrations --check --dry-run no detectó
cambios pendientes. La migración planning.0002_task_progress está aplicada localmente. El porcentaje
no necesita otra migración. collectstatic copió app.css, plan-reading.css y motion.js;
node --check pasó para el controlador actualizado.

El seguimiento conserva 20 pruebas de aplicación (18 correctas y 2 omitidas) y
ahora cuenta con 28 HTTP correctas y una prueba del cálculo porcentual. Cubren atomicidad con auditoría, propietario/CSRF, actor de sesión,
plan activo exacto, versión esperada, reenvío idempotente sin revivir estados,
notas obligatorias, escape HTML y formularios con/sin HTMX. Verifican GET sin
escrituras, historial hasta cinco, candidatas sin controles de ejecución y
consultas acotadas con 2 frente a 20 registros e historiales reales.

El porcentaje usa completadas × 100 // total y devuelve 0 en una lista vacía.
Se comprueban HTMX, GET tras POST sin JS, reapertura, estado en proceso y el límite
499/500 → 99 %, evitando mostrar 100 % con pendientes.

La herencia invalida tareas afectadas y sus descendientes, no revive una tarea
eliminada/reintroducida y se descarta por completo si cambió materialmente la ficha.
Un fallo de arrastre revierte la aprobación. La nota de origen permanece separada
de notas posteriores. Los payloads de planes y candidatas no se reescriben.

Las cinco omisiones necesitan PostgreSQL: aprobación concurrente, salto de filas
bloqueadas del worker, cuota concurrente, dos cambios competidores de una tarea y
repetición concurrente de la misma clave. La prueba secuencial de dos pestañas no
sustituye las pruebas de bloqueo ni acredita capacidad multiusuario.

## Agenda y preparación: base anterior conservada

La aclaración del usuario se mantiene: barras verticales, sin paginación ni Ver más.
Todas las filas del plan aprobado se renderizan en una lista ordenada. Con más de
tres elementos se usa scroll CSS nativo con barra fina, espacio reservado, nombre
accesible, tabindex 0 y foco visible. Agenda usa máximos 400/360 px y Preparación
300/340 px en escritorio/móvil. El texto y recursos abiertos determinan cuántas filas
se ven. Candidatas e impresión no tienen recorte de altura.

La base anterior pasó 42 comprobaciones de rueda, teclado, temas, continuidad,
sin JS e impresión, sin errores o solicitudes externas. Su resultado se conserva
en Temporal/qa-plan-scroll/results.json y la captura aún útil de agenda en
agenda-scroll-light-desktop.png. La captura anterior de Preparación se retiró,
sustituida por las actuales. agenda.js y su copia servida permanecen retirados.

## Calendario y temas: base anterior conservada

El recorrido acceso → Calendario → mes/día → agenda aprobada → evento → Propuestas →
formulario pasó 65 comprobaciones previas en Edge aislado: 1663×946, 1440×900 y
390×844. Se midieron tipografía, geometría, temas, teclado, preferencia persistida y
sincronizada entre pestañas, almacenamiento bloqueado y fallback sin JavaScript.
Se comprobaron permisos por propietario, fechas inválidas y revisión vigente.

Las 22 pruebas del calendario cubren permisos, GET, zonas, DST, medianoche, febrero,
límites 1900–2100, parámetros, exclusión de candidatas, escape y consultas sin N+1.
Las catorce de presentación mantienen listas 0/1/3/4, dependencias, horarios e
inmutabilidad; las ocho de demo conservan carga atómica/idempotente y credenciales.

Evidencia útil: Temporal/qa-calendar/results.json y seis PNG de calendario claro/
oscuro en escritorio/móvil y formulario claro/oscuro móvil. Son resultados de ese
recorrido, no nuevas capturas del seguimiento. Las referencias FIME usaron CSS
público y datos sintéticos, red bloqueada, sin backend, correo o credenciales.

## Demo GICA y limpieza

Caso mantenido de adminjorge: plan activo versión 1, revisión de ficha 2 y alternativa
pendiente. EVENTO1.jpg es la fuente; 2026, America/Lima, 90 minutos y 100 cupos son
supuestos explícitos. Los planes iniciales son manuales, sin IA. La carga inicial
presenta once tareas «No iniciado»; repetir seed_demo_event conserva los cambios.
Ver [carga de demo](../README.md#demo-gica).

La corrida anterior de seguimiento eliminó su única sesión marcada, usuario, evento, dos planes, seis
registros de progreso y siete cambios auditados. Los hashes del plan, candidata,
progreso y auditoría originales GICA coinciden; versión 1, revisión 2 y candidata
pendiente intactas. El snapshot aprobado de la copia tampoco fue reescrito por
el seguimiento. No se alteró la contraseña de Jorge ni se guardaron secretos.

La corrida actual retiró un progreso, tres transiciones y su usuario/evento/sesión;
los cinco hashes originales (ficha, planes, candidatas, progreso y auditoría) coinciden.

Todo auxiliar queda en Temporal/, ignorado por Git: resultados y dos PNG actuales;
sin scripts de una sola vez. Se retira la captura sustituida de Preparación sin
crear otro informe. Código, pruebas, migración y documentación mantenida conservan
sus carpetas oficiales; entorno y base activa no se tratan como obsoletos.

## Movimiento y límites pendientes

Motion 14.10.1 local conserva licencia MIT y SRI según su
[revisión acotada](decisiones/motion-dependency-review.md), títulos con máscara, transiciones,
replay, movimiento reducido y fallback. CSP no se relajó.

El avance es declaración manual del organizador. No hay adjuntos, responsables ni
verificación independiente; dependencias informativas. El chat incorpora esos
registros desde el incremento del 12 de noviembre descrito abajo; no tiene una operación para modificarlos.

No se comprobaron Safari/Firefox, dispositivos físicos, carga multiusuario, voz real,
inferencia API, PostgreSQL operativo o despliegue OVH. No hubo consumo API, micrófono,
Zoom, inscripción real, pago VIP o certificados. Las fases de adaptación, participante,
cierre, recuperación de procedimientos y entregables siguen el [plan](construction-plan.md).

## Incremento del 12 de noviembre: ficha editable y contexto de tareas

Se mantuvo el monolito y la numeración 0–6 del plan. El usuario confirmó cierre el
15 de noviembre, prioridad al recorrido completo, aprobación humana de cambios
del plan y estados y voz por turnos con texto revisable. No se instalaron nuevas
dependencias, activaron proveedores ni realizaron inferencias reales.

### Comportamiento implementado

- **Editar ficha** abre `/events/<id>/edit/`. Reutiliza el servicio existente,
  valida propietario y revisión y conserva el plan aprobado y el avance. Una ficha
  obsoleta devuelve 409 sin guardar, muestra la ficha vigente y conserva los campos
  propuestos para una segunda confirmación explícita.
- El contexto del chat incluye solamente tareas del plan aprobado del evento,
  estados persistidos, versiones, fechas y porcentaje calculado. No incluye notas
  libres, identidades de actores, progreso de planes históricos ni candidatas.
  Los estados son declaraciones humanas, sin verificación independiente.
- El worker captura contexto e historial una vez bajo el bloqueo del evento y
  reutiliza esa instantánea para presupuesto previo e inferencia. Se identifica
  su fecha de captura; un cambio durante la generación aparecerá en la siguiente
  consulta. El chat no obtiene herramientas ni modifica estados o planes.

### Pruebas de servidor

`python -B manage.py test --noinput`: **407 pruebas, 401 correctas y seis omitidas
por requerir PostgreSQL**, 81,258 segundos, system check sin incidencias.
Se añadieron once pruebas de edición y siete de contexto/worker. Cubren permisos,
CSRF, revisión obsoleta, datos inválidos, escape, preservación de trabajo aprobado,
aislamiento por evento/revisión, cancelación y revocación de propietario.
Las fronteras HTTP de los proveedores se simularon; no acreditan calidad de una
respuesta real ni consumo observado en una cuenta.

### Comprobación en navegador

**Browser plugin not available**: no figura el plugin Browser y su skill en esta
sesión. Se usó la alternativa Playwright ya autorizada, con Edge instalado,
headless y perfil temporal separado; no se descargaron paquetes o navegadores.
El flujo se sirvió con `StaticLiveServerTestCase` y SQLite en memoria, separado de
la base activa. El servidor y navegador de QA se cerraron al terminar.

Recorrido: detalle → Editar ficha → guardar → ficha cambiada desde otra ventana →
409 con campos conservados → guardar explícitamente tras revisar. Se comprobó
persistencia de nombre, capacidad y revisión. Viewports: 1440×900 y 390×844.

| Comprobación | Resultado |
| --- | --- |
| URL, título y contenido visible | Correctos |
| Pantalla vacía o error de framework | Ausentes |
| Consola y JavaScript | Sin errores ni advertencias; 409 esperado separado |
| Interacción y persistencia | Guardado, conflicto y reenvío explícito correctos |
| Móvil | Formulario legible, sin desbordamiento horizontal |
| Evidencia visual | Tres PNG inspeccionados o conservados en Temporal/qa-event-edit |

Evidencias actuales: `Temporal/qa-event-edit/results.json`, `desktop-edit.png`,
`desktop-conflict.png` y `mobile-edit.png`. Auxiliares ignorados por Git; el script
de una sola ejecución se retiró tras la verificación. No se alteraron datos,
contraseña ni sesión del usuario habitual, ni se comprobó su servidor del puerto
8000. La comprobación de PostgreSQL no encontró ejecutables en PATH ni una carpeta
estándar de instalación; no sustituye un inventario completo del equipo.

Persisten: PostgreSQL/concurrencia, instalación reproducible, historial Git inicial,
entrevista guiada, primera inferencia real, prueba física de voz, decisiones
fijadas/impactos, participantes/cierre, carga y entregables del concurso.

## Checklist personal ampliado del 12 de noviembre

Por solicitud del usuario se amplió el módulo existente, sin crear otro checklist.
La navegación y las tres operaciones GET, guardar y comprobar quedan restringidas
a la cuenta activa `adminjorge`, con rol administrador. Otros administradores,
incluidos superusuarios, reciben 403 y no ven el enlace. El propietario configurable
es `SPARKX_CHECKLIST_OWNER_USERNAME`; deshabilitar `SPARKX_CHECKLIST_ENABLED` oculta
la ayuda y conserva los datos.

Las 15 gestiones conservan sus claves, cuatro grupos y cinco condiciones. Ahora
incluyen 50 pasos, 46 confirmaciones específicas y enlaces oficiales fijos. Guardar
Completado requiere todas las casillas del punto; se permite guardar progreso
parcial. Estado, casillas y fecha persisten; revisiones e idempotencia abarcan
también cambios de confirmaciones. No se reciben notas, adjuntos o credenciales.
Una declaración anterior completada sin casillas se conserva y solicita revisión
antes de sumar al porcentaje; no se reinicia su estado.

**Comprobar configuración local** es un POST con CSRF que solamente lee perfil,
presencia de credencial, límites disponibles frente a una reserva máxima y una
cadena coherente de registros de propuesta/aprobación/consumo del propietario.
No consulta al proveedor, crea cuentas, reserva fondos, ejecuta trabajos o completa
puntos. Los mensajes separan una observación local de la revisión externa de
saldo, cuota, validez de clave o facturación. La fecha identifica la observación
de esa vista; al volver se invita a comprobar de nuevo.

### Evidencia técnica y datos

- Suite específica: `manage.py test apps.project_checklist --noinput`, **65/65**.
- Suite completa: `manage.py test --noinput`, **442 pruebas, 436 correctas, seis
  omitidas por PostgreSQL**, 84,857 segundos; system check sin incidencias.
- `makemigrations --check --dry-run`: sin cambios pendientes.
- Migración `0002_personal_confirmations` aplicada a SQLite local: columna JSON
  aditiva y actualización de rótulos. Cero filas de avance previas; los recuentos
  de diez modelos de eventos, planes, tareas, chat, trabajos y Gestión IA coinciden.
  No se crearon cuentas ni trabajos y no se cambiaron presupuestos o contraseñas.
- Servicio local iniciado en `127.0.0.1:8000` sin autoreload y sin iniciar worker.
  `/health/` devuelve 200 y el checklist anónimo 302 al login; cuenta privada activa
  comprobada sin leer ni modificar contraseña o sesión. No es despliegue público.

### Comprobación de interfaz

**Browser plugin not available**; fallback Playwright autorizado previamente,
Edge instalado headless con perfil separado y SQLite en memoria. **20/20**
comprobaciones correctas. Recorrido: abrir guía → intentar completar sin casillas
→ 400 con error visible y guía abierta → confirmar y guardar → 6 % persistido tras
recargar → comprobar configuración local sin cambios de avance ni nuevas cuentas,
trabajos o consumos. También se probó guardado sin JavaScript.

| Comprobación | Resultado |
| --- | --- |
| Identidad, contenido y 15 guías | Correctos |
| Pantalla vacía o error de aplicación | Ausentes |
| Consola y JavaScript | Cero errores o advertencias; 400 esperado separado |
| Interacción y persistencia | Rechazo incompleto, guardado, recarga y comprobación correctos |
| Temas y móvil | Claro 1440×900 y oscuro 390×844; sin desbordamiento |
| Evidencia | Cinco PNG de datos sintéticos y results.json en Temporal/qa-personal-checklist |

Las capturas muestran datos de prueba, incluido un 6 % sintético; no son el avance
real de Jorge ni prueba de créditos activos. El servidor y navegador de QA se
cerraron y su base desechable se destruyó; el servidor normal 8000 sigue abierto.
El script de una sola ejecución se retiró. No hubo descargas, dependencias nuevas,
red externa de la aplicación o llamadas API. Siguen pendientes cuentas externas,
micrófono físico, otros navegadores y concurrencia PostgreSQL.
