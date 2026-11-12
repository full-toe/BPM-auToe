"""
logica de BPM auToe (BPMauToe.tox; antes Ritmo.tox): une el motor (DAT 'motor') con TD. Un solo Script CHOP
('calculo') la llama por cuadro: lee el audio filtrado del cuadro, alimenta el motor, elige la fuente de
tempo y saca todos los canales. El audio entra por la ENTRADA del tox (conectar un Audio Device In, o el
CHOP de audio que se quiera): así el tox no depende de la placa de cada computadora.
La salida pasa por la Rejilla del motor: la grilla nunca salta, solo acelera o frena (corrige en <= 4 s).
Fuentes (Fuente = Prioridad): App externa (ritmo_app, OSC) > MIDI Clock si llega > Link si hay pares >
Automático > Tap/manual. El detector interno queda siempre de respaldo: si la app deja de mandar, sigue él.
Latencias: audio = buffer de la placa + un hop; video = 2 cuadros + Proyector (ms). La grilla se
calcula para el instante en que la imagen se VE y los golpes se fechan cuando SONARON.
"""
import math
import time
import numpy as np

VERSION = '1.2.3'           # subir en cada cambio (se ve en la franja del tempo y en el parámetro Versión)
OSC = '/BPMauToe/'           # prefijo OSC de la app BPM auToe

# El estado vive en el DAT 'estado' (que no se edita): así, cambiar esta lógica o el motor no reinicia
# la detección. Si el motor cambió de código, se pasa su estado a una instancia nueva.
_M = me.parent().op('estado').module.M
_T = me.parent().op('estado').module.T


def Motor(comp):
	m = _M.get(comp.path)
	clase = comp.op('motor').module.Motor
	if m is None:
		m = clase(48000.0)
		_M[comp.path] = m
	elif type(m) is not clase:
		n = clase(m.rate)
		n.__dict__.update(m.__dict__)
		_M[comp.path] = m = n
	return m


def Reiniciar(comp):
	_M.pop(comp.path, None)


def _cfg(comp, m):
	p = comp.par
	m.cfg.update(bpmmin=p.Bpmmin.eval(), bpmmax=max(p.Bpmmin.eval() + 10, p.Bpmmax.eval()),
				 auto=bool(p.Automatico.eval()), auto1=bool(p.Auto1.eval()), autocompas=bool(p.Autocompas.eval()),
				 ataque=p.Ataque.eval(), caida=p.Caida.eval(), agc=bool(p.Agc.eval()),
				 ganancia=p.Ganancia.eval(), caidagolpes=p.Caidagolpes.eval(), modo=p.Modo.eval(),
				 silencio_db=p.Silenciodb.eval() if p['Silenciodb'] is not None else -50.0)
	if not p.Autocompas.eval():
		m.bpb = max(1, int(p.Tiempos.eval()))


def FuenteAudio(comp):
	"""El CHOP de audio conectado a la entrada del tox (p. ej. un Audio Device In), o None."""
	cs = comp.inputConnectors[0].connections if comp.inputConnectors else []
	return cs[0].owner if cs else None


def Latencias(comp, rate):
	la = 0.0
	if not comp.par.Entradaprueba.eval():
		ia = FuenteAudio(comp)
		if ia is not None and ia.OPType == 'audiodeviceinCHOP':            # buffer de la placa
			u, v = ia.par.bufflenunit.eval(), ia.par.bufferlength.eval()
			la = v if u == 'seconds' else (v / rate if u == 'samples' else v / project.cookRate)
		p = comp.par['Latenciaentrada']
		la += (p.eval() / 1000.0) if p is not None else 0.0                # otra fuente: a mano
	la += Motor(comp).hop / rate
	lv = 2.0 / project.cookRate + comp.par.Proyectorms.eval() / 1000.0
	return la, lv


