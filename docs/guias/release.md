# Entrega del código de ArquiGica

El paquete es una copia instalable del código del prototipo. No contiene la
instalación personal de Jorge: cuentas, eventos, directorio, conversaciones,
presupuestos, perfiles API, claves, bases de datos, sesiones, capturas y respaldos
no forman parte de la distribución. Generarlo no publica un repositorio externo;
la publicación requiere una acción separada y autorizada.

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
.\.venv\Scripts\python.exe -B tools\package_release.py --output entrega\ArquiGica_Proyecto.zip
.\.venv\Scripts\python.exe -B tools\package_release.py --verify entrega\ArquiGica_Proyecto.zip
Get-FileHash -Algorithm SHA256 -LiteralPath entrega\ArquiGica_Proyecto.zip
```

Sin `--output`, el nombre incluye la versión de `pyproject.toml`. La entrega
principal usa `ArquiGica_Proyecto.zip` y contiene una única carpeta `ArquiGica/`.
El verificador sigue leyendo paquetes anteriores con raíz `SPARKX3.0/`, pero
rechaza mezclar raíces en un mismo archivo. El escáner se detiene ante formatos
de credenciales reconocidos sin imprimir sus valores. Las excepciones para ocho
tokens ficticios de pruebas negativas están acotadas a hash y archivo exactos;
no se excluyen globalmente las pruebas. La búsqueda por formatos no garantiza
detectar todos los secretos ni convierte en públicos los datos de trabajo.
El verificador rechaza rutas absolutas, traversal, nombres no portátiles,
duplicados, enlaces, tamaños excesivos y contenido que no coincide con el
manifiesto. No ejecuta ni extrae contenido del archivo al comprobarlo.

## Instalar una copia nueva en Windows

Requisitos: Python 3.12 o superior y acceso a los paquetes fijados de PyPI. Extraer
el ZIP en una carpeta propia y entrar en su subcarpeta `ArquiGica`.

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
Para el lanzador integrado `iniciar.cmd`, crear el superusuario con nombre
`adminjorge`; con otro nombre usar `manage.py runromeo --username NOMBRE`. El
lanzador integrado también revisa los trabajos explícitos autorizados pendientes;
una instalación nueva no tiene ninguno. No ejecutar `prepare_romeo` como parte de
la instalación general: es un comando específico que prepara un piloto de pago.

La copia de código no incluye los registros personales de la instalación
original. Desde **Directorio** y **Eventos** se registran las identidades y la
ficha de forma manual, o con el acompañamiento por texto/voz de Gica. Guardar,
generar y aprobar mantienen sus controles humanos.

**Mis eventos → Iniciar demo con OpenAI** inicia el caso narrado autorizado: alta
de organización y expositor, ficha del evento, solicitud de agenda y revisión del
resultado. Necesita perfil, clave en memoria y presupuesto autorizado; la copia
nueva no los configura. Ese modo sólo aplica a la identidad fija del piloto y no
concede aprobación automática a eventos manuales. **Recorrido completo** conserva
la pausa **Aprobar y continuar**. La alternativa gratuita se elige expresamente
desde Conoce a Gica y depende de la cuota del proveedor. Los modos y límites están
en [Gestión de IA](ai-management.md); las instrucciones de arranque están en
[Inicio y ejecución](inicio.md).

Los comandos históricos
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
Consultar [verificación](../verification.md) para los resultados y sus límites.

## Preparación para GitHub

Extraer el paquete en un directorio nuevo, revisar sus archivos y crear allí el
repositorio Git. El paquete no incluye el historial Git local, que podría tener
material previamente retirado. Los informes finales pueden adjuntarse a una
entrega de GitHub como archivos separados. Elegir la visibilidad y la licencia
del código propio según lo acordado por sus autores; se conservan las licencias
de terceros sin atribuirles el código del proyecto. La generación del ZIP no
crea el repositorio ni publica archivos.

Antes de un acceso público, seguir [despliegue](deployment.md): PostgreSQL, secreto
exclusivo, `DEBUG=0`, HTTPS, servidor de producción, respaldo/restauración y
comprobación de roles y carga. Una copia instalable no acredita ese despliegue.
