# Inicio e instalación de ArquiGica

## Instalación actual de Jorge

Desde la raíz de `SPARKX3.0`, haz doble clic en **iniciar.cmd**.
También puedes ejecutarlo desde PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\JORGE\Downloads\PROGRAMACION\SPARKX3.0'
.\iniciar.cmd
```

Cuando aparezca **ArquiGica disponible en http://127.0.0.1:8000/**, abre esa
dirección en el navegador e inicia sesión. La ventana del lanzador debe
permanecer abierta. Si el servicio ya está activo, usa la dirección existente;
no hace falta iniciar otra instancia.

El lanzador necesita `.venv\Scripts\python.exe`, las migraciones aplicadas
y la cuenta administradora local `adminjorge` activa. No crea cuentas, claves
ni presupuestos al ejecutarse. Puede procesar trabajos autorizados que ya
estuvieran pendientes.

## Primera instalación en otro equipo

Requisitos del proyecto: Python 3.12 o superior, dependencias de
`requirements.txt` y acceso a esa carpeta. La copia de código no incluye los
usuarios ni datos de la instalación de Jorge.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path var
.\.venv\Scripts\python.exe -B manage.py migrate
.\.venv\Scripts\python.exe -B manage.py createsuperuser --username adminjorge
.\.venv\Scripts\python.exe -B manage.py check
.\iniciar.cmd
```

La contraseña se introduce en el asistente de Django. No existe una contraseña
predeterminada en el código. Las variables de `.env.example` documentan opciones;
ese archivo no se carga automáticamente.

Si tu administrador tiene otro nombre, ejecuta:

```powershell
.\.venv\Scripts\python.exe -B manage.py runromeo --username NOMBRE
```

Para abrir únicamente la web, sin el coordinador de trabajos:

```powershell
.\.venv\Scripts\python.exe -B manage.py runlocal
```

## Antes de mostrar la demo

1. Abre **ArquiGica-presentacion.code-workspace** en VS Code y revisa el
   [mapa de arquitectura](../architecture.md).
2. En el navegador entra a **Mis eventos**. Para cargar la interfaz actual,
   utiliza Ctrl+F5 si tenías una pestaña de una versión anterior.
3. Comprueba el micrófono y la voz local si vas a conversar con Gica. La demo
   narrada no necesita que dictes respuestas.
4. Para una generación real, configura proveedor, presupuesto y conexión en
   **Gestión de IA → APIs y agentes**. Una clave guardada en memoria se pierde
   al reiniciar; no se debe pegar en código ni documentación.
5. Pulsa **Iniciar demo con OpenAI**, o elige el recorrido que corresponda a la
   configuración disponible. No se cambia automáticamente a un proveedor de pago.

El piloto presenta a Gica, registra la organización y el expositor, crea el
evento, solicita la propuesta, muestra el calendario y explica el cambio de
expositor. La guía manual pregunta lo que falta y prepara formularios; sus
acciones de guardar, generar y aprobar mantienen controles humanos.

Si falta la clave OpenAI, aparece **Guía en pausa**. Pulsa **Guardar clave API**
para abrir la configuración en otra pestaña, guarda la conexión y vuelve a la
pestaña de la guía. Pulsa **Reanudar guía** para continuar desde el mismo paso;
se conservan la ficha y las respuestas. Si aún falta la clave, seguirá en pausa.
Mantén esa pestaña abierta; recargarla, cerrarla o reiniciar ArquiGica termina
el recorrido en memoria. Guardar la clave no reanuda ni envía la solicitud por sí solo.

## Detener y volver a iniciar

Desde el perfil administrador, elige **Apagar ArquiGica** y confirma. También
puedes usar Ctrl+C en la ventana del lanzador. Espera la confirmación final de
apagado antes de cerrar la ventana o volver a iniciarlo.

El proceso espera operaciones en curso; un apagado no cancela un cargo ya
enviado al proveedor. Los eventos y versiones guardados permanecen. Las
conexiones privadas temporales deben configurarse de nuevo después.

## Problemas de arranque frecuentes

| Mensaje o situación | Acción |
| --- | --- |
| No se encontró el entorno Python | Crear `.venv` e instalar `requirements.txt`. |
| Puerto 8000 ocupado o ArquiGica ya abierto | Usar `http://127.0.0.1:8000/`; apagar la instancia existente antes de reiniciar. |
| Migraciones pendientes | Con el servicio detenido, ejecutar `manage.py migrate`. |
| Falta administrador activo | Crear tu superusuario o indicar su nombre con `--username`. |
| No hay conexión OpenAI disponible | Guardar de nuevo la conexión desde el módulo privado. |
| Cuota gratuita agotada | Revisar el modelo y su estado; no se garantiza disponibilidad ilimitada. |

El servidor local está limitado a `127.0.0.1`. Para publicar el sistema,
consulta [Despliegue](deployment.md), no expongas este lanzador directamente.
