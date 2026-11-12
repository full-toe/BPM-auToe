"""
ritmo_construir: arma (o rearma) Ritmo.tox en /project1 + la franja en el visualizador de Controles
+ la página Ritmo del Destino maestro. Correr en TD:
	exec(open('C:/Toe/Proyectos/BPM auToe/fuentes/ritmo_construir.py', encoding='utf8').read())
"""
SRC = 'C:/Toe/Proyectos/BPM auToe/fuentes/'
R = op('/project1')


def leer(n):
	return open(SRC + n, encoding='utf8').read()


# =================================================================== componente
C = R.op('Ritmo') or R.create(baseCOMP, 'Ritmo')
C.nodeX, C.nodeY = -2475, 2900
for c in list(C.children):
	c.destroy()
for pg_ in list(C.customPages):
	pg_.destroy()
C.par.opshortcut = 'Ritmo'
C.color = (0.3, 0.25, 0.45)


def fl(g, n, l, lo, hi, d, ro=False):
	p = g.appendFloat(n, label=l)[0]
	p.normMin, p.normMax, p.default, p.val, p.readOnly = lo, hi, d, d, ro
	return p


def tg(g, n, l, d):
	p = g.appendToggle(n, label=l)[0]
	p.default = p.val = d
	return p


def me_(g, n, l, names, labels, d):
	p = g.appendMenu(n, label=l)[0]
	p.menuNames, p.menuLabels, p.default, p.val = names, labels, d, d
	return p


t = C.appendCustomPage('Tempo')
fl(t, 'Bpm', 'BPM', 20, 300, 120, True)
me_(t, 'Modo', 'Modo', ['auto', 'banda', 'electronica'], ['Automático (según qué tan estable es el tempo)', 'Forzar banda en vivo', 'Forzar electrónica'], 'auto')
me_(t, 'Fuente', 'Fuente', ['prioridad', 'auto', 'tap', 'link', 'midi', 'app'],
	['Prioridad (App > MIDI > Link > Auto > Tap)', 'Automático', 'Tap / manual', 'Ableton Link', 'MIDI Clock',
	 'App externa (ritmo_app)'], 'prioridad')
tg(t, 'Automatico', 'BPM automático', True)
for n, l in (('Tap', 'Tap'), ('Temanuevo', 'Tema nuevo (olvidar y escuchar de nuevo)'), ('Resync', 'Resync (este es el 1)'), ('Mitad', '÷2'), ('Doble', '×2'),
			 ('Nudgemenos', 'Nudge −'), ('Nudgemas', 'Nudge +')):
	t.appendPulse(n, label=l)
fl(t, 'Bpmmin', 'BPM mínimo', 40, 200, 70)
fl(t, 'Bpmmax', 'BPM máximo', 60, 300, 180)
tg(t, 'Auto1', 'Detectar el 1 del compás', False)
tg(t, 'Autocompas', 'Detectar el compás', True)
p = t.appendInt('Tiempos', label='Tiempos por compás')[0]
p.normMin, p.normMax, p.default, p.val = 1, 12, 4, 4
p = t.appendInt('Tiemposdetectados', label='Compás detectado')[0]
p.readOnly = True
fl(t, 'Confianza', 'Confianza del automático', 0, 1, 0, True)
t.appendStr('Fuenteactiva', label='Fuente activa')[0].readOnly = True

a = C.appendCustomPage('Audio')
d = a.appendMenu('Driver', label='Driver')[0]
d.menuSource = "me.op('in_audio').par.driver"
d = a.appendMenu('Dispositivo', label='Dispositivo')[0]
d.menuSource = "me.op('in_audio').par.device"
a.appendPulse('Reconectar', label='Reconectar')
tg(a, 'Entradaprueba', 'Usar archivo de prueba', False)
a.appendFile('Archivoprueba', label='Archivo de prueba')
fl(a, 'Ganancia', 'Ganancia', 0, 4, 1)
fl(a, 'Silenciodb', 'Umbral de silencio (dB)', -80, -20, -50)   # por debajo = silencio (no detecta tempo)
tg(a, 'Agc', 'Ganancia automática', True)
fl(a, 'Ataque', 'Ataque (s)', 0, 0.5, 0.01)
fl(a, 'Caida', 'Caída (s)', 0, 2, 0.25)
fl(a, 'Caidagolpes', 'Caída de golpes (s)', 0.02, 1, 0.25)

