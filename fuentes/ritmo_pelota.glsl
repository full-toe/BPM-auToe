// pelota: prueba visual de la grilla (cuadradito del tamaño del botón AUTO en la franja del tempo). Rebota cada 2 tiempos con aceleración constante
// (parábola, como la gravedad) y toca el piso justo en el tiempo; el fondo destella 70 ms en cada tiempo.
// Apagada (clic en el cuadradito la prende / apaga): gris, con la pelota quieta en el piso.
uniform vec4 uR;   // x fase de 2 tiempos (0..1), y tiempo del compás (1..), z fase del tiempo (0..1), w bpm
uniform vec2 uConf;  // x = confianza suavizada (0..1): altura del salto, destello y aplastado; y = prendida
out vec4 fragColor;
void main(){
	vec2 res = uTDOutputInfo.res.zw;
	vec2 p = gl_FragCoord.xy;
	float f = uR.x;
	float ms = uR.z * 60000.0 / max(uR.w, 1.0);
	bool on = uConf.y > 0.5;
	float k = on ? clamp(uConf.x, 0.0, 1.0) : 0.0;                              // confianza suavizada: escala todo
	vec3 col = vec3(0.06) + vec3(0.16) * k * step(ms, 70.0);      // destello de fondo: blanco tenue, 70 ms
	float piso = 2.0, r = res.y * 0.1,                              // piso al ras del borde de abajo
	      alto = res.y - piso - 2.0 * r - res.y * 0.06;
	float h = 4.0 * f * (1.0 - f) * k;                              // parábola; la altura = confianza
	float aplastar = (exp(-f * 25.0) + exp(-(1.0 - f) * 25.0)) * k;   // el golpe también según la confianza
	vec2 c = vec2(res.x * 0.5, piso + r + alto * h);
	vec2 q = (p - c) / vec2(r * (1.0 + 0.35 * aplastar), r * (1.0 - 0.3 * aplastar));
	bool uno = abs(uR.y - 1.0) < 0.5;
	col = mix(col, vec3(0.75), step(abs(p.y - piso), 1.0));                     // piso
	col = mix(col, !on ? vec3(0.3) : uno ? vec3(1.0, 0.75, 0.25) : vec3(0.95), smoothstep(1.0, 0.9, length(q)));
	if (!on) col *= 0.6;
	vec2 b = min(p, res - p);
	col = mix(col, vec3(0.25), step(min(b.x, b.y), 1.0));                     // borde del cuadradito
	fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
