"""silencio.py: techno 20 s, silencio largo con ruido muy bajo (40 s), techno 20 s. ¿Detecta tempo en el silencio?"""
import numpy as np
import banco
import electronica_tempo_variable as e

a, _ = e.sintetizar(lambda t: 128.0, 20)
b, _ = e.sintetizar(lambda t: 124.0, 20)
ruido = (np.random.default_rng(1).normal(0, 1, 40 * e.SR) * 10 ** (-70 / 20)).astype(np.float32)   # -70 dB
y = np.concatenate([a, ruido, b])
pred, curva = banco.correr(banco.cargarMotor(), y, e.SR, 'auto')
m = banco.cargarMotor()
print(' '.join('%d:%.0f' % (t, bb) for t, bb in curva[::6]))
