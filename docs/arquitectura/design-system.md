# Sistema visual vigente: ArquiGica, calendario y temas

Actualizado el 16 de noviembre de 2026. El usuario eligió la escala y organización del
proyecto local Python/2. FIME-UPG-2026 y pidió calendario, tema claro y tema oscuro,
con un botón de sol/luna. Esta dirección sustituye la escala amplia anterior.
Django/HTMX, permisos, datos y revisión de planes conservan sus contratos.

## Identidad de ArquiGica

El azul institucional **#00437D** se extrajo del PNG `logo_gicacertification.png`
aportado por el usuario. El logo usa exclusivamente **azul #00437D y blanco**:
en el tema claro se presenta azul sobre blanco; en el oscuro, blanco sobre azul
institucional. El monograma y el nombre conservan esta identidad bicolor, sin
turquesa ni colores adicionales.

La interfaz combina esta identidad con el turquesa **#087F8C**, reservado a
acciones y estados. El tema claro combina blanco y fondos suaves; el oscuro
usa grafito con tintas claras para mantener contraste. Los enlaces oscuros
pueden usar azul **#9BC7ED**, y las acciones principales, turquesa **#59C6CA**;
esas variantes corresponden a controles de interfaz y no al logo.

El inicio de sesión divide la pantalla entre identidad y formulario: monograma
y nombre ArquiGica a un lado, acceso compacto al otro. En móvil los bloques se
apilan. La marca del producto es ArquiGica; SparkX 3.0 sigue siendo el concurso.

## Referencia y conceptos

Se inspeccionaron dashboard_web/styles.css y calendar.js de FIME. La referencia se
renderizó con su CSS y calendario reales, datos ficticios identificados y red bloqueada;
no se ejecutó el backend ni se abrieron correo o credenciales.

Las referencias se revisaron a 1663×946 y 1440×900 píxeles. Los conceptos claro
y oscuro se prepararon a 1662×946. Las capturas y los registros auxiliares son
material privado de desarrollo y no forman parte del código distribuido.

Los conceptos se generaron con Image Gen integrado y se inspeccionaron con view_image.
Las medidas efectivas de la referencia del usuario prevalecen sobre los errores de
escala del generador: sidebar 218 px y H1 26 px. No se reproducen texturas ni degradados.
La UI es HTML/CSS, no una imagen. Las imágenes auxiliares permanecen sólo en Temporal/.

## Tipografía y geometría

| Elemento | Valor |
| --- | --- |
| Familia | Segoe UI, Arial, system-ui; fuente del sistema sin descargas |
| Cuerpo / auxiliar / controles | 14 / 12–13 / 13 px |
| H1 / H2 / H3 | 26/17/14 px; pesos 700/650/650 |
| Encabezado del mes | 19 px, como el calendario de FIME |
| Sidebar / barra superior | 218 / 53 px |
| Márgenes / separación / interiores | 24 / 20 / 20–22 px |
| Bordes / radios | 1 / 5–6 px |
| Acciones | 32–36 px en escritorio; al menos 44 px en móvil |
| Formulario móvil | Campos de 16 px para conservar lectura y evitar zoom de entrada |

Agenda, Preparación, Propuestas, Actividad, formularios, acceso y calendario comparten la misma
escala. Los títulos de evento pueden ocupar varias líneas. El agente usa 330 px en
escritorio y pasa debajo cuando falta ancho. Agenda y preparación mantienen su altura
natural hasta los límites de lectura indicados abajo; los espacios no se fuerzan para llenar una captura.

## Lectura de agenda y preparación

Una sola barra del evento separa Agenda, Preparación, Propuestas y Actividad.
Agenda conserva las anclas #plan y #agenda; Preparación usa #preparation. Se mantienen
teclado e historial. El usuario aclaró mediante una captura que quería una barra de
desplazamiento vertical fina dentro de las listas. La paginación se retiró.

Con más de tres sesiones o tareas, la lista aprobada ocupa una región de altura
máxima acotada, con scroll vertical nativo, scrollbar fina y espacio reservado para
ella. Se ven aproximadamente tres filas: la cantidad exacta depende del texto y de
las instrucciones abiertas. No se fuerzan alturas en listas cortas.

Agenda usa máximo 400 px en escritorio y 360 en móvil; Preparación, 300 y 340 px.
El encabezado y el total quedan fuera del scroll. La región tiene nombre accesible,
foco visible y tabindex 0 para poder desplazarse con teclado; Tab permite continuar
al siguiente control. Rueda y gesto táctil mantienen el comportamiento del navegador,
incluida la continuidad hacia la página al llegar al extremo.

