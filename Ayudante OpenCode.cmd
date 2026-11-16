@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro el entorno Python de ArquiGica. Revisa README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 -B -m tools.opencode.runner wizard
pause
