# Cambios de BPM auToe

Cada sección «## versión» es lo que muestra el cartel de «Hay una versión nueva» (una línea por cambio).

## 0.7.0
- Ahora es una app instalable: aparece en el menú Inicio y se desinstala desde Configuración de Windows.
- Al abrirla avisa si hay una versión nueva y se actualiza con un clic.
- La configuración se guarda en la carpeta del usuario (%APPDATA%\BPM auToe) y no se pierde al actualizar.

## 0.6.0
- Audio con loopback de WASAPI: puede escuchar lo que suena por una salida, no solo entradas.
- Lista de audio ordenada: solo los dispositivos activos de Windows, entradas y salidas por separado.
- Cada dispositivo se abre a su frecuencia y se pasa a 48 kHz.

## 0.5.1
- Ableton Link: la app lleva la sesión (tempo y fase del compás).
- OSC con prefijo /BPMauToe/: estado a TouchDesigner (9100), valores con nombre (9102), comandos (9101).
