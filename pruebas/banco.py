"""
banco.py: prueba el motor de Ritmo.tox contra temas con la grilla anotada a mano (GTZAN, Ballroom).
Corre afuera de TouchDesigner (Python + numpy), en paralelo.

	python banco.py [gtzan|ballroom|todo] [cantidad_maxima] [modo banda|electronica]

Mide por tema: tempo correcto (±4 %), error de octava (mitad/doble/tercio), F de tiempos (±70 ms,
desde los 5 s) y segundos hasta engancharse. Escribe resultados.csv y un resumen por género.
"""
import csv
import glob
import importlib.util
import math
import os
import sunau
import sys
import wave
from multiprocessing import Pool

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
MOTOR = 'C:/Toe/Proyectos/BPM auToe/fuentes/ritmo_motor.py'
DATOS = os.path.join(AQUI, 'datos')


def _prioridadBaja():
	"""Los procesos de prueba usan el procesador solo cuando sobra (prioridad IDLE de Windows)."""
	try:
		import ctypes
		ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
	except Exception:
		pass


def pool(n=int(os.environ.get("PROCS", "2"))):
	"""2 procesos con prioridad baja: tarda más pero no le saca procesador a TouchDesigner."""
	_prioridadBaja()
	return Pool(n, initializer=_prioridadBaja)


def cargarMotor():
	spec = importlib.util.spec_from_file_location('ritmo_motor', MOTOR)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	for k, v in os.environ.items():                     # MOTOR_X=valor cambia constantes del motor (pruebas A/B)
		if k.startswith('MOTOR_'):
			setattr(mod, k[6:], float(v))
	return mod


def leerAudio(ruta):
	lector = sunau if ruta.lower().endswith('.au') else wave
	with lector.open(ruta, 'rb') as w:
		sr, nc, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
		b = w.readframes(n)
	if sw == 2:
		y = np.frombuffer(b, '>i2' if lector is sunau else '<i2').astype(np.float32) / 32768
	elif sw == 1:
		y = (np.frombuffer(b, np.uint8).astype(np.float32) - 128) / 128
	else:
		y = np.frombuffer(b, '>i4' if lector is sunau else '<i4').astype(np.float32) / 2 ** 31
	if nc > 1:
		y = y.reshape(-1, nc).mean(axis=1)
	if os.environ.get('MAXSEG'):                        # cortar a los primeros N segundos (pruebas más rápidas)
		y = y[:int(float(os.environ['MAXSEG']) * sr)]
	return y / (np.abs(y).max() + 1e-9) * 0.8, sr


def bandas(y, sr):
	F = np.fft.rfft(y)
	fr = np.fft.rfftfreq(len(y), 1 / sr)

	def b(lo, hi):
		return np.fft.irfft(F * ((fr >= lo) & (fr < hi)), len(y)).astype(np.float32)
	return np.stack([b(0, 120), b(1500, 2600), b(8000, 1e9), b(0, 250), b(700, 1400), b(4000, 1e9), y], 1)


def correr(mod, y, sr, modo, fps=60):
	"""Pasa el audio por el motor como en TD; devuelve (tiempos de beat predichos, bpm cada 0.5 s)."""
	X = bandas(y, sr)
	m = mod.Motor(sr)
	m.cfg['modo'] = modo
	n = int(sr / fps)
	beats, curva, ultimo = [], [], None
	for i in range(0, len(y) - n, n):
		t = i / sr
		m.alimentar(X[i:i + n], t + n / sr, 0.0, 1 / fps)      # como en TD: fecha = fin del cuadro
		if t - m.ultimaEst > 0.5:
			m.estimar(t)
			curva.append((t, m.bpm))
		b = m.grilla(t)['beats']
		k = math.floor(b)
		if ultimo is not None and k > ultimo:
			# instante exacto en que se cruzó el tiempo entero (interpolado dentro del cuadro)
			db = b - prevb
			beats.append(t - (b - k) / db * (1 / fps) if db > 0 else t)
		ultimo, prevb = k, b
	return np.array(beats), curva


def fmedida(pred, ref, desde=5.0, tol=0.07):
	pred = pred[pred >= desde]
	ref = ref[ref >= desde]
	if len(pred) == 0 or len(ref) == 0:
		return 0.0
	usados = np.zeros(len(pred), bool)
	aciertos = 0
	for r in ref:
		d = np.abs(pred - r)
		d[usados] = 9
		j = int(np.argmin(d))
		if d[j] <= tol:
			usados[j] = True
			aciertos += 1
	p, c = aciertos / len(pred), aciertos / len(ref)
	return 0.0 if p + c == 0 else 2 * p * c / (p + c)


