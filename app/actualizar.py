"""
actualizar: al abrir BPM auToe (versión instalada) busca en GitHub si hay una versión nueva y, si la hay,
muestra un cartel con lo que cambia: «Actualizar» baja el instalador, cierra la app y lo corre (el
instalador la vuelve a abrir con la misma configuración); «Ahora no» sigue como si nada.
Nunca actualiza sin que se lo pidan. Si no hay internet o GitHub no responde, no muestra nada.
Para probar el cartel sin publicar nada: variable de entorno BPMAUTOE_PROBAR_VERSION=0.0.1 (la app se cree vieja).
"""
import json
import os
import subprocess
import tempfile
import threading
import tkinter as tk
import urllib.request

REPO = 'full-toe/BPM-auToe'
API = 'https://api.github.com/repos/%s/releases/latest' % REPO
AGENTE = {'User-Agent': 'BPM-auToe-actualizador', 'Accept': 'application/vnd.github+json'}
FONDO, TEXTO, BOTON, ACENTO = '#161616', '#d9d9d9', '#333333', '#3a7d4f'


def _num(v):
	try:
		return tuple(int(x) for x in v.strip().lstrip('vV').split('.'))
	except ValueError:
		return (0,)


def buscar(version):
	"""-> (version_nueva, notas, url_instalador) si en GitHub hay una más nueva que 'version'; si no, None."""
	try:
		with urllib.request.urlopen(urllib.request.Request(API, headers=AGENTE), timeout=5) as r:
			d = json.load(r)
	except Exception:
		return None
	nueva = d.get('tag_name', '')
	url = next((a['browser_download_url'] for a in d.get('assets', [])
				if a.get('name', '').lower().endswith('-instalador.exe')), None)
	if not url or _num(nueva) <= _num(version):
		return None
	notas = [l.strip() for l in (d.get('body') or '').splitlines() if l.strip() and not l.startswith('#')]
	return nueva.lstrip('vV'), notas[:6], url


def al_abrir(raiz, version, cerrar_app):
	"""Busca en segundo plano; si hay versión nueva, muestra el cartel. cerrar_app() guarda y cierra la app."""
	version = os.environ.get('BPMAUTOE_PROBAR_VERSION', version)

	def fondo():
		res = buscar(version)
		if res:
			raiz.after(0, lambda: Cartel(raiz, version, res, cerrar_app))
	threading.Thread(target=fondo, daemon=True).start()


class Cartel:
	def __init__(self, raiz, version, res, cerrar_app):
		self.nueva, notas, self.url = res
		self.cerrar_app = cerrar_app
		t = self.t = tk.Toplevel(raiz, bg=FONDO, padx=22, pady=16)
		t.title('BPM auToe')
		t.resizable(False, False)
		t.attributes('-topmost', True)
		tk.Label(t, text='Hay una versión nueva: %s' % self.nueva, bg=FONDO, fg='white',
				 font=('Segoe UI', 13, 'bold')).pack(anchor='w')
		tk.Label(t, text='(tenés la %s)' % version, bg=FONDO, fg=TEXTO, font=('Segoe UI', 9)).pack(anchor='w')
		if notas:
			tk.Label(t, text='Qué cambia:', bg=FONDO, fg=TEXTO, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(12, 2))
			for n in notas:
				tk.Label(t, text='• ' + n.lstrip('-*• '), bg=FONDO, fg=TEXTO, font=('Segoe UI', 10),
						 wraplength=360, justify='left').pack(anchor='w')
		self.estado = tk.Label(t, text='', bg=FONDO, fg=TEXTO, font=('Segoe UI', 9))
		self.estado.pack(anchor='w', pady=(10, 0))
		f = tk.Frame(t, bg=FONDO)
		f.pack(fill='x', pady=(8, 0))
		self.bSi = tk.Button(f, text='Actualizar', command=self.actualizar, bg=ACENTO, fg='white', relief='flat',
							 activebackground=ACENTO, font=('Segoe UI', 10, 'bold'), padx=16, pady=4)
		self.bSi.pack(side='left')
		self.bNo = tk.Button(f, text='Ahora no', command=t.destroy, bg=BOTON, fg='white', relief='flat',
							 activebackground=BOTON, font=('Segoe UI', 10), padx=16, pady=4)
		self.bNo.pack(side='left', padx=(10, 0))
		t.update_idletasks()
		x = raiz.winfo_x() + 40
		y = raiz.winfo_y() + raiz.winfo_height() + 20
		t.geometry('+%d+%d' % (x, y))

	def actualizar(self):
		self.bSi.config(state='disabled')
		self.bNo.config(state='disabled')
		self.estado.config(text='Bajando la versión %s…' % self.nueva)
		threading.Thread(target=self._bajar, daemon=True).start()

	def _bajar(self):
		destino = os.path.join(tempfile.gettempdir(), 'BPM-auToe-%s-instalador.exe' % self.nueva)
		try:
			req = urllib.request.Request(self.url, headers={'User-Agent': AGENTE['User-Agent']})
			with urllib.request.urlopen(req, timeout=60) as r, open(destino, 'wb') as f:
				f.write(r.read())
		except Exception:
			self.t.after(0, self._fallo)
			return
		self.t.after(0, lambda: self._instalar(destino))

	def _fallo(self):
		self.estado.config(text='No se pudo bajar. Probá de nuevo más tarde.')
		self.bNo.config(state='normal', text='Cerrar')

	def _instalar(self, archivo):
		# el instalador espera a que la app se cierre, instala y la vuelve a abrir
		subprocess.Popen([archivo, '/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], close_fds=True)
		self.cerrar_app()