def _fuente(comp, ahora):
	elegida = comp.par.Fuente.eval()
	if elegida == 'app':                     # app elegida a mano: si no está mandando, respaldo interno
		return 'app' if _appViva(comp, ahora) else ('auto' if comp.par.Automatico.eval() else 'tap')
	if elegida != 'prioridad':
		return elegida
	if _appViva(comp, ahora):          # la app va primero: ella misma lleva la sesión de Link
		return 'app'
	if comp.par.Midiclock.eval() and ahora - _T.get(comp.path + 'clk', -9) < 1.0:
		return 'midi'
	lk = comp.op('link')
	if comp.par.Link.eval() and lk is not None and lk.numChans and _peers(lk) > 0:
		return 'link'
	return 'auto' if comp.par.Automatico.eval() else 'tap'


# ---------------------------------------------------------------- app externa (ritmo_app por OSC)
# /ritmo/estado: [t entero, t fracción, beat entero, beat fracción, bpm, barra, tiempos por compás,
#   confianza, sin ritmo, auto, entrada, nivel, graves, medios, agudos, kick, caja, hihat, golpes x3].
# t es time.perf_counter() de la app: en la misma PC es el mismo reloj que acá, así la grilla se
# reconstruye para cada cuadro sin los tirones del momento en que llega cada mensaje.
NIVELES_APP = ['entrada', 'nivel', 'graves', 'medios', 'agudos', 'kick', 'caja', 'hihat',
			   'golpe_kick', 'golpe_caja', 'golpe_hihat']


def App(comp, args):
	"""Lo llama app_osc_callbacks por cada mensaje de estado de la app."""
	if len(args) >= 21:
		_T[comp.path + 'app'] = (list(args), time.perf_counter())


def _appViva(comp, ahora):
	a = _T.get(comp.path + 'app')
	return a is not None and ahora - a[1] < 0.5


def _app(comp, *args):
	"""Si la fuente activa es la app, le manda el comando (los botones de acá manejan la app)."""
	o = comp.op('app_cmd')
	if _T.get(comp.path + 'f') != 'app' or o is None:
		return False
	o.sendOSC(OSC + 'cmd', list(args))
	return True


def _peers(lk):
	c = lk.chan('peers') or lk.chan('numpeers')
	return c.eval() if c is not None else 0


