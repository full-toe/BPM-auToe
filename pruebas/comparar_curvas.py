"""
comparar_curvas.py: ¿por qué la curva de golpes del motor (tiempo real) rinde menos que la calculada
de una vez? Compara ventanas de 8 y 12 s, con y sin el aporte del bombo.
	python comparar_curvas.py [cantidad]
"""
import os
import sys
from multiprocessing import Pool

import numpy as np

import banco
import onset_variantes as ov


def uno(c):
	try:
		y, sr = banco.leerAudio(c[0])
		ref = np.array([float(l.split()[0]) for l in open(c[1]) if l.strip()])
		bref = 60 / np.median(np.diff(ref))
		mod = banco.cargarMotor()
		X = banco.bandas(y[:int(16 * sr)], sr)
		res = {}
		for peso in (0.5, 0.0):
			mod.PESO_BOMBO = peso
			m = mod.Motor(sr)
			n = sr // 60
			for i in range(0, int(16 * sr) - n, n):
				m.alimentar(X[i:i + n], i / sr, 0, 1 / 60)
			res['motor b%.1f 12s' % peso] = ov.tempo(m.O[-int(12 * m.fs):], m.fs) / bref
			res['motor b%.1f 8s' % peso] = ov.tempo(m.O[-int(8 * m.fs):], m.fs) / bref
		o, fs = ov.onset(y[int(4 * sr):int(16 * sr)], sr, 'actual')
		res['offline 12s'] = ov.tempo(o, fs) / bref
		res['offline 8s'] = ov.tempo(o[-int(8 * fs):], fs) / bref
		return {k: (abs(v - 1) <= .04, any(abs(v / f - 1) <= .04 for f in (1, 2, .5))) for k, v in res.items()}
	except Exception:
		return None


if __name__ == '__main__':
	n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
	cs = banco.listar('gtzan')
	cs = cs[::max(1, len(cs) // n)][:n]
	with banco.pool() as p:
		out = [o for o in p.map(uno, cs) if o]
	print('temas', len(out))
	for k in out[0]:
		print('%-16s exacto %5.1f%%  octava %5.1f%%' % (k, 100 * np.mean([o[k][0] for o in out]),
													  100 * np.mean([o[k][1] for o in out])))