ds = C.appendCustomPage('Desfasaje')
fl(ds, 'Latenciaaudio', 'Latencia de audio (ms, auto)', 0, 500, 0, True)
fl(ds, 'Latenciavideo', 'Latencia de video (ms, auto)', 0, 500, 0, True)
fl(ds, 'Proyectorms', 'Compensación base (ms)', 0, 400, 150)   # base fija medida a ojo; ◀ ▶ ajustan encima
fl(ds, 'Desfasaje', 'Desfasaje total (ms)', 0, 800, 0, True)

sy = C.appendCustomPage('Sync')
tg(sy, 'Link', 'Ableton Link', False)
tg(sy, 'Midiclock', 'MIDI Clock', False)
sy.appendStr('Mididispositivo', label='Dispositivo MIDI Clock (nombre)')   # como en el Mapeador MIDI de TD
C.appendCustomPage('Interno').appendStr('Paneltexto')[0].readOnly = True
C.appendCustomPage('Acerca').appendStr('Version', label='Versión')[0].readOnly = True


def mk(tp, n, x, y):
	o = C.create(tp, n)
	o.nodeX, o.nodeY = x, y
	return o


# --- entrada
ia = mk(audiodeviceinCHOP, 'in_audio', 0, 100)
ia.par.driver.expr = 'parent().par.Driver'
ia.par.device.expr = 'parent().par.Dispositivo'
ia.par.format = 'mono'
ia.par.bufferlength = 0.05
ia.par.ratemode = 'auto'
ia.par.active.expr = 'not parent().par.Entradaprueba'
pr = mk(audiofileinCHOP, 'prueba', 0, -50)
pr.par.file.expr = 'parent().par.Archivoprueba'
pr.par.play.expr = 'parent().par.Entradaprueba'
sw = mk(switchCHOP, 'fuente_audio', 175, 25)
sw.inputConnectors[0].connect(ia)
sw.inputConnectors[1].connect(pr)
sw.par.index.expr = 'int(parent().par.Entradaprueba)'
mo = mk(mathCHOP, 'mono', 350, 25)
mo.inputConnectors[0].connect(sw)
mo.par.chanop = 'add'
# --- bandas
mg = mk(mergeCHOP, 'bandas', 700, 25)
for i, (n, tp, fr) in enumerate([('f_kick', 'lowpass', 120), ('f_caja', 'bandpass', 2000), ('f_hihat', 'highpass', 8000),
								  ('f_graves', 'lowpass', 250), ('f_medios', 'bandpass', 1000), ('f_agudos', 'highpass', 4000)]):
	o = mk(audiofilterCHOP, n, 525, 250 - i * 90)
	o.inputConnectors[0].connect(mo)
	o.par.filter, o.par.units, o.par.cutofffrequency = tp, 'frequency', fr
	mg.inputConnectors[i].connect(o)
mg.inputConnectors[6].connect(mo)
# --- cálculo
cb = mk(textDAT, 'calculo_callbacks', 875, 200)
cb.text = "def onCook(scriptOp):\n\top('logica').module.Cocinar(scriptOp)\n\treturn\n"
sc = mk(scriptCHOP, 'calculo', 875, 25)
sc.par.callbacks = cb.name
sc.inputConnectors[0].connect(mg)
est = mk(textDAT, 'estado', 1225, 350)   # el motor vive acá: cambiar el código no reinicia la detección
est.text = ("# estado: guarda el motor y los datos de la lógica para que sobrevivan a cambios de código.\n"
			"# No editar este DAT (al editarlo se reinicia la detección).\nM = {}\nT = {}\n")