def Cocinar(s):
	comp = s.parent()
	m = Motor(comp)
	_cfg(comp, m)
	ahora = time.perf_counter()
	dt = min(0.25, max(1e-3, ahora - _T.get(comp.path, ahora - 1 / 60)))
	_T[comp.path] = ahora
	x = np.zeros((0, 7))
	if s.inputs and s.inputs[0].numChans >= 7:
		inp = s.inputs[0]
		if abs(inp.rate - m.rate) > 1:
			m._setRate(inp.rate)
		x = inp.numpyArray()[:7].T
	la, lv = Latencias(comp, m.rate)
	cap = _T.get(comp.path + 'captura')                 # Capturar(): guarda el audio que entra (para afinar)
	if cap is not None and len(x):
		cap.append(x[:, 6].astype(np.float32).copy())
	m.alimentar(x, ahora, la, dt)
	f = _fuente(comp, ahora)
	_T[comp.path + 'f'] = f
	if f == 'link':
		lk = comp.op('link')
		m.externo(lk['tempo'].eval(), lk['beats'].eval(), ahora)
	elif f == 'midi':
		e = _T.get(comp.path + 'clkest')
		if e:
			m.externo(e[0], e[1] + (ahora - e[2]) * e[0] / 60.0, ahora)
	elif f == 'app':
		a = _T[comp.path + 'app'][0]
		t, b, bpm = a[0] + a[1], a[2] + a[3], a[4]
		m.externo(bpm, b + (ahora - t) * bpm / 60.0, ahora)
		m.ajuste = 0.0                                   # el corrimiento ◀ ▶ ya viene en el beat de la app
		m.barra, m.bpb = int(a[5]), max(1, int(a[6]))
		m.confianza, m.sinritmo = float(a[7]), a[8] > 0.5
	m.cfg['auto'] = m.cfg['auto'] and f == 'auto'
	if f in ('auto', 'tap') and ahora - m.ultimaEst > 0.5:
		m.estimar(ahora - la)
	# ◀ ▶ mantenidos: el reloj corre un 5 % más rápido / lento mientras estén apretados
	nd = _T.get(comp.path + 'nudge', 0)
	if nd:
		m.ajuste += nd * 0.05 * dt * m.bpm / 60.0
	# la grilla avanza con el reloj de cuadros de TD (parejo, el mismo de las animaciones), atado suavemente
	# al reloj real: así no hay tirones por el momento exacto en que se cocina cada cuadro
	base = absTime.seconds
	dif = ahora - base
	off = _T.get(comp.path + 'off')
	off = dif if off is None or abs(dif - off) > 0.15 else off + 0.02 * (dif - off)
	_T[comp.path + 'off'] = off
	# Rejilla: la grilla de salida nunca salta; sigue al motor (y a la fuente externa) solo con velocidad
	mod = comp.op('motor').module
	rj = _M.get(comp.path + 'rej')
	if rj is None or type(rj) is not mod.Rejilla:
		n = mod.Rejilla()
		if rj is not None:
			n.__dict__.update(rj.__dict__)
		_M[comp.path + 'rej'] = rj = n
	tf = base + off
	rj.paso(tf, m.beat(tf) + m.ajuste, m.bpm)
	g = mod.grillaDe(rj.posicion(tf + lv), m.bpm, m.barra - rj.k, m.bpb, m.confianza, m.sinritmo)
	g.update(m.niveles())
	if f == 'app':
		a = _T[comp.path + 'app'][0]
		g.update(zip(NIVELES_APP, a[10:21]))
		if len(a) > 21:
			g['bpm'] = a[21]               # tempo (a[4] es la velocidad real de la rejilla, que corrige fase)
	# luz del botón apretado: prendida mientras se mantiene ◀ ▶, destello corto en los demás
	idx, t0 = _T.get(comp.path + 'btn', (0, -9))
	g['boton'] = idx
	g['boton_luz'] = 1.0 if nd else max(0.0, 1.0 - (ahora - t0) / 0.3)
	g['ajuste'] = max(0.0, 1.0 - (ahora - _T.get(comp.path + 'tnuevo', -9)) / 0.6)   # destello de TEMA NUEVO
	# confianza suavizada (~0,7 s) para lo visual: sin saltos bruscos de porcentaje (una cuenta por cuadro)
	if f == 'tap':                         # sin automático el tempo es fijo (TAP): confianza plena, siempre con ritmo
		g['confianza'], g['sinritmo'] = 1.0, 0.0
	cs = _T.get(comp.path + 'confs', g['confianza'])
	cs += (1 - math.exp(-dt / 0.7)) * (g['confianza'] - cs)
	_T[comp.path + 'confs'] = cs
	g['confianza_suave'] = cs
	# automático prendido (con la app, el de la app): el botón muestra AUDIO o MANUAL
	g['auto'] = float(_T[comp.path + 'app'][0][9] > 0.5) if f == 'app' else float(comp.par.Automatico.eval())
	g['fuente'] = ['auto', 'tap', 'link', 'midi', 'app'].index(f) if f in ('auto', 'tap', 'link', 'midi', 'app') else 0
	# todos los valores de una vez (escribir canal por canal desde Python cuesta ~40 µs cada uno);
	# los nombres los pone el Rename CHOP 'nombres' (se fija solo si cambian)
	s.copyNumpyArray(np.array(list(g.values()), dtype=np.float32).reshape(-1, 1))
	nombres = ' '.join(g)
	if _T.get(comp.path + 'nombres') != nombres:
		comp.op('nombres').par.renameto = nombres
		_T[comp.path + 'nombres'] = nombres
	if absTime.frame % 6:
		return
	# estado visible en el panel (cada 6 cuadros y solo si cambió)
	_mostrar(comp, 'Bpm', round(m.bpm, 2))
	_mostrar(comp, 'Confianza', round(m.confianza, 2))
	_mostrar(comp, 'Tiemposdetectados', m.bpb)
	_mostrar(comp, 'Latenciaaudio', round(la * 1000, 1))
	_mostrar(comp, 'Latenciavideo', round(lv * 1000, 1))
	_mostrar(comp, 'Desfasaje', round((la + lv) * 1000, 1))
	_revisarPanel(comp)
	PanelTextos(comp)


