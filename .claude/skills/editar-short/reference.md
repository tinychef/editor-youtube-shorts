# Referencia del plan (`plan.json`)

## Raíz

| campo | qué hace |
|---|---|
| `work` | carpeta de `prepare` (relativa al plan) |
| `output` | MP4 de salida (relativo al plan) |
| `theme` | `"claro"` · `"oscuro"` · `"tonyciencia"` · `{"base", "accent", "accent_text", "on_accent", "vars": {...}}` |
| `fixes` | `{"Cloud": "Claude"}`: reemplazo de palabra completa en los subtítulos, sin importar mayúsculas |
| `captions` | ver abajo |
| `layout` | lista de `{"at", "mode", …opciones}`; ver Diseños |
| `zooms` | `[{"at", "dur" o "until", "scale"}]`: acercamientos suaves sobre la persona |
| `cut_zoom` | zoom alterno en cada corte (por defecto 1.09 full · 1.08 split · 1.05 popout · 1.04 sticker; `1` lo apaga) |
| `overlays` | tarjetas y textos (abajo) |
| `sfx` | `false` para apagar, o `{"volume": 1.0, "extra": [{"at", "name"}]}`. Nombres disponibles: `pop`, `whoosh`, `swoosh`, `rise`, `click`, `tick`, `type`, `ding`, `cash`, `thump`, `buzz` y `success` |
| `music` | `{"file": "musica.mp3", "level": -20, "duck": -9}`: música con ducking bajo la voz (usa música con licencia) |
| `denoise` | `true`: reducción de ruido suave en la voz |
| `progress` | `true` o un color: barra de progreso arriba |
| `default_layout` | modo si `layout` está vacío (default `sticker`) |

## Subtítulos (`captions`)

`{"max_words": 3, "max_chars": 20, "emphasis": ["gratis", "código abierto"], "auto_emphasis": true, "case": null, "karaoke": false, "y": null, "mute": [["w:40", "w:52"]], "replace": [{"w": [31, 33], "text": "la suscripción"}], "enabled": true}`

- `emphasis` acepta palabras o frases. Los números se resaltan solos (`auto_emphasis`).
- `case`: `"upper"`, `"lower"` o `null` (como se dijo).
- `karaoke`: la palabra que se está diciendo se ilumina.
- `y` fija la altura (px). Si no lo pones, se ubica solo por diseño y esquivando la cara.
- `replace` reescribe un tramo de palabras: índices de `transcript.txt`, ambos incluidos.

## Diseños (`layout`)

| modo | opciones |
|---|---|
| `full` | `zoom`, `face_y` (0–1, altura de la cara) |
| `sticker` | `zoom`, `head_y` (0–1, dónde queda la coronilla; default 0.47), `scale`, `max_face`, `dx`, `outline` (true/px/0), `shadow` |
| `split` | `split` (0–1, default 0.5), `radius`, `face_y` |
| `popout` | `frame_top` (0–1), `margin`, `radius`, `pop_px`, `outline` (true = borde blanco solo fuera del marco) |
| `pip` | `size` (px) |
| `broll` | — (la persona se oculta) |

Todos aceptan `trans` (s de transición, default 0.32) y `zone` (para mover la zona de tarjetas: `{"top": [y0, y1], "cap": y, "title": y}`).

## Elementos (`overlays`): campos comunes

| campo | qué hace |
|---|---|
| `type` | componente (abajo) |
| `id` | nombre para `attach` |
| `at`, `until` / `dur` | tiempos |
| `layer` | `"under"` (detrás de la persona recortada) u `"over"` (encima). Hay un default por tipo; en `full` todo va encima |
| `place` | `stack` (se apila en la zona gráfica), `header`, `title`, `abs`, `full` |
| `x`, `y`, `anchor` | posición en px con `place: abs` (anchor [0.5, 0.5] = centro) |
| `attach`, `corner`, `dx`, `dy` | pega el elemento a la esquina de otra tarjeta (`corner` [0,0] arriba-izq … [1,1] abajo-der) |
| `in`, `out` | animación: `"up"`, `"down"`, `"left"`, `"right"`, `"pop"`, `"fade"`, `"zoom"`, `"stamp"`, `"rise"` o `["up", 0.4]` |
| `sfx` | sonido al entrar (o `null`) |
| `mute_captions` | silencia subtítulos mientras se ve |
| `w` | ancho en px |

