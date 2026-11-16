"""One ArquiGica entry point; private connections are managed inside the platform."""
import os
from pathlib import Path
import socket
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            print("ArquiGica ya esta abierto. Usa Apagar ArquiGica y vuelve a ejecutar este lanzador.")
            return 1
    except OSError:
        pass
    try:
        print("Iniciando ArquiGica con Gica-1. Administra las claves desde Gestion de IA > APIs y agentes.")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        from django.core.management import execute_from_command_line
        execute_from_command_line(["manage.py", "runromeo"])
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nArquiGica detenido.")
        return 0
    finally:
        os.environ.pop("OPENAI_API_KEY", None)


if __name__ == "__main__":
    raise SystemExit(main())
