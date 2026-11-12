"""
BPM auToe (ritmo_app): el detector de BPM de Ritmo como aplicación aparte de TouchDesigner.
  * Escucha una entrada de audio (placa, micrófono) o lo que suena por una salida (loopback de WASAPI);
	solo lista los dispositivos activos de Windows (los de Configuración > Sonido). Separa el audio en las 7 bandas
	que usa el motor (mismos cortes que el banco de pruebas) y corre el MISMO motor que Ritmo.tox
	(BPM auToe/fuentes/ritmo_motor.py, sin copiarlo).
  * Ventana angosta igual a la franja de Ritmo en el visualizador de Controles (1280 x 90).
  * Manda el reloj por OSC (UDP) ~60 veces por segundo a /BPMauToe/estado; quien lo recibe (p. ej. TD)
	reconstruye la rejilla con su propio reloj (mismo reloj del sistema en la misma PC), sin tirones.
  * Recibe comandos por OSC en /BPMauToe/cmd ('tap', 'resync', 'doble', 'mitad', 'auto', 'nudge', ...).
Clic derecho en la ventana: audio que escucha, compensación, siempre arriba.
"""
import ctypes
import ctypes.wintypes
import importlib.util
import json
import math
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import winreg

import numpy as np
import pyaudiowpatch as pa                    # PortAudio con loopback de WASAPI (pip install PyAudioWPatch)
try:
	import link as linkpy                     # Ableton Link (pip install LinkPython-extern)
except ImportError:
	linkpy = None
from pythonosc import osc_bundle_builder, osc_message_builder
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from scipy.signal import butter, sosfilt, sosfilt_zi

VERSION = '0.7.0'
NOMBRE = 'BPM auToe'
OSC = '/BPMauToe/'                  # prefijo de todas las direcciones OSC
# empaquetada (.exe instalado o portable): motor e ícono van adentro.
# La configuración vive en %APPDATA%\BPM auToe (la misma para la versión instalada, el .exe y el script),
# así sobrevive a las actualizaciones. Si había una vieja al lado del programa, se toma la primera vez.
EMPAQUETADA = getattr(sys, 'frozen', False)
AQUI = os.path.dirname(sys.executable) if EMPAQUETADA else os.path.dirname(os.path.abspath(__file__))
RECURSOS = getattr(sys, '_MEIPASS', AQUI)
MOTOR = (os.path.join(RECURSOS, 'ritmo_motor.py') if EMPAQUETADA
		 else os.path.normpath(os.path.join(AQUI, '..', 'fuentes', 'ritmo_motor.py')))   # BPM auToe/fuentes
CARPETA_CONFIG = os.path.join(os.environ.get('APPDATA', AQUI), NOMBRE)
CONFIG = os.path.join(CARPETA_CONFIG, 'ritmo_app_config.json')
CONFIG_VIEJAS = [os.path.join(AQUI, 'ritmo_app_config.json'), os.path.join(AQUI, 'portable', 'ritmo_app_config.json')]
ICONO = os.path.join(RECURSOS, 'bpm_autoe.ico')
# OSC: destino_tox = Ritmo.tox en TD (solo el paquete /BPMauToe/estado); destinos = otros programas
# (valores con nombre). Un puerto solo puede escucharlo un programa a la vez.
DEFECTO = {'entrada': '', 'entrada_salida': False, 'destino_tox': '127.0.0.1:9100', 'destinos': ['127.0.0.1:9102'], 'cmd_puerto': 9101,
		   'link': True, 'link_ms': 0, 'compas': 'auto',
		   'compensacion_ms': 50, 'siempre_arriba': False, 'pelota': True, 'x': 100, 'y': 100}
RATE = 48000

# franja: ancho inicial y alto fijo (pixeles; las cajas de la derecha se acomodan al ancho, ver Ventana)
W, H = 1280, 90


def _cargarMotor():
	spec = importlib.util.spec_from_file_location('ritmo_motor', MOTOR)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


def _msg(direccion, args):
	b = osc_message_builder.OscMessageBuilder(address=direccion)
	for a in args:
		b.add_arg(a)
	return b.build()


def _hex(c):
	return '#%02x%02x%02x' % tuple(int(max(0, min(1, v)) * 255) for v in c)


def _mezcla(a, b, k):
	return tuple(x + (y - x) * k for x, y in zip(a, b))


# ====================================================================== dispositivos de audio
def _nombresWindows():
	"""Nombres de los dispositivos activos tal como los muestra Windows: 'Nombre (placa)'. PortAudio pierde los
	acentos ('micr�fonos'); con esta lista se recuperan."""
	nombres = []
	for tipo in ('Capture', 'Render'):
		try:
			k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
							   r'SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio' + '\\' + tipo)
		except OSError:
			continue
		i = 0
		while True:
			try:
				g = winreg.EnumKey(k, i)
			except OSError:
				break
			i += 1
			try:
				if winreg.QueryValueEx(winreg.OpenKey(k, g), 'DeviceState')[0] != 1:    # 1 = activo
					continue
				p = winreg.OpenKey(k, g + r'\Properties')
				nombres.append('%s (%s)' % (winreg.QueryValueEx(p, '{a45c254e-df1c-4efd-8020-67d146a850e0},2')[0],
											winreg.QueryValueEx(p, '{b3f8fa53-0004-438e-9003-51a46e139bfc},6')[0]))
			except OSError:
				pass
	return nombres


