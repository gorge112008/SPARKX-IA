# Revisión de la dependencia de animación Motion

Fecha de consulta: **8 de noviembre de 2026**, America/Lima. Esta revisión documenta una decisión de incorporación; no acredita por sí sola la integración ni la compatibilidad CSP en la aplicación. No se instalaron ni ejecutaron los paquetes descargados para realizarla.

## Decisión

Fijar **Motion 14.10.1**, licencia **MIT**, y servir una copia local del bundle UMD oficial `dist/motion.js`. Usar únicamente `Motion.animateMini`, `Motion.inView` y `Motion.stagger` para las transiciones del dashboard. No incorporar React, ejecutar scripts npm ni depender de un CDN durante la navegación.

La distribución UMD es mayor que una importación optimizada, pero permite conservar el proyecto Django/HTMX sin añadir un bundler y su cadena de instalación. Las tres funciones están exportadas en el archivo inspeccionado. `animateMini` utiliza las API de animación del navegador; para este alcance se necesitan transformaciones completas y opacidad, no las capacidades adicionales del motor híbrido.

La documentación anuncia aproximadamente 3,2 kB para `animate` mini y 0,5 kB para `inView`. Son cifras de las funciones optimizadas, **no el tamaño del UMD completo**. No existe un bundle `motion-mini.js` UMD autocontenido en el tarball inspeccionado. `dist/es/mini.mjs` tiene 40 bytes y reexporta `framer-motion/dom/mini`; copiarlo aisladamente no resuelve esa dependencia.

No se añade GSAP: las funciones necesarias ya están cubiertas y una segunda biblioteca no aporta una necesidad identificada en este incremento.

## Fuentes y versión

| Recurso | Dirección exacta |
| --- | --- |
| Documentación de instalación | https://motion.dev/docs/quick-start |
| `animate` y variante mini | https://motion.dev/docs/animate |
| `inView` | https://motion.dev/docs/inview |
| `stagger` | https://motion.dev/docs/stagger |
| Repositorio oficial | https://github.com/motiondivision/motion |
| Metadatos npm fijados | https://registry.npmjs.org/motion/14.10.1 |
| Registro con fechas y etiquetas | https://registry.npmjs.org/motion |
| Tarball oficial | https://registry.npmjs.org/motion/-/motion-14.10.1.tgz |
| Bundle en el CDN indicado por la documentación | https://cdn.jsdelivr.net/npm/motion@14.10.1/dist/motion.js |
| Licencia de la versión | https://cdn.jsdelivr.net/npm/motion@14.10.1/LICENSE.md |

El registro npm devolvió `latest: 14.10.1`, publicada el **6 de noviembre de 2026 a las 14:25:26.082 UTC**. Se fija ese número; no usar `@latest`, rangos de versión ni una URL que cambie silenciosamente.

## Integridad y tamaños medidos

El tarball se descargó por HTTPS y se leyó en memoria. Su SHA-512 calculado coincidió con `dist.integrity` del registro npm:

```text
sha512-CRlxgrRmG5SNu5jxyYmiw3Oo6IrPq8xhQ0EmOm6WS6tx956G6O4WqVBA8ovrIwt4Sb/A9M0j2T2Vca7ze5PkRQ==
```

El archivo `package/dist/motion.js` extraído en memoria y el bundle servido por la URL exacta de jsDelivr dieron el mismo SHA-256:

```text
b39d6cdb97506ae8c00da5221ad23bb3799845b64bf58b8e19c297d81211a916
```

SRI SHA-384 calculado para esos bytes:

```text
sha384-lnXs/o2QVHbH7aNA9JGkcMdW38AWVgMHWWrPU/fGgHi+eRj2j0a8va/1nlijpjHX
```

| Elemento | Tamaño observado |
| --- | ---: |
| Bundle UMD minificado | 183.604 bytes |
| Mismos bytes comprimidos con `gzip.compress` de Python | 61.208 bytes |
| Archivo de licencia | 1.100 bytes |
| Tarball: tamaño descomprimido declarado por npm | 970.416 bytes |
| Tarball: archivos declarados y enumerados | 44 |

El tamaño gzip es una medición local orientativa; la transferencia real depende de la compresión y configuración del servidor. El SHA-256 de `LICENSE.md` fue `1bf0dc3f7727723e5a032ed12164a47cf92c05204cb1a3485f123c24e2833ed1`. El texto declara copyright de Motion B.V. (2024). La copia local debe conservar la licencia y su aviso.

El registro también contiene firmas de distribución. **No se verificaron criptográficamente las firmas npm ni una atestación de procedencia**; no confundir la coincidencia del hash con la validación de identidad del editor o una auditoría del proceso de compilación.

## Dependencias y scripts declarados

