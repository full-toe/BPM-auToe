"""barrido.py: prueba valores de PREFIERE_DOBLE. Cuenta solo temas con BPM anotado dentro de 75-175."""
import os, sys
from multiprocessing import Pool
import numpy as np
import banco

VAL = float(os.environ.get('PD', '0.6'))


def uno(c):
	mod = banco.cargarMotor()
	mod.PREFIERE_DOBLE = VAL
	banco.cargarMotor = lambda: mod
	return banco.evaluar(c + ('banda',))


if __name__ == '__main__':
	cs = banco.listar('gtzan')
	cs = cs[::max(1, len(cs) // 200)][:200]
	with banco.pool() as p:
		r = [x for x in p.map(uno, cs) if x and 'error' not in x and 75 <= x['bpm_ref'] <= 175]
	print('PREFIERE_DOBLE %.2f | temas %d | exacto %.1f%% | octava %.1f%% | F %.3f' % (VAL, len(r), 100 * np.mean([x['acierto'] for x in r]),
		  100 * np.mean([x['octava'] != '' for x in r]), np.mean([x['f'] for x in r])))
