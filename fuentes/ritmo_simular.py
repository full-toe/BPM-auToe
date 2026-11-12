"""
ritmo_simular: prueba el motor de Ritmo con un .wav, sin esperar en tiempo real (correr en TD o con numpy).
simular(ruta, modulo_motor) -> lista de BPM cada 'paso' segundos. Filtros por FFT (parecidos a los de TD).
"""
import wave
import numpy as np


def simular(ruta, mod, paso=2.0, fps=60, latA=0.0, desde=0.0, segundos=90.0):
	with wave.open(ruta) as w:
		sr, nc, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
		w.setpos(min(w.getnframes() - 1, int(desde * sr)))
		b = w.readframes(int(segundos * sr))
	if sw == 3:
		a = np.frombuffer(b, np.uint8).reshape(-1, 3)
		y = (a[:, 0].astype(np.int32) | (a[:, 1].astype(np.int32) << 8) | (a[:, 2].astype(np.int32) << 16))
		y = np.where(y >= 1 << 23, y - (1 << 24), y).astype(np.float32) / (1 << 23)
	elif sw == 4:
		y = np.frombuffer(b, np.int32).astype(np.float32) / (1 << 31)
	else:
		y = np.frombuffer(b, np.int16).astype(np.float32) / 32768
	if nc > 1:
		y = y.reshape(-1, nc).mean(axis=1)
	F = np.fft.rfft(y)
	fr = np.fft.rfftfreq(len(y), 1 / sr)

	def banda(lo, hi):
		return np.fft.irfft(F * ((fr >= lo) & (fr < hi)), len(y))
	X = np.stack([banda(0, 120), banda(1500, 2600), banda(8000, 1e9), banda(0, 250), banda(700, 1400),
				  banda(4000, 1e9), y], 1)
	m = mod.Motor(sr)
	n = int(sr / fps)
	out, prox = [], paso
	for i in range(0, len(y) - n, n):
		t = i / sr
		m.alimentar(X[i:i + n], t, latA, 1 / fps)
		if t - m.ultimaEst > 0.5:
			m.estimar(t - latA)
		if t >= prox:
			out.append(round(m.bpm, 1))
			prox += paso
	return out