def _mostrar(comp, nombre, v):
	p = comp.par[nombre]
	if p is not None and p.eval() != v:
		p.val = v


# ---------------------------------------------------------------- botones
def _t(comp):
	return time.perf_counter()


def Tap(comp):
	if _app(comp, 'tap'):
		return
	Motor(comp).tap(_t(comp))                            # corrige tempo y fase; NO apaga el automático


def TemaNuevo(comp):
	if _app(comp, 'temanuevo'):
		return
	Motor(comp).temaNuevo(_t(comp))
	_T[comp.path + 'tnuevo'] = _t(comp)


def Resync(comp):
	if _app(comp, 'resync'):
		return
	Motor(comp).resync(_t(comp) + Latencias(comp, Motor(comp).rate)[1])


def Doble(comp):
	if _app(comp, 'doble'):
		return
	Motor(comp).escalar(2.0, _t(comp))


def Mitad(comp):
	if _app(comp, 'mitad'):
		return
	Motor(comp).escalar(0.5, _t(comp))


def Nudge(comp, signo):
	if _app(comp, 'paso', signo * 0.02):
		return
	Motor(comp).nudge(signo * 0.02)


def FijarBpm(comp, bpm):
	Motor(comp).fijarBpm(bpm, _t(comp))


# ---------------------------------------------------------------- panel (franja horizontal / vertical)
# Lo dibujan 'panel_fondo' (GLSL, lee las cajas de la tabla 'panel_layout'), 'panel_bpm' y 'panel_textos';
# 'pelota_t' ubica la pelotita y 'panel_final' junta todo (es lo que se ve en el nodo y en la ventana).
# Página Panel: orientación (horizontal / vertical) y tamaño (ampliado / medio / reducido).
# Al achicar se oculta, en este orden: luces del compás, ÷2 ×2 ◀ ▶ (medio), AUTO y pelota (reducido).
# TAP y RESYNC quedan siempre. Coordenadas en pixeles, origen abajo a la izquierda.
BOTONES = ['AUTO', 'TAP', 'RESYNC', '÷2', '×2', '◀', '▶']          # mismo orden que en ritmo_panel.glsl
OCULTAR = {'ampliado': set(), 'medio': {'luces', 'cuadro'}, 'reducido': {'luces', 'cuadro', 'AUTO', 'PELOTA'}}
FUENTES = ['prioridad', 'auto', 'tap', 'link', 'midi', 'app']
NOMBRES_FUENTE = {'prioridad': 'PRIORIDAD', 'auto': 'AUDIO', 'tap': 'MANUAL', 'link': 'LINK', 'midi': 'MIDI',
				  'app': 'APP'}
M, G = 10, 8                     # margen y separación


