"""estado.py: muestra si el monitor está abierto, el uso de procesador y cuántas pruebas hay activas / en pausa."""
import os

import psutil

yo = os.getpid()
mon, activas, pausa = 0, 0, 0
for p in psutil.process_iter(['pid', 'name', 'cmdline']):
	if p.pid == yo or (p.info['name'] or '').lower() not in ('python.exe', 'pythonw.exe'):
		continue
	cmd = p.info['cmdline'] or []
	try:
		if len(cmd) > 1 and cmd[1].endswith('monitor_pruebas.py'):
			mon += 1
		elif any('multiprocessing' in c for c in cmd):
			if p.status() == psutil.STATUS_STOPPED:
				pausa += 1
			else:
				activas += 1
	except psutil.Error:
		pass
print('monitor abierto: %d | procesador %.0f%% | pruebas activas %d, en pausa %d' % (mon, psutil.cpu_percent(5), activas, pausa))
