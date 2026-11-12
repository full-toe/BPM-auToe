// panel: franja de BPM auToe. Las cajas vienen de la ENTRADA 0 (textura de 12 x 1 que arma logica.AplicarPanel
// según orientación y tamaño): 0 lienzo (ancho, alto, luces visibles, cantidad), 1 nivel de entrada,
// 2 confianza, 3 luces (x de la primera, y, separación, radio), 4..10 botones AUTO TAP RESYNC ÷2 ×2 ◀ ▶
// (x0, y0, x1, y1; oculto = 0 0 0 0). Coordenadas en pixeles, origen abajo a la izquierda.
uniform vec4 uA;   // tiempo (1..), tiempos por compás, golpe del tiempo, confianza
uniform vec4 uB;   // auto, auto 1, sin ritmo, audio que entra (0..1 = -60..0 dB)
uniform vec4 uC;   // x = (libre), y = (libre), z = botón apretado (1..7), w = su luz
out vec4 fragColor;
vec4 L(int i){ return texelFetch(sTD2DInputs[0], ivec2(i, 0), 0); }
float caja(vec2 p, vec4 r){ return step(r.x, p.x) * step(p.x, r.z) * step(r.y, p.y) * step(p.y, r.w); }
void main(){
	vec2 p = gl_FragCoord.xy;
	vec3 c = vec3(0.085);
	c = mix(c, vec3(0.16), step(p.y, 1.5));                                  // línea separadora
	vec4 lz = L(0), vu = L(1), cf = L(2), lu = L(3);
	// audio que entra (debajo del BPM): verde -> amarillo (-12 dB) -> rojo (-3 dB)
	float u = (p.x - vu.x) / max(1.0, vu.z - vu.x);
	vec3 col = u < 0.8 ? vec3(0.3, 0.8, 0.4) : (u < 0.95 ? vec3(0.95, 0.8, 0.2) : vec3(0.95, 0.3, 0.25));
	c = mix(c, vec3(0.18), caja(p, vu));
	c = mix(c, col, caja(p, vec4(vu.x, vu.y, vu.x + (vu.z - vu.x) * uB.w, vu.w)));
	// confianza del automático (línea fina)
	c = mix(c, vec3(0.2), caja(p, cf));
	c = mix(c, vec3(0.45, 0.75, 0.95), caja(p, vec4(cf.x, cf.y, cf.x + (cf.z - cf.x) * uA.w, cf.w)));
	// luces del compás (el 1 en ámbar)
	if (lz.z > 0.5) {
		float n = max(1.0, uA.y);
		for (int i = 0; i < 12; i++) {
			if (float(i) >= n) break;
			vec2 q = vec2(lu.x + float(i) * lu.z, lu.y);
			float d = length(p - q);
			bool esta = abs(float(i) + 1.0 - uA.x) < 0.5;
			vec3 cl = (i == 0) ? vec3(1.0, 0.75, 0.2) : vec3(0.45, 0.8, 0.95);
			vec3 ap = vec3(0.22);
			vec3 luz = esta ? mix(cl * 0.6, cl, uA.z) : ap;
			if (uB.z > 0.5) luz = ap * (esta ? 1.4 : 1.0);
			c = mix(c, luz, smoothstep(lu.w + 1.0, lu.w - 1.0, d));
		}
	}
	// botones (los ocultos vienen en 0)
	for (int i = 0; i < 7; i++) {
		vec4 r = L(4 + i);
		if (r.z <= r.x) continue;
		vec3 cb = vec3(0.2);
		if (i == 0 && uB.x > 0.5) cb = vec3(0.3, 0.55, 0.35);                         // AUTO prendido
		if (abs(float(i + 1) - uC.z) < 0.5) cb = mix(cb, vec3(0.85, 0.85, 0.9), 0.55 * uC.w);  // apretado
		c = mix(c, cb, caja(p, r));
	}
	fragColor = TDOutputSwizzle(vec4(c, 1.0));
}
