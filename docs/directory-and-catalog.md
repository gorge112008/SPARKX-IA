# Directorio privado y catálogo de eventos

Actualización del 16 de noviembre de 2026: el directorio inicial de adminjorge
contiene **Universidad Nacional del Callao - UNAC** y **Dr. Robert Castillo Alva**.
La limpieza autorizada retiró 45 personas, dos organizaciones y sus vínculos de
directorio; conservó los eventos, planes y evidencias, con respaldo local previo.

Los contactos se completan manualmente o durante las preguntas de creación.
Organizaciones y personas admiten hasta 12 alias editables, uno por línea.
**UNAC** y **Universidad Nacional del Callao** resuelven la misma organización;
**Robert** y **Robert Castillo Alva** resuelven al expositor registrado. La
coincidencia de identidad es exacta después de normalizar tildes, espacios y
mayúsculas. Si hay varias coincidencias se pide elegir, sin fusionarlas.

Si falta una institución o una persona declarada como expositor/invitado, Gica
pregunta si deseas registrarla: sólo una respuesta afirmativa explícita crea el
contacto. «No» u «omitir» continúa sin registrarlo. Dar de alta un contacto no
crea una cuenta ni confirma el evento; la vinculación al evento ocurre al
confirmar su creación. Las descripciones libres de recursos no se convierten
automáticamente en personas. El alta confirmada permanece aunque canceles el
borrador. Cada consulta y alta conserva el ámbito de su organizador.

La semilla masiva descrita a continuación es un antecedente de pruebas; ya no
representa el directorio activo de adminjorge.

Incremento del 15 de noviembre de 2026. Jorge autorizó crear datos ficticios de
expositores, participantes e invitados, buscar eventos por calendario/fecha/empresa
y preparar consultas mecánicas para el agente, bajo cuentas y permisos existentes.

## Qué se rescató de UNAC 1.3.0

Se leyó estáticamente el ZIP aportado, sin extraer ni ejecutar sus instaladores,
servidor o frontend compilado. El original permanece intacto en
`outputs/unac-actualizacion-1.3.0/unac-actualizacion-1.3.0.zip`, fuera de SparkX.
Tamaño: 245.201 bytes. SHA-256:
`f8039c13960f53b31c58ea659fb07bf24b4a9ee563708354c1d3769f7432321a`.
Las rutas de la tabla son miembros del ZIP bajo `unac-actualizacion-1.3.0/payload/`.

| Idea observada | Evidencia de referencia | Aplicación o límite en SparkX |
| --- | --- | --- |
| Normalización compartida | `shared/schema.js:1`, `server/directory.js:70` | Una función para NFKC/NFKD, tildes, mayúsculas y espacios. Normalizar para buscar no fusiona personas por nombre. |
| Cargas repetibles | `server/store.js:374`, `417` | Semilla UUIDv5 por propietario, con transacción y segunda carga sin cambios. El importador de archivos con hash+mapeo queda para una fase posterior. |
| Diferencias que requieren revisión | `server/store.js:498`, `778` | Edición con versión obligatoria y HTTP 409 conserva el borrador y muestra la versión actual. No hay sobrescritura automática ni fusión por semejanza. |
| Población común para vistas | `server/directory.js:233`, `279` | Catálogo único para listado, calendario y herramienta; contar y filtrar antes de paginar. Fechas civiles según zona del evento y sesiones aprobadas. |
| Procedencia e historial | `server/store.js:228`, `488`, `609` | Registro de actor/entidad/campos modificados sin duplicar nombre, correo o valores anteriores en la auditoría. Semillas y propuestas marcadas como sintéticas/locales. |
| Archivado reversible | `server/store.js:640` | Personas y organizaciones se archivan; conservan sus participaciones históricas. |

La separación de originales, consolidación y consulta de la referencia es útil
para futuras importaciones. Este incremento no implementa una arquitectura
Bronze/Silver/Gold, un importador masivo ni resolución automática de identidades.
Los algoritmos sobre JSON completo en memoria no se trasladan como almacenamiento:
SparkX conserva ORM, claves foráneas, restricciones y transacciones de Django.

## Seguridad que mejoramos al adaptar

En la referencia, `server/auth.js:8` concede lectura a guest y `server/app.js:178`
y `218` devuelven estado/fichas a sesiones autenticadas. `server/store.js:175`
proyecta el alumno completo, con información histórica. Negar la descarga no evita
que el cliente recupere esos JSON. Es un hallazgo estático de esas rutas; no una
prueba de explotación de un despliegue real.

Aquí cada consulta se limita al propietario antes de contar o devolver resultados.
Administrador del portal no significa acceso a los contactos/eventos de otros
organizadores. Revisor conserva únicamente sus eventos asignados y no accede al
directorio general, ni a sus herramientas o escrituras. Sus filtros de empresas
solo muestran las asociadas a sus eventos autorizados.

Persona de contacto y cuenta de acceso son entidades distintas. Crear un contacto
no crea contraseña, sesión o privilegios. Las relaciones exigen el mismo dueño;
las lecturas también protegen contra relaciones históricas corruptas. Las
herramientas excluyen correos, notas, descripciones completas y payloads de planes.

Las escrituras usan servicios explícitos, actor vigente, versiones exactas y
transacciones. La relación con un evento sigue orden de bloqueo Event → User,
igual que Jobs y chat local. Se conserva CSRF y la CSP existente. La revisión
independiente detectó expansión Unicode de nombres normalizados: se valida su
longitud después de normalizar, antes de guardar. Tiene prueba de regresión.