La revisión de metadatos cubrió estos paquetes y versiones. Las dependencias describen la instalación npm completa; el UMD inspeccionado es autocontenido y no obliga al navegador a descargarlas.

| Paquete | Dependencias de ejecución declaradas |
| --- | --- |
| `motion 14.10.1` | `framer-motion 14.10.1`, `tslib ^2.4.0` |
| `framer-motion 14.10.1` | `motion-dom 14.10.1`, `motion-utils 14.7.0`, `tslib ^2.4.0` |
| `motion-dom 14.10.1` | `motion-utils 14.7.0` |
| `motion-utils 14.7.0` | Ninguna |
| `tslib 2.9.1` | Ninguna |

`tslib 2.9.1` era la versión estable consultada compatible con el rango; esto no demuestra qué versión interna se utilizó al compilar el UMD del editor. `motion` y `framer-motion` declaran React, React DOM y Remix como peer dependencies opcionales. Su presencia en los metadatos no implica que el UMD del recorrido JavaScript necesite React.

No se declararon `preinstall`, `install` ni `postinstall` en los cinco paquetes revisados. Sí existen los siguientes grupos de scripts:

- `motion`: desarrollo, pruebas, build, clean, prepack, typecheck y postpublish.
- `framer-motion`: desarrollo/watch, pruebas de cliente y servidor, build, clean, measure, prepack, prettier, typecheck y postpublish.
- `motion-dom`: desarrollo, pruebas, build, clean, measure, prepack y typecheck.
- `motion-utils`: desarrollo, pruebas, build, clean y typecheck.
- `tslib`: sin scripts declarados.

Los scripts de build usan herramientas de desarrollo como TypeScript y Rollup; algunos scripts `clean` contienen borrado de directorios del propio paquete. **No se ejecutó ninguno**. La decisión de servir el archivo ya compilado evita incorporarlos a la instalación del proyecto.

## Consultas de vulnerabilidades conocidas

Consultadas el **8 de noviembre de 2026**:

1. Endpoint npm `POST https://registry.npmjs.org/-/npm/v1/security/advisories/bulk`, con este cuerpo de versiones públicas:

   ```json
   {
     "motion": ["14.10.1"],
     "framer-motion": ["14.10.1"],
     "motion-dom": ["14.10.1"],
     "motion-utils": ["14.7.0"],
     "tslib": ["2.9.1"]
   }
   ```

   Resultado observado: `{}`.

