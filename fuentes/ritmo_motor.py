"""
ritmo_motor: motor del tempo de Ritmo.tox (numpy puro, sin TD: se puede probar afuera).

Entra por cuadro el audio de ese cuadro ya filtrado en bandas (columnas: kick, caja, hihat, graves,
medios, agudos, completo). Calcula:
  * envolventes por banda (ataque / caída) con ganancia automática (AGC) -> nivel, graves, medios...
  * golpes de kick / caja / hihat (pulso 1 que cae) por flujo de energía con umbral adaptativo
  * curva de golpes (onset) a ~190 Hz -> BPM automático (autocorrelación con peine + preferencia
	por el centro del rango) con histéresis: en partes sin ritmo mantiene el último tempo
  * fase del tiempo por PLL (media circular de los golpes sobre el reloj), el 1 del compás por
	acentos del bombo y el compás (3 o 4) por periodicidad de acentos
  * grilla: fases de 1/16 de tiempo a 16 compases en el instante en que la imagen se VE
	(se adelanta la latencia de audio + la de video)
Todo el tiempo interno es 'tiempo de sonido' (cuándo sonó en la sala).
"""
import math
import numpy as np

BANDAS = ['kick', 'caja', 'hihat', 'graves', 'medios', 'agudos', 'completo']
CADENA_OCTAVAS = True     # desempatar 3:4 / 2:3 por la cadena de octavas
PESO_FASE_BOMBO = 1.0     # peso del bombo al decidir dónde cae el tiempo (fase)
PREFIERE_DOBLE = 0.6       # el doble gana si tiene al menos esta fracción de la fuerza del más lento
PESO_BOMBO = 0.0         # cuánto suma el golpe del bombo a la curva de golpes (además del flujo espectral)
DIVISIONES = [('1_16', 0.25, False), ('1_8', 0.5, False), ('1_4', 1, False), ('1_2', 2, False),
			  ('1', 1, True), ('2', 2, True), ('4', 4, True), ('8', 8, True), ('16', 16, True)]


def grillaDe(b, bpm, barra, bpb, confianza=0.0, sinritmo=False):
	"""Canales de la grilla para la posición b (en tiempos) a 'bpm', con el 1 del compás en 'barra'."""
	bb = b - barra
	bars = bb / bpb
	# 'beats' se manda acotado (los CHOP guardan 32 bits: con números grandes pierde precisión);
	# 1680 tiempos es múltiplo de compases de 3, 4, 5, 6 y 7
	out = {'bpm': bpm, 'beats': b % 1680.0, 'tiempo': math.floor(bb % bpb) + 1,
		   'compas': math.floor(bars), 'compas_tiempos': bpb,
		   'golpe_tiempo': math.exp(-(b % 1.0) * 60.0 / bpm / 0.1),
		   'golpe_compas': math.exp(-(bb % bpb) * 60.0 / bpm / 0.15),
		   'confianza': confianza, 'sinritmo': float(sinritmo)}
	for nombre, n, esCompas in DIVISIONES:
		out['fase_' + nombre] = ((bars / n) if esCompas else (bb / n)) % 1.0
	return out


