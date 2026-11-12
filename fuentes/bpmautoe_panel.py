"""
bpmautoe_panel.py: panel de BPMauToe con orientación (horizontal / vertical) y tamaño
(ampliado / medio / reducido). Lo llama bpmautoe_construir.py; se puede correr solo en TD con B = el COMP:
	B = op.BPMauToe; exec(open('C:/Toe/Proyectos/BPM auToe/fuentes/bpmautoe_panel.py', encoding='utf8').read())
"""
SRC = 'C:/Toe/Proyectos/BPM auToe/fuentes/'
leer = lambda n: open(SRC + n, encoding='utf8').read()

# parámetros (página Panel)
pg = ([x for x in B.customPages if x.name == 'Panel'] or [B.appendCustomPage('Panel')])[0]
if B.par['Panelorient'] is None:
	p = pg.appendMenu('Panelorient', label='Orientación')[0]
	p.default = p.val = 'horizontal'
	p = pg.appendMenu('Paneltam', label='Tamaño')[0]
	p.menuNames, p.menuLabels = ['ampliado', 'medio', 'reducido'], ['Ampliado', 'Medio', 'Reducido']
	p.default = p.val = 'ampliado'
	pg.sort('Panelorient', 'Paneltam', 'Abrirpanel', 'Cerrarpanel')
po = B.par.Panelorient                                     # (la versión cuadrada se sacó: a Toe no le gustó)
po.menuNames, po.menuLabels = ['horizontal', 'vertical'], ['Horizontal', 'Vertical']
if po.eval() not in ('horizontal', 'vertical'):
	po.val = 'horizontal'


def mk(tp, n):
	return B.op(n) or B.create(tp, n)


# cajas del panel: tabla (la llena logica.AplicarPanel) -> CHOP -> textura de 12 x 1 -> entrada del GLSL
tl = mk(tableDAT, 'panel_layout')
dc = mk(dattoCHOP, 'panel_layout_chop')
dc.par.dat = 'panel_layout'
dc.par.output, dc.par.firstrow, dc.par.firstcolumn = 'chanpercol', 'values', 'values'
ct = mk(choptoTOP, 'panel_layout_top')
ct.par.chop = 'panel_layout_chop'
ct.par.dataformat, ct.par.format = 'rgba', 'rgba32float'
B.op('panel_fondo').inputConnectors[0].connect(ct)
B.op('panel_pixel').text = leer('ritmo_panel.glsl')
B.op('panel_fondo').par.vec1valuex.expr = "op('nombres')['auto'] or 0"      # AUTO verde (también con la app)
B.op('logica').text = leer('ritmo_logica.py')
B.op('logica').module.AplicarPanel(B)

# lo que se ve en el nodo: el panel (se puede apretar con la vista del nodo activa)
B.par.opviewer = './ventana_panel'                        # relativo al COMP (así anda en cualquier proyecto)
B.viewer = True
