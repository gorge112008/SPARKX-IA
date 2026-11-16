# Preparación de despliegue

Este documento describe la configuración prevista; no acredita un despliegue ejecutado.

1. Verificar recursos libres y servicios compartidos del OVH, acceso, copias y puertos.
   El panel aportado declara 4 vCPU, 8 GB RAM, 75 GB y Debian 13 en Canadá.
2. Usar PostgreSQL con un usuario acotado y copias restaurables; definir DATABASE_URL.
   La URL admite sslmode explícito; opciones desconocidas se rechazan.
3. Establecer DJANGO_DEBUG=0, DJANGO_SECRET_KEY aleatoria, hosts exactos y
   DJANGO_CSRF_TRUSTED_ORIGINS con el origen HTTPS.
4. Ejecutar un servidor WSGI/ASGI de producción y el worker como procesos separados,
   desde el mismo código y configuración. runserver es solo para localhost.
5. Terminar HTTPS en un proxy que sanee X-Forwarded-Proto; solo entonces activar
   DJANGO_TRUST_PROXY=1 y restringir el acceso directo al servidor web interno.
   Sin ese ajuste, configurar TLS directamente en el servidor. No confiar en el header
   de un cliente público.
6. Ejecutar migrate, collectstatic y check --deploy con configuración real.
   El modo de producción exige PostgreSQL salvo una excepción explícita de prueba.
7. Validar concurrencia PostgreSQL, permisos, CSRF, cancelación, límites de proveedor,
   arranque limpio y restauración. Medir 20 usuarios web antes de afirmar capacidad.
8. Revisar costes y cuota API. Solo después comprobar inferencia real con datos
   de demostración identificados. No iniciar compras, recargas ni procesos de pago solos.

Pendiente: empaquetado de contenedores/servicio, ensayo sobre VPS, HTTPS real, recuperación,
observabilidad y mediciones. Los objetivos de 50–100 usuarios no son resultados.
La arquitectura mantiene un monolito modular hasta que mediciones justifiquen separar
servicios. El worker de base de datos evita introducir Redis/Celery en el primer incremento.