class Rejilla:
	"""Salida continua de la grilla: la posición NUNCA salta ni retrocede; sigue al motor solo cambiando
	la velocidad (la usan la app externa y quien quiera una rejilla sin tirones para sus animaciones).
	  * Diferencia de fase con el motor: se corrige acelerando o frenando y termina en <= 4 s
		(desvío de velocidad hasta max(4 %, lo necesario para medio tiempo en 4 s)).
	  * Cambio de tempo del motor (detector, TAP, x2, /2, fuente externa): la velocidad lo sigue suave.
	  * Si la diferencia pasa de medio tiempo, se corre la numeración del compás (k), no la posición.
	Uso por cuadro: b = rej.paso(t, motor.beat(t) + motor.ajuste, motor.bpm); barra = motor.barra - rej.k."""
	PLAZO = 4.0          # s: una corrección de fase termina como máximo en este tiempo
	TAU = 0.5            # s: constante de la corrección (errores chicos: suave y lenta)
	TAU_TEMPO = 0.4      # s: cuánto tarda la velocidad en seguir un cambio de tempo

	def __init__(self):
		self.b, self.t, self.bpm, self.vel, self.k = None, 0.0, 120.0, 2.0, 0

	def paso(self, t, bMotor, bpmMotor):
		if self.b is None:
			self.b, self.t, self.bpm = bMotor, t, bpmMotor
			self.vel = bpmMotor / 60.0
			return self.b
		dt = max(0.0, min(0.25, t - self.t))
		self.t = t
		self.b += self.vel * dt                                       # avanza con la velocidad de antes
		self.bpm += (1 - math.exp(-dt / self.TAU_TEMPO)) * (bpmMotor - self.bpm)
		bps = max(0.2, self.bpm / 60.0)
		e = bMotor - self.k - self.b
		if abs(e) > 0.5:                                              # lejos: se corre la numeración, no la posición
			n = round(e)
			self.k += n
			e -= n
		tope = max(0.04, 0.6 / (bps * self.PLAZO))                   # 0,6 (y no 0,5): margen para la cola
		c = max(-tope, min(tope, e / (bps * self.TAU)))
		self.vel = bps * (1.0 + c)
		return self.b

	def posicion(self, t):
		"""Posición en el instante t (entre pasos se extrapola con la velocidad actual)."""
		return self.b + (t - self.t) * self.vel if self.b is not None else 0.0