No se copió la autenticación propietaria, la prueba estática corta de segundo
factor ni los códigos en claro de la referencia. Tampoco se copió su auditoría
con valores personales completos o su almacenamiento JSON como base de datos.
La auditoría de SparkX es un registro de aplicación, no un almacén inmutable o
certificado. Concurrencia real y reglas de bloqueo requieren PostgreSQL.

## Modelo y navegación

- `Organization`: institución/empresa del organizador, nombre normalizado único
  dentro de su espacio, versión, activo/archivado y etiqueta de dato ficticio.
- `Person`: nombre, categoría habitual, afiliación opcional, correo opcional,
  especialidad, versión, estado y etiqueta sintética. UUID es la identidad. El
  correo normalizado no se repite dentro del mismo directorio; no es identidad global.
- `Event.organization`: empresa organizadora principal explícita. No se infiere
  del empleador de asistentes. En esta entrega se admite una empresa principal.
- `EventPerson`: persona + evento + rol, estado y versión. Una persona puede tener
  varios roles y participar en varios eventos. Vínculo previsto no es inscripción,
  reserva de cupo, aceptación de invitación, confirmación externa ni asistencia.
- `DirectoryAudit`: actor, entidad, acción, campos y fecha; sin copias de valores.

Entra en **Directorio**, filtra personas por nombre/categoría/empresa y alterna
a empresas. Cada evento ofrece **Personas del evento** para vincular contactos y
confirmar/cancelar sus roles. El formulario del evento permite elegir empresa y
marcarlo como ficticio. El catálogo y calendario filtran texto, empresa, fechas y
plan aprobado/pendiente, conservando filtros al navegar.

No se convierten los nombres `speaker` del plan en personas automáticamente.
Vincular contactos no reescribe planes históricos, crea propuestas ni cambia el
avance de tareas. El directorio aún no es una restricción de disponibilidad del
solver. Si se integra como entrada material de generación, su versión deberá
incorporarse al snapshot del Job/candidata y comprobarse al aprobar.

## Herramientas mecánicas y ahorro

`apps.directory.tools.execute_tool(actor=..., name=..., arguments=...)` acepta
solo `search_people`, `search_events` y `event_people`. Actor procede del servidor;
campos desconocidos, escrituras y límites fuera de 1–20 son rechazados. Devuelve
campos mínimos, total, truncamiento explícito, límite y fecha de consulta.
El endpoint GET autenticado es `/directory/tools/?tool=search_people&limit=10`.

El chat del evento reconoce comandos exactos en español:

- `buscar expositores` o `buscar expositores: nombre`.
- `buscar participantes`, `buscar invitados` y sus filtros tras dos puntos.
- `buscar eventos: UNAC` (búsqueda textual, no un filtro empresarial por UUID).
- `personas de este evento`.

Estas consultas ejecutan Python y generan una respuesta identificada como local,
sin modelo de IA, Job o AIUsage. Una clave repetida con el mismo texto conserva
la respuesta; otro contenido con esa clave se rechaza. No modifican directorio,
planes, confirmaciones o tareas. El resto del chat conserva el control de perfil
y presupuesto; no se activó ningún proveedor, worker o modelo de pago.

Esta conexión determinista es acotada: no es una interpretación libre del lenguaje
ni un ciclo general de tool calling con proveedores. Los modelos gratuitos se
ensayaron por separado; asignarles especialidades o automatizar su selección sigue
necesitando evaluación por tarea. No se subió el paquete UNAC a esos proveedores.

Se mide el tamaño de respuesta en bytes, claramente distinto de tokens. Evitar
una llamada para estas consultas no demuestra un porcentaje de ahorro en generación
de agendas. Eso necesita comparación A/B con iguales restricciones y calidad.
La caché semántica, compresión aprendida y selección entrenada de modelos quedan
pospuestas; este incremento empieza por consultas estructuradas y código mecánico.

## Datos de demostración

Comando local, con servidor detenido durante mantenimiento:

```powershell
.\.venv\Scripts\python.exe -B manage.py seed_synthetic_directory --owner adminjorge --dry-run
.\.venv\Scripts\python.exe -B manage.py seed_synthetic_directory --owner adminjorge
```

Crea 2 organizaciones sintéticas, 3 expositores, 30 participantes y 12 invitados,
60 vínculos por confirmar y los 6 eventos acordados del 16 al 21 de noviembre de
2026. Las 6 propuestas son ejemplos locales válidos y pendientes de aprobación;
no son respuestas generadas por los modelos del benchmark. Correos `.invalid` y
nombres ficticios. La segunda carga conserva registros, decisiones y auditoría.
Una colisión con un registro ajeno/no ficticio revierte la carga.

Los datos no representan anuncios de UNAC/GICA, trámites oficiales o participación
real. Crear participantes en este directorio no implementa registro público ni
control de aforo. Esas funciones siguen fuera de este incremento.

## Límites operativos

El directorio utiliza filtros SQL con alcance, selección de relaciones y paginación
de 20. La búsqueda por subcadena no equivale a búsqueda difusa ni garantiza uso de
un índice de texto. El catálogo mantiene la proyección completa de eventos visibles
para respetar fechas locales y sesiones derivadas; su coste crece con ese conjunto.
No se presenta como prueba de carga o solución ya medida para grandes volúmenes.
No se añadieron dependencias, servicios, CDNs o librerías de calendario.

Los resultados de pruebas, navegador y preservación de datos se registran en
[verification.md](verification.md) y `Temporal/qa-directory/`. La integración
productiva de IA, PostgreSQL/carga, despliegue y los entregables del concurso
mantienen su estado pendiente; esta ampliación no los acredita por sí sola.
