"""
ritmo_util: suma el ritmo de la grilla de Ritmo.tox (op.Ritmo) al valor de la perilla (0..1),
antes de la curva y el rango. Profundidad 0 = no se usa (y el Destino no depende del reloj); negativa = resta.
Además multiplica por el canal 'ar' de Controles (master AUDIO-RITMO x CYCLE).
Detectar bajadas: multiplica por la confianza suavizada de Ritmo (en un break o sin ritmo claro, se apaga solo).
"""
import math

LARGO = {'1_16': 0.25, '1_8': 0.5, '1_4': 1, '1_2': 2}          # en tiempos; el resto en compases


def Forma(nombre, p, paso):
	if nombre == 'rampa':
		return p
	if nombre == 'bajada':
		return 1.0 - p
	if nombre == 'seno':
		return 0.5 - 0.5 * math.cos(2 * math.pi * p)
	if nombre == 'triangulo':
		return 1.0 - abs(2 * p - 1)
	if nombre == 'cuadrada':
		return 1.0 if p < 0.5 else 0.0
	if nombre == 'golpe':
		return math.exp(-6.0 * p)
	x = math.sin(paso * 12.9898 + 78.233) * 43758.5453                 # aleatorio fijo por paso
	return x - math.floor(x)


def _factorControles():
	"""Cuánto suena lo audio-rítmico según Controles (master AUDIO-RITMO x CYCLE); 1 si no hay Controles."""
	c = getattr(op, 'Controles', None)
	e = c.op('estado') if c is not None else None
	ch = e.chan('ar') if e is not None else None
	return ch.eval() if ch is not None else 1.0


def Valor(destino, base):
	# la grilla la da BPMauToe (la app externa por OSC); si no está en el proyecto, el módulo Ritmo
	r = getattr(op, 'BPMauToe', None) or getattr(op, 'Ritmo', None)
	g = r.op('grilla') if r is not None else None
	if g is None or not g.numChans:
		return base
	pr = destino.par
	div = pr.Ritmodiv.eval()
	f = g['fase_' + div]
	if f is None:
		return base
	p = (f.eval() + pr.Ritmofase.eval()) % 1.0
	largo = LARGO.get(div) or float(div) * g['compas_tiempos'].eval()
	paso = math.floor((g['beats'].eval() + 1e-6) / largo)
	k = g['confianza_suave'].eval() if pr.Ritmobajadas.eval() else 1.0
	k *= _factorControles()
	return base + pr.Ritmoprof.eval() * k * Forma(pr.Ritmoforma.eval(), p, paso)