class Motor:
	def __init__(self, rate=48000.0):
		self.cfg = dict(modo='auto', bpmmin=70.0, bpmmax=180.0, auto=True, auto1=False, autocompas=True,
						ataque=0.01, caida=0.25, agc=True, ganancia=1.0, caidagolpes=0.25)
		self.bpm, self.t0, self.b0 = 120.0, 0.0, 0.0
		self.barra = 0                  # en qué tiempo (entero) empieza el compás
		self.bpb = 4
		self.confianza = 0.0
		self.sinritmo = True
		self._setRate(rate)
		self._pend = None               # candidato a tempo nuevo (bpm, veces)
		self._pend1 = None              # candidato a nuevo 1 del compás
		self._pendc = None              # candidato a compás nuevo
		self.env = np.zeros(len(BANDAS))
		self.pico = np.full(len(BANDAS), 1e-3)
		self.golpe = np.zeros(3)
		self._umbral = np.full(3, 1e-3)
		self._ultgolpe = np.full(3, -9.0)
		self.taps = []
		self.ajuste = 0.0
		self._faseP = 0.0
		self._nivel = 0.0
		self.estabilidad = 0.0      # 0 = banda (respira) .. 1 = electrónica (estable); modo 'auto'
		self._hist = []
		self._errFase = 0.05
		self.senal = 0.0
		self.ultimaEst = 0.0
		self._vuelta = None
		self._ref = 1e-6
		self._sinDesde = None
		self._temaNuevo = True
		self._gracia = 0.0

	def _setRate(self, rate):
		self.rate = float(rate)
		self.hop = max(64, int(round(self.rate / 190.0)))
		self.fs = self.rate / self.hop
		n = int(10 * self.fs)
		self.O = np.zeros(n)            # curva de golpes (todas las bandas)
		self.K = np.zeros(n)            # curva de golpes del bombo
		self.T = np.zeros(n)            # tiempo de sonido de cada muestra
		self.prevE = None
		self.resto = np.zeros((0, len(BANDAS)))
		self._cola = np.zeros(1024)
		self._ventana = np.hanning(1024)
		self._nb = int(10000 / (self.rate / 1024))          # bandas hasta 10 kHz
		self._prevL = None
		self._mSF, self._mK = None, None

	# ------------------------------------------------------------------ reloj
	def beat(self, t):
		return self.b0 + (t - self.t0) * self.bpm / 60.0

	def fijarBpm(self, bpm, t):
		bpm = float(min(400.0, max(20.0, bpm)))
		self.b0, self.t0, self.bpm = self.beat(t), t, bpm

	# ------------------------------------------------------------------ audio
	def alimentar(self, x, tcook, latA, dt):
		"""x: (muestras, 7) audio filtrado de este cuadro; tcook: tiempo del cuadro; latA: latencia
		de entrada (s); dt: duración del cuadro (s). Devuelve nada; deja env/golpe al día."""
		# corrección de fase pendiente: se aplica suave (~0,3 s) para que la grilla no dé saltos
		if self._faseP:
			paso = self._faseP * (1 - math.exp(-dt / 0.3))
			tope = 0.04 * self.bpm / 60.0 * dt                  # nunca más de ±4 % de velocidad
			paso = max(-tope, min(tope, paso))
			self.b0 += paso
			self._faseP -= paso
		if x.shape[0] == 0:
			self.env *= math.exp(-dt / max(1e-3, self.cfg['caida']))
			self.golpe *= math.exp(-dt / max(1e-3, self.cfg['caidagolpes']))
			return
		# envolventes por banda (RMS del cuadro)
		rms = np.sqrt(np.mean(x * x, axis=0)) * self.cfg['ganancia']
		self.senal = float(rms[-1])                         # nivel crudo (antes del AGC): para avisar "sin señal"
		self._nivel += (1 - math.exp(-dt / 0.4)) * (self.senal - self._nivel)   # nivel de entrada (~0,4 s)
		if self.cfg['agc']:
			self.pico = np.maximum(rms, self.pico * math.exp(-dt / 8.0))      # pico con caída lenta
			v = rms / np.maximum(self.pico, 1e-3)
		else:
			v = rms * 4.0
		a = 1 - math.exp(-dt / max(1e-3, self.cfg['ataque']))
		c = 1 - math.exp(-dt / max(1e-3, self.cfg['caida']))
		self.env += np.where(v > self.env, a, c) * (v - self.env)
		# curva de golpes por hops
		y = np.vstack([self.resto, x]) if len(self.resto) else x
		nh = len(y) // self.hop
		self.golpe *= math.exp(-dt / max(1e-3, self.cfg['caidagolpes']))
		if nh:
			h = y[:nh * self.hop].reshape(nh, self.hop, -1)
			E = np.log1p(1e4 * np.mean(h[:, :, :3] * h[:, :, :3], axis=1))   # (nh, 3) kick caja hihat
			prev = self.prevE if self.prevE is not None else E[0]
			d = np.diff(np.vstack([prev, E]), axis=0)
			self.prevE = E[-1]
			f = np.maximum(d, 0)                                               # flujo positivo
			sf = self._flujoEspectral(y[:nh * self.hop, 6], nh)
			# curva de golpes = flujo espectral (cualquier ataque: piano, guitarra, caja...) + bombo,
			# cada uno normalizado a su nivel medio
			if self._mSF is None:                         # arranca con el nivel real (no con un mínimo)
				self._mSF, self._mK = sf.mean() + 1e-4, f[:, 0].mean() + 1e-4
			self._mSF += 0.002 * (sf.mean() - self._mSF)
			self._mK += 0.002 * (f[:, 0].mean() - self._mK)
			o = sf / max(self._mSF, 1e-6) + PESO_BOMBO * f[:, 0] / max(self._mK, 1e-6)
			fin = len(y) - (np.arange(nh) + 1) * self.hop                      # muestras después del hop
			ts = tcook - fin / self.rate - latA
			self.O = np.roll(self.O, -nh); self.O[-nh:] = o[-len(self.O):]
			self.K = np.roll(self.K, -nh); self.K[-nh:] = f[-len(self.K):, 0]
			self.T = np.roll(self.T, -nh); self.T[-nh:] = ts[-len(self.T):]
			# golpes por banda: umbral adaptativo + 80 ms mínimos entre golpes
			self._umbral += (1 - 0.99 ** nh) * (f.mean(axis=0) - self._umbral)
			for i in range(3):
				j = np.nonzero(f[:, i] > 2.5 * self._umbral[i] + 0.05)[0]
				if len(j) and ts[j[-1]] - self._ultgolpe[i] > 0.08:
					self._ultgolpe[i] = ts[j[-1]]
					self.golpe[i] = 1.0
		self.resto = y[nh * self.hop:]

	def _flujoEspectral(self, s, nh):
		"""Flujo espectral por hop: suma del aumento de energía (log) en cada banda fina hasta 10 kHz."""
		NF = 1024
		largo = np.concatenate([self._cola, s])
		ini = len(self._cola)
		fines = ini + (np.arange(nh) + 1) * self.hop
		marcos = np.stack([largo[e - NF:e] if e >= NF else np.pad(largo[:e], (NF - e, 0)) for e in fines])
		mag = np.abs(np.fft.rfft(marcos * self._ventana, axis=1))[:, :self._nb]
		Lg = np.log1p(100.0 * mag)
		prev = self._prevL if self._prevL is not None else Lg[0]
		d = np.diff(np.vstack([prev, Lg]), axis=0)
		self._prevL = Lg[-1]
		self._cola = largo[:fines[-1]][-NF:]
		return np.maximum(d, 0).mean(axis=1)

	# ------------------------------------------------------------------ BPM automático
	def estimar(self, ahora):
		"""Cada ~0.5 s: tempo, fase, 1 del compás y compás."""
		self.ultimaEst = ahora
		L = int(8 * self.fs)
		o = self.O[-L:]
		reciente = self.O[-int(1.5 * self.fs):].mean()
		# puerta de silencio: por debajo del umbral es silencio aunque el ruido de fondo tenga 'golpes';
		# el tempo queda como estaba y la referencia se congela (no se acostumbra al ruido)
		if self._nivel < 10 ** (self.cfg.get('silencio_db', -50.0) / 20.0):
			if not self.sinritmo or self._sinDesde is None:
				self._sinDesde = ahora
			if ahora - self._sinDesde > 2.0:
				self._temaNuevo = True
			self.confianza, self.sinritmo, self._vuelta = 0.0, True, None
			return
		# nivel de golpes de referencia: promedio lento (~20 s), no el pico (un pico suelto lo dejaba alto)
		self._nEst = getattr(self, '_nEst', 0) + 1
		if self._ref <= 1e-6 or self._nEst < 10:      # primeros ~5 s: sigue lo que escucha (sin el golpe del arranque)
			self._ref = reciente
		else:
			self._ref += (1 - math.exp(-0.5 / 20.0)) * (reciente - self._ref)
		if o.std() < 1e-4 or reciente < 0.25 * self._ref:      # silencio o parte sin golpes: se mantiene todo
			if not self.sinritmo or self._sinDesde is None:
				self._sinDesde = ahora
			if ahora - self._sinDesde > 2.0:
				self._temaNuevo = True                           # (modo banda) terminó el tema
			self.confianza, self.sinritmo = 0.0, True
			self._vuelta = None
			return
		self._sinDesde = None
		if self.sinritmo and self._vuelta is None:
			self._vuelta = ahora                                 # volvió el ritmo: no mezclar con lo de antes
		if self._vuelta is not None:
			desde = ahora - self._vuelta
			if desde < 3.0:
				return
			if desde < 8.0:
				o = self.O[-int(desde * self.fs):]
			else:
				self._vuelta = None
		cand, prom, ac, lag = self._tempo(o)
		self._medirEstabilidad(cand, ahora)
		cand4 = self._tempo(self.O[-int(4 * self.fs):])[0]
		self.confianza = max(0.0, min(1.0, 0.6 * prom + 0.4 * max(0.0, ac[int(lag)] * 2)))
		self.sinritmo = self.confianza < 0.35
		estable = abs(cand4 / cand - 1) < 0.04 or min(abs(cand4 / cand - 2), abs(cand4 / cand - 0.5)) < 0.04
		if self.cfg['auto'] and not self.sinritmo and estable:
			self._aceptar(cand, ahora)
		if not self.sinritmo:
			self._pll(ahora)
			if self.cfg['auto1'] or self.cfg['autocompas']:
				self._acentos()

	def _tempo(self, o):
		"""Tempo de un tramo de la curva de golpes: (bpm, prominencia, autocorrelación, lag)."""
		L = len(o)
		# se resta la tendencia lenta (~0,3 s) y se queda lo que sobresale: picos más marcados
		k = max(3, int(0.3 * self.fs))
		x = np.maximum(o - np.convolve(o, np.ones(k) / k, 'same'), 0)
		x = x - x.mean()
		n = 1 << int(math.ceil(math.log2(2 * L)))
		X = np.fft.rfft(x, n)
		ac = np.fft.irfft(X * np.conj(X), n)[:L]
		ac = ac / max(ac[0], 1e-9)
		lmin = 60 * self.fs / self.cfg['bpmmax']
		lmax = 60 * self.fs / self.cfg['bpmmin']
		lags = np.arange(int(lmin), int(math.ceil(lmax)) + 1)
		lags = lags[(lags > 2) & (lags * 4 < L)]
		idx = np.arange(L)
		# el tiempo verdadero también se repite a la mitad (corcheas) y al doble; sumar la mitad evita
		# la confusión 3:2 (p. ej. 93 en vez de 140 con hi-hats en corcheas)
		s = (np.interp(lags, idx, ac) + 0.5 * np.interp(lags / 2.0, idx, ac)
			 + 0.5 * np.interp(2 * lags, idx, ac) + 0.25 * np.interp(4 * lags, idx, ac))
		bpms = 60 * self.fs / lags
		centro = math.sqrt(self.cfg['bpmmin'] * self.cfg['bpmmax'])
		s = s * (0.75 + 0.25 * np.exp(-0.5 * (np.log2(bpms / centro) / 0.8) ** 2))
		k = int(np.argmax(s))
		# parientes 3:4 / 2:3: con hi-hats en semicorcheas un pulso cada 3 también se repite (p. ej. 168 en vez
		# de 127). Se comparan el ganador y sus parientes por la fuerza de su cadena de octavas (el tiempo
		# verdadero también se repite a la mitad, al doble y al cuádruple; el falso no)
		if CADENA_OCTAVAS:
			def cadena(l):
				return sum(w * np.interp(l * f, idx, ac) for f, w in ((0.25, 0.5), (0.5, 0.75), (1, 1.0), (2, 0.75), (4, 0.5))
						   if l * f < L - 1)
			mejor, puntaje = k, -1e9
			for r in (1.0, 0.75, 4 / 3.0, 2 / 3.0, 1.5):
				lr = lags[k] * r
				if lags[0] <= lr <= lags[-1]:
					kk = int(np.argmin(np.abs(lags - lr)))
					sc = cadena(lags[kk]) * (0.75 + 0.25 * np.exp(-0.5 * (np.log2(bpms[kk] / centro) / 0.8) ** 2))
					if sc > puntaje * (1.0 if r == 1.0 else 1.05):          # el ganador original tiene preferencia
						mejor, puntaje = kk, sc
			k = mejor
		# mitad de tempo: un tema a 140 también se repite cada 2 tiempos (70). Si el doble entra en el
		# rango y tiene al menos el 60 % de la fuerza, se prefiere el doble (lo habitual en la música).
		kd = int(np.argmin(np.abs(lags - lags[k] / 2.0)))
		if abs(lags[kd] - lags[k] / 2.0) <= 1.0 and s[kd] >= PREFIERE_DOBLE * s[k]:
			k = kd
		# refinamiento parabólico
		dl = 0.0
		if 0 < k < len(s) - 1:
			den = s[k - 1] - 2 * s[k] + s[k + 1]
			if abs(den) > 1e-12:
				dl = 0.5 * (s[k - 1] - s[k + 1]) / den
		cand = 60 * self.fs / (lags[k] + dl)
		prom = float((s[k] - np.median(s)) / (np.max(s) - np.min(s) + 1e-9))
		return cand, prom, ac, lags[k]

	# Modo: 'banda' = cada tema tiene su tempo; al terminar un tema (>2 s sin ritmo) el próximo tempo
	# se toma enseguida. 'electronica' = el tempo cambia poco y despacio; saltos con mucha insistencia.
	# insistencia (en estimaciones de 0,5 s) que necesita un cambio DENTRO de un tema, según su tamaño:
	# necesita = hasta 15 %, salto = más de 15 %, octava = mitad / doble
	MODOS = {'banda': dict(tol=0.03, suave=0.4, necesita=3, salto=12, octava=30),
			 'electronica': dict(tol=0.06, suave=0.3, necesita=10, salto=30, octava=60)}

	def _modo(self):
		"""Parámetros según el modo. En 'auto' se mezclan banda y electrónica según qué tan estable es
		el tempo: electrónica (cuantizada) = estable; banda en vivo = respira."""
		modo = self.cfg.get('modo', 'auto')
		if modo in self.MODOS:
			return self.MODOS[modo]
		a, b, e = self.MODOS['banda'], self.MODOS['electronica'], self.estabilidad
		return {k: a[k] + (b[k] - a[k]) * e for k in a}

	def _medirEstabilidad(self, cand, ahora):
		"""0 = el tempo respira (banda), 1 = muy estable (electrónica). Mira los últimos ~20 s."""
		self._hist = [(t, c) for t, c in self._hist if ahora - t < 20.0] + [(ahora, cand)]
		if len(self._hist) < 12:
			return
		c = np.array([x for _, x in self._hist])
		c = c * np.where(c / np.median(c) > 1.4, 0.5, 1.0) * np.where(c / np.median(c) < 0.7, 2.0, 1.0)   # misma octava
		disp = float(np.median(np.abs(c / np.median(c) - 1)))
		obj = max(0.0, min(1.0, 1 - disp / 0.012)) * max(0.0, min(1.0, 1 - self._errFase / 0.06))
		self.estabilidad += 0.15 * (obj - self.estabilidad)

	def _aceptar(self, cand, ahora):
		md = self._modo()
		# continuidad de octava: si da casi justo la mitad / el doble del tempo que venía, se mantiene la octava
		for f in (2.0, 0.5):
			c2 = cand * f
			if abs(c2 / self.bpm - 1) < 0.08 and self.cfg['bpmmin'] <= c2 <= self.cfg['bpmmax']:
				cand = c2
				break
		r = cand / self.bpm
		modo = self.cfg.get('modo', 'auto')
		banda = modo == 'banda' or (modo == 'auto' and self.estabilidad < 0.5)
		if self._temaNuevo:                            # arranque / tras silencio / TEMA NUEVO (ambos modos)
			# tema nuevo: se toma en cuanto 2 estimaciones seguidas coinciden; 10 s de gracia para corregir
			if self._pend and abs(cand / self._pend[0] - 1) < 0.03:
				self.fijarBpm(0.5 * (cand + self._pend[0]), ahora)
				self._temaNuevo, self._pend, self._gracia = False, None, ahora + 10.0
			else:
				self._pend = (cand, 1)
			return
		if banda and ahora < self._gracia:
			md = dict(md, necesita=2, octava=4)
		if abs(r - 1) < md['tol']:                 # mismo tempo: se afina (más lento en electrónica)
			self.fijarBpm(self.bpm + md['suave'] * (cand - self.bpm), ahora)
			self._pend = None
			return
		octava = min(abs(r - 2), abs(r - 0.5)) < 0.04
		if octava:
			necesita = md['octava']                    # mitad / doble: muchísima insistencia
		elif abs(r - 1) > 0.15:
			necesita = md['salto']                     # salto grande dentro del tema: varios segundos
		else:
			necesita = md['necesita']
		if self._pend and abs(cand / self._pend[0] - 1) < 0.03:
			self._pend = (0.5 * (cand + self._pend[0]), self._pend[1] + 1)
		else:
			self._pend = (cand, 1)
		if self._pend[1] >= necesita:
			self.fijarBpm(self._pend[0], ahora)
			self._pend = None

	def _pll(self, ahora):
		"""Fase por 'peine': de 48 posiciones de la grilla elige la que más coincide con los golpes
		fuertes (sin la tendencia lenta), con peso extra del bombo, que marca los tiempos y no los
		contratiempos. Corrige de a poco hacia esa posición."""
		w = max(3, int(0.3 * self.fs))
		m = self.T > ahora - 5.0
		if m.sum() < max(20, w + 1):               # el suavizado no puede ser mas largo que el tramo
			return
		o, k, t = self.O[m], self.K[m], self.T[m]
		x = np.maximum(o - np.convolve(o, np.ones(w) / w, 'same'), 0)
		x = x / (x.mean() + 1e-9) + PESO_FASE_BOMBO * k / (k.mean() + 1e-9)
		fr = (self.beat(t) + self._faseP) % 1.0               # contando la corrección que falta aplicar
		fases = np.arange(48) / 48.0
		d = np.abs(((fr[None, :] - fases[:, None]) + 0.5) % 1.0 - 0.5)       # distancia circular
		puntaje = (x[None, :] * np.exp(-0.5 * (d / 0.04) ** 2)).sum(axis=1)
		j = int(np.argmax(puntaje))
		if puntaje[j] < 1.2 * puntaje.mean():
			return                                  # no hay una posición clara
		e = (fases[j] + 0.5) % 1.0 - 0.5           # dónde caen los golpes respecto del reloj
		self._errFase += 0.2 * (abs(e) - self._errFase)
		self._faseP -= 0.5 * e                      # se aplica de a poco en alimentar (sin saltos)

	def _acentos(self):
		m = self.K > 0
		t, k = self.T[m], self.K[m]
		if len(t) < 8:
			return
		b = self.beat(t)
		cerca = np.abs(b - np.round(b)) < 0.15
		nb = np.round(b[cerca]).astype(int)
		w = k[cerca]
		if len(nb) < 8:
			return
		# acento por tiempo (últimos ~24 tiempos)
		ultimo = int(nb.max())
		serie = np.zeros(24)
		j = ultimo - nb
		ok = (j >= 0) & (j < 24)
		np.add.at(serie, 23 - j[ok], w[ok])
		if self.cfg['autocompas']:
			sc = serie - serie.mean()
			def corr(l):
				return float(np.dot(sc[l:], sc[:-l]) / (np.dot(sc, sc) + 1e-9))
			c3, c4 = corr(3), corr(4)
			nuevo = 3 if (c3 > c4 + 0.3 and c3 > 0.3) else (4 if c4 > c3 else None)
			if nuevo and nuevo != self.bpb:
				self._pendc = (nuevo, (self._pendc[1] + 1) if self._pendc and self._pendc[0] == nuevo else 1)
				if self._pendc[1] >= 8:
					self.bpb, self._pendc = nuevo, None
			else:
				self._pendc = None
		if self.cfg['auto1']:
			acc = np.zeros(self.bpb)
			np.add.at(acc, (nb - self.barra) % self.bpb, w)
			p = int(np.argmax(acc))
			if p != 0 and acc[p] > 1.25 * (acc.sum() - acc[p]) / max(1, self.bpb - 1):
				self._pend1 = (p, (self._pend1[1] + 1) if self._pend1 and self._pend1[0] == p else 1)
				if self._pend1[1] >= 3:
					self.barra += p
					self._pend1 = None
			else:
				self._pend1 = None

	# ------------------------------------------------------------------ manual
	def tap(self, t):
		if self.taps and t - self.taps[-1] > 2.0:
			self.taps = []
		self.taps = (self.taps + [t])[-8:]
		if len(self.taps) >= 2:
			iv = np.diff(self.taps)
			med = np.median(iv)
			iv = iv[np.abs(iv - med) < 0.2 * med]
			if len(iv):
				self.fijarBpm(60.0 / iv.mean(), t)
		self.b0, self.t0 = float(round(self.beat(t))), t       # el toque cae en un tiempo

	def temaNuevo(self, t):
		"""Corte entre temas: olvida los golpes escuchados y vuelve a escuchar desde ahora
		(el primer tempo firme se toma enseguida)."""
		self.O[:] = 0
		self.K[:] = 0
		self._temaNuevo, self._pend, self._vuelta, self._sinDesde = True, None, None, None
		self.sinritmo, self.confianza, self._ref, self._nEst = True, 0.0, 1e-6, 0

	def resync(self, t):
		# este tiempo pasa a ser el 1; el corrimiento manual (◀ ▶) se mantiene
		self.barra = int(round(self.beat(t) + self.ajuste))

	def escalar(self, f, t):
		self.fijarBpm(self.bpm * f, t)

	def nudge(self, tiempos):
		self.ajuste += tiempos

	def externo(self, bpm, beats, t):
		"""Link / MIDI clock: el reloj lo manda otro."""
		self.bpm, self.b0, self.t0 = float(bpm), float(beats), t

	# ------------------------------------------------------------------ salida
	def grilla(self, t):
		# ajuste = corrimiento manual de fase (◀ ▶)
		return grillaDe(self.beat(t) + self.ajuste, self.bpm, self.barra, self.bpb, self.confianza, self.sinritmo)

	def niveles(self):
		e = np.clip(self.env, 0, 1)
		d = dict(zip(BANDAS, e))
		entrada = max(0.0, min(1.0, (20 * math.log10(max(self.senal, 1e-6)) + 60) / 60.0))   # -60..0 dB
		return {'entrada': entrada, 'nivel': d['completo'], 'graves': d['graves'], 'medios': d['medios'], 'agudos': d['agudos'],
				'kick': d['kick'], 'caja': d['caja'], 'hihat': d['hihat'],
				'golpe_kick': self.golpe[0], 'golpe_caja': self.golpe[1], 'golpe_hihat': self.golpe[2]}