def Diseno(orient, tam, n, ancho=0):
	"""Cajas del panel: devuelve dict con W, H, yb (base del bloque del BPM), luces (x, y, paso, radio) o None
	y cajas {nombre: (x0, y0, x1, y1)} de los botones visibles y de la PELOTA.
	ancho (horizontal): ancho mínimo; si sobra lugar, los botones se corren al borde derecho."""
	oc = OCULTAR.get(tam, set())
	n = max(1, int(n))
	cajas, luces = {}, None
	if orient == 'horizontal':
		H, x = 90, 270
		if 'luces' not in oc:
			luces = (x + 23, 45, 46, 16)
			x += n * 46 + 10
		for nom in ('PELOTA', 'AUTO', 'TAP', 'RESYNC'):
			if nom not in oc:
				cajas[nom] = (x, 15, x + 90, 75)
				x += 90 + G
		if 'cuadro' not in oc:
			cajas.update({'÷2': (x, 47, x + 28, 75), '×2': (x + 32, 47, x + 60, 75),
						  '◀': (x, 15, x + 28, 43), '▶': (x + 32, 15, x + 60, 43)})
			x += 60 + G
		W = x - G + 12
		if ancho > W:                                          # completa el ancho: botones a la derecha
			d = ancho - W
			cajas = {k: (a + d, b, c + d, e) for k, (a, b, c, e) in cajas.items()}
			W = ancho
		return {'W': W, 'H': H, 'yb': 0, 'luces': luces, 'cajas': cajas}
	# vertical: de arriba hacia abajo (y negativa) y al final se corre todo por el alto
	W = 200
	y = -90                                                    # bloque del BPM arriba
	if 'luces' not in oc:
		paso = min(46.0, (W - 2 * M) / float(n))               # si no entran, más juntas y más chicas
		luces = [(W - n * paso) / 2.0 + paso / 2.0, y - 25, paso, min(16.0, paso * 0.35)]
		y -= 50
	ancho = W - 2 * M
	if tam == 'reducido':                                      # TAP y RESYNC lado a lado
		w2 = (ancho - G) / 2.0
		cajas['TAP'] = (M, y - 50, M + w2, y)
		cajas['RESYNC'] = (M + w2 + G, y - 50, W - M, y)
		y -= 50 + G
	else:
		if 'PELOTA' not in oc:
			cajas['PELOTA'] = ((W - 180) / 2.0, y - 120, (W + 180) / 2.0, y)
			y -= 120 + G
		for b in ('AUTO', 'TAP', 'RESYNC'):
			if b not in oc:
				cajas[b] = (M, y - 44, W - M, y)
				y -= 44 + G
	if 'cuadro' not in oc:
		w4 = (ancho - 3 * G) / 4.0
		for i, b in enumerate(('÷2', '×2', '◀', '▶')):
			cajas[b] = (M + i * (w4 + G), y - 36, M + i * (w4 + G) + w4, y)
		y -= 36 + G
	H = int(round(-y - G + M))
	cajas = {k: (a, b + H, c, d + H) for k, (a, b, c, d) in cajas.items()}
	if luces:
		luces[1] += H
	return {'W': W, 'H': H, 'yb': H - 90, 'luces': luces, 'cajas': cajas}


def AplicarPanel(comp):
	"""Arma el panel según la página Panel: tabla de cajas para el GLSL, tamaños, BPM, pelotita y ventana."""
	orient = comp.par.Panelorient.eval() if comp.par['Panelorient'] is not None else 'horizontal'
	tam = comp.par.Paneltam.eval() if comp.par['Paneltam'] is not None else 'ampliado'
	n = Motor(comp).bpb
	L = Diseno(orient, tam, n, comp.par.Panelancho.eval() if comp.par['Panelancho'] is not None else 0)
	W, H, yb, cj = int(L['W']), int(L['H']), L['yb'], L['cajas']
	xb = min(250, W - 20)                                      # fin de las barras de nivel y confianza
	filas = [[W, H, 1 if L['luces'] else 0, n], [20, yb + 28, xb, yb + 34], [20, yb + 24, xb, yb + 25],
			 list(L['luces']) if L['luces'] else [0, 0, 0, 0]]
	filas += [list(cj[b]) if b in cj else [0, 0, 0, 0] for b in BOTONES]
	filas.append([0, 0, 0, 0])
	t = comp.op('panel_layout')
	t.clear()
	t.appendRows([['%.2f' % v for v in f] for f in filas])
	comp.op('panel_fondo').par.resolutionw, comp.op('panel_fondo').par.resolutionh = W, H
	pb = comp.op('panel_bpm')
	pb.par.positionx, pb.par.positiony = 20, (yb + 66) - H / 2.0          # el texto se ubica desde el centro
	pb.par.fontsizex = 29 if orient == 'vertical' else 34                # en la vertical (angosta) un poco menor
	pt = comp.op('pelota_t')
	pt.par.resolutionw, pt.par.resolutionh = W, H
	if 'PELOTA' in cj:
		x0, y0, x1, y1 = cj['PELOTA']
		pt.par.sx, pt.par.sy = (x1 - x0) / W, (y1 - y0) / H
		pt.par.tx, pt.par.ty = (x0 + x1) / 2.0 - W / 2.0, (y0 + y1) / 2.0 - H / 2.0
	else:
		pt.par.sx = pt.par.sy = 0.0001                                    # oculta
	vp = comp.op('ventana_panel')
	vp.par.w, vp.par.h = W, H
	w = comp.op('ventana')
	w.par.winw, w.par.winh = W, H
	# dónde aparece la ventana en la pantalla principal: horizontal arriba al centro, vertical a la izquierda
	# al centro
	w.par.justifyoffsetto = 'primarydisplay'
	w.par.justifyh, w.par.justifyv = {'horizontal': ('center', 'top'), 'vertical': ('left', 'center')}.get(orient, ('center', 'top'))
	_T[comp.path + 'lay'] = L
	_T[comp.path + 'laykey'] = (orient, tam, n)
	_T.pop(comp.path + 'textos', None)


