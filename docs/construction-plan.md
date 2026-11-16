# Plan de construcción de ArquiGica

## Alcance vigente

El prototipo prioriza describir un evento, preparar una propuesta con IA,
revisarla, conservar una versión aprobada y seguir su preparación. El piloto
actual se concentra en un seminario virtual de 90 minutos. No representa la
implementación completa de todos los módulos del desafío SparkX 3.0.

La IA propone contenido. El servidor controla permisos, validaciones, versiones
y consumo. Gica guía al usuario, pregunta lo que falta y prepara acciones;
no administra cuentas, conexiones privadas ni presupuestos.

## Etapas implementadas

| Etapa | Resultado disponible |
| --- | --- |
| Base de la aplicación | Monolito modular Django, plantillas, HTMX y JavaScript; arranque local con `iniciar.cmd`. |
| Acceso | Login por correo o usuario, roles Administrador/Organizador/Revisor y revisión de eventos asignados. |
| Información del evento | Ficha, organizaciones, personas reutilizables, asignaciones y calendario con filtros. |
| Guía Gica | Interacción por texto o voz, preguntas según el paso, acciones locales acotadas y patrones revisados. |
| Propuesta compacta | Adaptador OpenAI, contexto limitado y salida JSON validada para agenda, preparación y comunicaciones. |
| Continuidad del plan | Versiones y comprobación de conflictos; revisión de cambios sin sustituir inmediatamente el plan aprobado. |
| Seguimiento | Estados No iniciado, En proceso y Completado, responsable, entregable y porcentaje de avance. |
| Control de IA | Conexiones privadas, autorización por agente, reservas y contabilidad bajo un límite explícito. |
| Presentación del piloto | Recorrido por directorio, ficha, agenda, calendario, cambios y Conoce a Gica. |

Las nuevas propuestas compactas solicitan entre ocho y diez tareas del seminario
y tres borradores: invitación, descripción e indicaciones. Se conserva la lectura
de resultados históricos más pequeños. Los mensajes requieren revisión y no se
envían a servicios externos desde este recorrido.

El cambio acotado `more_case_time` propone al menos cinco minutos adicionales
para el caso práctico, conserva 90 minutos totales y un mínimo de diez para
preguntas. El servidor mantiene títulos, tareas, fecha y expositor. El cambio
requiere confirmación humana, también durante la demo.

Si falta la clave OpenAI, la guía conserva el paso y ofrece reanudar después de
configurar la conexión. Guardar la clave no envía la solicitud por sí solo. La
simulación de estados de la demo no guarda tareas ficticias como completadas.

## Etapas parcialmente cubiertas

- **Planificación adaptativa:** hay restricciones, revisiones y un cambio de
  agenda cerrado; falta evaluar solicitudes abiertas sobre eventos distintos.
- **IA y economía:** existe contabilidad y un piloto OpenAI acotado. La
  disponibilidad de modelos gratuitos depende de sus cuotas; no se demuestra
  calidad equivalente ni ahorro comparativo entre proveedores.
- **Voz y personalización:** hay controles, guía y patrones revisados. Las
  pruebas con audio simulado no acreditan micrófono ni voz física en cada equipo.
- **Inscripciones:** existe una base de registro y capacidad, sin acreditar
  asistencia real ni una operación pública con participantes.
- **Seguridad operacional:** hay controles de acceso y límites del agente;
  producción, concurrencia y recuperación requieren aceptación propia.

## Etapas pendientes

1. Verificar transacciones, carreras y bloqueos con PostgreSQL, y medir carga
   multiusuario. SQLite sólo respalda el piloto local de una instancia.
2. Validar el recorrido con organizadores y participantes, con criterios y
   escenarios comparables definidos antes de medir resultados.
3. Comprobar audio y micrófono en el dispositivo real, incluyendo interrupciones
   y permisos del navegador.
4. Preparar operación pública: HTTPS, configuración de producción, gestión de
   secretos, respaldo y restauración verificados.
5. Ampliar recomendaciones individuales, análisis de opiniones y analítica
   posterior cuando existan datos reales y un alcance aprobado.

## Criterio de cierre de cada ampliación

Cada cambio debe tener un escenario concreto, permisos definidos, resultado
observable y comprobaciones pertinentes. Una propuesta generada no demuestra
que las tareas se hayan realizado ni que el evento haya ocurrido. Los resultados
simulados, las pruebas de software y las inferencias reales se registran por
separado. Publicar el sistema o enviar mensajes requiere autorización específica.

La evidencia vigente está en [Verificación](verification.md). El mapa del código
está en [Arquitectura](architecture.md) y el arranque en
[Inicio e instalación](guias/inicio.md).