mk(textDAT, 'motor', 875, 350).text = leer('ritmo_motor.py')
mk(textDAT, 'logica', 1050, 350).text = leer('ritmo_logica.py')
k = mk(chopexecuteDAT, 'mantener', 875, -150)
k.text = ("# mantener: hace que 'calculo' se cocine en cada cuadro aunque nadie lea las salidas\n"
		  "# (el motor tiene que escuchar siempre para no perder el ritmo). No hace nada más.\n"
		  "def onValueChange(channel, sampleIndex, val, prev):\n\treturn\n")
k.par.chop, k.par.channel, k.par.valuechange = 'nombres', 'beats', True
nm = mk(renameCHOP, 'nombres', 960, 25)            # la lógica escribe chan1..N y acá se nombran
nm.inputConnectors[0].connect(sc)
nm.par.renamefrom = '*'
sc = nm
sa = mk(selectCHOP, 'sel_audio', 1050, 100)
sa.inputConnectors[0].connect(sc)
sa.par.channames = 'nivel graves medios agudos kick caja hihat golpe_*'
sg = mk(selectCHOP, 'sel_grilla', 1050, -50)
sg.inputConnectors[0].connect(sc)
sg.par.channames = 'bpm beats tiempo compas* golpe_tiempo golpe_compas fase_* confianza* sinritmo fuente'
mk(outCHOP, 'audio', 1225, 100).inputConnectors[0].connect(sa)
mk(outCHOP, 'grilla', 1225, -50).inputConnectors[0].connect(sg)
es = mk(audiospectrumCHOP, 'espectro_calc', 525, -250)
es.inputConnectors[0].connect(mo)
es.par.outputmenu, es.par.outlength, es.par.frequencylog = 'setmanually', 32, True
mk(outCHOP, 'espectro', 1225, -250).inputConnectors[0].connect(es)
mk(outCHOP, 'senal', 1225, -400).inputConnectors[0].connect(mo)
# --- sync
lk = mk(abletonlinkCHOP, 'link', 175, -250)
lk.par.active.expr = 'parent().par.Link'
for n in ('tempo', 'beats'):
	if lk.par[n] is not None:
		lk.par[n] = True
mc = mk(midiinDAT, 'midi_clock', 175, -400)
mc.par.active.expr = 'parent().par.Midiclock'
mc.par.skiptiming, mc.par.maxlines = False, 8
mcb = mk(textDAT, 'midi_clock_callbacks', 175, -550)
mcb.text = ("# midi_clock_callbacks: pulsos del MIDI Clock (0xF8), start (0xFA) y stop (0xFC) -> logica.Clock\n"
			"TIPOS = {0xF8: 'clock', 0xFA: 'start', 0xFC: 'stop'}\n\n"
			"def onReceiveMIDI(dat, rowIndex, message, channel, index, value, input, bytes):\n"
			"\tif bytes:\n\t\tt = TIPOS.get(bytes[0])\n\t\tif t:\n\t\t\top('logica').module.Clock(parent(), t)\n\treturn\n")
mc.par.callbacks = mcb.name
mc.par.device = '/local/midi/device'
mc.par.id.expr = ("next((r[0].val for r in op('/local/midi/device').rows()[1:] if parent().par.Mididispositivo.eval() "
				  "and parent().par.Mididispositivo.eval().lower() in r[1].val.lower()), '')")
# --- app externa (ritmo_app): estado por OSC en 9100 -> logica.App; comandos de los botones por 9101
acb = mk(textDAT, 'app_osc_callbacks', 0, -700)
acb.par.language = 'python'
acb.text = '\n'.join([
	'# app_osc_callbacks: estado que manda ritmo_app (detector de BPM externo) por OSC -> logica.App',
	'def onReceiveOSC(dat, rowIndex, message, byteData, timeStamp, address, args, peer):',
	"\tif address == '/ritmo/estado':",
	"\t\tparent().op('logica').module.App(parent(), args)",
	'\treturn', ''])
