"""
clic_derecho: clic derecho sobre el visualizador de Controles.
  * Sobre un knob, un fader (salvo el crossfade) o un knob extra: abre la ventana de parámetros de su(s)
	Destino(s), al lado del mouse y siempre dentro de la pantalla donde está el mouse.
  * En cualquier otro lugar (p. ej. un preset: guardar) hace lo de siempre (ControlesEXT.VisClick 'der').
Las ventanas de parámetros de TD no dejan elegir la posición: se detecta la ventana nueva y se mueve
con la API de Windows (GetCursorPos / MonitorFromPoint / SetWindowPos).
"""
import ctypes
from ctypes import wintypes

U = ctypes.WinDLL('user32', use_last_error=True)
# tipos declarados: en Windows de 64 bits, sin esto HWND_TOPMOST (-1) se pasa mal y Windows descarta el pedido
U.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
U.SetWindowPos.restype = wintypes.BOOL
U.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
U.MonitorFromPoint.restype = wintypes.HMONITOR
U.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
U.SetForegroundWindow.argtypes = [wintypes.HWND]
U.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
U.IsWindowVisible.argtypes = [wintypes.HWND]


class _MI(ctypes.Structure):
	_fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT), ('rcWork', wintypes.RECT),
				('dwFlags', wintypes.DWORD)]


def _ext():
	return parent(2).ext.ControlesEXT


def Clave(u, v):
	"""Salida lógica bajo el mouse ('S3', 'X2', 'L2') o None. Misma geometría que ControlesEXT.VisClick."""
	ext = _ext()
	G = parent(2).op('ControlesEXT').module.Geo
	x, y = u * G.W, v * G.H
	cerca = lambda cx, cy, r: (x - cx) ** 2 + (y - cy) ** 2 <= r * r
	for k in range(8):
		cx, cy = G.knob(k)
		if 7 + k < ext.NS and cerca(cx, cy, G.KR + 8):
			return 'S%d' % (8 + k)                          # knobs = salidas 8..15
		fx0, fx1 = G.fader(k)
		if k > 0 and fx0 - 6 <= x <= fx1 + 6 and G.FY0 - 6 <= y <= G.FY1 + 6:
			return 'S%d' % k                                # faders 2..8 = salidas 1..7 (el 1 es crossfade)
	for j in range(ext.NE):
		cx, cy = G.extra(j)
		if cerca(cx, cy, G.ER + 8):
			return '%s%d' % (ext.CapaKnobs()[1], j + 1)     # fila de abajo: extras (X) o loopera (L) según el banco
	return None


def _ventanasTD():
	pid = ctypes.windll.kernel32.GetCurrentProcessId()
	hs = []

	@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
	def cb(h, _):
		p = wintypes.DWORD()
		U.GetWindowThreadProcessId(h, ctypes.byref(p))
		if p.value == pid and U.IsWindowVisible(h):
			hs.append(h)
		return True
	U.EnumWindows(cb, 0)
	return set(hs)


def _ubicar(h, mx, my, n):
	"""Pone la ventana h al lado del mouse (mx, my), dentro del área útil del monitor del mouse."""
	r = wintypes.RECT()
	U.GetWindowRect(h, ctypes.byref(r))
	w, alto = r.right - r.left, r.bottom - r.top
	mi = _MI()
	mi.cbSize = ctypes.sizeof(_MI)
	U.GetMonitorInfoW(U.MonitorFromPoint(wintypes.POINT(mx, my), 2), ctypes.byref(mi))
	a = mi.rcWork
	x = mx + 24 + n * 28
	if x + w > a.right:                                      # no entra a la derecha: a la izquierda del mouse
		x = mx - 24 - w - n * 28
	y = my - 40 + n * 28
	x = max(a.left, min(x, a.right - w))
	y = max(a.top, min(y, a.bottom - alto))
	# encima de todo (el panel de Controles es 'siempre arriba': si no, quedaba debajo) y al frente
	U.SetWindowPos(h, wintypes.HWND(-1), int(x), int(y), 0, 0, 0x0001 | 0x0040)  # HWND_TOPMOST, SWP_NOSIZE | SWP_SHOWWINDOW
	U.SetForegroundWindow(h)


def Abrir(u, v):
	"""Clic derecho: parámetros del mapeo al lado del mouse; si no hay control, lo de siempre."""
	clave = Clave(u, v)
	ext = _ext()
	if clave is None:
		ext.VisClick(u, v, 'der')
		return
	ds = ext.DestinosSalida(clave)
	if not ds:
		ui.status = 'Controles: %s no está conectado a ningún mapeo' % clave
		return
	p = wintypes.POINT()
	U.GetCursorPos(ctypes.byref(p))
	antes = _ventanasTD()
	for d in ds:
		d.openParameters()
	run("args[0].module._Acomodar(args[1], args[2], args[3])", me, antes, p.x, p.y, delayFrames=2)


def _Acomodar(antes, mx, my, intento=0):
	nuevas = sorted(_ventanasTD() - antes)
	if not nuevas and intento < 10:                          # la ventana tarda un poco en aparecer
		run("args[0].module._Acomodar(args[1], args[2], args[3], args[4])", me, antes, mx, my, intento + 1, delayFrames=2)
		return
	for n, h in enumerate(nuevas):
		_ubicar(h, mx, my, n)
