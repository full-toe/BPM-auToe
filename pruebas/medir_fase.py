"""
medir_fase.py: en los temas con el tempo correcto, ¿cuánto y hacia dónde se corre la grilla?
Muestra el corrimiento como fracción del tiempo (0 = justo, ±0.5 = contratiempo) y en ms.
	python medir_fase.py [cantidad]
"""
import os
import sys
from multiprocessing import Pool

import numpy as np

import banco


def uno(c):
	try:
		y, sr = banco.leerAudio(c[0])
		ref = np.array([float(l.split()[0]) for l in open(c[1]) if l.strip()])
		bref = 60 / np.median(np.diff(ref))
		pred, curva = banco.correr(banco.cargarMotor(), y, sr, 'banda')
		if not curva or abs(curva[-1][1] / bref - 1) > 0.04:
			return None
		T = 60 / bref
		p = pred[pred > 12]
		d = np.array([x - ref[np.argmin(np.abs(ref - x))] for x in p])
		fr = np.angle(np.mean(np.exp(2j * np.pi * d / T))) / (2 * np.pi)       # fracción de tiempo
		return (c[3], round(float(fr), 3), round(float(fr * T * 1000)), round(banco.fmedida(pred, ref, 12), 2))
	except Exception:
		return None


if __name__ == '__main__':
	n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
	cs = banco.listar('gtzan')
	cs = cs[::max(1, len(cs) // n)][:n]
	with banco.pool() as p:
		out = [o for o in p.map(uno, cs) if o]
	fr = np.array([o[1] for o in out])
	print('temas con tempo correcto:', len(out))
	print('corrimiento (fracción de tiempo): mediana %.3f | |fr|<0.1: %d%% | cerca de ±0.5 (contratiempo): %d%% | ±0.25: %d%%' % (
		np.median(fr), 100 * np.mean(np.abs(fr) < 0.1), 100 * np.mean(np.abs(np.abs(fr) - 0.5) < 0.1),
		100 * np.mean(np.abs(np.abs(fr) - 0.25) < 0.08)))
	print('ms (solo los que están cerca de 0):', np.round(np.median([o[2] for o in out if abs(o[1]) < 0.15]), 1))
	print('histograma fracción:', np.histogram(fr, bins=[-0.5, -0.35, -0.15, -0.05, 0.05, 0.15, 0.35, 0.5])[0])