def dispositivos(p):
	"""Lo que la app puede escuchar, solo por WASAPI (sin las copias de MME, DirectSound y WDM-KS):
	entradas (micrófono, placa, cable virtual) y salidas (lo que suena por ellas, con loopback).
	Cada uno: nombre, idx, salida (bool), rate, ch, defecto (el predeterminado de Windows)."""
	try:
		w = p.get_host_api_info_by_type(pa.paWASAPI)
	except OSError:
		return []
	buenos = _nombresWindows()
	salidaDef = ''
	if w['defaultOutputDevice'] >= 0:
		salidaDef = p.get_device_info_by_index(w['defaultOutputDevice'])['name']
	lista = []
	for d in p.get_device_info_generator_by_host_api(host_api_index=w['index']):
		lb = bool(d.get('isLoopbackDevice'))
		if d['maxInputChannels'] < 1:
			continue                                      # las salidas se escuchan por su copia [Loopback]
		nombre = d['name'].replace(' [Loopback]', '') if lb else d['name']
		if '�' in nombre:
			patron = re.compile(re.escape(nombre).replace('�', '.'))
			nombre = next((b for b in buenos if patron.fullmatch(b)), nombre.replace('�', '?'))
		lista.append(dict(nombre=nombre, idx=d['index'], salida=lb, rate=float(d['defaultSampleRate']),
						  ch=int(d['maxInputChannels']),
						  defecto=(d['name'].startswith(salidaDef + ' [') if lb and salidaDef
								   else d['index'] == w['defaultInputDevice'])))
	return lista


class Remuestreo:
	"""Pasa los bloques de la frecuencia del dispositivo (Windows usa la suya: 44,1, 48 o 96 kHz) a RATE,
	con estado entre bloques para que no haya cortes: filtro antialias (si baja) e interpolación lineal."""
	def __init__(self, fs):
		self.k = fs / RATE                                   # muestras de entrada por cada muestra de salida
		self.pos = 0.0                                       # dónde cae la próxima muestra (0 = 1.ª del bloque)
		self.prev = 0.0                                      # última muestra del bloque anterior
		self.sos = butter(8, 0.45 * RATE, fs=fs, output='sos') if fs > RATE else None
		self.zi = sosfilt_zi(self.sos) * 0 if self.sos is not None else None

	def __call__(self, y):
		if abs(self.k - 1) < 1e-9 or not len(y):
			return y
		if self.sos is not None:
			y, self.zi = sosfilt(self.sos, y, zi=self.zi)
		n = len(y)
		t = np.arange(self.pos, n - 1 + 1e-9, self.k)
		x = np.concatenate(([self.prev], y))                 # x[i + 1] = y[i]: se puede interpolar desde -1
		out = np.interp(t + 1, np.arange(n + 1), x)
		self.pos = (t[-1] + self.k - n) if len(t) else self.pos - n
		self.prev = y[-1]
		return out.astype(np.float32)


