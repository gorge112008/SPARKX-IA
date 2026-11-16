@echo off
setlocal
title SparkX - plataforma y Gica-1
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro el entorno Python de SparkX. Consulta README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B tools\start_sparkx.py
if errorlevel 1 (
  echo No se pudo iniciar SparkX. Revisa el mensaje anterior.
  pause
  exit /b 1
)
endlocal
