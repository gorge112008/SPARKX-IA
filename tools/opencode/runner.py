"""Prepare small tasks for a credential-free, restricted OpenCode process.

No command imports generated files into SparkX or executes their contents.
Inputs must be explicitly selected, non-secret text. Permissions are harness
controls, not an OS sandbox or a guarantee about a remote model's privacy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import uuid

from .catalog import ALLOWED_MODELS, DEFAULT_MODEL, MODEL_POLICIES, CatalogVerificationError, verify_free_model
from .comparison import build_comparison, render_markdown
from .configuration import ISOLATION_FLAGS, build_config
from .install import EXECUTABLE_PATH, PROJECT_ROOT, VERSION, installation_is_verified

TASK_ROOT = PROJECT_ROOT / "Temporal" / "opencode" / "tasks"
MAX_INPUT_BYTES = 24000
MAX_FILES = 5
MAX_PROMPT_CHARS = 3000
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_SECONDS = 180
SAFE_ROOTS = {"apps", "templates", "static", "docs"}
SAFE_SUFFIXES = {".py", ".html", ".css", ".js", ".md", ".json", ".txt"}
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{25,})")


class TaskError(RuntimeError):
    pass


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise TaskError("La ruta sale de la carpeta autorizada.")
    return resolved


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def child_environment(task_dir: Path) -> dict[str, str]:
    """Build from a small OS allowlist, rather than copying secrets then filtering."""
    runtime = _inside(task_dir / ".runtime", task_dir)
    directories = {name: runtime / folder for name, folder in (
        ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state"),
        ("USERPROFILE", "profile"), ("APPDATA", "appdata"),
        ("LOCALAPPDATA", "localappdata"), ("TEMP", "tmp"), ("TMP", "tmp"),
    )}
    env = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT") if name in os.environ}
    system = Path(env.get("SystemRoot", r"C:\Windows")) / "System32"
    env["PATH"] = str(system)
    for name, directory in directories.items():
        directory.mkdir(parents=True, exist_ok=True)
        env[name] = str(directory)
    env.update(ISOLATION_FLAGS)
    env["OPENCODE_TEST_HOME"] = env["USERPROFILE"]
    env.update({"NO_COLOR": "1", "DO_NOT_TRACK": "1", "GIT_TERMINAL_PROMPT": "0", "CI": "1"})
    return env


def run_bounded(arguments: list[str], *, cwd: Path, env: dict, seconds=MAX_SECONDS, stop_on_model_error=False) -> dict:
    """Bound stdout/stderr and time; only terminate the private child we created."""
    chunks = queue.Queue(maxsize=128)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    started = time.monotonic()
    process = subprocess.Popen(arguments, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

    def drain(name, stream):
        try:
            for value in iter(lambda: stream.read1(4096), b""):
                chunks.put((name, value))
        finally:
            chunks.put((name, None))
            stream.close()

    for name in output:
        threading.Thread(target=drain, args=(name, getattr(process, name)), daemon=True).start()
    finished = set()
    failure = None
    live_lines = bytearray()
    try:
        while len(finished) < 2:
            if time.monotonic() - started > seconds:
                failure = "La tarea superó el tiempo máximo y se detuvo."
                break
            try:
                name, value = chunks.get(timeout=.2)
            except queue.Empty:
                continue
            if value is None:
                finished.add(name)
            else:
                output[name].extend(value)
                if sum(len(v) for v in output.values()) > MAX_OUTPUT_BYTES:
                    failure = "La salida superó el tamaño máximo y se detuvo."
                    break
                if name == "stdout" and stop_on_model_error:
                    live_lines.extend(value)
                    while b"\n" in live_lines:
                        line, _, rest = live_lines.partition(b"\n")
                        live_lines = bytearray(rest)
                        try:
                            event = json.loads(line)
                        except (ValueError, UnicodeError):
                            continue
                        if isinstance(event, dict) and (event.get("type") in ("retry", "error") or (
                            event.get("type") == "step_finish" and isinstance(event.get("part"), dict)
                            and event["part"].get("reason") == "length"
                        )):
                            failure = "OpenCode informó un error, reintento o límite de salida. Se detuvo la tarea; no se eligió otro modelo."
                            break
                    if failure:
                        break
        if failure:
            if os.name == "nt" and process.poll() is None:
                taskkill = Path(env.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
                subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
            if process.poll() is None:
                process.kill()
            problem = TaskError(failure)
            problem.partial_output = {
                "exit_code": process.wait(timeout=10),
                "seconds": round(time.monotonic() - started, 3),
                **{name: value.decode("utf-8", errors="replace") for name, value in output.items()},
            }
            raise problem
        code = process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    return {"exit_code": code, "seconds": round(time.monotonic() - started, 3),
            **{name: value.decode("utf-8", errors="replace") for name, value in output.items()}}


def selected_text(relative: str) -> tuple[str, bytes]:
    candidate = Path(relative)
    if not candidate.parts or candidate.is_absolute() or ".." in candidate.parts:
        raise TaskError("Selecciona una ruta relativa dentro de SparkX.")
    if candidate.parts[0] not in SAFE_ROOTS and candidate.as_posix() != "README.md":
        raise TaskError("Solo se admiten archivos de código o documentación revisados.")
    if candidate.suffix.lower() not in SAFE_SUFFIXES or any(
        part.startswith(".") or part.lower() in {"var", "temporal", "node_modules", "__pycache__"}
        for part in candidate.parts
    ):
        raise TaskError("El archivo seleccionado no pertenece al contexto permitido.")
    source = _inside(PROJECT_ROOT / candidate, PROJECT_ROOT)
    if any((PROJECT_ROOT / Path(*candidate.parts[:i])).is_symlink() for i in range(1, len(candidate.parts) + 1)):
        raise TaskError("No se admiten enlaces en los archivos seleccionados.")
    with source.open("rb") as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise TaskError("El archivo supera el máximo de contexto permitido.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TaskError("El contexto debe ser texto UTF-8.") from error
    if "\0" in text or SECRET.search(text):
        raise TaskError("El contexto parece contener material sensible o no es texto.")
    return candidate.as_posix(), data


def model_policy_permission(model, *, synthetic_demo=False, accept_model_policy=False) -> None:
    if type(synthetic_demo) is not bool or type(accept_model_policy) is not bool:
        raise TaskError("Las declaraciones de datos y política deben ser explícitas.")
    policy = MODEL_POLICIES[model]
    if policy["synthetic_only"] and not synthetic_demo:
        raise TaskError("Este modelo solo se admite con datos ficticios declarados (--synthetic).")
    if policy["requires_policy_consent"] and not accept_model_policy:
        raise TaskError("Revisa y acepta las condiciones de este modelo (--accept-model-policy).")


def prepare_task(prompt: str, *, mode="review", model=DEFAULT_MODEL, files=(), demo=False,
                 synthetic=False, accept_model_policy=False) -> Path:
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS or SECRET.search(prompt):
        raise TaskError("Describe una tarea breve, sin claves ni información sensible.")
    if model not in ALLOWED_MODELS or mode not in ("review", "draft"):
        raise TaskError("Modelo o modo no admitido.")
    if type(demo) is not bool or type(synthetic) is not bool:
        raise TaskError("La declaración de datos ficticios no es válida.")
    # Adding the built-in example does not make separately selected files
    # synthetic. Those need the user's separate declaration.
    declared_synthetic = synthetic or (demo and not files)
    model_policy_permission(model, synthetic_demo=declared_synthetic, accept_model_policy=accept_model_policy)
    if len(files) > MAX_FILES:
        raise TaskError("Selecciona como máximo cinco archivos.")
    inputs = [selected_text(item) for item in files]
    if demo:
        inputs.append(("ejemplo.py", b'def porcentaje(completadas, total):\n    return round(completadas / total * 100)\n'))
    if len(inputs) > MAX_FILES:
        raise TaskError("El ejemplo y los archivos seleccionados superan cinco archivos.")
    if sum(len(data) for _, data in inputs) > MAX_INPUT_BYTES:
        raise TaskError("Los archivos combinados superan 24.000 bytes.")
    task_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
    directory = _inside(TASK_ROOT / task_id, PROJECT_ROOT)
    (directory / "inputs").mkdir(parents=True)
    (directory / "outputs").mkdir()
    manifest = []
    for index, (relative, data) in enumerate(inputs, 1):
        target = f"inputs/{index:02d}-{Path(relative).name}.txt"
        (directory / target).write_bytes(data)
        manifest.append({"source": relative, "copy": target, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    configuration = build_config("opencode/" + model, mode)
    env = child_environment(directory)
    config_path = Path(env["XDG_CONFIG_HOME"]) / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(config_path, configuration)
    _write_json(directory / "task.json", {"id": task_id, "mode": mode, "model": model, "prompt": prompt.strip(),
                "inputs": manifest, "status": "prepared", "synthetic_demo": declared_synthetic,
                "accept_model_policy": accept_model_policy,
                "model_policy": dict(MODEL_POLICIES[model]),
                "created_at": datetime.now(timezone.utc).isoformat()})
    return directory


def task_directory(task_id: str) -> Path:
    if not re.fullmatch(r"\d{8}T\d{6}-[0-9a-f]{10}", task_id):
        raise TaskError("El identificador de tarea no es válido.")
    return _inside(TASK_ROOT / task_id, TASK_ROOT)


def write_comparison(task_id: str) -> dict:
    """Reprice an existing receipt locally. Never restart its model task."""
    directory = task_directory(task_id)
    source = _inside(directory / "result.json", directory)
    with source.open("rb") as stream:
        raw = stream.read(MAX_OUTPUT_BYTES + 1)
    if len(raw) > MAX_OUTPUT_BYTES:
        raise TaskError("El resultado supera el tamaño permitido para comparar.")
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict) or result.get("task") != task_id:
        raise TaskError("El resultado no corresponde a esta tarea.")
    report = build_comparison(result)
    for filename in ("cost-comparison.json", "cost-comparison.md"):
        path = directory / filename
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise TaskError("La ruta de comparación no pertenece a la tarea.")
    _write_json(directory / "cost-comparison.json", report)
    (directory / "cost-comparison.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def verify_effective_configuration(entries, *, task_dir: Path, expected: dict) -> None:
    """Reject ignored, overridden or unexpectedly merged configuration sources."""
    if not isinstance(entries, list):
        raise TaskError("OpenCode no devolvió una configuración verificable.")
    if any(not isinstance(entry, dict) or entry.get("type") not in ("document", "directory") for entry in entries):
        raise TaskError("OpenCode devolvió una fuente de configuración desconocida.")
    documents = [entry for entry in entries if entry.get("type") == "document"]
    if len(documents) != 1:
        raise TaskError("Se detectaron fuentes de configuración ajenas a la tarea.")
    config_dir = task_dir / ".runtime" / "config" / "opencode"
    if any(not Path(entry.get("path", "")).resolve().is_relative_to(config_dir.resolve()) for entry in entries):
        raise TaskError("OpenCode cargó una configuración fuera de la tarea aislada.")
    actual = documents[0].get("info", {})
    if not isinstance(actual, dict) or set(actual) - set(expected):
        raise TaskError("OpenCode cargó opciones adicionales que no se autorizaron.")
    if actual.get("mcp") not in (None, {}, {"servers": {}}):
        raise TaskError("OpenCode cargó servidores MCP ajenos a esta tarea.")
    if actual.get("providers", {}) != expected.get("providers", {}):
        raise TaskError("OpenCode cambió la configuración del proveedor.")
    for key in ("default_agent", "permissions", "policies", "share", "update", "warming", "compaction",
                "formatter", "lsp", "snapshots", "plugins", "skills", "commands", "references",
                "instructions", "websearch", "watcher", "experimental"):
        if actual.get(key) != expected.get(key):
            raise TaskError("OpenCode ignoró o cambió una restricción de configuración: " + key)
    provider, model = expected["model"].split("/", 1)
    normalized_model = {"providerID": provider, "model": model}
    if actual.get("model") != normalized_model:
        raise TaskError("El modelo efectivo no coincide con el modelo autorizado.")
    if set(actual.get("agents", {})) != set(expected["agents"]):
        raise TaskError("OpenCode cargó agentes distintos de los preparados.")
    for name, configured in expected["agents"].items():
        agent = actual["agents"][name]
        for key in ("permissions", "steps", "disabled", "system", "mode"):
            if agent.get(key) != configured.get(key):
                raise TaskError("La configuración efectiva del agente cambió: " + name)
        if agent.get("model") != normalized_model:
            raise TaskError("Un agente auxiliar usa otro modelo.")


def preflight(task_dir: Path, task: dict, env: dict) -> dict:
    expected = build_config("opencode/" + task["model"], task["mode"])
    result = run_bounded([str(EXECUTABLE_PATH), "debug", "config", "--standalone"],
                         cwd=task_dir, env=env, seconds=35)
    if result["exit_code"] or result["stderr"].strip():
        raise TaskError("OpenCode no pudo comprobar su configuración local. No se llamó al modelo.")
    try:
        verify_effective_configuration(json.loads(result["stdout"]), task_dir=task_dir, expected=expected)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise TaskError("La configuración de OpenCode no es verificable. No se llamó al modelo.") from error
    return {"configuration_verified": True, "version": VERSION, "private_server": True,
            "model": task["model"], "seconds": result["seconds"]}


def run_task(task_id: str) -> dict:
    directory = task_directory(task_id)
    try:
        with (directory / ".execution-claim").open("x", encoding="ascii") as claim:
            claim.write(str(os.getpid()))
    except FileExistsError as error:
        raise TaskError("Esta tarea ya fue reclamada por una ejecución; prepara una nueva.") from error
    return _run_claimed_task(task_id)


def _run_claimed_task(task_id: str) -> dict:
    directory = task_directory(task_id)
    manifest_path = directory / "task.json"
    task = json.loads(manifest_path.read_text(encoding="utf-8"))
    if task.get("status") != "prepared" or task.get("id") != task_id:
        raise TaskError("Esta tarea ya se intentó o no está preparada; crea otra para repetirla.")
    if task.get("model") not in ALLOWED_MODELS or task.get("mode") not in ("review", "draft"):
        raise TaskError("La tarea tiene un modelo o modo ajeno a la lista permitida.")
    model_policy_permission(task["model"], synthetic_demo=task.get("synthetic_demo", False),
                            accept_model_policy=task.get("accept_model_policy", False))
    if (not isinstance(task.get("prompt"), str) or not task["prompt"].strip()
            or len(task["prompt"]) > MAX_PROMPT_CHARS or SECRET.search(task["prompt"])):
        raise TaskError("La descripción guardada no es válida o parece contener material sensible.")
    if not isinstance(task.get("inputs"), list) or len(task["inputs"]) > MAX_FILES:
        raise TaskError("La lista de contexto preparada no es válida.")
    if not installation_is_verified():
        raise TaskError("La instalación de OpenCode no supera la verificación de integridad.")
    def verify_inputs():
        total_bytes = 0
        for entry in task["inputs"]:
            path = _inside(directory / entry["copy"], directory / "inputs")
            with path.open("rb") as stream:
                data = stream.read(MAX_INPUT_BYTES + 1)
            total_bytes += len(data)
            if (path.is_symlink() or total_bytes > MAX_INPUT_BYTES or SECRET.search(data.decode("utf-8"))
                    or hashlib.sha256(data).hexdigest() != entry["sha256"]):
                raise TaskError("Una copia de entrada cambió; prepara de nuevo el contexto.")
    verify_inputs()
    env = child_environment(directory)
    local_check = preflight(directory, task, env)
    if MODEL_POLICIES[task["model"]]["requires_policy_consent"]:
        model_check = verify_free_model(task["model"], synthetic_demo=task["synthetic_demo"],
                                        accept_model_policy=task["accept_model_policy"])
    else:
        model_check = verify_free_model(task["model"])
    task.update(status="running", started_at=datetime.now(timezone.utc).isoformat())
    _write_json(manifest_path, task)
    report = {"task": task_id, "mode": task["mode"], "model": model_check,
              "preflight": local_check, "automatic_import": False,
              "token_semantics": "opencode-v" + VERSION}
    prompt = ("Trabaja únicamente en esta ubicación de tarea. Archivos disponibles: "
              + ", ".join(entry["copy"] for entry in task["inputs"])
              + ". Tu encargo es: " + task["prompt"]
              + ". No ejecutes código ni comandos. No cambies modelo, permisos, entradas o configuración. "
              "Devuelve como máximo 1200 palabras. Los borradores van solo en outputs/.")
    command = [str(EXECUTABLE_PATH), "run", "--standalone", "--model", "opencode/" + task["model"],
               "--agent", "sparkx-" + task["mode"], "--format", "json", "--archived",
               "--title", "SparkX: " + task_id, prompt]
    try:
        result = run_bounded(command, cwd=directory, env=env, stop_on_model_error=True)
        events = result.pop("stdout")
        (directory / "events.jsonl").write_text(events, encoding="utf-8")
        (directory / "diagnostics.txt").write_text(result.pop("stderr"), encoding="utf-8")
        verify_inputs()
        response = parse_response(events)
        report["observed_steps"] = response["steps"]
        report["observed_tokens"] = response["tokens"]
        report["reported_cost"] = response["cost"]
        if response["text"]:
            (directory / "outputs" / "respuesta.md").write_text(response["text"], encoding="utf-8")
        report.update(result)
        report["status"] = "review_required" if result["exit_code"] == 0 and not response["error"] else "failed"
        task["status"] = report["status"]
    except (TaskError, OSError) as error:
        report.update(status="failed", error=str(error))
        partial = getattr(error, "partial_output", None)
        if isinstance(partial, dict):
            (directory / "events.jsonl").write_text(partial["stdout"], encoding="utf-8")
            (directory / "diagnostics.txt").write_text(partial["stderr"], encoding="utf-8")
            observed = parse_response(partial["stdout"])
            report.update(observed_steps=observed["steps"], observed_tokens=observed["tokens"],
                          reported_cost=observed["cost"], counters_incomplete=True,
                          seconds=partial["seconds"], exit_code=partial["exit_code"])
        task["status"] = "failed"
    finally:
        task["finished_at"] = datetime.now(timezone.utc).isoformat()
        _write_json(manifest_path, task)
        _write_json(directory / "result.json", report)
    # Accounting is deterministic and offline; its failure must not rewrite the
    # inference result or imply that the model needs to run again.
    try:
        write_comparison(task_id)
    except (OSError, ValueError, TaskError) as error:
        print("No se pudo preparar la comparación local: " + str(error), file=sys.stderr)
    return report


def parse_response(events: str) -> dict:
    """Read documented CLI events, never execute the returned text or tools."""
    texts, tokens, costs = [], [], []
    error = False
    steps = 0
    for line in events.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            error = True
            continue
        if not isinstance(event, dict):
            error = True
            continue
        part = event.get("part", {})
        if event.get("type") in ("error", "retry"):
            error = True
        elif event.get("type") == "text" and isinstance(part, dict) and isinstance(part.get("text"), str):
            if part["text"].strip():
                texts.append(part["text"])
        elif event.get("type") == "step_finish" and isinstance(part, dict):
            steps += 1
            tokens.append(part.get("tokens"))
            costs.append(part.get("cost"))
            if part.get("reason") == "length":
                error = True
    return {"text": "\n\n".join(texts), "tokens": tokens, "cost": costs, "steps": steps,
            "error": error or not texts}


def wizard() -> int:
    """A small, explicit handoff instead of opening the full private repository."""
    print("Ayudante OpenCode para desarrollar SparkX")
    print("Solo modelos gratuitos comprobados. Los archivos elegidos se envían a un proveedor remoto.")
    print("No incluyas claves, datos personales o información confidencial. Los borradores requieren revisión.")
    if not installation_is_verified():
        print("Primero ejecuta: .\\.venv\\Scripts\\python.exe -B tools/opencode/install.py")
        return 1
    models = list(ALLOWED_MODELS)
    print("Modelos disponibles (el precio se comprobará antes del envío):")
    for index, model in enumerate(models, 1):
        suffix = " · datos ficticios y aceptación de condiciones" if MODEL_POLICIES[model]["synthetic_only"] else ""
        print(f"  {index}. {ALLOWED_MODELS[model]}{suffix}")
    selection = input("Modelo [1 predeterminado]: ").strip() or "1"
    if not selection.isdecimal() or not 1 <= int(selection) <= len(models):
        raise TaskError("Selecciona un número de modelo válido.")
    model = models[int(selection) - 1]
    policy = MODEL_POLICIES[model]
    print(policy["privacy"])
    print(policy["quota_note"])
    synthetic = accepted = False
    if policy["requires_policy_consent"]:
        print("Condiciones: " + policy["policy_url"])
        if input("Declara que encargo y archivos son ficticios y acepta estas condiciones: escribe ACEPTO DATOS FICTICIOS: ").strip() != "ACEPTO DATOS FICTICIOS":
            print("Cancelado antes de preparar o enviar datos.")
            return 0
        synthetic = accepted = True
    mode = "draft" if input("Modo [1 revisar / 2 preparar borrador]: ").strip() == "2" else "review"
    prompt = input("Describe una tarea pequeña: ").strip()
    files = [item.strip() for item in input("Archivos relativos separados por coma (vacío = sin archivos): ").split(",") if item.strip()]
    directory = prepare_task(prompt, mode=mode, files=files, model=model,
                             synthetic=synthetic, accept_model_policy=accepted)
    print("Preparada en: " + str(directory))
    print("En modo borrador solo puede escribir en outputs/. El código original se conserva.")
    if input("¿Enviar esta tarea al modelo gratuito? Escribe ENVIAR para continuar: ").strip() != "ENVIAR":
        print("No se enviaron datos. Puedes revisar la preparación y ejecutarla después.")
        return 0
    report = run_task(directory.name)
    print("Resultado: " + report["status"])
    print("Revisa: " + str(directory / "result.json"))
    print("Respuesta y borradores: " + str(directory / "outputs"))
    print("Consumo y escenarios hipotéticos: " + str(directory / "cost-comparison.md"))
    return 0 if report["status"] == "review_required" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Verificar instalación local, sin inferencia.")
    commands.add_parser("wizard", help="Preparar y enviar una tarea desde una guía interactiva.")
    prepare = commands.add_parser("prepare", help="Preparar una tarea sin red ni inferencia.")
    prepare.add_argument("--task", required=True)
    prepare.add_argument("--mode", choices=("review", "draft"), default="review")
    prepare.add_argument("--model", choices=sorted(ALLOWED_MODELS), default=DEFAULT_MODEL)
    prepare.add_argument("--file", action="append", default=[])
    prepare.add_argument("--demo", action="store_true")
    prepare.add_argument("--synthetic", action="store_true", help="Declaro que encargo y archivos contienen solo datos ficticios.")
    prepare.add_argument("--accept-model-policy", action="store_true", help="Acepto las condiciones específicas del modelo seleccionado.")
    compare = commands.add_parser("compare", help="Comparar consumo existente con tarifas de referencia, sin red ni modelos.")
    compare.add_argument("task_id")
    diagnostic = commands.add_parser("inspect", help="Inspección local del binario aislado; no inferencia.")
    diagnostic.add_argument("task_id")
    diagnostic.add_argument("--part", choices=("help", "run-help", "debug-help", "config", "agents", "paths"), default="help")
    run = commands.add_parser("run", help="Ejecutar una tarea preparada con el modelo gratuito comprobado.")
    run.add_argument("task_id")
    args = parser.parse_args(argv)
    try:
        if args.command == "wizard":
            return wizard()
        elif args.command == "status":
            print(json.dumps({"installed_verified": installation_is_verified(), "version": VERSION,
                              "models": sorted(ALLOWED_MODELS), "model_policies": {k: dict(v) for k, v in MODEL_POLICIES.items()},
                              "automatic_import": False, "paid_credentials": False}))
        elif args.command == "prepare":
            directory = prepare_task(args.task, mode=args.mode, model=args.model, files=args.file, demo=args.demo,
                                     synthetic=args.synthetic, accept_model_policy=args.accept_model_policy)
            print("Tarea preparada, sin llamadas: " + directory.name)
        elif args.command == "compare":
            report = write_comparison(args.task_id)
            print(json.dumps(report, ensure_ascii=True))
        elif args.command == "run":
            report = run_task(args.task_id)
            print(json.dumps(report, ensure_ascii=True))
            return 0 if report["status"] == "review_required" else 1
        else:
            if not installation_is_verified():
                raise TaskError("Instala primero el binario oficial verificado.")
            directory = task_directory(args.task_id)
            env = child_environment(directory)
            parts = {"help": ["--help"], "run-help": ["run", "--help"], "debug-help": ["debug", "--help"],
                     "config": ["debug", "config"], "agents": ["debug", "agents"], "paths": ["debug", "paths"]}
            private = ["--standalone"] if args.part in ("config", "agents", "run-help", "help") else []
            result = run_bounded([str(EXECUTABLE_PATH), *parts[args.part], *private], cwd=directory, env=env, seconds=35)
            print(json.dumps(result, ensure_ascii=True))
        return 0
    except (TaskError, CatalogVerificationError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