def _revisarPanel(comp):
	orient = comp.par.Panelorient.eval() if comp.par['Panelorient'] is not None else 'horizontal'
	tam = comp.par.Paneltam.eval() if comp.par['Paneltam'] is not None else 'ampliado'
	if _T.get(comp.path + 'laykey') != (orient, tam, Motor(comp).bpb):
		AplicarPanel(comp)


def PanelClick(comp, x, y):
	"""x, y en pixeles del panel (origen abajo a la izquierda)."""
	L = _T.get(comp.path + 'lay')
	if not L:
		return
	for nombre, (x0, y0, x1, y1) in L['cajas'].items():
		if not (x0 <= x <= x1 and y0 <= y <= y1):
			continue
		if nombre == 'PELOTA':
			comp.par.Pelota = not comp.par.Pelota.eval()
			return
		_T[comp.path + 'btn'] = (BOTONES.index(nombre) + 1, time.perf_counter())      # para la luz del botón
		if nombre in ('◀', '▶'):
			_T[comp.path + 'nudge'] = -1 if nombre == '◀' else 1   # hasta soltar (PanelSoltar)
			_app(comp, 'nudge', _T[comp.path + 'nudge'])
			return
		if nombre == 'AUTO' and _app(comp, 'auto'):
			return
		{'AUTO': lambda: setattr(comp.par, 'Automatico', not comp.par.Automatico.eval()),
		 'TAP': lambda: Tap(comp), 'RESYNC': lambda: Resync(comp), '÷2': lambda: Mitad(comp),
		 '×2': lambda: Doble(comp)}[nombre]()
		return


def PanelSoltar(comp):
	"""Se soltó el mouse sobre el panel: termina el ◀ ▶ mantenido."""
	_T[comp.path + 'nudge'] = 0
	_app(comp, 'nudge', 0)