## Componentes

| type | props |
|---|---|
| `hook` | `lines` [2 líneas], `accent` [índices], `style` (`"box"` = caja oscura), `size` |
| `title` | `lines`, `accent`, `sub`, `size`, `style` (`"on-bg"` para texto oscuro) |
| `section` | `n`, `of`, `label`, `right` (pill a la derecha), `style` (`"big"` = «1 · TÍTULO» grande en acento) |
| `app` | `logo`, `name`, `sub`, `price`, `per`, `dark`, `states: [{"at", "state": "cancelado"/"gratis", "label"}]`, `free` |
| `logos` | `items: [{"logo", "label"}]`, `title`, `size`, `stagger`, `card` |
| `logo` | `logo`, `name`, `sub`, `size` |
| `list` | `title`, `badge`, `unit`, `rows: [{"logo", "name", "value"}]`, `total: {"label", "value"}`, `strike` (tiempo), `free`, `savings: {"label", "value"}` |
| `repo` | `repo` ("dueño/nombre"), `desc`, `stars`, `forks`, `license`, `lang`, `badge`, `badge_at`, `dark` |
| `browser` | `url`, `title`, `image` (ruta o data URI de una captura), `height`, `scroll` (0–1), `scroll_at`, `marks: [{"x","y","w","h" (%), "at"}]`, `chips` |
| `terminal` | `title`, `lines: [{"cmd", "out": [...]}]`, `cps` (velocidad de tecleo) |
| `search` | `query`, `hint`, `logo` |
| `checklist` | `title`, `items`, `every` (s entre ítems), `dark` |
| `stat` | `items: [{"label", "value", "unit", "sub"}]` (los números cuentan hacia arriba) |
| `compare` | `logo`, `name`, `per`, `from`, `to`, `strike` (tiempo) |
| `chat` | `title`, `logo`, `messages: [{"who": "user"/"ai", "text", "at"}]` |
| `image` | `src` (ruta), `title`, `caption`, `w`, `h` |
| `badge` | `text`, `color` (`acc`/`dark`/`danger`/`ok`/`light`), `size`, `tilt` |
| `stamp` | `text`, `color`, `size`, `tilt` |
| `cta` | `keyword`, `text`, `lead` (default «Comenta»), `sub` |
| `cursor` | `x`, `y`, `size`, `click_at` |
| `arrow` | `from` [x,y], `to` [x,y], `curve`, `color`, `label`, `dur` |
| `html` | `html`, `css` (componente a medida; ver abajo) |

### Componentes a medida (`html`)

Usa las clases del sistema: `card`, `card dark`, `pill acc|dark|danger|ok|light`, `mono`, `strike`.

Las variables de tema disponibles son `var(--accent)`, `var(--text)`, `var(--muted)`, `var(--card)`, `var(--radius)` y `var(--font-display)`.

Cualquier hijo se anima con atributos:

```html
<div class="card">
  <div data-in="up" data-at="0.2">Primera línea</div>
  <span class="pill acc" data-in="pop" data-at="0.8" data-sfx="pop">GRATIS</span>
  <b data-in="count" data-at="0.3" data-dur="1" data-to="$1,037">$1,037</b>
  <span data-in="type" data-at="1.2" data-dur="1.5" data-text="npm i claude">npm i claude</span>
  <span class="strike" data-in="strike" data-at="2">$29</span>
</div>
```

Tipos de `data-in`: `fade`, `pop`, `up`, `down`, `left`, `right`, `zoom`, `stamp`, `type`, `count`, `strike`, `dim`, `out`, `grow`, `draw` (paths SVG con `pathLength="1"`), `ripple`.

Las animaciones son funciones puras del tiempo: **no uses `@keyframes` ni `transition` de CSS**, porque cada cuadro se dibuja por separado.
