"""A single-process, loopback-only development entry point with graceful stop."""
import errno
import socket
import threading

from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.management.base import BaseCommand, CommandError
from django.core.servers.basehttp import (
    ServerHandler, ThreadedWSGIServer, WSGIRequestHandler, get_internal_wsgi_application,
)
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from config import local_runtime


class LocalServerHandler(ServerHandler):
    http_version = "1.0"


class LocalRequestHandler(WSGIRequestHandler):
    # Close each connection after its response. Idle keep-alive sockets must
    # not prevent server_close() from joining the active request threads.
    protocol_version = "HTTP/1.0"

    def handle_one_request(self):
        # Use Django's parsing, WSGI lifecycle and connection cleanup, with a
        # local HTTP/1.0 responder (Django otherwise hardcodes HTTP/1.1 here).
        try:
            self.raw_requestline = self.rfile.readline(65537)
        except TimeoutError:
            # Browser preconnections may send no request before our read timeout.
            # Close only this idle connection; it is not an application failure.
            self.close_connection = True
            return
        if len(self.raw_requestline) > 65536:
            self.requestline = self.request_version = self.command = ""
            self.send_error(414)
            return
        if not self.parse_request():
            return
        handler = LocalServerHandler(
            self.rfile, self.wfile, self.get_stderr(), self.get_environ(),
        )
        handler.request_handler = self
        handler.run(self.server.get_app())


class LocalServer(ThreadedWSGIServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, *args, **kwargs):
        self._request_condition = threading.Condition()
        self._pending_requests = 0
        self._active_request_threads = set()
        super().__init__(*args, allow_reuse_address=not hasattr(socket, "SO_EXCLUSIVEADDRUSE"), **kwargs)

    def process_request(self, request, client_address):
        # Count before starting the thread so shutdown cannot miss a request
        # that was accepted but has not yet entered its handler.
        with self._request_condition:
            self._pending_requests += 1
        try:
            super().process_request(request, client_address)
        except BaseException:
            with self._request_condition:
                self._pending_requests -= 1
                self._request_condition.notify_all()
            raise

    def process_request_thread(self, request, client_address):
        thread_id = threading.get_ident()
        with self._request_condition:
            self._pending_requests -= 1
            self._active_request_threads.add(thread_id)
            self._request_condition.notify_all()
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._request_condition:
                self._active_request_threads.discard(thread_id)
                self._request_condition.notify_all()

    def drain_shutdown_requests(self, runtime):
        # The acknowledgement streams wait for this drain. They must be the
        # only excluded threads; server_close joins them after emitting receipt.
        with self._request_condition:
            while (self._pending_requests or
                   self._active_request_threads - runtime.shutdown_stream_ids()):
                self._request_condition.wait(.1)

    def server_bind(self):
        # Windows SO_REUSEADDR permits two listeners on one port. Reserve it
        # exclusively so a second launch fails without disturbing the first.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address


class Command(BaseCommand):
    help = "Inicia ArquiGica sólo en este PC, con apagado web para el superusuario local."
    runtime_description = "Servidor local de desarrollo, sin recarga automática. No inicia workers ni llamadas de IA."

    def on_server_started(self):
        pass

    def on_server_stopping(self):
        pass

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=8000, help="Puerto local (predeterminado: 8000).")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("runlocal sólo funciona en desarrollo local (DEBUG). Usa el servidor de despliegue en producción.")
        port = options["port"]
        if not 1 <= port <= 65535:
            raise CommandError("El puerto debe estar entre 1 y 65535.")
        if local_runtime.get_runtime() is not None:
            raise CommandError("Este proceso ya tiene un servidor local activo.")
        executor = MigrationExecutor(connections["default"])
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError("Hay migraciones pendientes. Ejecuta primero: .venv\\Scripts\\python.exe manage.py migrate")
        connections.close_all()
        try:
            server = LocalServer(("127.0.0.1", port), LocalRequestHandler)
        except OSError as exc:
            if exc.errno in {errno.EADDRINUSE, 10048}:
                raise CommandError(
                    f"El puerto {port} ya está en uso. La instancia abierta puede ejecutar una versión anterior. "
                    "Si pertenece a ArquiGica, guarda tus cambios, detenla desde su terminal o con Apagar ArquiGica "
                    "y vuelve a iniciar para cargar el código actualizado. También puedes elegir otro puerto "
                    "con --port y usar la dirección que indique ese nuevo arranque. No se detuvo ningún proceso."
                ) from exc
            raise CommandError(f"No se pudo abrir el servidor local (error {exc.errno}).") from exc
        runtime = local_runtime.LocalRuntime(server.server_port)
        try:
            server.set_app(StaticFilesHandler(get_internal_wsgi_application()))
            server.timeout = 0.25
            local_runtime._runtime = runtime
            self.stdout.write(self.style.SUCCESS(f"ArquiGica disponible en http://127.0.0.1:{server.server_port}/"))
            self.stdout.write("Mantén esta ventana abierta. Para detener: Ctrl+C o Apagar ArquiGica desde tu cuenta técnica administradora.")
            self.stdout.write(self.runtime_description)
            self.on_server_started()
            while not runtime.stop_requested.is_set():
                server.handle_request()
        except KeyboardInterrupt:
            runtime.request_shutdown()
        finally:
            try:
                self.on_server_stopping()
                server.drain_shutdown_requests(runtime)
                # Close the listener before the signed-in browser receives the
                # completion receipt. Accepted sockets finish independently.
                server.socket.close()
                runtime.shutdown_succeeded = True
            finally:
                local_runtime._runtime = None
                runtime.shutdown_complete.set()
                try:
                    server.server_close()
                finally:
                    connections.close_all()
        self.stdout.write(self.style.SUCCESS("ArquiGica detenido. Los datos guardados se conservan."))