2. GitHub Advisory API, una petición por paquete y versión: `GET https://api.github.com/advisories?ecosystem=npm&affects=motion%4014.10.1&per_page=100`, sustituyendo `affects` por cada pareja de la tabla. Resultado observado en las cinco consultas: `[]`.
3. [Avisos publicados por los mantenedores](https://github.com/motiondivision/motion/security/advisories): la página mostró que no había avisos publicados.

Estos resultados significan que las consultas realizadas no devolvieron avisos aplicables. **No certifican ausencia de vulnerabilidades**, malware, errores desconocidos ni una seguridad absoluta. Deben repetirse al actualizar la biblioteca y antes de una exposición externa; las bases pueden incorporar avisos con posterioridad.

## Inspección textual del bundle y CSP

Se inspeccionaron como texto tanto `dist/motion.js` como `dist/motion.dev.js` del tarball. No se ejecutaron. La búsqueda no encontró llamadas o referencias a `eval(`, `new Function`, `fetch(`, `XMLHttpRequest`, `WebSocket`, `sendBeacon`, `innerHTML`, `document.write` ni importaciones dinámicas en el bundle minificado. En el archivo legible se comprobaron las exportaciones y el helper de estilos descrito abajo.

Esta búsqueda detecta patrones concretos; no es un análisis completo del flujo del programa y puede omitir formas equivalentes, código indirecto o problemas lógicos. La ausencia de esos textos tampoco demuestra por sí sola compatibilidad con toda política CSP.

Se encontró un helper de **`animateView`** que crea un elemento `<style>` con id `motion-view`, asigna reglas mediante `textContent` y lo inserta en `document.head`. Puede chocar con una política estricta de estilos. **No usar `animateView` en esta integración**. Limitar el wrapper a `animateMini`, `inView` y `stagger`; no añadir `unsafe-eval`, `unsafe-inline` ni nuevos orígenes a CSP por esta dependencia.

Con self-hosting el script debe cargarse desde el mismo origen como recurso externo, antes del wrapper del proyecto. No necesita peticiones de terceros. La animación usa propiedades de estilo y APIs del navegador: **la integración se comprobó posteriormente bajo la CSP vigente de ArquiGica**, según la sección de cierre de este documento. La inspección estática por sí sola no habría acreditado ese resultado.

## Reproducción de la comprobación de integridad

Ejecutar Python con biblioteca estándar en un entorno autorizado con acceso a los dos orígenes públicos. Este ejemplo descarga y analiza bytes en memoria, sin extraer archivos al disco ni ejecutar el paquete:

```python
import base64
import gzip
import hashlib
import io
import json
import tarfile
import urllib.request

metadata_url = "https://registry.npmjs.org/motion/14.10.1"
bundle_url = "https://cdn.jsdelivr.net/npm/motion@14.10.1/dist/motion.js"
metadata = json.load(urllib.request.urlopen(metadata_url))
tarball = urllib.request.urlopen(metadata["dist"]["tarball"]).read()
integrity = "sha512-" + base64.b64encode(hashlib.sha512(tarball).digest()).decode()
assert integrity == metadata["dist"]["integrity"]

with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
    bundle = archive.extractfile("package/dist/motion.js").read()
    license_bytes = archive.extractfile("package/LICENSE.md").read()

cdn_bundle = urllib.request.urlopen(bundle_url).read()
assert bundle == cdn_bundle
assert hashlib.sha256(bundle).hexdigest() == (
    "b39d6cdb97506ae8c00da5221ad23bb3799845b64bf58b8e19c297d81211a916"
)
print("bytes", len(bundle), "gzip", len(gzip.compress(bundle)))
print("SHA256", hashlib.sha256(bundle).hexdigest())
print("SRI", "sha384-" + base64.b64encode(hashlib.sha384(bundle).digest()).decode())
print("license SHA256", hashlib.sha256(license_bytes).hexdigest())
```

Para repetir la consulta npm, enviar el JSON anterior al endpoint bulk con `Content-Type: application/json`. Para GitHub, utilizar el endpoint indicado con `Accept: application/vnd.github+json` y un `User-Agent` identificable. Estas consultas públicas no requieren credenciales del proyecto. Conservar la fecha y distinguir una respuesta vacía de un fallo HTTP o de red.

## Comprobaciones previstas al integrarlo

- Confirmar de nuevo el hash de la copia que finalmente se sirva y conservar la licencia.
- Probar carga y ejecución sin peticiones de terceros, sin errores de consola ni violaciones de CSP.
- Verificar movimiento perceptible en carga/entrada a viewport y después de navegación o intercambios HTMX apropiados, evitando reproducirlo en cada sondeo de estado.
- Respetar `prefers-reduced-motion` inicial y sus cambios; mantener texto y controles utilizables si el script o la biblioteca fallan.
- Comprobar foco, lectores de pantalla y selección del texto si se crean envoltorios por palabra; no usar HTML no confiable para dividir contenido.

El resultado de esas pruebas pertenece a la evidencia de integración de la aplicación y no se da por obtenido en este informe de dependencia.


## Cierre de integración local — 8 de noviembre de 2026

El bundle descargado coincide con el SHA-256 y SRI documentados. Se integra localmente con animateMini e inView, sin CDN en ejecución, sin npm/install scripts ni cambios en CSP. La revisión de navegador pasó 45 comprobaciones del recorrido descrito en [verification.md](../verification.md): carga, progresión real de transformaciones, repetición, navegación, reducción de movimiento, ausencia de JS y bloqueo controlado del vendor. En la ejecución normal no hubo errores de recursos, peticiones externas ni violaciones CSP; se comprobó también CSP con reducción dinámica. Esto valida el alcance probado y no constituye una certificación universal de la dependencia.

## Ajuste de interacción y porcentaje — 8 de noviembre de 2026

La investigación actual midió Hyrup en navegador y contrastó sus módulos públicos:
[encabezado](https://framerusercontent.com/sites/5cOZuFk9Ptv7eCdHmZtLsY/mqsFFrCNq.CBh20wxz.mjs)
y [CTA/nav](https://framerusercontent.com/sites/5cOZuFk9Ptv7eCdHmZtLsY/toplevel-deps.Bbt7x8WC.mjs).
El H1 entra como bloque tras una máscara; CTA/nav desplazan un segundo rótulo
durante 400 ms con curva [.4,0,.4,1]. La demora de marketing se acorta para ArquiGica;
H2 por palabras, foco y presión son adaptaciones propias. No se copian activos
del sitio ni se incorporan bibliotecas nuevas. Detalle en
[sistema visual](../arquitectura/design-system.md#movimiento-de-títulos-y-controles).

La copia Motion conserva SHA-256 y SRI originales, verificados de nuevo localmente.
Se usan textContent/nodos DOM y una copia CSS decorativa bajo aria-hidden, con
nombre único del control. Se restauran títulos, estilos y observadores al acabar,
cancelar, retirar contenido HTMX o imprimir. El porcentaje se calcula en servidor
y no representa consumo IA ni progreso de una inferencia. La comprobación de
navegador actual y sus límites se consolidan en [verificación](../verification.md).