ao = mk(oscinDAT, 'app_osc', 175, -700)
ao.par.port, ao.par.callbacks, ao.par.maxlines = 9100, acb.name, 1
ao.par.splitbundle = True                        # la app manda un paquete (bundle) por cuadro
ac = mk(oscoutDAT, 'app_cmd', 175, -850)
ac.par.address, ac.par.port = '127.0.0.1', 9101
# --- botones
px = mk(parameterexecuteDAT, 'botones', 1050, 500)
px.text = '''# botones: los pulsos del panel llaman a la lógica
def onPulse(par):
	L = op('logica').module
	c = parent()
	acciones = {'Tap': L.Tap, 'Resync': L.Resync, 'Doble': L.Doble, 'Mitad': L.Mitad, 'Temanuevo': L.TemaNuevo,
				'Nudgemenos': lambda c: L.Nudge(c, -1), 'Nudgemas': lambda c: L.Nudge(c, 1)}
	if par.name in acciones:
		acciones[par.name](c)
	elif par.name == 'Reconectar':
		op('in_audio').par.refresh.pulse()          # vuelve a leer los dispositivos de Windows
		op('in_audio').par.active = False
		run("args[0].par.active.expr = 'not parent().par.Entradaprueba'", op('in_audio'), delayFrames=5)
'''
px.par.op, px.par.pars, px.par.valuechange, px.par.onpulse = '..', '*', False, True
# --- panel (franja 1280 x 90)
pp = mk(textDAT, 'panel_pixel', 1400, 350)
pp.par.language = 'glsl'
pp.text = leer('ritmo_panel.glsl')
g = mk(glslTOP, 'panel_fondo', 1400, 200)
g.par.pixeldat = pp.name
g.par.outputresolution, g.par.resolutionw, g.par.resolutionh = 'custom', 1280, 90
G = "op('grilla')"
g.par.vec0name = 'uA'
for c_, ch in zip('xyzw', ('tiempo', 'compas_tiempos', 'golpe_tiempo', 'confianza')):
	getattr(g.par, 'vec0value' + c_).expr = G + "['%s']" % ch
g.par.vec1name = 'uB'
g.par.vec1valuex.expr = 'parent().par.Automatico'
g.par.vec1valuey.expr = 'parent().par.Auto1'
g.par.vec1valuez.expr = G + "['sinritmo']"
g.par.vec1valuew.expr = "op('nombres')['entrada'] or 0"           # medidor de entrada
g.par.vec2name = 'uC'
g.par.vec2valuex.expr = "op('nombres')['ajuste'] or 0"            # destello de TEMA NUEVO
g.par.vec2valuey.expr = "parent().par.Modo == 'electronica'"       # color del botón BANDA / TECHNO
g.par.vec2valuez.expr = "op('nombres')['boton'] or 0"               # botón apretado
g.par.vec2valuew.expr = "op('nombres')['boton_luz'] or 0"           # y su luz
bp = mk(textTOP, 'panel_bpm', 1575, 200)
bp.inputConnectors[0].connect(g)
bp.par.text.expr = "parent().par.Paneltexto + ' BPM'"
bp.par.font, bp.par.typeface, bp.par.fontsizexunit, bp.par.fontsizex = 'Montserrat', 'Bold', 'pixels', 34
bp.par.alignx, bp.par.aligny, bp.par.positionunit, bp.par.positionx, bp.par.positiony = 'left', 'center', 'pixels', 20, 20
spd = mk(tableDAT, 'panel_spec', 1750, 350)
spd.clear()
spd.appendRow(['x', 'y', 'text'])
tx = mk(textTOP, 'panel_textos', 1750, 200)
tx.inputConnectors[0].connect(bp)
tx.par.font, tx.par.fontsizexunit, tx.par.fontsizex, tx.par.alignx, tx.par.aligny = 'Montserrat', 'pixels', 15, 'left', 'center'
tx.par.specdat = spd.name
mk(nullTOP, 'panel', 1925, 200).inputConnectors[0].connect(tx)
C.par.Driver = 'default'
b2 = [n for n in ia.par.device.menuNames if 'Voicemeeter_Out_B2' in n]
if b2:
	C.par.Dispositivo = b2[0]
C.par.externaltox = 'C:/Toe/Proyectos/Visuales/TOX/Ritmo.tox'
for n in ('calculo_callbacks1', 'midi_clock_callbacks1', 'link_callbacks'):    # los que TD crea solos
	if C.op(n) is not None and n != 'link_callbacks':
		C.op(n).destroy()