# ====================================================================== motor + audio (hilo propio)
class Ritmo:
	def __init__(self, cfg):
		self.cfg = cfg
		self.mod = _cargarMotor()
		self.m = self.mod.Motor(float(RATE))
		self.rej = self.mod.Rejilla()
		self._linkT = 0.0
		self.link = None
		if linkpy is not None:
			self.link = linkpy.Link(120.0)
			self.link.startStopSyncEnabled = False
			self.link.enabled = bool(cfg['link'])
		self.m.cfg.update(bpmmin=70.0, bpmmax=180.0, silencio_db=-50.0)
		self.cola = queue.Queue()
		self.cmds = queue.Queue()
		self.lock = threading.Lock()
		self.auto = True
		self.nudge = 0
		self.confSuave = 0.0
		self.snap = None                  # lo último calculado (lo lee la ventana)
		self.latA = 0.0
		self.stream = None
		self.error = ''
		self.conSenal = time.perf_counter()
		# filtros por banda con estado (orden 2), mismos cortes que el banco de pruebas
		cortes = [('lowpass', 120), ('bandpass', (1500, 2600)), ('highpass', 8000),
				  ('lowpass', 250), ('bandpass', (700, 1400)), ('highpass', 4000)]
		self.sos = [butter(2, f, btype=t, fs=RATE, output='sos') for t, f in cortes]
		self.zi = [sosfilt_zi(s) * 0 for s in self.sos]
		self._clientes()
		self.pa = pa.PyAudio()
		self.abrirAudio(cfg.get('entrada', ''), bool(cfg.get('entrada_salida')))
		self._oscEntrada()
		threading.Thread(target=self._bucle, daemon=True).start()

	# ---------------------------------------------------------------- audio
	def abrirAudio(self, nombre, salida=False):
		"""Abre el dispositivo por su nombre: una entrada o (salida=True) lo que suena por esa salida. Si no está
		(o no se eligió ninguno), la entrada predeterminada de Windows. Acepta nombres viejos cortados (MME)."""
		if self.stream is not None:
			self.stream.close()
			self.stream = None
		lista = dispositivos(self.pa)
		d = (next((x for x in lista if x['salida'] == salida and x['nombre'] == nombre), None) or
			 next((x for x in lista if nombre and x['salida'] == salida and x['nombre'].startswith(nombre)), None) or
			 next((x for x in lista if x['defecto'] and not x['salida']), None))
		if d is None:
			self.error = 'no hay entradas de audio en Windows'
			return
		try:
			self.rem, self.ch = Remuestreo(d['rate']), d['ch']
			self.stream = self.pa.open(format=pa.paFloat32, channels=d['ch'], rate=int(d['rate']), input=True,
									   input_device_index=d['idx'], frames_per_buffer=256, stream_callback=self._cb)
			self.latA = float(self.stream.get_input_latency())
			self.cfg['entrada'], self.cfg['entrada_salida'] = d['nombre'], d['salida']
			self.error = ''
		except Exception as e:
			self.error = 'no se pudo abrir %s: %s%s' % (d['nombre'][:30], e, ' (¿la usa otro programa en modo exclusivo?)'
													   if d['salida'] else '')

	def buscarDispositivos(self):
		"""PortAudio arma la lista una sola vez: para ver una placa recién conectada hay que reiniciarlo."""
		if self.stream is not None:
			self.stream.close()
			self.stream = None
		self.pa.terminate()
		self.pa = pa.PyAudio()
		self.abrirAudio(self.cfg['entrada'], bool(self.cfg.get('entrada_salida')))

	def _cb(self, datos, n, tinfo, estado):
		# una salida sin sonido no manda bloques: el motor ve silencio ('SIN SEÑAL')
		y = np.frombuffer(datos, np.float32).reshape(-1, self.ch).mean(axis=1)
		self.cola.put(self.rem(y))
		return None, pa.paContinue

	def _bandas(self, y):
		cols = []
		for i, s in enumerate(self.sos):
			z, self.zi[i] = sosfilt(s, y, zi=self.zi[i])
			cols.append(z)
		cols.append(y)
		return np.stack(cols, 1).astype(np.float32)

	# ---------------------------------------------------------------- OSC: comandos que llegan
	def _oscEntrada(self):
		d = Dispatcher()
		for dc in (OSC + 'cmd', '/ritmo/cmd'):            # '/ritmo/cmd': lo que mandan los Ritmo.tox viejos
			d.map(dc, lambda dir_, *a: self.cmds.put(tuple(a)))
		self.srv = None
		try:
			self.srv = ThreadingOSCUDPServer(('127.0.0.1', int(self.cfg['cmd_puerto'])), d)
			threading.Thread(target=self.srv.serve_forever, daemon=True).start()
			self.error = ''
		except OSError as e:
			self.error = 'puerto de comandos ocupado: %s' % e

	def _clientes(self):
		cl = lambda d: SimpleUDPClient(d.rsplit(':', 1)[0], int(d.rsplit(':', 1)[1]))
		self.oscTox = cl(self.cfg['destino_tox'])
		self.osc = [cl(d) for d in self.cfg['destinos']]

	def puertos(self, tox, destinos, cmd):
		"""Cambia los puertos OSC sin reiniciar: tox = 'ip:puerto' de Ritmo.tox, destinos = lista 'ip:puerto',
		cmd = puerto donde la app recibe comandos."""
		self.cfg.update(destino_tox=tox, destinos=destinos)
		self._clientes()
		if int(cmd) != int(self.cfg['cmd_puerto']) or self.srv is None:
			if self.srv is not None:
				self.srv.shutdown()
				self.srv.server_close()
			self.cfg['cmd_puerto'] = int(cmd)
			self._oscEntrada()

	def comando(self, *a):
		self.cmds.put(tuple(a))

	def _aplicar(self, a, ahora):
		m, c = self.m, a[0] if a else ''
		if c == 'tap':
			m.tap(ahora)                          # corrige tempo y fase; NO apaga el automático
		elif c == 'auto':
			self.auto = bool(a[1]) if len(a) > 1 else not self.auto
		elif c == 'resync':
			m.resync(ahora + self.latV())
		elif c == 'doble':
			m.escalar(2.0, ahora)
		elif c == 'mitad':
			m.escalar(0.5, ahora)
		elif c == 'nudge':                       # 'nudge', -1 | 0 | 1 (mantenido)
			self.nudge = int(a[1]) if len(a) > 1 else 0
		elif c == 'paso' and len(a) > 1:          # corrimiento de fase de un paso (en tiempos)
			m.nudge(float(a[1]))
		elif c == 'temanuevo':
			m.temaNuevo(ahora)
		elif c == 'bpm' and len(a) > 1:
			m.fijarBpm(float(a[1]), ahora)

	# ---------------------------------------------------------------- Ableton Link (Ableton, Resolume...)
	def _link(self, barra, bpb):
		"""La app lleva la sesión de Link: tempo = velocidad de la rejilla y fase = su posición, con el 1 del
		compás en el quantum. Solo se comunica si hay diferencia (la rejilla ya es continua: no hay saltos)."""
		L = self.link
		if L is None or not L.enabled:
			return
		tl = L.clock().micros()
		bq = self.rej.posicion(time.perf_counter()) - barra           # tiempos contados desde un 1 del compás
		tt = tl + int(self.cfg['link_ms'] * 1000)                    # compensación: + = los demás más tarde
		s = L.captureAppSessionState()
		vel = self.rej.vel * 60.0
		cambio = False
		if abs(s.tempo() - vel) > 0.01:
			s.setTempo(vel, tt)
			cambio = True
		if abs(s.beatAtTime(tt, bpb) - bq) > 0.002:
			s.forceBeatAtTime(bq, tt, bpb)
			cambio = True
		if cambio:
			L.commitAppSessionState(s)

	def pares(self):
		return self.link.numPeers() if self.link is not None and self.link.enabled else -1

	def activarLink(self, si):
		self.cfg['link'] = bool(si)
		if self.link is not None:
			self.link.enabled = bool(si)

	def latV(self):
		return self.cfg['compensacion_ms'] / 1000.0

	# ---------------------------------------------------------------- bucle (~60 por segundo)
	def _bucle(self):
		try:
			ctypes.windll.winmm.timeBeginPeriod(1)          # sleep de 1 ms en Windows
		except Exception:
			pass
		m = self.m
		previo = time.perf_counter()
		while True:
			time.sleep(0.004)
			ahora = time.perf_counter()
			dt = ahora - previo
			if dt < 1 / 60.0:
				continue
			previo = ahora
			dt = min(0.25, dt)
			partes = []
			while not self.cola.empty():
				partes.append(self.cola.get_nowait())
			x = self._bandas(np.concatenate(partes)) if partes else np.zeros((0, 7), np.float32)
			while not self.cmds.empty():
				self._aplicar(self.cmds.get_nowait(), ahora)
			la = self.latA + m.hop / RATE
			m.cfg['auto'] = self.auto
			cp = self.cfg.get('compas', 'auto')                   # tiempos por compás: 'auto' o 2..7
			m.cfg['autocompas'] = cp == 'auto'
			if cp != 'auto':
				m.bpb = int(cp)
			m.alimentar(x, ahora, la, dt)
			if ahora - m.ultimaEst > 0.5:
				m.estimar(ahora - la)
			if self.nudge:
				m.ajuste += self.nudge * 0.05 * dt * m.bpm / 60.0
			if m.senal > 1e-4:
				self.conSenal = ahora
			# la salida es la Rejilla: nunca salta, sigue al motor solo cambiando la velocidad (<= 4 s)
			b = self.rej.paso(ahora, m.beat(ahora) + m.ajuste, m.bpm)
			vel = self.rej.vel * 60.0                     # velocidad real de la rejilla (en BPM)
			barra = m.barra - self.rej.k
			niv = m.niveles()
			# sin automático el tempo es fijo (lo manda el TAP): confianza plena y siempre con ritmo
			conf = m.confianza if self.auto else 1.0
			sinr = m.sinritmo if self.auto else False
			self.confSuave += (1 - math.exp(-dt / 0.7)) * (conf - self.confSuave)   # como en TD
			if ahora - self._linkT > 0.05:
				self._linkT = ahora
				self._link(barra, m.bpb)
			with self.lock:
				self.snap = dict(t=ahora, b=b, bpm=m.bpm, vel=vel, barra=barra, bpb=m.bpb, conf=conf,
								 sinritmo=sinr, niv=niv, auto=self.auto, sinSenal=ahora - self.conSenal > 3.0)
			# por cuadro:
			#  * a Ritmo.tox (destino_tox): /BPMauToe/estado, todo junto, con tiempo y beat partidos (entero +
			#    fracción) para no perder precisión; rearma la rejilla con su propio reloj
			#  * a los demás destinos: un paquete con cada valor con nombre (/BPMauToe/bpm, /BPMauToe/fase_1_4,
			#    /BPMauToe/kick...) para cualquier programa: la rejilla en el instante en que se VE (+ compensación)
			try:
				ti, bi = math.floor(ahora), math.floor(b)
				self.oscTox.send(_msg(OSC + 'estado', [
					int(ti), float(ahora - ti), int(bi), float(b - bi), float(vel), int(barra), int(m.bpb),
					float(conf), float(sinr), float(self.auto),
					float(niv['entrada']), float(niv['nivel']), float(niv['graves']), float(niv['medios']),
					float(niv['agudos']), float(niv['kick']), float(niv['caja']), float(niv['hihat']),
					float(niv['golpe_kick']), float(niv['golpe_caja']), float(niv['golpe_hihat']), float(m.bpm)]))
				pq = osc_bundle_builder.OscBundleBuilder(osc_bundle_builder.IMMEDIATELY)
				g = self.mod.grillaDe(self.rej.posicion(ahora + self.latV()), m.bpm, barra, m.bpb,
									  conf, sinr)
				g.update(niv)
				g['auto'] = float(self.auto)
				g['confianza_suave'] = self.confSuave
				# orden de salida: confianza y confianza suave juntas
				orden = [k for k in g if k != 'confianza_suave']
				orden.insert(orden.index('confianza') + 1, 'confianza_suave')
				for k in orden:
					pq.add_content(_msg(OSC + k, [float(g[k])]))
				datos = pq.build()
				for cl in self.osc:
					cl.send(datos)
			except OSError:
				pass


