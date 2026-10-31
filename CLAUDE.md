# CLAUDE.md

Editor de YouTube Shorts. Cuando el usuario pase un video y pida editarlo, sigue la skill **`.claude/skills/editar-short/SKILL.md`**: `prepare` → leer `transcript.txt` → escribir `plan.json` → `render --frames` para revisar → `render` → `qa` → entregar.

## Comandos

```bash
python -m shorts doctor                      # revisa ffmpeg, Python, Chromium, MediaPipe
python -m shorts prepare video.mp4 --name x  # transcribe, corta pausas, recorta a la persona → work/x/
python -m shorts render plan.json            # 1080x1920, -14 LUFS → out/
python -m shorts render plan.json --frames "1,w:20"   # cuadros sueltos para revisar
python -m shorts qa out/x.mp4                # hoja de contactos + loudness
python -m shorts logo claude photoshop       # ver cómo se resuelve un logo
```

## Arquitectura

- `shorts/prepare.py`: transcripción (`transcribe.py`, faster-whisper), cortes (`cuts.py`), recorte y seguimiento (`matte.py`, MediaPipe, en paralelo).
- `shorts/render.py`: orquesta. `layout.py` (geometría de cada diseño + transiciones), `compose.py` (composición numpy/OpenCV: fondo → tarjetas → persona con borde blanco → subtítulos), `timeline.py` (plan → elementos), `captions.py`, `audio.py` (efectos sintetizados + mezcla a -14 LUFS).
- `shorts/overlay/`: las tarjetas son HTML/CSS dibujadas por Chromium cuadro a cuadro. `runtime.js` es determinista: cada cuadro es función pura de t, y una firma igual reutiliza la captura anterior.
- `shorts/themes.py`: temas `ios` (predeterminado), `claro`, `oscuro`, `tonyciencia` (variables CSS + fondo + estilo del recorte). `Backdrop` dibuja el fondo cuadro a cuadro: la cuadrícula de puntos de `ios` se mueve (`bg.scroll`, `bg.parallax`) en el compositor, nunca en la capa HTML, para no romper la caché de capturas.
- `shorts/logos.py`: logos (archivo propio → Simple Icons CC0 → monograma tipo app → favicon).

## Reglas

- Los videos de prueba, `work/` y `out/` no se suben (`.gitignore`). No subas videos de otros creadores.
- Animaciones de tarjetas: nada de `@keyframes`/`transition` en CSS. Todo va por `data-in` o por el runtime (puro en t). Partículas con semilla fija (`rng`), nunca `Math.random`. Las animaciones continuas (partículas, «escribiendo…») duran poco, porque cada cuadro distinto es una captura nueva.
- Dentro de una tarjeta, no pongas `visibility: visible` a un hijo: se vería también en la copia oculta de la otra capa. Usa `''` para heredar.
- Si cambias geometría de un diseño (`layout.py`), revisa también su zona de tarjetas y subtítulos (`zone()`), y mira cuadros sueltos de los 6 modos.
