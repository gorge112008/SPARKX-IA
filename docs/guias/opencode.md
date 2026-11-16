# OpenCode como apoyo al desarrollo

Implementación del 14 de noviembre de 2026. Es una herramienta de desarrollo
separada del agente de eventos, del worker y del presupuesto de IA de ArquiGica.
La integración se limita a un ayudante acotado de desarrollo. Hermes, Letta y
otros servicios de agentes no son dependencias del producto.

## Instalación y estado comprobado

Se instaló OpenCode **2.2.7 para Windows x64 baseline** desde el
[release oficial e inmutable](https://github.com/anomalyco/opencode/releases/tag/v2.2.7).
El ZIP de 124.794.066 bytes se contrastó con SHA-256
`93323d0d6f72f9d1ba9f847e8002de71ace79bb5ea64f18d6b70bbbc30cc719e`.
Se extrajo únicamente `opencode.exe`, con comprobante y hash del ejecutable en
`.opencode/bin/2.2.7/install.json`. Esa dependencia local está ignorada por Git;
el instalador, configuración, broker y pruebas se conservan en `tools/opencode/`.
No se modificaron PATH, paquetes globales ni la instalación de Django.

El binario cargó la configuración preparada y superó **31 comprobaciones locales**,
incluidas 16 decisiones de permisos mediante su API real. La comprobación del límite
de salida de 2.048 tokens también pasó el preflight del binario. Estas pruebas no
consultaron un modelo. Evidencia en `Temporal/opencode/qa-policy-results.json`.

La primera inferencia fue bloqueada por la revisión automática al aplicar la
instrucción anterior de no hacer llamadas. Jorge autorizó expresamente la prueba
gratuita con datos sintéticos y entonces se ejecutó. GLM-5.3 Flash generó el borrador
en **19,453 s**, con tres pasos observados y coste **cero reportado por OpenCode**.
El catálogo público comprobado inmediatamente antes también indicó precios cero.
No se usaron claves ni cuentas de pago. No se revisó una factura del proveedor.

El ejemplo tenía 80 bytes: una función de porcentaje con redondeo prematuro y
división entre cero. El modelo leyó la copia y creó `outputs/porcentaje.py`.
Después de inspeccionar el código se verificaron **siete casos locales**, incluidos
999/1000 → 99 y total cero → 0. Los hashes de entrada permanecieron intactos y no se
importó ningún archivo en ArquiGica. Esta muestra no demuestra calidad general,
ahorro de tokens, capacidad multiusuario o una distribución de latencias.

## Uso

Abre **Ayudante OpenCode.cmd**. La guía permite elegir entre trece candidatos revisados,
seleccionar revisión o borrador, describir una tarea pequeña y elegir archivos
relativos. Muestra privacidad y cuotas antes de preparar. Los diez modelos
adicionales exigen escribir **ACEPTO DATOS FICTICIOS**. Prepara primero una copia;
solo enviará contexto cuando escribas **ENVIAR**. La autorización dada al agente
cubrió esta prueba sintética; no habilita nuevas inferencias automáticas ni las
llamadas de la API de ArquiGica. Revisa el contexto antes de cada envío manual.

Ampliación del 15/11: se revisaron Big Pickle, Iceman, Inkling 2 Small, Flint 40B,
Nemotron 3 Ultra y Nemotron 3.5 Super VL, además de los siete originales. El
catálogo remoto confirmó doce con precio cero; Ultra no apareció y el gate impide
ejecutarlo. No se han probado inferencias de estos nuevos candidatos. La lista es
curada, no habilita modelos desconocidos ni garantiza cuota. El agente de eventos
integra doce mediante su puente separado y aceptación por solicitud; véase
[contrato de aislamiento](ai-management.md#aislamiento-y-modelos-ampliados).

También puede usarse desde PowerShell en la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -B -m tools.opencode.runner status
.\.venv\Scripts\python.exe -B -m tools.opencode.runner prepare --mode review --file static/js/task-progress.js --task "Revisa este archivo y enumera solo problemas demostrables. No ejecutes código."
```

El comando devuelve un identificador. Revisa `Temporal/opencode/tasks/<id>/task.json`
y sus `inputs/` antes de autorizar el envío. Para una tarea autorizada:

```powershell
.\.venv\Scripts\python.exe -B -m tools.opencode.runner run <id>
```

`outputs/respuesta.md` contiene el texto; otros archivos en `outputs/` son borradores.
`result.json` distingue fallo de resultado pendiente de revisión y conserva los
contadores que OpenCode informe. Un contador ausente permanece desconocido. No se
importan cambios ni se ejecuta código generado. La reclamación exclusiva impide
dos ejecuciones simultáneas o posteriores de una tarea. Una tarea intentada no se
reintenta, incluso si falla la comprobación previa: se prepara otra después de
revisar la causa. Las alternativas se seleccionan
manualmente con `--model`; el broker no cambia de modelo por su cuenta.

Para preparar un modelo adicional, sin hacer todavía llamadas:

```powershell
.\.venv\Scripts\python.exe -B -m tools.opencode.runner prepare --model longcat-2.5-free --demo --accept-model-policy --task "Revisa únicamente el ejemplo ficticio, sin ejecutarlo."
```

`--demo` añade una función ficticia fija. Si seleccionas otros archivos, debes
declararlos ficticios con `--synthetic`; añadir el ejemplo no clasifica los demás
archivos. Esa declaración es responsabilidad del usuario, no una certificación
automática del contenido. Las condiciones quedan guardadas en `task.json` y el
broker vuelve a comprobar las declaraciones al ejecutar.

Para reinstalar en otra copia autorizada:

```powershell
.\.venv\Scripts\python.exe -B tools/opencode/install.py
.\.venv\Scripts\python.exe -B tools/opencode/install.py --check
```

## Reparto de tareas

| Responsable | Trabajo adecuado |
| --- | --- |
| Código determinista | Búsquedas, comprobaciones, validaciones, formato y ejecución de pruebas conocidas. No necesitan un modelo. |
| OpenCode gratuito | Revisar fragmentos pequeños, proponer documentación breve, casos de prueba o cambios simples como borradores aislados. |
| Codex y revisión humana | Arquitectura, seguridad, permisos, gastos, migraciones, conflictos y decisión sobre incorporar cambios. |

No se garantiza un ahorro porcentual: todavía no hay mediciones comparables. Las
solicitudes independientes no reciben todo el historial de ChatGPT ni el banco del
mentor. La memoria canónica sigue en `.agents/skills/mentor-sparkx/`; no se duplicó.

## Modelos y límites

Selección revisada el 14 de noviembre, comprobada por GET del catálogo público:

| Modelo | Condiciones declaradas por OpenCode | Uso habilitado aquí |
| --- | --- | --- |
| GLM-5.3 Flash Free | Sin entrenamiento ni retención del proveedor declarados. | Predeterminado; única inferencia comprobada. |
| DeepSeek V4.1 Flash Free | Sin entrenamiento ni retención del proveedor declarados. | Alternativa seleccionable. |
| MiniMax M3.1 Flash Free | Sin entrenamiento ni retención del proveedor declarados. | Alternativa seleccionable. |
| LongCat 2.5 Free | Alojado en China; sin retención/entrenamiento declarados; 100 solicitudes por día. | Solo datos ficticios y aceptación específica. |
| Beam Free | Conservación de 30 días por seguridad, sin entrenamiento; restricciones regionales. | Solo datos ficticios y aceptación específica. |
| MiMo V2.6 Flash Free | Los datos pueden utilizarse para mejorar el modelo. | Solo datos ficticios y aceptación específica. |
| Nemotron 3.5 Lightning Free | Prueba de NVIDIA; registros para seguridad y mejora de productos; prohíbe datos personales/confidenciales. | Solo datos ficticios y aceptación específica. |

Fuente: [modelos y privacidad oficiales](https://opencode.ai/docs/console/models/).
Son declaraciones del proveedor, no una auditoría independiente. Todas son ofertas
temporales. No se encontró una cuota fija pública garantizada de RPM/TPM para esta
selección. El catálogo no mide ni impone la cuota de LongCat: las solicitudes
auxiliares también pueden consumirla; una tarea puede requerir varias solicitudes.
La calidad, latencia y generación de los seis modelos alternativos no se
han probado. Los cuatro nuevos sí pasaron preflight local del binario real.

Estos modelos corresponden al ayudante de desarrollo: el tráfico gratuito requiere
OpenCode. No se añadieron como proveedor de la API del agente de eventos de ArquiGica.

Antes de cada ejecución, el broker consulta el
[catálogo público](https://opencode.ai/inference/openai/v1/models) y exige precio
cero en entrada, salida y lectura de caché, y en cualquier precio adicional presente.
Si el modelo desaparece, cambia de precio o la comprobación falla, se detiene.
No usa cuentas conectadas, tarjetas, claves API de pago o la sesión de ChatGPT.

## Consumo observado y escenarios de pago

Cada tarea intentada genera, cuando hay registros interpretables, dos archivos
locales: `cost-comparison.json` y `cost-comparison.md`. Distinguen coste reportado
por OpenCode, tokens observados y costes **hipotéticos** con tarifas pagadas.
También pueden generarse para una tarea anterior, sin red ni inferencia:

```powershell
.\.venv\Scripts\python.exe -B -m tools.opencode.runner compare 20261115T024003-a63dd261ee
```

El estimador es determinista y utiliza `Decimal`. Según la
[fuente fijada de OpenCode 2.2.7](https://raw.githubusercontent.com/anomalyco/opencode/v2.2.7/packages/core/src/session/usage.ts),
`input` excluye caché y `output` excluye razonamiento. Por ello la salida valorada
es `output + reasoning`, y la entrada suma tres categorías separadas. No aplicar
esta fórmula a otro API sin comprobar primero su semántica.

Se incluyen tres tarifas base de texto por millón, con fuente y fecha:

| Referencia de OpenCode · 14 de noviembre de 2026 | Entrada USD | Lectura de caché USD | Salida con razonamiento USD |
| --- | ---: | ---: | ---: |
| GLM 5.3 Flash | 0,15 | 0,03 | 0,50 |
| DeepSeek V4.1 Flash | 0,30 | 0,006 | 1,20 |
| MiniMax M3 | 0,30 | 0,06 | 1,20 |

[Tarifas publicadas](https://opencode.ai/docs/console/models/). MiniMax M3 es distinto
de M3.1 Flash Free. Todas las comparaciones reutilizan los mismos contadores, sin
suponer igualdad entre modelos, tokenizadores, razonamiento, caché o número de pasos.
La tarifa de escritura de caché no está publicada para estas referencias: si hubiera
uso positivo, el total quedaría desconocido. También se conservan como desconocidos
los contadores ausentes y las tarifas por niveles de contexto no implementadas.

La muestra real anterior tiene **6.683 tokens observados**: 5.627 de entrada
(3.451 sin caché y 2.176 de lectura) y 1.056 de salida (799 visibles y 257 de
razonamiento). OpenCode reportó **USD 0**. Aplicar las tarifas anteriores a estos
contadores da respectivamente **USD 0,00111093**, **0,002315556** y **0,00243306**.
No se invocó ningún modelo pagado para calcularlo.

La tabla proyecta repetir idénticamente la muestra 1, 100 o 1.000 veces. No es un
coste por participante, una previsión mensual ni una prueba de capacidad. Excluye
impuestos, compra de créditos, voz, herramientas, almacenamiento e infraestructura.
El coste real de una implementación pagada solo podrá medirse ejecutando esa
implementación con autorización y comprobando su consumo y facturación.
El pago por sí solo no garantiza seguridad: se conservan permisos, aislamiento,
minimización de datos y revisión de las condiciones del proveedor.

| Control | Alcance real |
| --- | --- |
| Contexto | Máximo cinco archivos seleccionados y 24.000 bytes combinados; descripción hasta 3.000 caracteres. No es una medición exacta de tokens. |
| Salida del modelo | 2.048 tokens por solicitud principal; no es una cuota total de la sesión ni cubre todas las rutas auxiliares del harness. |
| Iteraciones | Tres pasos configurados. El último paso reduce herramientas; no garantiza exactamente tres peticiones HTTP. |
| Proceso | Máximo 180 segundos y 1 MiB de stdout/stderr combinados; cierre del proceso privado puede añadir algunos segundos. |
| Errores | Interrupción al observar eventos de error, reintento o salida truncada. El motor nativo tiene reintentos internos; no se inventó un ajuste para desactivarlos. La interrupción es un control práctico, no una prueba de una única petición HTTP. |
| Datos | Copias explícitas de texto; sin acceso de herramientas a la base activa, credenciales, directorios externos o código original. |
| Publicación | Sin integración automática, commits, push, envíos o despliegues. |

Al interrumpir por error, límite o tiempo, el broker conserva los eventos y
contadores parciales disponibles. Marca el recibo como incompleto: sus subtotales
no se convierten en un coste total conocido ni se reejecuta la tarea.
En el ensayo de agendas se observó recorte de líneas largas en la herramienta
nativa de lectura. Para esos casos se usa JSON indentado y líneas cortas; revisa
el texto efectivamente leído antes de atribuir un fallo al modelo. El límite de
2.048 tokens incluye razonamiento: puede agotarse sin respuesta visible.

El [ensayo UNAC/GICA](../validacion/event-benchmark.md) completó 42 celdas principales. GLM pasó
6/6 con este perfil; otros resultados se conservan sin ocultar truncamientos o
fechas inválidas. MiMo y Nemotron devolvieron HTTP 429 por cuota gratuita agotada
al final. La gratuidad no garantiza disponibilidad ni capacidad multiusuario.

## Seguridad y privacidad

Cada tarea usa servidor `--standalone`, configuración, perfil, caché y estado propios.
El entorno se construye desde una lista pequeña del sistema; no se copian las
variables del proceso para después intentar quitar secretos. Las políticas bloquean
shell, navegador, red de herramientas, Code Mode, subagentes, MCP, plugins externos
y skills. Review solo lee `inputs/`; draft además escribe `outputs/`.

Los permisos son controles de OpenCode, **no un sandbox del sistema operativo**.
La [documentación de permisos](https://opencode.ai/docs/permissions/) y
[políticas](https://opencode.ai/docs/policies/) explica sus diferencias y la fusión de
configuraciones. El preflight rechaza fuentes ajenas, agentes, modelos o restricciones
que no coincidan; no basta con que el proceso termine con código cero.

Se deshabilitan la búsqueda de configuración de proyectos y las skills externas;
los directorios globales usados por el hijo están aislados. `instructions: []` por
sí solo no desactiva la búsqueda de AGENTS, según la
[documentación de instrucciones](https://opencode.ai/docs/instructions/).
No se abre el repositorio entero con una sesión convencional de OpenCode.

El contexto seleccionado se transmite a un proveedor remoto. No incluyas documentos
personales, datos reales de participantes, claves o información confidencial. La
detección local de algunos patrones sensibles no certifica que un archivo esté limpio.
El harness añade fecha, plataforma y rutas de trabajo; esas rutas pueden contener el
nombre del usuario de Windows. La comunicación no se describe como anónima.
Tampoco se promete ausencia absoluta de metadatos técnicos o telemetría; consulta la
[política de privacidad](https://opencode.ai/legal/privacy-policy).

## Comprobaciones reproducibles

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tools/opencode -p "test_*.py"
.\.venv\Scripts\python.exe -B manage.py check
```

Las pruebas cubren instalación e integridad, catálogo y cambios de precio, políticas,
aislamiento del contexto, configuración efectiva y detención de procesos propios.
**124/124 pruebas correctas en 4,364 s**, sin solicitar modelos. La aplicación pasó
`manage.py check` y no hay cambios de migración. Los auxiliares útiles viven en `Temporal/opencode/`; elimina
los borradores y sesiones sustituidos una vez revisados, siguiendo `AGENTS.md`.

La evidencia de inferencia y revisión está en
`Temporal/opencode/tasks/20261115T024003-a63dd261ee/`: `result.json`,
`events.jsonl`, el borrador y `review.json`. Los contadores comunicados fueron
3.451 tokens de entrada sin caché, 799 de salida visible, 257 de razonamiento y
2.176 de lectura de caché, sumados por categoría entre los tres pasos. Son categorías
disjuntas de este harness; el total es 6.683 tokens observados. No equivalen a una
factura auditada ni a los 80 bytes del archivo.
Esta sobrecarga refuerza que una corrección mecánica tan pequeña suele resolverse
directamente con código; el ejemplo comprueba la conexión y los límites.

La ampliación inicial no realizó nuevas inferencias. El ensayo posterior de seis
eventos sí fue autorizado y está documentado por separado. El preflight de los cuatro modelos
adicionales está en `Temporal/opencode/model-preflight.json`; sus carpetas privadas
de comprobación se retiraron y no quedaron procesos OpenCode activos. La comparación
se calculó sobre el recibo anterior, sin modificarlo. La API, perfiles activos y
presupuesto de ArquiGica no cambiaron.
