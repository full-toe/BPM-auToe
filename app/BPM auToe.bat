@echo off
rem Abre la app Ritmo (detector de BPM fuera de TouchDesigner) sin ventana de consola.
cd /d "%~dp0"
start "" pythonw ritmo_app.py