def evaluar(args):
	audio, anot, base, genero, modo = args
	try:
		mod = cargarMotor()
		y, sr = leerAudio(audio)
		if anot.endswith('.bpm'):                        # GiantSteps: solo el BPM (sin grilla de tiempos)
			bpm_ref = float(open(anot).read().split()[0])
			ref = None
			genero = ('<115' if bpm_ref < 115 else '115-130' if bpm_ref < 130 else '130-150' if bpm_ref < 150 else '>150')
		else:
			ref = np.array([float(l.split()[0]) for l in open(anot) if l.strip()])
			if len(ref) < 4:
				return None
			bpm_ref = 60.0 / np.median(np.diff(ref))
		pred, curva = correr(mod, y, sr, modo)
		final = curva[-1][1] if curva else 0
		r = final / bpm_ref
		acc1 = abs(r - 1) <= 0.04
		octava = next((nombre for f, nombre in ((2, 'doble'), (0.5, 'mitad'), (3, 'triple'), (1 / 3, 'tercio'),
												 (1.5, '3/2'), (2 / 3, '2/3')) if abs(r / f - 1) <= 0.04), '')
		engancha = next((t for t, b in curva if all(abs(bb / bpm_ref - 1) <= 0.04 for tt, bb in curva if tt >= t)), None)
		return dict(base=base, genero=genero, tema=os.path.basename(audio), bpm_ref=round(bpm_ref, 1),
					bpm=round(final, 1), acierto=int(acc1), octava=octava, f=round(fmedida(pred, ref), 3) if ref is not None else 0.0,
					engancha=round(engancha, 1) if engancha is not None else '')
	except Exception as e:
		return dict(base=base, genero=genero, tema=os.path.basename(audio), error=str(e)[:80])


def listar(cual):
	casos = []
	if cual in ('gtzan', 'todo'):
		for a in sorted(glob.glob(os.path.join(DATOS, 'gtzan', 'genres', '*', '*.au')) +
						glob.glob(os.path.join(DATOS, 'gtzan', 'genres', '*', '*.wav'))):
			g, nombre = os.path.basename(os.path.dirname(a)), os.path.splitext(os.path.basename(a))[0]
			num = nombre.split('.')[-1]
			cand = glob.glob(os.path.join(DATOS, 'gtzan', '*', 'beats', 'gtzan_%s_%s.beats' % (g, num)))
			if cand:
				casos.append((a, cand[0], 'gtzan', g))
	if cual in ('ballroom', 'todo'):
		for a in sorted(glob.glob(os.path.join(DATOS, 'ballroom', 'BallroomData', '*', '*.wav'))):
			nombre = os.path.splitext(os.path.basename(a))[0]
			cand = glob.glob(os.path.join(DATOS, 'ballroom', '*', nombre + '.beats'))
			if cand:
				casos.append((a, cand[0], 'ballroom', os.path.basename(os.path.dirname(a))))
	if cual in ('giantsteps', 'todo'):
		for a in sorted(glob.glob(os.path.join(DATOS, 'giantsteps', 'wav', '*.wav'))):
			an = os.path.join(DATOS, 'giantsteps', 'annotations_v2', 'tempo', os.path.splitext(os.path.basename(a))[0] + '.bpm')
			if os.path.exists(an):
				casos.append((a, an, 'giantsteps', 'electronica'))
	return casos


def main():
	cual = sys.argv[1] if len(sys.argv) > 1 else 'todo'
	maximo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
	modo = sys.argv[3] if len(sys.argv) > 3 else 'banda'
	casos = listar(cual)
	if maximo:
		paso = max(1, len(casos) // maximo)
		casos = casos[::paso][:maximo]                 # muestra pareja de todos los géneros
	print('temas:', len(casos), '| modo', modo, flush=True)
	with pool() as p:
		res = []
		for i, r in enumerate(p.imap_unordered(evaluar, [c + (modo,) for c in casos]), 1):
			if r:
				res.append(r)
			if i % 5 == 0 or i == len(casos):
				for dest in filter(None, (os.path.join(AQUI, 'progreso.txt'), os.environ.get('TAREA_AVANCE'))):
					with open(dest, 'w', encoding='utf8') as f:
						f.write('%s: %d de %d temas' % (cual, i, len(casos)))
	errores = [r for r in res if 'error' in r]
	ok = [r for r in res if 'error' not in r]
	with open(os.path.join(AQUI, 'resultados.csv'), 'w', newline='', encoding='utf8') as f:
		w = csv.DictWriter(f, fieldnames=['base', 'genero', 'tema', 'bpm_ref', 'bpm', 'acierto', 'octava', 'f', 'engancha'])
		w.writeheader()
		w.writerows(ok)
	grupos = {}
	for r in ok:
		grupos.setdefault((r['base'], r['genero']), []).append(r)
	print('%-10s %-14s %4s %8s %8s %6s %8s' % ('base', 'genero', 'n', 'tempo%', 'octava%', 'F', 'engancha'))
	for k in sorted(grupos):
		g = grupos[k]
		eng = [r['engancha'] for r in g if r['engancha'] != '']
		print('%-10s %-14s %4d %7.0f%% %7.0f%% %6.2f %7.1fs' % (k[0], k[1], len(g), 100 * np.mean([r['acierto'] for r in g]),
			  100 * np.mean([r['octava'] != '' for r in g]), np.mean([r['f'] for r in g]), np.mean(eng) if eng else -1))
	if ok:
		print('TOTAL %d temas | tempo %.0f%% | octava %.0f%% | F %.3f | errores %d' % (
			len(ok), 100 * np.mean([r['acierto'] for r in ok]), 100 * np.mean([r['octava'] != '' for r in ok]),
			np.mean([r['f'] for r in ok]), len(errores)))
	for e in errores[:5]:
		print('ERROR', e)


if __name__ == '__main__':
	main()
