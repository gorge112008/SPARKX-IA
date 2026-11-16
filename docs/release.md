# Entrega del código de SparkX 3.0

El paquete es una copia instalable del código del prototipo. No contiene la
instalación personal de Jorge: cuentas, eventos, directorio, conversaciones,
presupuestos, perfiles API, claves, bases de datos, sesiones, capturas y respaldos
no forman parte de la distribución. No se ha publicado un repositorio externo.

## Contenido y estructura

`tools/package_release.py` selecciona código, migraciones, pruebas, plantillas,
estilos, scripts, recursos estáticos y documentación mediante una lista permitida.
Conserva las licencias de las dependencias estáticas y el aviso de la muestra de
voz. Genera un `AGENTS.md` portátil sin referencias al mentor privado. `.env.example`
documenta variables de entorno; no contiene una clave utilizable y no se carga
automáticamente. Los binarios de OpenCode y los modelos de voz no se distribuyen.

Se excluyen `.env` reales, `.git`, `.venv`, `.agents`, `.codex`, `.aws`, `.opencode`,
`Temporal`, `var`, `entrega`, bases SQLite, archivos de claves, registros y cachés.
`entrega/` guarda los artefactos finales y queda fuera de Git y del ZIP del código.
Los informes y las diapositivas se entregan aparte, sin incorporarlos como
dependencias de la aplicación.

El ZIP ordena las entradas, fija sus fechas y permisos y contiene
`release-manifest.json` con ruta, tamaño y SHA-256 de cada archivo. A igualdad de
código y versión de las herramientas de compresión, genera los mismos bytes.
Un `.zip.sha256` adjunto permite comprobar el archivo completo. Esto comprueba
integridad, no autentica al autor ni sustituye una firma digital.

## Generación y comprobación

Desde la raíz del proyecto, con el código final detenido para edición:

```powershell
.\.venv\Scripts\python.exe -B -m unittest tools.test_package_release
.\.venv\Scripts\python.exe -B tools\package_release.py --check-only
.\.venv\Scripts\python.exe -B tools\package_release.py
.\.venv\Scripts\python.exe -B tools\package_release.py --verify entrega\SparkX3.0-codigo-v0.1.0.zip
Get-FileHash -Algorithm SHA256 -LiteralPath entrega\SparkX3.0-codigo-v0.1.0.zip
```

El nombre usa la versión de `pyproject.toml`. El escáner se detiene ante formatos
de credenciales reconocidos sin imprimir sus valores. Las excepciones para ocho
tokens ficticios de pruebas negativas están acotadas a hash y archivo exactos;
no se excluyen globalmente las pruebas. La búsqueda por formatos no garantiza
detectar todos los secretos ni convierte en públicos los datos de trabajo.
El verificador rechaza rutas absolutas, traversal, nombres no portátiles,
duplicados, enlaces, tamaños excesivos y contenido que no coincide con el
manifiesto. No ejecuta ni extrae contenido del archivo al comprobarlo.

## Instalar una copia nueva en Windows

Requisitos: Python 3.12 o superior y acceso a los paquetes fijados de PyPI. Extraer
el ZIP en una carpeta propia y entrar en su subcarpeta `SPARKX3.0`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path var
.\.venv\Scripts\python.exe -B manage.py migrate
.\.venv\Scripts\python.exe -B manage.py createsuperuser
.\.venv\Scripts\python.exe -B manage.py check
.\.venv\Scripts\python.exe -B manage.py runlocal
```

Entrar en `http://127.0.0.1:8000/` con la cuenta recién creada. No hay usuario,
contraseña ni API configurados por defecto. `runlocal` inicia sólo la web local.
Para el lanzador integrado `Iniciar SparkX.cmd`, crear el superusuario con nombre
`adminjorge`; con otro nombre usar `manage.py runromeo --username NOMBRE`. El
lanzador integrado también revisa los trabajos explícitos autorizados pendientes;
una instalación nueva no tiene ninguno. No ejecutar `prepare_romeo` como parte de
la instalación general: es un comando específico que prepara un piloto de pago.

La copia de código no incluye los registros personales de la instalación
original. **Mis eventos → Iniciar piloto guiado** registra y crea el caso de
presentación si falta, mediante el recorrido autorizado y sus formularios.
También se pueden registrar otras identidades y eventos manualmente desde
Directorio y Eventos. Los comandos históricos
`seed_demo_event` y `seed_journey_demo` cargan casos sintéticos distintos; no se
deben describir como el piloto real actual ni como inferencia de un modelo.

Para ejecutar las pruebas mantenidas sin contactar proveedores:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -B manage.py test --noinput
.\.venv\Scripts\python.exe -B -m unittest tools.test_package_release
```

Las pruebas de bloqueos y carreras requieren PostgreSQL. SQLite sirve para el
prototipo de una sola instancia; no acredita capacidad de 20, 50 o 100 usuarios.
Consultar `docs/verification.md` para los resultados de esta entrega y sus límites.

## Preparación para GitHub

Extraer el paquete en un directorio nuevo, revisar sus archivos y crear allí el
repositorio Git. El paquete no incluye el historial Git local, que podría tener
material previamente retirado. Los informes finales pueden adjuntarse a una
entrega de GitHub como archivos separados. Elegir la visibilidad y la licencia
del código propio según lo acordado por sus autores; se conservan las licencias
de terceros sin atribuirles el código del proyecto. La generación del ZIP no
crea el repositorio ni publica archivos.

Antes de un acceso público, seguir `docs/deployment.md`: PostgreSQL, secreto
exclusivo, `DEBUG=0`, HTTPS, servidor de producción, respaldo/restauración y
comprobación de roles y carga. Una copia instalable no acredita ese despliegue.
