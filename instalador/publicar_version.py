"""publicar_version.py: arma una versión nueva de BPM auToe y (con --publicar) la sube a GitHub.

Pasos para sacar una versión:
  1. Subir VERSION en app/ritmo_app.py (p. ej. '0.7.1').
  2. Escribir en CAMBIOS.md una sección «## 0.7.1» con lo que cambia (una línea por cambio, con «- »):
     es lo que ve el cartel de «Hay una versión nueva».
  3. Guardar los cambios en git (commit y push).
  4. python instalador/publicar_version.py             -> arma el .exe y el instalador (para probar)
     python instalador/publicar_version.py --publicar  -> además crea la versión en GitHub con el instalador
Las apps instaladas lo ven la próxima vez que se abren.
"""
import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
APP = os.path.join(RAIZ, 'app')
ISCC = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Inno Setup 6', 'ISCC.exe')
if not os.path.exists(ISCC):
	ISCC = r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
GH = shutil.which('gh') or r'C:\Program Files\GitHub CLI\gh.exe'
REPO = 'full-toe/BPM-auToe'


def correr(cmd, **kw):
	print('>', ' '.join('"%s"' % c if ' ' in c else c for c in cmd), flush=True)
	r = subprocess.run(cmd, **kw)
	if r.returncode:
		sys.exit('ERROR (código %d)' % r.returncode)
	return r


def notas(version):
	"""Sección «## <version>» de CAMBIOS.md."""
	texto = open(os.path.join(RAIZ, 'CAMBIOS.md'), encoding='utf8').read()
	m = re.search(r'^## %s\b.*?\n(.*?)(?=^## |\Z)' % re.escape(version), texto, re.M | re.S)
	if not m or not m.group(1).strip():
		sys.exit('Falta la sección «## %s» en CAMBIOS.md' % version)
	return m.group(1).strip()


def main():
	publicar = '--publicar' in sys.argv
	fuente = open(os.path.join(APP, 'ritmo_app.py'), encoding='utf8').read()
	version = re.search(r"^VERSION = '([\d.]+)'", fuente, re.M).group(1)
	texto = notas(version)
	print('BPM auToe %s' % version)

	if publicar:
		estado = subprocess.run(['git', 'status', '--porcelain'], cwd=RAIZ, capture_output=True, text=True).stdout
		if estado.strip():
			sys.exit('Hay cambios sin guardar en git: hacé commit y push antes de publicar.\n' + estado)
		tags = subprocess.run(['git', 'tag', '--list', 'v' + version], cwd=RAIZ, capture_output=True, text=True).stdout
		if tags.strip():
			sys.exit('La versión v%s ya existe: subí VERSION en app/ritmo_app.py.' % version)

	# 1. el .exe (motor e ícono adentro)
	correr([sys.executable, os.path.join(APP, 'construir_exe.py')])
	salida = os.path.join(AQUI, 'salida')
	os.makedirs(salida, exist_ok=True)
	shutil.copy2(os.path.join(APP, 'portable', 'BPM auToe %s.exe' % version), os.path.join(salida, 'BPM auToe.exe'))

	# 2. el instalador
	correr([ISCC, '/Q', '/DVersion=' + version, os.path.join(AQUI, 'bpm_autoe.iss')])
	instalador = os.path.join(salida, 'BPM-auToe-%s-instalador.exe' % version)
	print('listo: %s (%.1f MB)' % (instalador, os.path.getsize(instalador) / 1e6))

	# 3. la versión en GitHub
	if publicar:
		archivo_notas = os.path.join(salida, 'notas_%s.md' % version)
		open(archivo_notas, 'w', encoding='utf8').write(texto + '\n')
		correr(['git', 'push'], cwd=RAIZ)
		correr([GH, 'release', 'create', 'v' + version, instalador, '--repo', REPO,
				'--title', 'BPM auToe %s' % version, '--notes-file', archivo_notas], cwd=RAIZ)
		print('publicada: https://github.com/%s/releases/tag/v%s' % (REPO, version))


if __name__ == '__main__':
	main()
