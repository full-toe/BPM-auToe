"""
tempo_variantes.py: compara fórmulas de cálculo del tempo sobre la curva de golpes del motor
(sin la lógica de aceptación). Para cada tema mira la estimación a los 6 s y a los 12 s.
	python tempo_variantes.py [cantidad]
"""
import math
import sys
from multiprocessing import Pool

import numpy as np

import banco


def curvaGolpes(y, sr):
	mod = banco.cargarMotor()
	X = banco.bandas(y, sr)
	m = mod.Motor(sr)
	n = int(sr / 60)
	O, T = [], []
	for i in range(0, len(y) - n, n):
		m.alimentar(X[i:i + n], i / sr, 0.0, 1 / 60)
	return m.O.copy(), m.fs


def ac_de(o):
	k = max(3, int(0.3 * 190))
	x = np.maximum(o - np.convolve(o, np.ones(k) / k, 'same'), 0)
	x = x - x.mean()
	L = len(x)
	n = 1 << int(math.ceil(math.log2(2 * L)))
	X = np.fft.rfft(x, n)
	ac = np.fft.irfft(X * np.conj(X), n)[:L]
	return ac / max(ac[0], 1e-9)


def variante(o, fs, nombre, bmin=70, bmax=180):
	ac = ac_de(o)
	L = len(ac)
	lags = np.arange(int(60 * fs / bmax), int(60 * fs / bmin) + 1)
	lags = lags[lags * 2 < L]
	idx = np.arange(L)
	a = lambda l: np.interp(l, idx, ac)
	bpms = 60 * fs / lags
	if nombre == 'actual':
		s = a(lags) + 0.5 * a(2 * lags) + 0.33 * a(3 * lags) + 0.25 * a(4 * lags)
		c = math.sqrt(bmin * bmax)
		s = s * (0.75 + 0.25 * np.exp(-0.5 * (np.log2(bpms / c) / 0.8) ** 2))
	elif nombre == 'prior120':
		s = np.maximum(a(lags), 0) * np.exp(-0.5 * (np.log2(bpms / 120) / 1.0) ** 2)
	elif nombre == 'arm+prior120':
		s = np.maximum(a(lags) + 0.5 * a(2 * lags), 0) * np.exp(-0.5 * (np.log2(bpms / 120) / 1.0) ** 2)
	elif nombre == 'mitad+prior120':                       # suma también el pulso a la mitad (corcheas)
		s = np.maximum(a(lags) + 0.5 * a(lags / 2.0) + 0.5 * a(2 * lags), 0) * np.exp(-0.5 * (np.log2(bpms / 120) / 1.0) ** 2)
	elif nombre == 'arm+prior120s07':
		s = np.maximum(a(lags) + 0.5 * a(2 * lags), 0) * np.exp(-0.5 * (np.log2(bpms / 120) / 0.7) ** 2)
	k = int(np.argmax(s))
	return 60 * fs / lags[k]


VARS = ['actual', 'prior120', 'arm+prior120', 'mitad+prior120', 'arm+prior120s07']


def uno(caso):
	audio, anot, base, genero = caso
	try:
		y, sr = banco.leerAudio(audio)
		ref = np.array([float(l.split()[0]) for l in open(anot) if l.strip()])
		bref = 60.0 / np.median(np.diff(ref))
		O, fs = None, None
		res = {}
		for seg in (6, 12):
			o, fs = curvaGolpes(y[:int(seg * sr) + int(0.05 * sr)], sr)
			o = o[-int(min(seg, 8) * fs):]
			for v in VARS:
				b = variante(o, fs, v)
				r = b / bref
				res[(v, seg)] = (abs(r - 1) <= 0.04, any(abs(r / f - 1) <= 0.04 for f in (1, 2, 0.5)))
		return genero, res
	except Exception as e:
		return None


if __name__ == '__main__':
	n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
	casos = banco.listar('gtzan')
	casos = casos[::max(1, len(casos) // n)][:n]
	with banco.pool() as p:
		out = [r for r in p.map(uno, casos) if r]
	print('temas', len(out))
	for v in VARS:
		for seg in (6, 12):
			ex = np.mean([r[(v, seg)][0] for g, r in out]) * 100
			oc = np.mean([r[(v, seg)][1] for g, r in out]) * 100
			print('%-18s %2ds  exacto %5.1f%%   octava ok %5.1f%%' % (v, seg, ex, oc))
