"""
onset_variantes.py: compara curvas de golpes (onset) para el tempo, calculadas sobre 12 s de cada tema.
	python onset_variantes.py [cantidad]
"""
import math
import os
import sys
from multiprocessing import Pool

import numpy as np

import banco


def stft(y, sr, nfft=1024, fs_o=190.0):
	hop = max(64, int(round(sr / fs_o)))
	n = 1 + (len(y) - nfft) // hop
	idx = np.arange(nfft)[None, :] + hop * np.arange(n)[:, None]
	S = np.abs(np.fft.rfft(y[idx] * np.hanning(nfft), axis=1))
	return S, sr / hop


def mel(sr, nfft, nb=40, fmax=8000):
	f = np.fft.rfftfreq(nfft, 1 / sr)
	m = lambda h: 2595 * np.log10(1 + h / 700)
	im = lambda x: 700 * (10 ** (x / 2595) - 1)
	pts = im(np.linspace(m(30), m(fmax), nb + 2))
	W = np.zeros((nb, len(f)))
	for i in range(nb):
		a, b, c = pts[i:i + 3]
		W[i] = np.clip(np.minimum((f - a) / (b - a), (c - f) / (c - b)), 0, None)
	return W


def onset(y, sr, nombre):
	S, fs = stft(y, sr)
	if nombre == 'actual':                                  # como el motor: log1p(100·mag), media del flujo
		nb = int(10000 / (sr / 1024))
		L = np.log1p(100 * S[:, :nb])
		o = np.maximum(np.diff(L, axis=0), 0).mean(axis=1)
	else:
		M = mel(sr, 1024) @ (S ** 2).T                      # (bandas, marcos)
		D = 10 * np.log10(np.maximum(M, 1e-10))
		D = np.maximum(D, D.max() - 80)
		if nombre == 'mel_superflux':                       # máximo en frecuencia del marco anterior (menos vibrato)
			from numpy.lib.stride_tricks import sliding_window_view
			P = np.pad(D, ((1, 1), (0, 0)), mode='edge')
			Dm = sliding_window_view(P, 3, axis=0).max(axis=-1)
			o = np.maximum(D[:, 1:] - Dm[:, :-1], 0).mean(axis=0)
		elif nombre == 'mel_lag2':
			o = np.maximum(D[:, 2:] - D[:, :-2], 0).mean(axis=0)
		else:
			o = np.maximum(np.diff(D, axis=1), 0).mean(axis=0)
	return o, fs


def tempo(o, fs, bmin=70, bmax=180):
	k = max(3, int(0.3 * fs))
	x = np.maximum(o - np.convolve(o, np.ones(k) / k, 'same'), 0)
	x = x - x.mean()
	L = len(x)
	n = 1 << int(math.ceil(math.log2(2 * L)))
	X = np.fft.rfft(x, n)
	ac = np.fft.irfft(X * np.conj(X), n)[:L]
	ac /= max(ac[0], 1e-9)
	lags = np.arange(int(60 * fs / bmax), int(60 * fs / bmin) + 1)
	lags = lags[lags * 2 < L]
	idx = np.arange(L)
	a = lambda l: np.interp(l, idx, ac)
	bpms = 60 * fs / lags
	s = np.maximum(a(lags) + 0.5 * a(lags / 2.0) + 0.5 * a(2 * lags), 0) * np.exp(-0.5 * (np.log2(bpms / 120)) ** 2)
	return 60 * fs / lags[int(np.argmax(s))]


VARS = ['actual', 'mel', 'mel_superflux', 'mel_lag2']


def uno(caso):
	audio, anot, base, genero = caso
	try:
		y, sr = banco.leerAudio(audio)
		y = y[int(4 * sr):int(16 * sr)]
		ref = np.array([float(l.split()[0]) for l in open(anot) if l.strip()])
		bref = 60.0 / np.median(np.diff(ref))
		res = {}
		for v in VARS:
			o, fs = onset(y, sr, v)
			r = tempo(o, fs) / bref
			res[v] = (abs(r - 1) <= 0.04, any(abs(r / f - 1) <= 0.04 for f in (1, 2, 0.5)))
		return genero, res
	except Exception:
		return None


if __name__ == '__main__':
	n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
	casos = banco.listar('gtzan')
	casos = casos[::max(1, len(casos) // n)][:n]
	with banco.pool() as p:
		out = [r for r in p.map(uno, casos) if r]
	print('temas', len(out))
	for v in VARS:
		print('%-15s exacto %5.1f%%   octava ok %5.1f%%' % (v, np.mean([r[v][0] for g, r in out]) * 100,
														  np.mean([r[v][1] for g, r in out]) * 100))