def PanelTextos(comp):
	"""Tabla de textos del panel (se rehace solo cuando cambia algo)."""
	m = Motor(comp)
	f = _T.get(comp.path + 'f', 'auto')
	sel = comp.par.Fuente.eval()
	_mostrar(comp, 'Paneltexto', '%.1f' % m.bpm)
	ahora = time.perf_counter()
	if m.senal > 1e-4:
		_T[comp.path + 'consenal'] = ahora
	sinSenal = f in ('auto', 'tap') and ahora - _T.get(comp.path + 'consenal', 0) > 3.0
	# si Windows reinició los dispositivos (p. ej. al conectar algo por USB) TD queda capturando silencio:
	# con 20 s sin señal se vuelve a leer la lista de dispositivos (y cada 20 s mientras siga igual)
	ia = FuenteAudio(comp)
	if (sinSenal and not comp.par.Entradaprueba.eval() and ahora - _T.get(comp.path + 'consenal', 0) > 20.0
			and ahora - _T.get(comp.path + 'refresco', 0) > 20.0 and ia is not None
			and ia.OPType == 'audiodeviceinCHOP'):
		_T[comp.path + 'refresco'] = ahora
		ia.par.refresh.pulse()
	fase = round(m.ajuste * 60000.0 / max(m.bpm, 1))          # corrimiento manual en ms
	sinEntrada = ia is None and not comp.par.Entradaprueba.eval()
	L = _T.get(comp.path + 'lay') or Diseno('horizontal', 'ampliado', m.bpb)
	angosto = L['W'] < 600                                     # panel chico: estado corto, sin versión
	estado = ('SIN ENTRADA · conectá un Audio Device In' if sinEntrada else
			  'SIN SEÑAL · revisar la entrada de audio' if sinSenal else
			  '%s%s · %d%%%s' % (NOMBRES_FUENTE.get(f, f.upper()), '' if sel == 'prioridad' else ' (fija)',
								 round(m.confianza * 100), (' · fase %+d ms' % fase) if fase and not angosto else ''))
	_mostrar(comp, 'Fuenteactiva', 'sin señal' if sinSenal else f)
	_mostrar(comp, 'Version', VERSION)
	filas = [['x', 'y', 'text'], [20, int(L['yb'] + 9), estado if angosto else 'v%s · %s' % (VERSION, estado)]]
	tt = comp.op('panel_textos')
	for nombre in BOTONES:
		if nombre in L['cajas']:
			x0, y0, x1, y1 = L['cajas'][nombre]
			et = nombre
			if nombre == 'AUTO':                                  # AUDIO = automático; MANUAL = se tapea
				c = comp.op('nombres').chan('auto')
				et = 'AUDIO' if (c.eval() if c is not None else comp.par.Automatico.eval()) else 'MANUAL'
			filas.append([int((x0 + x1) / 2 - tt.evalTextSize(et)[0] / 2), int((y0 + y1) / 2 - 7), et])
	nuevo = [[str(c) for c in r] for r in filas]
	if nuevo != _T.get(comp.path + 'textos'):
		_T[comp.path + 'textos'] = nuevo
		t = comp.op('panel_spec')
		t.clear()
		t.appendRows(nuevo)


# ---------------------------------------------------------------- captura (para afinar el detector)
def Capturar(comp, segundos, ruta):
	"""Guarda 'segundos' del audio que entra a un .wav (mono, 16 bits) para probar el motor afuera."""
	_T[comp.path + 'captura'] = []
	run("args[0].module._GuardarCaptura(args[1], args[2])", me, comp, ruta,
		delayMilliSeconds=int(segundos * 1000), delayRef=op.TDResources)


def _GuardarCaptura(comp, ruta):
	import wave
	partes = _T.pop(comp.path + 'captura', None) or []
	y = np.concatenate(partes) if partes else np.zeros(1, np.float32)
	with wave.open(ruta, 'wb') as w:
		w.setnchannels(1)
		w.setsampwidth(2)
		w.setframerate(int(Motor(comp).rate))
		w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- MIDI clock (24 pulsos por negra)
def Clock(comp, tipo):
	"""tipo: 'clock' | 'start' | 'stop'. Lo llama el MIDI In DAT."""
	ahora = time.perf_counter()
	k = comp.path
	if tipo == 'start':
		_T[k + 'clkn'] = 0
		_T[k + 'clkt'] = []
	if tipo != 'clock':
		return
	_T[k + 'clk'] = ahora
	n = _T.get(k + 'clkn', 0) + 1
	_T[k + 'clkn'] = n
	ts = (_T.get(k + 'clkt', []) + [ahora])[-49:]
	_T[k + 'clkt'] = ts
	if len(ts) >= 25:
		bpm = 60.0 / ((ts[-1] - ts[0]) / (len(ts) - 1) * 24)
		_T[k + 'clkest'] = (bpm, n / 24.0, ahora)
