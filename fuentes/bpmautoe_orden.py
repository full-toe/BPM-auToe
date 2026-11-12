"""
bpmautoe_orden.py: ordena la red de BPMauToe (grupos en columnas, sin superposiciones) y pone un comentario
por grupo. Lo llama bpmautoe_construir.py; también se puede correr solo en TD:
	B = op.BPMauToe; exec(open('C:/Toe/Proyectos/BPM auToe/fuentes/bpmautoe_orden.py', encoding='utf8').read())
Necesita la variable B (el COMP).
"""
# DATs que TD acopla solo a los GLSL y que no se usan (los shaders leen panel_pixel y pelota_pixel)
for n in ('panel_fondo_pixel', 'panel_fondo_info', 'panel_fondo_compute', 'pelota_pixel1', 'pelota_info',
		  'pelota_compute'):
	if B.op(n) is not None:
		B.op(n).destroy()
for a in [o for o in B.findChildren(depth=1, type=annotateCOMP)]:
	a.destroy()

# (columna x, fila y) de cada operador: flujo de izquierda a derecha
LUGAR = {
	# entrada
	'entrada': (0, 75), 'prueba': (0, -75), 'fuente_audio': (200, 0), 'mono': (400, 0),
	# bandas
	'f_kick': (600, 375), 'f_caja': (600, 225), 'f_hihat': (600, 75), 'f_graves': (600, -75),
	'f_medios': (600, -225), 'f_agudos': (600, -375), 'espectro_calc': (600, -575), 'bandas': (800, 0),
	# cálculo
	'calculo': (1000, 0), 'nombres': (1200, 0),
	'calculo_callbacks': (1000, 200), 'motor': (1200, 200), 'logica': (1400, 200), 'estado': (1600, 200),
	# salidas
	'sel_audio': (1800, 150), 'sel_grilla': (1800, 0), 'audio': (2000, 150), 'grilla': (2000, 0),
	'senal': (2000, -150), 'espectro': (2000, -575),
	# sincronía externa (los callbacks van debajo de su operador)
	'link': (0, -850), 'link_callbacks': (0, -1000), 'midi_clock': (250, -850), 'midi_clock_callbacks': (250, -1000),
	'app_osc': (500, -850), 'app_osc_callbacks': (500, -1000), 'app_cmd': (750, -850),
	# botones
	'botones': (1000, -850), 'mantener': (1200, -850),
	# panel
	'panel_layout': (2000, 400), 'panel_layout_chop': (2200, 400), 'panel_layout_top': (2400, 400),
	'panel_spec': (3000, 400), 'panel_pixel': (2400, 200), 'panel_fondo': (2600, 200), 'panel_bpm': (2800, 200),
	'panel_textos': (3000, 200), 'panel': (3200, 200),
	'pelota_pixel': (2400, -50), 'pelota': (2600, -50), 'pelota_t': (2800, -50),
	'panel_final': (3400, 75), 'ventana_panel': (3600, 75), 'panel_mouse': (3600, -100), 'ventana': (3800, 75),
}
for n, (x, y) in LUGAR.items():
	o = B.op(n)
	if o is not None:
		o.nodeX, o.nodeY = x, y
sueltos = [o.name for o in B.findChildren(depth=1) if o.name not in LUGAR and o.OPType != 'annotateCOMP']


def nota(nombre, titulo, cuerpo, miembros):
	ops_ = [B.op(n) for n in miembros if B.op(n) is not None]
	if not ops_:
		return
	x0 = min(o.nodeX for o in ops_) - 30
	y0 = min(o.nodeY for o in ops_) - 30
	x1 = max(o.nodeX + o.nodeWidth for o in ops_) + 30
	y1 = max(o.nodeY + o.nodeHeight for o in ops_) + 110
	a = B.create(annotateCOMP)
	a.name = nombre
	a.par.Titletext, a.par.Bodytext = titulo, cuerpo
	a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight = x0, y0, x1 - x0, y1 - y0


nota('nota_entrada', '1 · ENTRADA DE AUDIO',
	 'entrada: conector del tox (conectá un Audio Device In). prueba: archivo de prueba (página Audio). '
	 'fuente_audio: elige entrada o prueba. mono: suma a un canal.',
	 ['entrada', 'prueba', 'fuente_audio', 'mono'])
nota('nota_bandas', '2 · BANDAS',
	 'f_*: filtros por banda (kick, caja, hi-hat, graves, medios, agudos). bandas: las junta para el cálculo. '
	 'espectro_calc: espectro para la salida espectro.',
	 ['f_kick', 'f_caja', 'f_hihat', 'f_graves', 'f_medios', 'f_agudos', 'bandas', 'espectro_calc'])
nota('nota_calculo', '3 · CÁLCULO DEL TEMPO',
	 'calculo: Script CHOP por cuadro (logica.Cocinar). nombres: nombres de los canales. motor: detector + Rejilla '
	 'sin saltos. logica: fuentes, latencias, panel, botones. estado: memoria del motor (no se reinicia al editar).',
	 ['calculo', 'nombres', 'calculo_callbacks', 'motor', 'logica', 'estado'])
nota('nota_salidas', '4 · SALIDAS',
	 'audio: niveles y golpes por banda. grilla: tempo, fases, compás, confianza. senal: forma de onda. '
	 'espectro: espectro de la entrada.',
	 ['sel_audio', 'sel_grilla', 'audio', 'grilla', 'senal', 'espectro'])
nota('nota_sync', 'SINCRONÍA EXTERNA',
	 'link: Ableton Link. midi_clock: MIDI Clock. app_osc: estado de la app BPM auToe (OSC 9100). app_cmd: manda '
	 'los botones a la app (9101). Prioridad: App > MIDI > Link > Automático > Tap.',
	 ['link', 'link_callbacks', 'midi_clock', 'midi_clock_callbacks', 'app_osc', 'app_osc_callbacks', 'app_cmd'])
nota('nota_botones', 'BOTONES',
	 'botones: los pulsos del panel de parámetros (Tap, Resync, Abrir panel...). mantener: ◀ ▶ mantenidos.',
	 ['botones', 'mantener'])
nota('nota_panel', '5 · PANEL (franja)',
	 'panel_layout -> panel_layout_chop -> panel_layout_top: cajas según Orientación y Tamaño (página Panel). '
	 'panel_fondo + panel_bpm + panel_textos -> panel (panel_spec: textos). pelota -> pelota_t: la '
	 'pelotita. panel_final: todo junto. ventana_panel: franja clickeable (panel_mouse). ventana: la abre aparte.',
	 ['panel_spec', 'panel_pixel', 'panel_fondo', 'panel_bpm', 'panel_textos', 'panel', 'pelota_pixel', 'pelota',
	  'pelota_t', 'panel_final', 'ventana_panel', 'panel_mouse', 'ventana'])
print('ordenado; sin lugar asignado:', sueltos)