Todas las filas se renderizan en el servidor, en una sola lista ordenada. El scroll
funciona sin JavaScript y conserva su posición, recursos abiertos y borradores al
alternar secciones/tema. La impresión elimina el límite de altura y muestra todo.
El aspecto exacto de la barra nativa puede variar según navegador y sistema.

La agenda separa fecha agrupada, columna de inicio–fin y duración, título y ponente;
el recurso se abre cuando hace falta. Los finales se calculan sumando minutos en
UTC y convirtiendo a la zona del evento. Al cruzar medianoche se incluye la fecha final.

Las tareas muestran orden, título y estado persistido; «Ver instrucciones» abre
propósito y requisitos previos por nombre. El resumen y riesgos del plan se despliegan
aparte. La candidata conserva todas sus filas visibles sin altura acotada antes de
aprobar; sus instrucciones siguen disponibles. El payload no se modifica.

### Seguimiento de tareas

Cada tarea aprobada muestra un indicador de siete píxeles y una etiqueta: gris
«No iniciado», ámbar «En proceso» y verde «Completado». El texto usa la tinta del tema;
el color no es la única señal. El resumen mantiene contadores reales de los tres
estados, porcentaje entero y una barra nativa con la fracción completada. El cálculo
es completadas × 100 // total; sin tareas, 0 %. «En proceso» no suma, y el truncamiento
evita mostrar 100 % con tareas pendientes. Se muestra también «x de y» y se anuncia
el nuevo resumen mediante aria-live polite tras el guardado.

«Actualizar estado» abre un formulario compacto con selector, nota y guardado.
Completar o reabrir exige nota. Se muestra quién cambió la tarea y cuándo;
«Ver historial» abre los últimos cinco cambios y el origen de un estado heredado.
Los errores aparecen junto al campo, conservan la entrada y reciben el foco.
Una pestaña obsoleta presenta el estado vigente para revisión.

HTMX sustituye solo la fila y el resumen. Se conservan scroll interno, instrucciones
abiertas y borradores de chat/propuesta. El POST normal funciona sin JavaScript.
En móvil los campos usan 16 px y los controles táctiles, al menos 44 px; se mantienen
las paletas y la región de lectura. En impresión se muestran estados y último actor;
se ocultan editores e historial y se elimina el recorte de lista.

Se reutilizan los tokens y la referencia FIME, sin nuevos plugins ni CDN. El script,
reglas y marcado de paginación, junto a los controles Ver más, se retiraron.

## Paletas

| Token | Claro ArquiGica | Oscuro ArquiGica |
| --- | --- | --- |
| Canvas | #f5f7fb | #101113 |
| Superficie | #ffffff | #17191d |
| Campo | #ffffff | #121419 |
| Texto | #172437 | #f7f8fa |
| Secundario | #637185 | #aab1bd |
| Borde | #e4e9f0 | #303641 |
| Azul institucional | #00437d | #00437d |
| Logo: tinta / fondo | #00437d / #ffffff | #ffffff / #00437d |
| Acento de acciones y estados | #087f8c | #087f8c |
| Enlace | #00437d | #9bc7ed |
| Acción principal / tinta | #087f8c / #ffffff | #59c6ca / #082b30 |
| Navegación activa | #e7eff8 | #182b3c |

El secundario claro se oscurece ligeramente frente al #68768a original: ese color
ofrecía contraste 4,31 sobre el canvas. Se mantienen blanco real en las superficies,
colores planos y separación mediante líneas. Las superficies no llevan sombras;
los controles usan una sombra breve únicamente durante hover o foco.

## Selector sol/luna

Un único botón en la barra superior cambia toda la aplicación. La luna ofrece modo
oscuro; el sol ofrece modo claro. El nombre accesible, title y aria-pressed reflejan
la acción y el estado. theme.js se carga antes del CSS para aplicar la preferencia
sin esperar al cuerpo del documento y sin scripts inline ni relajar CSP.

Se guarda únicamente light o dark en localStorage, clave sparkx.theme. La selección
persiste al navegar y recargar y se sincroniza entre pestañas. Sin selección manual
se sigue el sistema. Si el almacenamiento está bloqueado, se conserva el cambio en
la página; sin JavaScript el CSS sigue el tema del sistema y no muestra un control
inoperante. El cambio de apariencia no envía formularios ni altera borradores.

## Calendario

La vista /calendar/ ofrece mes anterior/siguiente, Hoy y selección de día mediante
enlaces normales. El rango admitido es 1900–2100; los parámetros inválidos producen
una pantalla controlada 400 con regreso al calendario. No hay biblioteca adicional.

La cuadrícula empieza en lunes y tiene de cuatro a seis semanas. Sólo usa eventos
del propietario autenticado; el panel de un día usa exclusivamente la revisión
aprobada vigente. Las candidatas y revisiones sustituidas no publican sesiones.
Horarios y fechas se muestran en la zona de cada evento, incluyendo sesiones que
atraviesan medianoche. Una fecha derivada del plan se distingue de una ficha fechada;
los eventos sin ninguna fecha aparecen aparte.

