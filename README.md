# BPM auToe

Detector de BPM en tiempo real para shows de visuales. Escucha la música (una entrada de audio o lo que
suena por una salida de la computadora), encuentra el tempo y la fase, y entrega una **rejilla de tiempo
que nunca salta**: solo acelera o frena de a poco, así las animaciones atadas a ella no dan tirones.

*Real-time BPM detector for live visuals. Listens to an audio input (or a system output via WASAPI
loopback), tracks tempo and phase, and outputs a beat grid that never jumps. Sends it over OSC and
Ableton Link, and ships as a TouchDesigner component too.*

## Qué hace
- **Detecta el tempo y la fase** desde el audio, con respaldo manual (TAP, ÷2, ×2, corrimiento ◀ ▶, RESYNC).
- **OSC** (UDP): el estado completo a TouchDesigner (puerto 9100), valores con nombre para cualquier
  programa (`/BPMauToe/bpm`, `/BPMauToe/fase_1_4`, `/BPMauToe/kick`…, puerto 9102) y recibe comandos
  (`tap`, `resync`, `doble`, `mitad`, `auto`, `nudge`, `bpm`…, puerto 9101).
- **Ableton Link**: la app lleva la sesión (probado con Ableton Live 12 y Resolume Arena).
- **Módulo de TouchDesigner** (`td/BPMauToe.tox`) con el mismo motor y panel propio.

## Instalar (Windows 10/11)
Bajar `BPM-auToe-<versión>-instalador.exe` de [Versiones](https://github.com/full-toe/BPM-auToe/releases/latest)
y abrirlo. No pide permiso de administrador. Queda en el menú Inicio y se desinstala desde
Configuración › Aplicaciones. Al abrirla, avisa si hay una versión nueva y se actualiza con un clic.

La configuración se guarda en `%APPDATA%\BPM auToe`.

## Carpetas
| Carpeta | Qué hay |
|---|---|
| `app/` | La app (Python + tkinter): `ritmo_app.py`, el aviso de versiones nuevas (`actualizar.py`) y `construir_exe.py` (PyInstaller). |
| `fuentes/` | El motor (`ritmo_motor.py`, numpy puro), la lógica compartida con TD (`ritmo_logica.py`), los shaders del panel y los scripts que arman el `.tox` dentro de TouchDesigner. |
| `td/` | `BPMauToe.tox`, el módulo para TouchDesigner. |
| `pruebas/` | Banco de pruebas del detector (`banco.py`) y sus resultados. |
| `instalador/` | El instalador (Inno Setup) y `publicar_version.py`, que arma y publica cada versión. |

## Correr desde el código
```
pip install numpy scipy PyAudioWPatch python-osc LinkPython-extern
python app/ritmo_app.py
```

## Banco de pruebas
`pruebas/banco.py` mide la exactitud del tempo contra tres bases públicas que **no se incluyen** acá
(hay que bajarlas aparte y ponerlas en `pruebas/datos/`): GTZAN (anotaciones de tempo de Marchand y
Peeters), Ballroom y GiantSteps Tempo (`pruebas/descargar_giantsteps.sh`).

## Sacar una versión nueva
1. Subir `VERSION` en `app/ritmo_app.py`.
2. Escribir lo que cambia en `CAMBIOS.md` (sección `## <versión>`).
3. Commit y push.
4. `python instalador/publicar_version.py --publicar`

## Licencia
GPL v3 (ver `LICENSE`). Hecho por Toe.