# ====================================================================== ventana (franja 1280 x 90)
class Ventana:
	"""Franja de BPM auToe. Se puede agrandar y achicar a lo ancho: lo de la izquierda (BPM, nivel, estado,
	luces del compás) queda a la izquierda, lo de la derecha (pelota y botones) a la derecha, y el espacio
	del medio crece o se achica. Si no entra, se ocultan en este orden: luces, ÷2 ×2 ◀ ▶, AUTO, pelota,
	TAP, RESYNC; lo oculto aparece en el menú del clic derecho."""
	FONDO = (0.085, 0.085, 0.085)
	MARGEN, SEP = 12, 8
	DERECHA = [('cuadro', 60), ('RESYNC', 90), ('TAP', 90), ('AUTO', 90), ('PELOTA', 90)]   # de derecha a izquierda
	QUITAR = ['luces', 'cuadro', 'AUTO', 'PELOTA', 'TAP', 'RESYNC']                          # orden en que se ocultan
	CUADRO = [('÷2', 0, 28, 47, 75), ('×2', 32, 60, 47, 75), ('◀', 0, 28, 15, 43), ('▶', 32, 60, 15, 43)]

	def __init__(self, raiz, ritmo, cfg):
		self.r, self.rt, self.cfg = raiz, ritmo, cfg
		raiz.title(NOMBRE)
		# si la posición guardada quedó fuera de todos los monitores (p. ej. se desconectó uno), a la vista
		pt = ctypes.wintypes.POINT(int(cfg['x']) + 40, int(cfg['y']) + 20)
		if not ctypes.windll.user32.MonitorFromPoint(pt, 0):
			cfg['x'], cfg['y'] = 100, 100
		raiz.geometry('%dx%d+%d+%d' % (int(cfg.get('ancho', W)), H, cfg['x'], cfg['y']))
		raiz.minsize(230, H)
		raiz.resizable(True, False)
		raiz.attributes('-topmost', bool(cfg['siempre_arriba']))
		raiz.protocol('WM_DELETE_WINDOW', self.salir)
		self.vArriba = tk.BooleanVar(value=bool(cfg['siempre_arriba']))
		self.vLink = tk.BooleanVar(value=bool(cfg['link']))
		c = self.c = tk.Canvas(raiz, width=W, height=H, bg=_hex(self.FONDO), highlightthickness=0)
		c.pack(fill='both', expand=True)
		Y = self.Y = lambda y: H - y                              # coordenadas de la franja -> lienzo
		self.linea = c.create_rectangle(0, H - 2, W, H, fill=_hex((0.16,) * 3), width=0)
		self.tBpm = c.create_text(20, Y(66), anchor='w', text='--', fill='white', font=('Segoe UI', 24, 'bold'))
		self.vuFondo = c.create_rectangle(20, Y(34), 250, Y(28), fill=_hex((0.18,) * 3), width=0)
		self.vu = c.create_rectangle(20, Y(34), 20, Y(28), fill=_hex((0.3, 0.8, 0.4)), width=0)
		self.confFondo = c.create_rectangle(20, Y(25), 250, Y(24), fill=_hex((0.2,) * 3), width=0)
		self.conf = c.create_rectangle(20, Y(25), 20, Y(24), fill=_hex((0.45, 0.75, 0.95)), width=0)
		self.tEstado = c.create_text(20, Y(10), anchor='w', fill='#d9d9d9', font=('Segoe UI', 9))
		self.anchoBpm = 230
		self.luces, self.xLuces = [], []
		self.pFondo = c.create_rectangle(0, 0, 0, 0, fill='#0f0f0f', outline='#404040')
		self.pPiso = c.create_line(0, 0, 0, 0, fill='#bfbfbf')
		self.pBola = c.create_oval(0, 0, 0, 0, fill='white', width=0)
		self.btn = {}                                             # nombre -> (rectángulo, texto)
		for nombre in ['AUTO', 'TAP', 'RESYNC'] + [x[0] for x in self.CUADRO]:
			self.btn[nombre] = (c.create_rectangle(0, 0, 0, 0, fill=_hex((0.2,) * 3), width=0),
								c.create_text(0, 0, text=nombre, fill='white',
											  font=('Segoe UI', 10 if nombre in ('AUTO', 'TAP', 'RESYNC') else 8)))
		self.cajas = {}                                           # nombre -> (x0, x1, y0, y1) visibles ahora
		self.ocultos = set()
		self.apretado = ('', -9.0)
		self.ancho = 0
		c.bind('<Configure>', lambda e: self._acomodar(e.width))
		c.bind('<ButtonPress-1>', self.clic)
		c.bind('<ButtonRelease-1>', lambda e: self.rt.comando('nudge', 0))
		c.bind('<Button-3>', self.menu)
		# teclas (con la ventana activa)
		self.aviso = ('', -9.0)
		raiz.bind('<space>', lambda e: self._tecla('TAP'))
		raiz.bind('<KeyPress-r>', lambda e: self._tecla('RESYNC'))
		raiz.bind('<KeyPress-R>', lambda e: self._tecla('RESYNC'))
		for k, f in (('f', lambda: self._comp(-10)), ('g', lambda: self._comp(10)),
					 ('h', lambda: self._linkMs(-5)), ('j', lambda: self._linkMs(5))):
			raiz.bind('<KeyPress-%s>' % k, lambda e, f=f: f())
			raiz.bind('<KeyPress-%s>' % k.upper(), lambda e, f=f: f())
		self._flechaHasta = 0.0
		raiz.bind('<KeyPress-Left>', lambda e: self._flecha(-1))
		raiz.bind('<KeyPress-Right>', lambda e: self._flecha(1))
		raiz.bind('<KeyRelease-Left>', lambda e: self._soltarFlecha())
		raiz.bind('<KeyRelease-Right>', lambda e: self._soltarFlecha())
		self.vCompas = tk.StringVar(value=str(cfg.get('compas', 'auto')))
		self.n = 0
		self.dibujar()

	# ---------------------------------------------------------------- acomodar al ancho
	def _acomodar(self, ancho):
		self.ancho = ancho
		c, Y = self.c, self.Y
		c.coords(self.linea, 0, H - 2, ancho, H)
		izq = 20 + max(120, self.anchoBpm) + 20                  # fin del bloque de la izquierda
		nl = max(1, len(self.luces) or 4)
		lugar = {'luces': nl * 46 + 20}
		lugar.update({n: w + self.SEP for n, w in self.DERECHA})
		visibles = set(lugar)
		for n in self.QUITAR:
			if sum(lugar[v] for v in visibles) <= ancho - izq - self.MARGEN:
				break
			visibles.discard(n)
		self.ocultos = set(lugar) - visibles
		self.cajas = {}
		x = ancho - self.MARGEN
		for nombre, w in self.DERECHA:
			if nombre not in visibles:
				continue
			if nombre == 'cuadro':
				for sub, a, b, y0, y1 in self.CUADRO:
					self.cajas[sub] = (x - w + a, x - w + b, y0, y1)
			else:
				self.cajas[nombre] = (x - w, x, 15, 75)
			x -= w + self.SEP
		for nombre, (rr, tt) in self.btn.items():
			if nombre in self.cajas:
				x0, x1, y0, y1 = self.cajas[nombre]
				c.coords(rr, x0, Y(y1), x1, Y(y0))
				c.coords(tt, (x0 + x1) / 2, Y((y0 + y1) / 2))
				c.itemconfig(rr, state='normal')
				c.itemconfig(tt, state='normal')
			else:
				c.itemconfig(rr, state='hidden')
				c.itemconfig(tt, state='hidden')
		est = 'normal' if 'PELOTA' in self.cajas else 'hidden'
		for o in (self.pFondo, self.pPiso, self.pBola):
			c.itemconfig(o, state=est)
		if 'PELOTA' in self.cajas:
			x0, x1, y0, y1 = self.cajas['PELOTA']
			c.coords(self.pFondo, x0, Y(y1), x1, Y(y0))
			c.coords(self.pPiso, x0 + 1, Y(y0 + 2), x1 - 1, Y(y0 + 2))
		# luces del compás: pegadas al bloque de la izquierda
		self.xLuces = [izq + 25 + i * 46 for i in range(nl)]
		for i, o in enumerate(self.luces):
			if i < len(self.xLuces):
				xx = self.xLuces[i]
				c.coords(o, xx - 16, Y(45) - 16, xx + 16, Y(45) + 16)
			c.itemconfig(o, state='hidden' if 'luces' in self.ocultos else 'normal')

	def _luces(self, n):
		for i in self.luces:
			self.c.delete(i)
		self.luces = [self.c.create_oval(0, 0, 0, 0, width=0) for _ in range(n)]
		self._acomodar(self.ancho)

	# ---------------------------------------------------------------- dibujo (~60 fps)
	def dibujar(self):
		with self.rt.lock:
			s = self.rt.snap
		if s and self.ancho:
			self._pintar(s)
		self.r.after(16, self.dibujar)

	def _pintar(self, s):
		c, Y = self.c, self.Y
		ahora = time.perf_counter() + self.rt.latV()             # la grilla en el instante en que se VE
		b = s['b'] + (ahora - s['t']) * s['vel'] / 60.0             # con la velocidad real de la rejilla
		bb = b - s['barra']
		n = max(1, int(s['bpb']))
		tiempo = int(math.floor(bb % n)) + 1
		golpe = math.exp(-(b % 1.0) * 60.0 / s['bpm'] / 0.1)
		texto = '%.1f BPM' % s['bpm']
		if c.itemcget(self.tBpm, 'text') != texto:
			c.itemconfig(self.tBpm, text=texto)
			x0, _, x1, _ = c.bbox(self.tBpm)
			if abs((x1 - x0 - 4) - self.anchoBpm) > 1:             # la barra mide lo mismo que el texto
				self.anchoBpm = x1 - x0 - 4
				c.coords(self.vuFondo, 20, Y(34), 20 + self.anchoBpm, Y(28))
				c.coords(self.confFondo, 20, Y(25), 20 + self.anchoBpm, Y(24))
				self._acomodar(self.ancho)
		e = s['niv']['entrada']
		col = (0.3, 0.8, 0.4) if e < 0.8 else ((0.95, 0.8, 0.2) if e < 0.95 else (0.95, 0.3, 0.25))
		c.coords(self.vu, 20, Y(34), 20 + self.anchoBpm * e, Y(28))
		c.itemconfig(self.vu, fill=_hex(col))
		c.coords(self.conf, 20, Y(25), 20 + self.anchoBpm * s['conf'], Y(24))
		if len(self.luces) != n:
			self._luces(n)
		for i, o in enumerate(self.luces):
			base = (1.0, 0.75, 0.2) if i == 0 else (0.45, 0.8, 0.95)
			apag = (0.22,) * 3
			if s['sinritmo']:
				luz = tuple(v * (1.4 if i + 1 == tiempo else 1) for v in apag)
			else:
				luz = _mezcla(tuple(v * 0.6 for v in base), base, golpe) if i + 1 == tiempo else apag
			c.itemconfig(o, fill=_hex(luz))
		# botones: AUTO prendido en verde, destello del apretado
		nombreAp, t0 = self.apretado
		luzB = 1.0 if self.rt.nudge else max(0.0, 1 - (time.perf_counter() - t0) / 0.3)
		for nombre, (rr, tt) in self.btn.items():
			colB = (0.3, 0.55, 0.35) if (nombre == 'AUTO' and s['auto']) else (0.2,) * 3
			if nombre == 'AUTO':                                  # AUDIO = automático; MANUAL = se tapea
				et = 'AUDIO' if s['auto'] else 'MANUAL'
				if c.itemcget(tt, 'text') != et:
					c.itemconfig(tt, text=et)
			if nombre == nombreAp:
				colB = _mezcla(colB, (0.85, 0.85, 0.9), 0.55 * luzB)
			c.itemconfig(rr, fill=_hex(colB))
		if 'PELOTA' in self.cajas:
			self._pelota(b, s)
		self.n += 1
		if self.n % 6 == 0 and time.perf_counter() - self.aviso[1] > 1.5:
			fase = round(self.rt.m.ajuste * 60000.0 / max(s['bpm'], 1))
			txt = ('v%s · SIN SEÑAL · elegir audio (clic derecho)' % VERSION if s['sinSenal'] else
				   'v%s · %s · %d%%%s · OSC %s' % (VERSION, 'AUDIO' if s['auto'] else 'MANUAL', round(s['conf'] * 100),
												   (' · fase %+d ms' % fase) if fase else '',
												   ' '.join(d.rsplit(':', 1)[1] for d in self.cfg['destinos'])))
			pares = self.rt.pares()
			if pares >= 0:
				txt += ' · LINK %d' % pares                      # cuántos programas siguen la sesión de Link
			if self.rt.error:
				txt = 'v%s · %s' % (VERSION, self.rt.error)
			c.itemconfig(self.tEstado, text=txt)

	def _pelota(self, b, s):
		"""Igual que ritmo_pelota.glsl: rebota cada 2 tiempos (parábola), altura y golpe según la confianza."""
		c, Y = self.c, self.Y
		x0, x1, y0, y1 = self.cajas['PELOTA']
		on = self.cfg['pelota']
		f = (b / 2.0) % 1.0
		k = self.rt.confSuave if on else 0.0                   # confianza suavizada (~0,7 s), como en TD
		ms = (b % 1.0) * 60000.0 / s['bpm']
		fondo = 0.06 + 0.16 * k * (ms < 70)
		c.itemconfig(self.pFondo, fill=_hex((fondo,) * 3))
		hh = y1 - y0
		r = hh * 0.1
		piso = y0 + 2
		alto = hh - 2 - 2 * r - hh * 0.06
		h = 4 * f * (1 - f) * k
		ap = (math.exp(-f * 25) + math.exp(-(1 - f) * 25)) * k
		cx, cy = (x0 + x1) / 2, piso + r + alto * h
		rx, ry = r * (1 + 0.35 * ap), r * (1 - 0.3 * ap)
		c.coords(self.pBola, cx - rx, Y(cy + ry), cx + rx, Y(cy - ry))
		uno = int(math.floor((b - s['barra']) % max(1, s['bpb']))) == 0
		c.itemconfig(self.pBola, fill='#4d4d4d' if not on else ('#ffbf40' if uno else '#f2f2f2'))

	# ---------------------------------------------------------------- mouse
	ACCION = {'AUTO': ('auto',), 'TAP': ('tap',), 'RESYNC': ('resync',), '÷2': ('mitad',), '×2': ('doble',),
			  '◀': ('nudge', -1), '▶': ('nudge', 1)}

	def clic(self, e):
		x, y = e.x, H - e.y
		for nombre, (x0, x1, y0, y1) in self.cajas.items():
			if x0 <= x <= x1 and y0 <= y <= y1:
				if nombre == 'PELOTA':
					self.cfg['pelota'] = not self.cfg['pelota']
					return
				self.apretado = (nombre, time.perf_counter())
				self.rt.comando(*self.ACCION[nombre])
				return

	def menu(self, e):
		mn = tk.Menu(self.r, tearoff=0)
		# lo que no entra en la ventana (RESYNC es el último en salir)
		quitados = [n for n in ('TAP', 'RESYNC', 'AUTO') if n in self.ocultos]
		for n in quitados:
			et = n if n != 'AUTO' else ('AUDIO → pasar a MANUAL' if self.rt.auto else 'MANUAL → pasar a AUDIO')
			mn.add_command(label=et, command=lambda n=n: self.rt.comando(*self.ACCION[n]))
		if 'cuadro' in self.ocultos:
			mn.add_command(label='÷2  (mitad de tempo)', command=lambda: self.rt.comando('mitad'))
			mn.add_command(label='×2  (doble de tempo)', command=lambda: self.rt.comando('doble'))
			mn.add_command(label='◀  correr la fase un paso', command=lambda: self.rt.comando('paso', -0.02))
			mn.add_command(label='▶  correr la fase un paso', command=lambda: self.rt.comando('paso', 0.02))
		if 'PELOTA' in self.ocultos:
			mn.add_command(label='Pelota: ' + ('apagar' if self.cfg['pelota'] else 'prender'),
						   command=lambda: self.cfg.update(pelota=not self.cfg['pelota']))
		if quitados or {'cuadro', 'PELOTA'} & self.ocultos:
			mn.add_separator()
		# audio: solo lo que Windows tiene activo; entradas arriba, salidas (lo que suena) abajo
		ent = tk.Menu(mn, tearoff=0)
		sal = bool(self.cfg.get('entrada_salida'))
		clave = lambda nombre, salida: ('S:' if salida else 'E:') + nombre
		self.vEntrada = tk.StringVar(value=clave(self.cfg['entrada'], sal))
		lista = dispositivos(self.rt.pa)
		for salida, titulo in ((False, 'ENTRADAS  (micrófono, placa, cable virtual)'),
							   (True, 'SALIDAS  (escuchar lo que suena por ahí)')):
			ent.add_command(label=titulo, state='disabled')
			for d in (x for x in lista if x['salida'] == salida):
				ent.add_radiobutton(label='   ' + d['nombre'] + ('   · predeterminada de Windows' if d['defecto'] else ''),
									value=clave(d['nombre'], salida), variable=self.vEntrada,
									command=lambda d=d: self.rt.abrirAudio(d['nombre'], d['salida']))
			ent.add_separator()
		ent.add_command(label='Actualizar la lista  (si se conectó o cambió algo)', command=self.rt.buscarDispositivos)
		mn.add_cascade(label='Audio que escucha  (ahora: %s%s)' % ('salida · ' if sal else '', self.cfg['entrada'][:40]),
					   menu=ent)
		mn.add_command(label='Compensación +10 ms  (ahora %d ms)' % self.cfg['compensacion_ms'],
					   command=lambda: self._comp(10))
		mn.add_command(label='Compensación -10 ms', command=lambda: self._comp(-10))
		if self.rt.link is not None:
			mn.add_separator()
			self.vLink.set(bool(self.cfg['link']))
			mn.add_checkbutton(label='Ableton Link (Ableton, Resolume...)', variable=self.vLink,
							   command=lambda: self.rt.activarLink(self.vLink.get()))
			mn.add_command(label='Link: compensación +5 ms  (ahora %d ms)' % self.cfg['link_ms'],
						   command=lambda: self._linkMs(5))
			mn.add_command(label='Link: compensación -5 ms', command=lambda: self._linkMs(-5))
		cm = tk.Menu(mn, tearoff=0)
		self.vCompas.set(str(self.cfg.get('compas', 'auto')))
		cm.add_radiobutton(label='Automático (3 o 4)', value='auto', variable=self.vCompas, command=self._compas)
		for n in range(2, 8):
			cm.add_radiobutton(label='%d tiempos' % n, value=str(n), variable=self.vCompas, command=self._compas)
		mn.add_cascade(label='Compás  (ahora: %s)' % ('automático' if self.cfg.get('compas', 'auto') == 'auto'
													  else '%s tiempos' % self.cfg['compas']), menu=cm)
		mn.add_command(label='Puertos OSC…', command=self._puertos)
		mn.add_separator()
		self.vArriba.set(bool(self.cfg['siempre_arriba']))
		mn.add_checkbutton(label='Mostrar ventana sobre todo', variable=self.vArriba, command=self._arriba)
		mn.add_command(label='OSC: manda a %s · comandos en %s' % (', '.join(self.cfg['destinos']),
																  self.cfg['cmd_puerto']), state='disabled')
		mn.add_command(label='Teclas: ESPACIO tap · R resync · ◀ ▶ fase · F/G compensación · H/J Link',
					   state='disabled')
		mn.tk_popup(e.x_root, e.y_root)

	# ---------------------------------------------------------------- teclas
	def _tecla(self, nombre):
		self.apretado = (nombre, time.perf_counter())             # destello del botón (si está a la vista)
		self.rt.comando(*self.ACCION[nombre])
		self._avisar(nombre)

	def _flecha(self, signo):
		# la repetición del teclado manda apretar/soltar seguido: se ignora el soltar si vuelve a apretar enseguida
		self._flechaHasta = 0.0
		if self.rt.nudge != signo:
			self.rt.comando('nudge', signo)
			self.apretado = ('◀' if signo < 0 else '▶', time.perf_counter())
			self._avisar('desfasaje manual ' + ('◀' if signo < 0 else '▶'))

	def _soltarFlecha(self):
		self._flechaHasta = time.perf_counter() + 0.06
		self.r.after(80, self._fin_flecha)

	def _fin_flecha(self):
		if self._flechaHasta and time.perf_counter() >= self._flechaHasta:
			self._flechaHasta = 0.0
			self.rt.comando('nudge', 0)

	def _avisar(self, texto):
		"""Mensaje corto en la línea de estado (1,5 s)."""
		self.aviso = (texto, time.perf_counter())
		self.c.itemconfig(self.tEstado, text='v%s · %s' % (VERSION, texto))

	def _linkMs(self, d):
		self.cfg['link_ms'] = self.cfg['link_ms'] + d
		self._avisar('compensación de Link %+d ms  (H / J)' % self.cfg['link_ms'])

	def _comp(self, d):
		self.cfg['compensacion_ms'] = max(0, self.cfg['compensacion_ms'] + d)
		self._avisar('compensación %d ms  (F / G)' % self.cfg['compensacion_ms'])

	def _compas(self):
		v = self.vCompas.get()
		self.cfg['compas'] = v if v == 'auto' else int(v)

	def _puertos(self):
		"""Ventanita para cambiar los puertos OSC (se aplican sin reiniciar)."""
		w = tk.Toplevel(self.r)
		w.title('Puertos OSC')
		w.resizable(False, False)
		w.attributes('-topmost', True)
		campos = [('Ritmo.tox en TouchDesigner (ip:puerto)', self.cfg['destino_tox']),
				  ('Otros programas (ip:puerto, separados por coma)', ', '.join(self.cfg['destinos'])),
				  ('Comandos que recibe la app (puerto)', str(self.cfg['cmd_puerto']))]
		vs = []
		for i, (et, val) in enumerate(campos):
			tk.Label(w, text=et, anchor='w').grid(row=i, column=0, sticky='w', padx=8, pady=4)
			v = tk.StringVar(value=val)
			tk.Entry(w, textvariable=v, width=34).grid(row=i, column=1, padx=8, pady=4)
			vs.append(v)

		def aplicar():
			try:
				tox = vs[0].get().strip()
				dest = [d.strip() for d in vs[1].get().split(',') if d.strip()]
				for d in [tox] + dest:
					int(d.rsplit(':', 1)[1])
				self.rt.puertos(tox, dest, int(vs[2].get()))
				guardar(self.cfg)
				w.destroy()
			except (ValueError, IndexError):
				self._avisar('puerto inválido: usar ip:puerto (p. ej. 127.0.0.1:9102)')
		tk.Button(w, text='Aplicar', command=aplicar).grid(row=3, column=1, sticky='e', padx=8, pady=8)

	def _arriba(self):
		self.cfg['siempre_arriba'] = bool(self.vArriba.get())
		self.r.attributes('-topmost', self.cfg['siempre_arriba'])

	def salir(self):
		self.cfg['x'], self.cfg['y'] = self.r.winfo_x(), self.r.winfo_y()
		self.cfg['ancho'] = self.r.winfo_width()
		guardar(self.cfg)
		if self.rt.stream is not None:
			self.rt.stream.close()
		self.r.destroy()


def cargar():
	cfg = dict(DEFECTO)
	for ruta in [CONFIG] + CONFIG_VIEJAS:
		try:
			with open(ruta, encoding='utf8') as f:
				cfg.update(json.load(f))
			break
		except (OSError, ValueError):
			pass
	return cfg


def guardar(cfg):
	os.makedirs(CARPETA_CONFIG, exist_ok=True)
	with open(CONFIG, 'w', encoding='utf8') as f:
		json.dump(cfg, f, indent=1, ensure_ascii=False)


if __name__ == '__main__':
	try:                                              # ícono propio en la barra de tareas (no el de Python)
		ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Toe.BPMAUTOE')
	except Exception:
		pass
	cfg = cargar()
	raiz = tk.Tk()
	if os.path.exists(ICONO):
		raiz.iconbitmap(default=ICONO)
	v = Ventana(raiz, Ritmo(cfg), cfg)
	# versión instalada: al abrir busca si hay una versión nueva en GitHub y avisa (no actualiza sola)
	if EMPAQUETADA or os.environ.get('BPMAUTOE_PROBAR_VERSION'):
		import actualizar
		raiz.after(1500, lambda: actualizar.al_abrir(raiz, VERSION, v.salir))
	raiz.mainloop()
