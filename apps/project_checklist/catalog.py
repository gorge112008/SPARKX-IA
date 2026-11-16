"""Immutable manual preparation checklist; never evidence of real execution."""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ChecklistConfirmation:
    key: str
    label: str


@dataclass(frozen=True)
class ChecklistLink:
    label: str
    url: str


@dataclass(frozen=True)
class ChecklistItem:
    key: str
    title: str
    description: str
    condition: str = ""
    steps: tuple[str, ...] = ()
    confirmations: tuple[ChecklistConfirmation, ...] = ()
    links: tuple[ChecklistLink, ...] = ()

    @property
    def optional(self):
        return bool(self.condition)


@dataclass(frozen=True)
class ChecklistGroup:
    key: str
    title: str
    description: str
    items: tuple[ChecklistItem, ...]


GROUPS = (
    ChecklistGroup("conexion", "Primera prueba real de IA", "Preparar la conexión sin compartir claves ni autorizar gastos desde este checklist.", (
        ChecklistItem("creditos_api", "Comprobar créditos y cuota API", "Revisar el beneficio disponible, su vinculación, saldo, vigencia y cuota en la cuenta del proveedor elegido. Declararlo aquí no consulta ni verifica la cuota externa.", steps=(
            "En ChatGPT abre Configuración → Facturación y comprueba si aparece el beneficio API. Si está disponible, revisa Vincular organización con el mismo correo y una organización de tu propiedad; si no aparece, deja este punto pendiente.",
            "En la plataforma API selecciona esa organización y revisa el saldo concedido y su caducidad. El primer abono puede ser proporcional al ciclo restante; la suscripción de chat por sí sola no acredita saldo API.",
            "Revisa los límites de la organización y del modelo elegido, la recarga automática y los créditos comprados. Al agotarse el beneficio, otros fondos podrían seguir consumiéndose; no actives recargas ni compres saldo como parte de esta comprobación.",
            "Comunica únicamente si el beneficio está activo, su saldo, caducidad y si hay cuota para el modelo. Nunca copies claves, contraseñas ni capturas con secretos en este módulo.",
        ), confirmations=(
            ChecklistConfirmation("creditos_api_organizacion", "Comprobé personalmente la organización y si el beneficio está activo."),
            ChecklistConfirmation("creditos_api_saldo_vigencia", "Revisé el saldo, su caducidad y los límites del modelo en la cuenta externa."),
            ChecklistConfirmation("creditos_api_recargas", "Revisé recargas y fondos alternativos; esta revisión no autoriza gasto adicional."),
        ), links=(
            ChecklistLink("Condiciones oficiales del beneficio API", "https://developers.openai.com/api/docs/guides/chatgpt-api-credits"),
            ChecklistLink("Abrir plataforma API", "https://platform.openai.com/"),
        )),
        ChecklistItem("credencial_privada", "Configurar la credencial en privado", "Crear una clave exclusiva de SparkX e introducirla mediante la configuración privada del servidor. Nunca pegarla en el chat, Git ni este módulo.", steps=(
            "En la cuenta del proveedor crea una credencial dedicada al proyecto, con los permisos mínimos que admita. Conserva el secreto en un gestor privado; este checklist no tiene un campo para introducirlo.",
            "Configura la variable privada requerida por el perfil elegido en los procesos web y worker. Pide acompañamiento para hacerlo por un canal seguro si lo necesitas; no edites el ejemplo público con una clave real.",
            "Abre Gestión de IA y comprueba el indicador local de configuración. Que la variable exista no acredita conexión, saldo ni inferencia real; esas comprobaciones pertenecen al recorrido real.",
        ), confirmations=(
            ChecklistConfirmation("credencial_privada_dedicada", "Preparé una credencial dedicada sin compartir su valor en el chat ni en este módulo."),
            ChecklistConfirmation("credencial_privada_procesos", "Configuré el acceso privado para web y worker, sin incluirlo en archivos versionados."),
            ChecklistConfirmation("credencial_privada_indicador", "Revisé el indicador local y entiendo que no prueba conexión ni saldo."),
        )),
        ChecklistItem("presupuesto_ia", "Definir el presupuesto del prototipo", "Decidir qué parte del saldo disponible se destinará a SparkX. El gasto adicional se mantiene en cero hasta autorización expresa. Marcar este punto no cambia ni autoriza el presupuesto de Gestión de IA.", steps=(
            "Con el saldo y la vigencia comprobados, decide un presupuesto bruto acotado para el piloto y un límite de tokens. Los créditos de un proveedor no se transfieren a otro y un nivel gratuito tiene sus propias condiciones.",
            "Revisa en Gestión de IA → Presupuesto el perfil seleccionado y los límites. Si no hay un presupuesto concreto acordado o saldo confirmado, mantén la generación de pago deshabilitada.",
            "Contrasta la configuración con las recargas y los fondos de la cuenta externa. El límite de SparkX solo controla sus solicitudes; no controla otros programas que utilicen la misma organización.",
        ), confirmations=(
            ChecklistConfirmation("presupuesto_ia_cifra", "Definí un límite concreto de dinero y tokens compatible con el saldo comprobado."),
            ChecklistConfirmation("presupuesto_ia_sin_extras", "No autoricé recargas, compras ni gastos adicionales al completar este punto."),
            ChecklistConfirmation("presupuesto_ia_limites", "Revisé por separado los límites de SparkX y de la cuenta del proveedor."),
        )),
        ChecklistItem("prueba_recorrido", "Probar el recorrido con IA real", "Crear una propuesta, revisarla, aprobarla y consultar su consumo con un proveedor operativo. Las respuestas controladas de pruebas no acreditan inferencia real.", steps=(
            "Realiza la prueba solo cuando credencial, cuota y presupuesto estén preparados. Usa un evento de demostración y confirma que web y worker están funcionando con el perfil seleccionado.",
            "Describe el evento y solicita una propuesta. Comprueba que llega una respuesta real; revisa agenda, restricciones y tareas antes de aprobar expresamente el plan.",
            "Pide una adaptación concreta y revisa sus diferencias antes de aprobarla. Confirma manualmente un cambio de estado de tarea y comprueba el porcentaje; el chat no debe modificar esos estados por sí solo.",
            "Recarga la página y comprueba que el plan y el avance se conservan. Revisa el trabajo y el consumo en Gestión de IA; si falta consumo o hay un error, deja constancia del pendiente sin presentarlo como éxito.",
        ), confirmations=(
            ChecklistConfirmation("prueba_recorrido_inferencia", "Observé una propuesta generada por el proveedor real, con su trabajo registrado."),
            ChecklistConfirmation("prueba_recorrido_aprobaciones", "Revisé y aprobé expresamente el plan y una adaptación; confirmé yo el estado de la tarea."),
            ChecklistConfirmation("prueba_recorrido_persistencia", "Comprobé que la versión aprobada y el avance sobreviven a una recarga."),
            ChecklistConfirmation("prueba_recorrido_consumo", "Revisé el consumo registrado y distinguí cualquier dato desconocido o pendiente."),
        )),
    )),
    ChecklistGroup("demo", "Validar la demostración", "Revisar los supuestos y el recorrido como usuario.", (
        ChecklistItem("supuestos_gica", "Revisar los supuestos de la demo GICA", "Comprobar el año 2026, zona America/Lima, duración inicial de 90 minutos y 100 cupos. Estos valores son supuestos de demostración, no datos confirmados por el afiche.", steps=(
            "Abre el evento de demostración GICA y contrasta título, ponente y fecha/hora anunciados con el afiche recibido. No completes datos desconocidos como si fueran confirmados.",
            "Revisa por separado los supuestos: año 2026, zona America/Lima, 90 minutos y 100 cupos. Confírmalos para el ensayo o solicita una corrección de la ficha sin reiniciar el evento ni borrar avances.",
            "Comprueba que el relato de la demo identifica los datos sintéticos, los supuestos y los planes preparados manualmente. La demo no representa una contratación ni una convocatoria real de GICA.",
        ), confirmations=(
            ChecklistConfirmation("supuestos_gica_afiche", "Contrasté con el afiche los datos que realmente aparecen en él."),
            ChecklistConfirmation("supuestos_gica_separados", "Revisé los cuatro supuestos y los distingo de los datos confirmados."),
            ChecklistConfirmation("supuestos_gica_demo", "Presentaré el caso como demostración, sin atribuir resultados o compromisos reales a GICA."),
        )),
        ChecklistItem("revision_usuario", "Validar claridad y navegación", "Revisar agenda, tareas y respuestas del agente; señalar los problemas que dificulten comprender o completar el recorrido.", steps=(
            "Recorre ficha → propuesta → revisión → aprobación → adaptación → seguimiento de tareas con tu cuenta. Comprueba que cada acción y su resultado se entienden sin instrucciones del desarrollador.",
            "Revisa agenda y preparación con sus barras de desplazamiento, tamaños de texto y temas claro/oscuro. Prueba también la vista estrecha si la usarás en la demostración.",
            "Anota únicamente el problema observado, la pantalla y cómo repetirlo, sin datos sensibles. Comprueba que el agente distingue lo pendiente, lo propuesto y lo aprobado, y no presenta una tarea como ejecutada por haberla redactado.",
        ), confirmations=(
            ChecklistConfirmation("revision_usuario_recorrido", "Recorrí personalmente las acciones principales y entiendo sus resultados."),
            ChecklistConfirmation("revision_usuario_lectura", "Comprobé lectura, desplazamiento y los temas claro/oscuro en las pantallas que utilizaré."),
            ChecklistConfirmation("revision_usuario_estados", "Revisé que propuestas, aprobaciones y ejecución de tareas no se confundan."),
        )),
        ChecklistItem("demo_voz", "Comprobar voz por turnos", "Probar físicamente micrófono, texto revisable y lectura opcional. La disponibilidad depende del navegador, sus permisos y las voces instaladas.", "Sólo si se decide usar dictado por voz en la demostración.", steps=(
            "Abre SparkX en el navegador que usarás para el ensayo, revisa el aviso de micrófono y concede el permiso solo si aceptas el tratamiento indicado. El reconocimiento puede utilizar un servicio remoto del navegador.",
            "Pulsa Dictar, habla una petición breve y comprueba que puedes corregir la transcripción antes de enviarla. Verifica la alternativa escrita si no hay soporte, se deniega el permiso o se entiende mal una palabra.",
            "Envía el texto únicamente con el perfil y presupuesto preparados para IA real. Revisa la respuesta escrita y prueba Leer y Detener si existe una voz compatible; una voz local evita ese servicio remoto de síntesis, pero no el coste de generar la respuesta.",
            "Comprueba que el micrófono y la lectura se detienen al terminar. Este ensayo es por turnos: no acredita conversación continua ni sesiones de voz ilimitadas.",
        ), confirmations=(
            ChecklistConfirmation("demo_voz_microfono", "Probé físicamente el micrófono y revisé el aviso y los permisos."),
            ChecklistConfirmation("demo_voz_revision", "Pude corregir el texto antes de enviarlo y tengo una alternativa escrita."),
            ChecklistConfirmation("demo_voz_lectura", "Comprobé respuesta escrita y lectura/detención, o identifiqué la falta de voz compatible."),
        )),
    )),
    ChecklistGroup("despliegue", "Preparar un eventual acceso público", "Estos puntos se pueden declarar No aplica si la demostración correspondiente permanece local.", (
        ChecklistItem("servicios_vps", "Identificar servicios existentes en OVH", "Indicar qué servicios funcionan actualmente en el VPS y cuáles deben preservarse antes de preparar un despliegue.", "Antes de usar el VPS para publicar SparkX.", steps=(
            "Si el ensayo permanecerá local, usa No aplica y explica esa decisión sin secretos. Si se considera OVH, confirma primero que ese despliegue forma parte de la entrega acordada.",
            "Revisa el inventario de servicios, puertos, dominios, datos y copias de seguridad existentes. Identifica qué debe preservarse; no detengas ni sustituyas servicios para completar este punto.",
            "Comprueba recursos disponibles y quién administra el VPS. La captura de 4 vCPU y 8 GB describe el plan contratado, no capacidad libre ni una prueba de concurrencia de SparkX.",
        ), confirmations=(
            ChecklistConfirmation("servicios_vps_modalidad", "Confirmé que el uso del VPS se acordó; si la demo es local, corresponde No aplica."),
            ChecklistConfirmation("servicios_vps_inventario", "Identifiqué servicios y datos que deben preservarse, sin interrumpirlos."),
            ChecklistConfirmation("servicios_vps_recursos", "Revisé disponibilidad y responsable del VPS, sin asumir capacidad por la ficha contratada."),
        )),
        ChecklistItem("acceso_ssh", "Preparar acceso SSH seguro y dominio", "Preparar el acceso autorizado y el dominio o subdominio disponible mediante un canal privado. No compartir contraseñas, claves SSH ni códigos de acceso aquí.", "Si se acuerda un despliegue público en OVH.", steps=(
            "Confirma la modalidad pública y el responsable del servidor. Si no habrá despliegue, usa No aplica; completar este checklist no autoriza publicar ni modificar DNS.",
            "Prepara por un mecanismo privado un acceso SSH dedicado y con permisos acotados. Conserva las claves fuera del chat y del repositorio; la identificación del destino debe verificarse antes de conectarse.",
            "Confirma el dominio o subdominio que ya tienes y quién controla DNS. Prepara un ensayo con HTTPS y plan de reversión antes de exponer datos; no contrates un dominio nuevo ni cambies DNS desde este punto.",
        ), confirmations=(
            ChecklistConfirmation("acceso_ssh_autorizado", "Confirmé el servidor y responsable autorizados para el despliegue acordado."),
            ChecklistConfirmation("acceso_ssh_privado", "Preparé el acceso mediante un canal privado, sin revelar claves ni contraseñas."),
            ChecklistConfirmation("acceso_ssh_destino", "Identifiqué dominio y control de DNS; publicar sigue siendo una acción separada."),
        )),
        ChecklistItem("password_publico", "Cambiar la contraseña inicial del administrador", "Elegir una contraseña robusta mediante el mecanismo privado de la aplicación antes de exponerla a internet. Este checklist nunca almacena contraseñas.", "Antes de habilitar acceso público a SparkX.", steps=(
            "Antes de exponer la aplicación, prepara en un gestor privado una contraseña larga y exclusiva para adminjorge. No reutilices la contraseña inicial ni la pegues aquí.",
            "Realiza el cambio mediante un mecanismo privado autorizado de Django. Si necesitas asistencia, solicita el procedimiento sin enviar el valor de la contraseña.",
            "Comprueba un inicio de sesión nuevo y revisa las sesiones que deban cerrarse. Registra solo que hiciste la comprobación; no almacenes secretos ni capturas del formulario rellenado.",
        ), confirmations=(
            ChecklistConfirmation("password_publico_exclusiva", "Sustituí la contraseña inicial por una larga y exclusiva, guardada en privado."),
            ChecklistConfirmation("password_publico_sesion", "Probé un nuevo inicio de sesión y revisé las sesiones anteriores."),
        )),
        ChecklistItem("datos_participantes", "Acordar el tratamiento de datos reales", "Definir qué datos se recogerán y revisar los textos informativos antes de invitar personas reales. Las pruebas locales pueden usar datos ficticios.", "Si participarán personas reales o se recogerán sus datos.", steps=(
            "Decide si la demostración usará solo datos sintéticos. Si se invita a personas reales, identifica los datos estrictamente necesarios, su finalidad y quién tendrá acceso.",
            "Revisa los textos informativos, el plazo de conservación y el procedimiento de eliminación. Define qué información podrá enviarse a cada proveedor IA; no introduzcas datos sensibles en servicios gratuitos sin revisar sus condiciones.",
            "Acuerda consentimiento y tratamiento del audio si se habilita micrófono. No guardes grabaciones, documentos personales ni listas de participantes como evidencia dentro de este checklist.",
        ), confirmations=(
            ChecklistConfirmation("datos_participantes_minimos", "Definí finalidad, datos mínimos y responsables del acceso."),
            ChecklistConfirmation("datos_participantes_retencion", "Revisé información al usuario, conservación y eliminación antes de recoger datos."),
            ChecklistConfirmation("datos_participantes_proveedores", "Revisé qué datos y audio podrían recibir proveedores externos y las condiciones aplicables."),
        )),
    )),
    ChecklistGroup("concurso", "Cerrar la entrega del concurso", "Validación del equipo antes de presentar los entregables.", (
        ChecklistItem("equipo_contribuciones", "Revisar equipo y contribuciones", "Confirmar los datos y las contribuciones reales de Jorge y Robert, junto con los datos de universidad y equipo ya recogidos en la propuesta.", steps=(
            "Contrasta los nombres, universidad y denominación del equipo con la propuesta aprobada. No vuelvas a inscribir al equipo: su inscripción y aprobación ya fueron confirmadas.",
            "Acuerda con Robert las contribuciones efectivamente realizadas y quién explicará cada parte. Distingue trabajo hecho, asistencia de IA y tareas pendientes, sin atribuir desarrollos no realizados.",
            "Revisa los datos de contacto exigidos para la entrega y conserva su versión completa en el paquete privado correspondiente. Este checklist solo registra tu confirmación; no necesita documentos de identidad ni datos sensibles.",
        ), confirmations=(
            ChecklistConfirmation("equipo_contribuciones_datos", "Revisé los datos del equipo contra la propuesta aprobada."),
            ChecklistConfirmation("equipo_contribuciones_reales", "Acordamos las contribuciones reales y quién defenderá cada parte."),
            ChecklistConfirmation("equipo_contribuciones_contacto", "Preparé los datos requeridos para la entrega sin copiarlos innecesariamente aquí."),
        )),
        ChecklistItem("horarios_concurso", "Confirmar horarios y formato", "Sigue vigente la entrega del 15 de noviembre de 2026. Falta verificar su hora y zona, además del idioma, duración y turno de presentación del 25 o 26 de noviembre.", steps=(
            "Revisa el comunicado más reciente del organizador y confirma la hora exacta y zona horaria del cierre del 15 de noviembre. No asumas que coincide con el final del día en Lima.",
            "Confirma idioma, duración permitida, modalidad, turno del 25 o 26 de noviembre y requisitos del vídeo o archivos. Si un dato sigue pendiente, conserva ese pendiente y evita marcarlo como confirmado.",
            "Calcula el margen de entrega en America/Lima y acuerda una hora interna anterior al cierre. Reserva un ensayo y quién operará la demostración y el respaldo.",
        ), confirmations=(
            ChecklistConfirmation("horarios_concurso_cierre", "Confirmé con una fuente del evento la hora y zona exactas del cierre."),
            ChecklistConfirmation("horarios_concurso_formato", "Confirmé idioma, duración, modalidad y turno de presentación."),
            ChecklistConfirmation("horarios_concurso_margen", "Acordé un plazo interno y un ensayo con margen respecto al cierre."),
        )),
        ChecklistItem("repositorio_licencia", "Elegir repositorio y revisar licencia", "Determinar la cuenta de GitHub, repositorio, visibilidad y licencia de acuerdo con las condiciones aplicables. No publicar secretos ni credenciales.", steps=(
            "Decide la cuenta responsable, nombre del repositorio y visibilidad según las bases y la forma de revisión del jurado. Un repositorio privado necesita un modo de acceso acordado; el checklist no lo crea ni publica.",
            "Revisa qué se versionará antes de preparar el historial: código y documentación vigentes, excluyendo credenciales, bases de datos activas, datos personales, entorno virtual y Temporal. Comprueba el README y el arranque desde una copia limpia.",
            "Revisa licencias y atribuciones de dependencias, fuentes, imágenes y material de terceros. Elige una licencia compatible con los derechos del equipo y las bases; no atribuyas al equipo derechos que no posee.",
            "Cuando se autorice publicar o compartir, comprueba el enlace y el acceso del destinatario sin exponer material privado. Marcar completado aquí no ejecuta esa publicación.",
        ), confirmations=(
            ChecklistConfirmation("repositorio_licencia_destino", "Elegí responsable, visibilidad y una forma de acceso adecuada para la evaluación."),
            ChecklistConfirmation("repositorio_licencia_archivos", "Revisé archivos versionables e ignorados, sin secretos, datos activos ni material temporal."),
            ChecklistConfirmation("repositorio_licencia_derechos", "Revisé licencia, atribuciones y derechos de los materiales incluidos."),
        ), links=(
            ChecklistLink("Guía de GitHub sobre licencias", "https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository"),
        )),
        ChecklistItem("entrega_ensayo", "Revisar, ensayar y realizar la entrega", "Revisar el paquete y ejecutar o autorizar expresamente el envío final. Esta declaración manual no publica ni envía archivos, ni acredita recepción por el organizador.", steps=(
            "Revisa informe, PPT, código o enlace de acceso, manual, datos del equipo y vídeo de demostración si procede. Comprueba que todos describen la misma versión y separan resultados medidos, datos sintéticos y limitaciones.",
            "Ensaya el recorrido completo con la duración e idioma confirmados. Comprueba recuperación de la sesión, aprobación humana, cambios de tareas y respuesta ante fallos; prepara vídeo o capturas de respaldo sin secretos.",
            "Abre los archivos y enlaces finales como lo haría el jurado; comprueba legibilidad, permisos de acceso y ausencia de claves, datos personales innecesarios y archivos temporales.",
            "Realiza personalmente el envío por el canal oficial o da una instrucción expresa para ese envío concreto. Comprueba y conserva el acuse de recepción; preparar el paquete o marcar esta tarjeta no equivale a entregarlo.",
        ), confirmations=(
            ChecklistConfirmation("entrega_ensayo_paquete", "Revisé informe, PPT, código, manual, datos del equipo y vídeo si procede como un paquete coherente."),
            ChecklistConfirmation("entrega_ensayo_demostracion", "Ensayé la demostración y dispongo de un respaldo revisado."),
            ChecklistConfirmation("entrega_ensayo_acceso", "Comprobé los archivos y enlaces finales, sus permisos y la ausencia de secretos."),
            ChecklistConfirmation("entrega_ensayo_recepcion", "Realicé el envío oficial y comprobé su recepción; marcar aquí no lo envía."),
        )),
    )),
)
ITEMS = MappingProxyType({item.key: item for group in GROUPS for item in group.items})
OPTIONAL_KEYS = tuple(item.key for item in ITEMS.values() if item.optional)
