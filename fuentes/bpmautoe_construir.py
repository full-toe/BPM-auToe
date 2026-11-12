"""
bpmautoe_construir.py: arma BPMauToe.tox (BPM auToe dentro de TD) a partir del módulo Ritmo del proyecto,
con las actualizaciones de la app: audio por la ENTRADA del tox (el usuario conecta su Audio Device In),
rejilla continua, panel propio (ventana) y OSC /BPMauToe/. Correr en TD:
	exec(open('C:/Toe/Proyectos/BPM auToe/fuentes/bpmautoe_construir.py', encoding='utf8').read())
Deja el COMP nuevo como /project1/BPMauToe_nuevo (el que lo llama decide si reemplaza al anterior).
"""
SRC = 'C:/Toe/Proyectos/BPM auToe/fuentes/'
leer = lambda n: open(SRC + n, encoding='utf8').read()
P = op('/project1')
R = P.op('Ritmo')
viejo = P.op('BPMauToe_nuevo')
if viejo is not None:
	viejo.destroy()
B = P.copy(R, name='BPMauToe_nuevo')
B.nodeX, B.nodeY = R.nodeX, R.nodeY - 400
B.allowCooking = True
B.par.opshortcut = ''
B.par.externaltox = 'C:/Toe/Proyectos/BPM auToe/td/BPMauToe.tox'
B.op('motor').text = leer('ritmo_motor.py')
B.op('logica').text = leer('ritmo_logica.py')


def mk(tp, n, x, y):
	o = B.op(n) or B.create(tp, n)
	o.nodeX, o.nodeY = x, y
	return o


# ------------------------------------------------------------------ entrada de audio: conector del tox
# primero los parámetros que apuntaban al dispositivo interno (si no, sus menús quedan con error)
for n in ('Driver', 'Dispositivo', 'Reconectar'):
	p = B.par[n]
	if p is not None:
		p.destroy()
ent = mk(inCHOP, 'entrada', 0, 100)
B.op('fuente_audio').inputConnectors[0].connect(ent)
if B.op('in_audio') is not None:
	B.op('in_audio').destroy()

# ------------------------------------------------------------------ parámetros
pa = [pg for pg in B.customPages if pg.name == 'Audio'][0]
if B.par['Latenciaentrada'] is None:
	p = pa.appendFloat('Latenciaentrada', label='Latencia extra de la entrada (ms)')[0]
	p.normMin, p.normMax, p.default = 0, 100, 0
pg = ([x for x in B.customPages if x.name == 'Panel'] or [B.appendCustomPage('Panel')])[0]
if B.par['Abrirpanel'] is None:
	pg.appendPulse('Abrirpanel', label='Abrir panel (ventana)')
	pg.appendPulse('Cerrarpanel', label='Cerrar panel')
B.par.Version = op('logica').module.VERSION if False else B.op('logica').module.VERSION

# los pulsos del panel de parámetros
B.op('botones').text = '\n'.join([
	'# botones: los pulsos del panel de parámetros llaman a la lógica',
	'def onPulse(par):',
	"\tL = op('logica').module",
	'\tc = parent()',
	"\tacciones = {'Tap': L.Tap, 'Resync': L.Resync, 'Doble': L.Doble, 'Mitad': L.Mitad, 'Temanuevo': L.TemaNuevo,",
	"\t\t\t\t'Nudgemenos': lambda c: L.Nudge(c, -1), 'Nudgemas': lambda c: L.Nudge(c, 1)}",
	'\tif par.name in acciones:',
	'\t\tacciones[par.name](c)',
	"\telif par.name == 'Abrirpanel':",
	"\t\top('ventana').par.winopen.pulse()",
	"\telif par.name == 'Cerrarpanel':",
	"\t\top('ventana').par.winclose.pulse()",
	''])

# OSC de la app: acepta el prefijo nuevo y el viejo
B.op('app_osc_callbacks').text = '\n'.join([
	'# app_osc_callbacks: estado que manda la app BPM auToe por OSC -> logica.App',
	'def onReceiveOSC(dat, rowIndex, message, byteData, timeStamp, address, args, peer):',
	"\tif address in ('/BPMauToe/estado', '/ritmo/estado'):",
	"\t\tparent().op('logica').module.App(parent(), args)",
	'\treturn', ''])
if B.op('nota_app') is not None:
	B.op('nota_app').destroy()

# ------------------------------------------------------------------ panel propio: franja + pelota + ventana
pt = mk(transformTOP, 'pelota_t', 1750, 550)
pt.inputConnectors[0].connect(B.op('pelota'))
pt.par.outputresolution, pt.par.resolutionw, pt.par.resolutionh = 'custom', 1280, 90
pt.par.tunit, pt.par.extend = 'pixels', 'zero'
pt.par.sx, pt.par.sy = 90 / 1280.0, 60 / 90.0
pt.par.tx, pt.par.ty = 861 - 640, 0                       # cuadradito de 90 x 60 a la izquierda de AUTO
pf = mk(compositeTOP, 'panel_final', 2100, 200)
pf.par.operand = 'over'
pf.inputConnectors[0].connect(pt)
pf.inputConnectors[1].connect(B.op('panel'))
vp = mk(containerCOMP, 'ventana_panel', 2275, 200)
vp.par.w, vp.par.h = 1280, 90
vp.par.top.expr = "parent().op('panel_final')"
pm = mk(panelexecuteDAT, 'panel_mouse', 2275, 50)
pm.par.panels = 'ventana_panel'
pm.par.panelvalue = 'lselect'
pm.par.offtoon, pm.par.ontooff, pm.par.valuechange = True, True, False
pm.text = '\n'.join([
	'# panel_mouse: clics sobre el panel (ventana_panel) -> logica.PanelClick / PanelSoltar',
	'# u y v van de 0 a 1: se pasan a pixeles con el tamaño actual del panel (cambia con orientación y tamaño)',
	'def onOffToOn(panelValue):',
	'\tc = panelValue.owner',
	'\tpn = c.panel',
	"\tparent().op('logica').module.PanelClick(parent(), pn.u.val * c.par.w.eval(), pn.v.val * c.par.h.eval())",
	'\treturn',
	'',
	'def onOnToOff(panelValue):',
	"\tparent().op('logica').module.PanelSoltar(parent())",
	'\treturn', ''])
w = mk(windowCOMP, 'ventana', 2450, 200)
w.par.winop = 'ventana_panel'
w.par.size, w.par.winw, w.par.winh = 'custom', 1280, 90
w.par.borders, w.par.title = True, 'BPM auToe'


# ------------------------------------------------------------------ panel: orientación y tamaño
exec(leer('bpmautoe_panel.py'))
# ------------------------------------------------------------------ orden de la red y comentarios por grupo
exec(leer('bpmautoe_orden.py'))
B.clearScriptErrors(recurse=True)
print('BPMauToe_nuevo armado, versión', B.par.Version.eval())
