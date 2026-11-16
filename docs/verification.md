# Verificación de ArquiGica

## Alcance del corte registrado

Este resumen conserva la evidencia del 16 de noviembre de 2026. Describe una
validación focalizada del piloto local; no certifica toda la aplicación ni una
operación en producción.

## Resultados de software

| Evidencia | Resultado registrado | Alcance |
| --- | --- | --- |
| Backend focalizado | 99 pruebas correctas en 31,433 s | Contratos compactos, OpenAI, cambio de agenda, flujo del piloto, compatibilidad y perfil. |
| Interfaz del recorrido | 7 grupos UI correctos | Instrucciones y desplazamiento, simulación de estados, tres mensajes, aprobación del cambio, cierre en Conoce a Gica y vistas móviles. |
| Pausa por clave ausente | 4 grupos de integración correctos | Pausa/reanudación, respuestas conservadas, doble clic, cambio de pestaña y cancelación. |

Los tres conteos corresponden a conjuntos distintos. Los grupos UI y de pausa
no son conteos de casos backend ni de llamadas a proveedores. La ejecución
focalizada también terminó con la comprobación Django sin incidencias.

Las pruebas de interfaz utilizaron Edge aislado, plantillas y JavaScript reales,
SQLite descartable, contenido preparado y dobles de proveedor/audio. No
modificaron la base activa ni enviaron solicitudes remotas. La escena de
preparación mostró 10 % de avance de ejemplo mientras el avance guardado
permaneció en 0 %. Los borradores de comunicación no se enviaron.

El caso de cambio usó una respuesta preparada: el caso práctico pasó de 35 a 40
minutos, las preguntas conservaron 15 y el total se mantuvo en 90. La propuesta
quedó pendiente de aprobación humana. Esto acredita validación y presentación
del resultado de prueba, no una inferencia nueva ni trabajo realizado.

## Consumo de IA observado

Corte histórico acumulado del 16 de noviembre de 2026:

| Dato | Valor registrado |
| --- | --- |
| Registros de consumo OpenAI liquidados | 5 |
| Tokens | 5.624: 4.620 de entrada y 1.004 de salida |
| Coste bruto estimado | USD 0,007985 |
| Tope acumulado autorizado del piloto | USD 1 |
| Disponible calculado en ese corte | USD 0,992015 |

Es una observación de la contabilidad del prototipo, no una factura de OpenAI,
un saldo actual ni el coste unitario de un evento. El cobro neto tras créditos
no se comprobó. Las pruebas con dobles y las capturas no se suman como inferencias
reales. No se ha medido ahorro comparativo de tokens, tiempo o dinero.

## Repetir las comprobaciones mantenidas

Desde la raíz del proyecto, con el entorno y dependencias instalados según
[Inicio e instalación](guias/inicio.md), se puede repetir la selección backend:

```powershell
$pruebas = @(
    'apps.assistant.tests.test_compact_planning'
    'apps.assistant.tests.test_compact_openai'
    'apps.assistant.tests.test_compact_changes'
    'apps.assistant.tests.test_pilot_workflow'
    'apps.assistant.tests.test_pilot_polish'
    'apps.assistant.tests.test_profile'
)
.\.venv\Scripts\python.exe -B manage.py check
.\.venv\Scripts\python.exe -B manage.py test $pruebas --verbosity 1
.\.venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run
```

La selección contiene pruebas con proveedores doblados; no necesita claves API
ni el servidor habitual en ejecución. Los conteos anteriores describen el corte
registrado y pueden cambiar cuando evolucione el código.

Para revisar la interfaz, usar una instalación o base descartable:

1. Recorrer directorio, ficha y calendario; comprobar que el evento conserva sus
   datos al volver al detalle.
2. Revisar instrucciones de preparación, estados, porcentaje y tres borradores;
   distinguir la simulación de los estados realmente guardados.
3. Revisar el cambio de agenda y su confirmación humana, y el cierre en Conoce
   a Gica, tanto en escritorio como en móvil.
4. Con OpenAI seleccionado y sin clave, comprobar la pausa. Guardar una conexión
   no debe reanudar automáticamente. Una reanudación con clave puede crear un
   trabajo real y consumir presupuesto: esa prueba requiere autorización propia.

Estos pasos son una guía de revisión manual; no sustituyen ni vuelven a ejecutar
los siete grupos UI y los cuatro grupos de integración del corte registrado.

## Pendientes de aceptación

- PostgreSQL: carreras, bloqueos, transacciones y carga multiusuario. Las pruebas
  sobre SQLite no establecen esas garantías.
- Voz y micrófono físicos, permisos e interrupciones en el equipo real.
- Disponibilidad de expositores y plataformas externas, operación pública,
  HTTPS y restauración de respaldos.
- Validación con usuarios, asistencia real y comparación de calidad o ahorro
  entre proveedores con escenarios equivalentes.

Consultar [Arquitectura](architecture.md) para las fronteras del sistema y
[Plan de construcción](construction-plan.md) para el alcance hecho y pendiente.