# =================================================================== pelota de prueba + visualizador de Controles
C.par['Pelota'] is None and t.appendToggle('Pelota', label='Pelota de prueba (visualizador)')
pd_ = mk(textDAT, 'pelota_pixel', 1400, 550)
pd_.par.language = 'glsl'
pd_.text = leer('ritmo_pelota.glsl')
pe = mk(glslTOP, 'pelota', 1575, 550)
pe.par.pixeldat = pd_.name
pe.par.outputresolution, pe.par.resolutionw, pe.par.resolutionh = 'custom', 180, 120     # proporción del botón AUTO
pe.par.vec0name = 'uR'
for c_, ch in zip('xyzw', ('fase_1_2', 'tiempo', 'fase_1_4', 'bpm')):
	getattr(pe.par, 'vec0value' + c_).expr = "op('grilla')['%s']" % ch
pe.par.vec1name = 'uConf'
pe.par.vec1valuex.expr = "op('grilla')['confianza_suave']"      # altura del salto = confianza (suavizada)
pe.par.vec1valuey.expr = 'parent().par.Pelota'                  # prendida (clic en el cuadradito)
g.par.vec2valuey.expr = 'parent().par.Pelota'
if op('/project1/Controles/visualizador') is not None:
	exec(leer('ritmo_visualizador.py'))

# =================================================================== Destino maestro: página Ritmo
D = op('/project1/Destino_maestro')
if D is not None and D.op('ritmo') is None:
	pg_ = D.appendCustomPage('Ritmo')
	p = pg_.appendFloat('Ritmoprof', label='Profundidad del ritmo')[0]
	p.normMin, p.normMax, p.default = -1, 1, 0                  # negativa = resta
	p = pg_.appendMenu('Ritmodiv', label='División')[0]
	p.menuNames = ['1_16', '1_8', '1_4', '1_2', '1', '2', '4', '8', '16']
	p.menuLabels = ['1/16 de tiempo', '1/8', '1/4 (1 tiempo)', '1/2 (2 tiempos)', '1 compás', '2 compases',
					'4 compases', '8 compases', '16 compases']
	p.default = p.val = '1_4'
	p = pg_.appendMenu('Ritmoforma', label='Forma')[0]
	p.menuNames = ['rampa', 'bajada', 'seno', 'triangulo', 'cuadrada', 'golpe', 'aleatorio']
	p.menuLabels = ['Rampa (sube)', 'Rampa (baja)', 'Seno', 'Triángulo', 'Cuadrada', 'Golpe con caída', 'Aleatorio por paso']
	p.default = p.val = 'golpe'
	p = pg_.appendToggle('Ritmobajadas', label='Detectar bajadas')[0]
	p.default = p.val = True                                     # × confianza suavizada de Ritmo
	p = pg_.appendFloat('Ritmofase', label='Corrimiento de fase')[0]
	p.normMin, p.normMax, p.default = 0, 1, 0
	for o in D.children:
		if o.nodeX >= 350 and o.OPType != 'annotateCOMP':
			o.nodeX += 175
	u = D.create(textDAT, 'ritmo_util')
	u.text = leer('destino_ritmo_util.py')
	u.nodeX, u.nodeY = 350, 180
	rt = D.create(expressionCHOP, 'ritmo')
	rt.nodeX, rt.nodeY = 350, 0
	rt.par.expr0expr.expr = "me.inputVal if parent().par.Ritmoprof <= 0 else op('ritmo_util').module.Valor(parent(), me.inputVal)"
	rt.inputConnectors[0].connect(D.op('canal'))
	D.op('limite_0_1').inputConnectors[0].connect(rt)
	a_ = D.op('nota_destino')
	if a_ is not None:
		a_.nodeWidth += 175
		a_.par.Bodytext = a_.par.Bodytext.eval() + ("\nritmo (+ ritmo_util): suma el ritmo de Ritmo.tox (página Ritmo: "
													"profundidad, división, forma, fase) al valor de la perilla, antes de la curva. "
													"Profundidad 0 = no hace nada.")
print('Ritmo armado:', C.path, '| errores:', [o.name for o in C.children if o.errors()])
