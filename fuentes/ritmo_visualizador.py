"""
ritmo_visualizador: suma las franjas de Ritmo al visualizador de Controles (sin tocar su extensión).
Alto total = 720 (lo de siempre) + 90 (franja del tempo, si hay Ritmo). La pelota de prueba es un cuadradito
del tamaño de AUTO (90 x 60) en la franja del tempo, a su izquierda (clic = prende / apaga; ver logica.PELOTA).
Correr en TD (lo llama ritmo_construir.py):
	exec(open('C:/Toe/Proyectos/BPM auToe/fuentes/ritmo_visualizador.py', encoding='utf8').read())
"""
V = op('/project1/Controles/visualizador')
T = "(1 if hasattr(op, 'Ritmo') and op.Ritmo.op('panel') is not None else 0)"
P = "(1 if hasattr(op, 'Ritmo') and op.Ritmo.par.Pelota.eval() else 0)"
H = "me.parent().par.h"


def mv(tp, n, x, y):
	o = V.op(n) or V.create(tp, n)
	o.nodeX, o.nodeY = x, y
	return o


V.par.h.expr = "720 + 90 * %s" % T
sel_t = mv(selectTOP, 'vis_tempo', 600, -200)
sel_t.par.top.expr = "op.Ritmo.op('panel') if %s else ''" % T
sel_p = mv(selectTOP, 'vis_pelota', 600, -400)
sel_p.par.top.expr = "op.Ritmo.op('pelota') if %s else ''" % T                      # siempre (apagada se ve gris)
capas = [(sel_p, 'vis_pelota_t', -400, 60, "765"),                               # (entrada, nombre, y, alto, centro y)
		 (sel_t, 'vis_arriba', -200, 90, "765"),
		 (V.op('vis_final'), 'vis_abajo', 0, 720, "360")]
ts = []
for src, n, y, alto, centro in capas:
	t = mv(transformTOP, n, 775, y)
	t.inputConnectors[0].connect(src)
	t.par.outputresolution = 'custom'
	t.par.resolutionw = 1280
	t.par.resolutionh.expr = H
	t.par.tunit, t.par.extend = 'pixels', 'zero'
	t.par.sy.expr = "%d / %s" % (alto, H)                      # sin estirar: cada una a su alto real
	t.par.ty.expr = "%s - %s / 2" % (centro, H)
	if n == 'vis_pelota_t':                                     # 90 x 60 como AUTO, centrado en x = 861
		t.par.sx = 90 / 1280.0
		t.par.tx = 861 - 640
	ts.append(t)
viejo = V.op('vis_con_tempo')
if viejo is not None and viejo.OPType != 'compositeTOP':
	viejo.destroy()
co = mv(compositeTOP, 'vis_con_tempo', 950, 0)
co.par.operand = 'over'                                    # pelota sobre todo
for i, t in enumerate(ts):
	co.inputConnectors[i].connect(t)
V.par.top.expr = "me.op('vis_con_tempo')"
op('/project1/Controles/ventana_visualizador').par.winh.expr = "int(1080 * op('visualizador').par.h / 1280)"

# --- mouse: repartir los clics por franja
m = V.op('vis_mouse')
s = m.text
ini = s.find('def _yv(pn):')
fin = s.find('def onOnToOff')
nuevo = '''def _yv(pn):
	# alto total = 720 (lo de siempre) + 90 (tempo); devuelve y dentro de lo de siempre
	H = parent().par.h.eval()
	return pn.v.val * H, H

def onOffToOn(panelValue):
	pn = panelValue.owner.panel
	y, H = _yv(pn)
	if panelValue.name == 'rselect':                     # u / v solo siguen al clic izquierdo
		y = pn.rollv.val * H
	if y > 720 and hasattr(op, 'Ritmo'):
		if panelValue.name == 'lselect':
			op.Ritmo.op('logica').module.PanelClick(op.Ritmo, pn.u.val * 1280, y - 720)
		return
	if panelValue.name == 'lselect':
		_ext().VisClick(pn.u.val, y / 720.0, 'izq')
	elif panelValue.name == 'rselect':
		cd = parent().op('clic_derecho')                 # parámetros del mapeo al lado del mouse
		if cd is not None:
			# u / v solo se actualizan con el clic izquierdo: con el derecho se usa la posición del mouse
			cd.module.Abrir(pn.rollu.val, y / 720.0)
		else:
			_ext().VisClick(pn.rollu.val, y / 720.0, 'der')
	return

'''
cdd = mv(textDAT, 'clic_derecho', 950, -400)
cdd.text = open('C:/Toe/Proyectos/BPM auToe/fuentes/controles_clic_derecho.py', encoding='utf8').read()
if ini >= 0 and fin > ini:
	m.text = s[:ini] + nuevo + s[fin:]
print('visualizador: alto', V.par.h.eval(), '| franjas', [t.name for t in ts])
