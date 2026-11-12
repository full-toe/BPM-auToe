"""construir_exe.py: arma el .exe portable de BPM auToe (un solo archivo, sin necesitar Python instalado).
Uso: python construir_exe.py   ->   portable\\BPM auToe <versión>.exe
Lleva adentro el motor (BPM auToe/fuentes/ritmo_motor.py) y el ícono. La configuración la guarda al
lado del .exe (ritmo_app_config.json)."""
import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
MOTOR = os.path.normpath(os.path.join(AQUI, '..', 'fuentes', 'ritmo_motor.py'))   # BPM auToe/fuentes
fuente = open(os.path.join(AQUI, 'ritmo_app.py'), encoding='utf8').read()
VERSION = re.search(r"^VERSION = '([\d.]+)'", fuente, re.M).group(1)
nombre = 'BPM auToe %s' % VERSION
v4 = tuple(int(x) for x in (VERSION.split('.') + ['0'] * 4)[:4])

# datos de versión de Windows (Propiedades del archivo -> Detalles)
info = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=%(v)s, prodvers=%(v)s, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040A04B0', [
	StringStruct('CompanyName', 'Toe'),
	StringStruct('FileDescription', 'BPM auToe - detector de BPM (OSC, Ableton Link)'),
	StringStruct('FileVersion', '%(s)s'),
	StringStruct('ProductName', 'BPM auToe'),
	StringStruct('ProductVersion', '%(s)s'),
	StringStruct('OriginalFilename', '%(n)s.exe')])]),
	VarFileInfo([VarStruct('Translation', [0x040A, 1200])])]
)""" % {'v': v4, 's': VERSION, 'n': nombre}
trabajo = os.path.join(AQUI, 'construccion')
os.makedirs(trabajo, exist_ok=True)
open(os.path.join(trabajo, 'version.txt'), 'w', encoding='utf8').write(info)

sep = ';'
cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
	   '--name', nombre, '--icon', os.path.join(AQUI, 'bpm_autoe.ico'),
	   '--version-file', os.path.join(trabajo, 'version.txt'),
	   '--add-data', MOTOR + sep + '.', '--add-data', os.path.join(AQUI, 'bpm_autoe.ico') + sep + '.',
	   '--distpath', os.path.join(AQUI, 'portable'), '--workpath', os.path.join(trabajo, 'tmp'),
	   '--specpath', trabajo]
for m in ('matplotlib', 'pandas', 'IPython', 'PyQt5', 'PySide6', 'PyQt6', 'notebook', 'pytest', 'sympy'):
	cmd += ['--exclude-module', m]
cmd.append(os.path.join(AQUI, 'ritmo_app.py'))
print('armando', nombre, '...', flush=True)
r = subprocess.run(cmd)
exe = os.path.join(AQUI, 'portable', nombre + '.exe')
if r.returncode == 0 and os.path.exists(exe):
	print('listo: %s (%.1f MB)' % (exe, os.path.getsize(exe) / 1e6))
	shutil.rmtree(os.path.join(trabajo, 'tmp'), ignore_errors=True)
else:
	print('ERROR al armar el .exe')
	sys.exit(1)
