"""
electronica_tempo_variable.py: techno sintético con el tempo cambiando de forma controlada (se sabe exactamente
dónde cae cada tiempo) para ver si Ritmo sigue rampas, frenadas, cambios de DJ y halftime.
	python electronica_tempo_variable.py [banda|electronica]
Para cada caso: error de BPM a lo largo del tiempo, F de tiempos (±70 ms) y peor desfase.
"""
import math
import sys

import numpy as np

import banco

SR = 22050
rng = np.random.default_rng(3)


def bombo(n):
	t = np.arange(n) / SR
	return np.sin(2 * np.pi * (45 + 90 * np.exp(-t * 35)) * t) * np.exp(-t * 9)


def hat(n):
	t = np.arange(n) / SR
	x = np.diff(np.r_[0, rng.normal(0, 1, n)])
	return x * np.exp(-t * 90) * 0.18


def clap(n):
	t = np.arange(n) / SR
	return rng.normal(0, 1, n) * np.exp(-t * 30) * 0.35


def sintetizar(bpm_de_t, dur, halftime=None):
	"""bpm_de_t(t) -> bpm instantáneo. Devuelve audio y tiempos reales de cada tiempo."""
	y = np.zeros(int(dur * SR))
	t = np.arange(len(y)) / SR
	y += 0.1 * np.sin(2 * np.pi * 55 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t))   # bajo de fondo
	beats, fase, k = [], 0.0, 0
	dt = 1 / SR * 64
	tt = 0.0
	while tt < dur:
		fase += bpm_de_t(tt) / 60 * dt * 2                    # en corcheas
		if fase >= k + 1:
			k += 1
			s = int(tt * SR)
			L = min(len(y) - s, int(0.3 * SR))
			if L > 0:
				esTiempo = k % 2 == 0
				medio = halftime is not None and halftime[0] <= tt < halftime[1]
				y[s:s + L] += hat(L)
				if esTiempo:
					if not medio or (k // 2) % 2 == 0:
						y[s:s + L] += bombo(L)
					if (k // 2) % 4 == 2 and not medio:
						y[s:s + L] += clap(L)
					beats.append(tt)
		tt += dt
	return (y / np.abs(y).max() * 0.8).astype(np.float32), np.array(beats)


CASOS = {
	'rampa 124->130 en 60 s': (lambda t: 124 + 6 * min(1, max(0, (t - 10) / 60)), 90, None),
	'frenada y vuelve 128->120->128': (lambda t: 128 - 8 * math.sin(math.pi * min(1, max(0, (t - 15) / 40))) ** 2, 80, None),
	'cambio de DJ 125->140 en 16 s': (lambda t: 125 + 15 * min(1, max(0, (t - 30) / 16)), 80, None),
	'halftime 20 s y vuelve (138)': (lambda t: 138.0, 80, (30, 50)),
	'estable 128 (control)': (lambda t: 128.0, 60, None),
}


def evaluar(nombre, modo):
	f, dur, ht = CASOS[nombre]
	y, ref = sintetizar(f, dur, ht)
	pred, curva = banco.correr(banco.cargarMotor(), y, SR, modo)
	err = [abs(b / f(t) - 1) * 100 for t, b in curva if t > 8]
	F = banco.fmedida(pred, ref, desde=8)
	ok = [t for t, b in curva if abs(b / f(t) - 1) <= 0.02]
	return nombre, np.mean(err), np.max(err), F


if __name__ == '__main__':
	modo = sys.argv[1] if len(sys.argv) > 1 else 'electronica'
	print('modo', modo)
	for n in CASOS:
		nombre, emed, emax, F = evaluar(n, modo)
		print('%-34s error BPM medio %4.1f%%  máx %5.1f%%  | F tiempos %.2f' % (nombre, emed, emax, F))