En escritorio los días tienen 100 px y los títulos largos se recortan con elipsis
dentro de su celda. El panel lateral de 300 px conserva títulos y horarios completos;
los datos ampliados del ponente permanecen en el evento. Las cifras son consultas
reales de la base, nunca valores copiados del concepto o del proyecto FIME.

En móvil se conservan siete columnas y días de 62 px con contadores reales. Los
nombres de evento y la agenda se leen debajo en tamaño normal, en lugar de reducirlos
a los 9 px del original. Tab/Enter permiten navegar; flechas/Home/End mueven el foco
entre enlaces de fecha. Sin JavaScript siguen funcionando todas las rutas.

## Contratos conservados

- Agenda / Preparación / Propuestas / Actividad mantienen anclas, teclado, historial y borradores.
- La demo GICA mantiene datos atribuidos, supuestos y su alternativa pendiente.
- Permisos, CSRF, idempotencia y revisión exacta siguen en el servidor.
- La apariencia no habilita IA ni simula llamadas cuando falta proveedor.
- Motion 14.10.1 local mantiene replay, movimiento reducido y fallback. No se anima
  chat, alertas ni polling. Ver [revisión](../decisiones/motion-dependency-review.md).

## Movimiento de títulos y controles

Referencia observada: [Hyrup About](https://www.hyrup.de/about-us) y
[Hyrup Home](https://www.hyrup.de/?ref=land-book.com), medidas el 8 de noviembre.
H1 completo tras una máscara vertical, no caracteres independientes. Los rótulos
de CTA/nav recorren una segunda copia bajo una máscara durante 400 ms con curva
cubic-bezier(.4,0,.4,1). Parámetros y fuentes en
[mediciones](../../Temporal/referencias/motion-current/results.json).

ArquiGica adapta la entrada del H1 a 880 ms y 120 ms de demora; H2 por palabras usa
660 ms con una secuencia total adicional de hasta 280 ms. El calendario incluye
sus encabezados. Los envoltorios de títulos se retiran al acabar o cancelar,
restaurando los nodos de texto originales, sin reescribir cambios ajenos.

Los botones conservan forma, tamaño, copy y paletas. El rótulo usa la curva de
400 ms observada; su copia CSS es decorativa, queda bajo aria-hidden y el control
conserva un único nombre accesible. Foco visible, elevación de 2 px y presión a
escala .98 son adaptaciones propias. Hover geométrico se aplica sólo con puntero
fino; teclado y pulsación tienen respuesta equivalente. Botones deshabilitados,
chat, alertas y trabajos no reciben el efecto.

Las entradas se ejecutan al cargar, abrir una sección o pulsar replay, sin bucles
permanentes ni repetición por polling. Se limpian observadores al retirar nodos
HTMX. Movimiento reducido inicial/dinámico y la impresión dejan texto estático;
sin JS queda el marcado original. Se reutiliza Motion local y CSS, sin dependencias
o CDN nuevos. La adaptación mantiene las medidas FIME; no reproduce el hero ni
el tamaño de letras del sitio de referencia.

## Comparación y evidencia

| Punto inspeccionado | Referencia y decisión |
| --- | --- |
| Composición | Sidebar 218, barra 53, calendario ancho y detalle de 300; estructura FIME. |
| Tipografía | Segoe UI y escala real 26/17/14; se corrige el sobredimensionado de Image Gen. |
| Paletas | Azul institucional con acciones turquesa; blanco en claro y grafito con tintas claras en oscuro. |
| Calendario | Semanas lunes–domingo, día seleccionado, controles y agenda legible. |
| Datos y copy | Títulos, número de eventos, zona y sesiones proceden de DB; no se inventa contenido de la imagen. |
| Móvil | Marcas por día y agenda debajo; adaptación deliberada para lectura y tacto. |
| Iconos | SVG outline del sistema existente; sol/luna, calendario, flechas y reloj. |
| Contenedores | Bordes finos, radios pequeños y alturas naturales; no hay hero ni tarjetas de relleno. |

Capturas finales y mediciones de calendario/temas en Temporal/qa-calendar/ y de
agenda en Temporal/qa-plan-scroll/ y preparación/porcentaje/movimiento en
Temporal/qa-motion-progress/. El resultado previo de seguimiento permanece en
Temporal/qa-task-progress/results.json, sin capturas sustituidas. Los resultados y límites
comprobados están en [verificación](../verification.md). Los diseños y capturas anteriores
sustituidos se retiran; se mantiene un único sistema visual vigente.
