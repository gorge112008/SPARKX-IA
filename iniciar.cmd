@echo off
setlocal
title ArquiGica - plataforma y Gica-1
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro el entorno Python de ArquiGica. Consulta README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B tools\start_sparkx.py
if errorlevel 1 (
  echo No se pudo iniciar ArquiGica. Revisa el mensaje anterior.
  pause
  exit /b 1
)
endlocal
