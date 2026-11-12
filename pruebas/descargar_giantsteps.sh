#!/bin/bash
# descargar_giantsteps.sh: baja los previews de GiantSteps Tempo (respaldo JKU) y los pasa a WAV mono 22 kHz.
D="/c/Toe/Proyectos/BPM auToe/pruebas/datos/giantsteps"
FF="/c/Program Files/Derivative/TouchDesigner.2025.32460/bin/ffmpeg.exe"
mkdir -p "$D/mp3" "$D/wav"
for f in "$D"/annotations_v2/tempo/*.bpm; do
  id=$(basename "$f" .bpm)
  [ -f "$D/wav/$id.wav" ] && continue
  curl -sL --retry 2 --max-time 60 -o "$D/mp3/$id.mp3" "https://www.cp.jku.at/datasets/giantsteps/backup/$id.mp3" || continue
  "$FF" -nostdin -loglevel error -threads 1 -y -i "$D/mp3/$id.mp3" -ac 1 -ar 22050 "$D/wav/$id.wav" && rm -f "$D/mp3/$id.mp3"
done
echo "LISTO $(ls $D/wav | wc -l) temas"
