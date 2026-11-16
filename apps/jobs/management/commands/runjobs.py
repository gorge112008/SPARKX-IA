"""Process durable jobs. SQLite is supported only for a single local worker."""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection

from apps.jobs.services import run_one


class Command(BaseCommand):
    help = "Procesa trabajos de IA persistidos; usa PostgreSQL para trabajadores concurrentes."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Procesa como máximo un trabajo y termina.")
        parser.add_argument("--poll-interval", type=float, default=2.0, help="Segundos entre consultas cuando no hay trabajos.")

    def handle(self, *args, **options):
        interval = options["poll_interval"]
        if not 0.1 <= interval <= 60:
            raise CommandError("El intervalo debe estar entre 0.1 y 60 segundos.")
        if connection.vendor == "sqlite":
            self.stderr.write(self.style.WARNING(
                "SQLite: ejecuta un solo worker local. Este modo no valida concurrencia ni bloqueos de PostgreSQL."
            ))
        try:
            while True:
                if not connection.in_atomic_block:
                    close_old_connections()
                job = run_one()
                if job is not None:
                    self.stdout.write(f"{job.pk} {job.status}")
                if options["once"]:
                    break
                if job is None:
                    time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Worker detenido. Los leases vencidos se revisarán en el próximo arranque.")
