# Referencia del plan (`plan.json`)

## Raíz

| campo | qué hace |
|---|---|
| `work` | carpeta de `prepare` (relativa al plan) |
| `output` | MP4 de salida (relativo al plan) |
| `theme` | `"ios"` (predeterminado) · `"claro"` · `"oscuro"` · `"tonyciencia"` · `{"base", "accent", "accent_text", "on_accent", "vars": {...}, "bg": {...}}`; ver Tema ios |
| `fixes` | `{"Cloud": "Claude"}`: reemplazo de palabra completa en los subtítulos, sin importar mayúsculas |
| `captions` | ver abajo |
| `layout` | lista de `{"at", "mode", …opciones}`; ver Diseños |
| `zooms` | `[{"at", "dur" o "until", "scale"}]`: acercamientos suaves sobre la persona |
| `cut_zoom` | zoom alterno en cada corte (por defecto 1.09 full · 1.08 split · 1.05 popout · 1.04 sticker; `1` lo apaga) |
| `overlays` | tarjetas y textos (abajo) |
| `sfx` | `false` para apagar, o `{"volume": 1.0, "extra": [{"at", "name"}]}`. Nombres disponibles: `pop`, `whoosh`, `swoosh`, `rise`, `click`, `tick`, `type`, `ding`, `cash`, `thump`, `buzz`, `success`, `haptic` (tick háptico), `softpop` (pop suave), `bubble` (burbuja de mensaje), `sparkle` (destello), `notif` (campanita), `ratchet` (odómetro) y `marker` (plumón) |
| `music` | `{"file": "musica.mp3", "level": -20, "duck": -9}`: música con ducking bajo la voz (usa música con licencia) |
| `denoise` | `true`: reducción de ruido suave en la voz |
| `progress` | `true` o un color: barra de progreso arriba |
| `default_layout` | modo si `layout` está vacío (default `sticker`) |

## Tema ios

Es el predeterminado. Fondo gris de iOS con una cuadrícula de puntos que sube sin parar (en bucle, sin saltos) y una segunda capa de puntos más grandes y tenues a media velocidad. El fondo se dibuja en el compositor, no en la capa HTML, así que no rompe la caché de las tarjetas.

```json
"theme": {"base": "ios", "bg": {"scroll": 40, "cell": 28, "dot": 2.2, "dot_color": "#C7C7CC",
                                "parallax": {"speed": 0.5, "cell": 56, "dot": 4.6, "alpha": 0.42}}}
```

| `bg.…` | qué hace |
|---|---|
| `scroll` | px/s; positivo = hacia arriba, negativo = hacia abajo, `0` = quieto |
| `cell` | separación de los puntos (px) |
| `dot` | radio de los puntos (px) |
| `dot_color` | color de los puntos |
| `parallax` | `0`/`false` la apaga; un número es la velocidad relativa (0.5 = media); o `{"speed", "cell" (múltiplo de `cell`), "dot", "alpha", "color"}` |

Colores (variables CSS): tarjetas `#FFFFFF` con radio 26 px, sombra `0 8px 24px rgba(0,0,0,.08)` y borde `rgba(60,60,67,.12)`; texto `#000000`, secundario `#8E8E93`, separadores `#C6C6C8`; acento `#FF0069` (`--accent`, con texto blanco) y `#D6005C` para texto chico sobre claro (`--accent-text`); `--grad` = degradado de Instagram (`#FF7A00 → #FF0069 → #D300C5 → #7638FA`), solo en la palabra del CTA, los `badge` y los anillos; rojo `#FF3B30` y verde `#34C759` de iOS.

Tipografía: `-apple-system, "SF Pro Display"/"SF Pro Text"` con respaldo en Inter (incluida). Títulos y subtítulos en Display Heavy/Black y la interfaz en Text Regular/Semibold con tracking ajustado (`--track-display`, `--track-ui`). En un Mac se ve con SF Pro; en Linux o Windows, con Inter. Los archivos de SF Pro no se incluyen: la licencia de Apple no lo permite.

## Subtítulos (`captions`)

`{"max_words": 3, "max_chars": 20, "emphasis": ["gratis", "código abierto"], "auto_emphasis": true, "case": null, "karaoke": false, "y": null, "mute": [["w:40", "w:52"]], "replace": [{"w": [31, 33], "text": "la suscripción"}], "enabled": true}`

- `emphasis` acepta palabras o frases. Los números se resaltan solos (`auto_emphasis`).
- `case`: `"upper"`, `"lower"` o `null` (como se dijo).
- `karaoke`: la palabra que se está diciendo se ilumina.
- `y` fija la altura (px). Si no lo pones, se ubica solo por diseño y esquivando la cara.
- `replace` reescribe un tramo de palabras: índices de `transcript.txt`, ambos incluidos.
- `marker`: palabras o frases que se subrayan en rosa mientras se dicen (`"marker": ["importante"]`).

## Diseños (`layout`)

| modo | opciones |
|---|---|
| `full` | `zoom`, `face_y` (0–1, altura de la cara) |
| `sticker` | `zoom`, `head_y` (0–1, dónde queda la coronilla; default 0.47), `scale`, `max_face`, `dx`, `outline` (true/px/0), `shadow` |
| `split` | `split` (0–1, default 0.5), `radius`, `face_y` |
| `popout` | `frame_top` (0–1), `margin`, `radius`, `pop_px`, `outline` (true = borde blanco solo fuera del marco) |
| `pip` | `size` (px) |
| `broll` | — (la persona se oculta) |

Todos aceptan:
- `transition`: cómo se entra a este diseño. `"morph"` (default: el marco se transforma), `"zoom"` (zoom con desenfoque radial; el cambio se hace en el punto más borroso) o `"slide"` (el diseño nuevo empuja al anterior; `"dir": "left"` default, `"right"`, `"up"`, `"down"`).
- `trans`: duración de la transición en s (default 0.32 morph · 0.42 zoom · 0.45 slide).
- `zone`: para mover la zona de tarjetas: `{"top": [y0, y1], "cap": y, "title": y}`.

## Elementos (`overlays`): campos comunes

| campo | qué hace |
|---|---|
| `type` | componente (abajo) |
| `id` | nombre para `attach` |
| `at`, `until` / `dur` | tiempos |
| `layer` | `"under"` (detrás de la persona recortada) u `"over"` (encima). Hay un default por tipo; en `full` todo va encima |
| `place` | `stack` (se apila en la zona gráfica), `header`, `title`, `top` (arriba, y = 190), `abs`, `full` |
| `x`, `y`, `anchor` | posición en px con `place: abs` (anchor [0.5, 0.5] = centro) |
| `attach`, `corner`, `dx`, `dy` | pega el elemento a la esquina de otra tarjeta (`corner` [0,0] arriba-izq … [1,1] abajo-der) |
| `in`, `out` | animación: `"up"`, `"down"`, `"left"`, `"right"`, `"pop"`, `"fade"`, `"zoom"`, `"stamp"`, `"rise"`, `"drop"` (cae desde arriba con rebote), `"bounce"` (resorte) o `["up", 0.4]` |
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

### Motion graphics (iOS / Instagram)

Todos son funciones puras del tiempo, con su sonido sintetizado. Los tiempos internos (`at` de cada mensaje o ítem, `on_at`, `roll_at`, `draw_at`, `open_at`, `scroll_at`) aceptan `"w:N"` como cualquier otro.

| type | qué es | props |
|---|---|---|
| `notif` | notificación de iOS que baja desde arriba (`place: top`, encima de todo) · sonido `notif` | `logo`, `title` (o `app`), `text`, `time` (default «ahora») |
| `imessage` | chat tipo iMessage; antes de cada burbuja salen los tres puntos de «escribiendo…» · `bubble` | `title`, `sub`, `logo` (avatar), `messages: [{"who": "me"/"them", "text", "at", "typing"}]`, `typing` (s de puntos, default 0.75; `0` los quita), `color` (burbuja propia; default rosa, `"#007AFF"` = azul iMessage) |
| `toggle` | interruptores de iOS que se encienden (grupo tipo Ajustes) · `haptic` | `title`, `items: [{"label", "sub", "logo", "at", "color"}]`, o uno solo con `label`, `sub`, `logo`, `on_at` |
| `rings` | anillos de progreso que se llenan, con el degradado de Instagram · `haptic` | `items: [{"label", "value" (0–100), "display", "color"}]` (1 a 3; con uno solo, el número va al centro), `title`, `size`, `fill_dur` |
| `chart` | gráfica que se dibuja y números que cuentan · `haptic` / `marker` | `kind` (`"bar"` o `"line"`), `items: [{"label", "value", "display"}]`, `title`, `sub`, `highlight` (índice en rosa; default el último), `max`, `height`, `stagger`, `grow_dur`, `draw_dur` |
| `odometer` | contador tipo odómetro: cada dígito gira en su rueda · `ratchet` + `cash` al final | `to`, `from` (default «0»), `label`, `sub`, `size` (px), `color` (`"acc"`), `roll_at`, `roll_dur`, `end_sfx` (`null` lo quita), `card` (`false` = sin tarjeta, texto con contorno) |
| `hearts` | corazones (o emojis) que suben flotando, como un live de Instagram (`place: full`) · `softpop` | `count` (16), `emoji` (`["❤️","🔥"]`; sin esto son corazones dibujados), `x`, `y` (origen; default 815, 1430), `rise`, `spread`, `size`, `colors`, `seed`, `dur` (máx. 4 s) |
| `confetti` | explosión de confeti (cae detrás de la persona) · `sparkle` | `x`, `y` o `attach`+`corner`, `count`, `power`, `colors`, `seed`, `style: "sparkle"` |
| `sparkle` | destellos de estrella alrededor de un punto + onda | igual que `confetti` (`radius`) |
| `punch` | «palabra golpe»: una palabra gigante a pantalla completa por ~0,6 s (silencia subtítulos) · `thump` | `text`, `sub`, `style` (`"acc"` rosa · `"dark"` · `"light"` · `"clear"` sobre el video · `"grad"`), `size` (máximo; se ajusta al ancho) |
| `marker` | frase con un subrayado o marcador que se dibuja bajo una palabra · `marker` | `text`, `mark` (índices de palabras; default todas), `style` (`"underline"` o `"highlight"`), `color`, `size`, `draw_at`, `draw_dur` |
| `homescreen` | íconos de apps que rebotan en una rejilla de pantalla de inicio · `softpop` | `items: [{"logo", "label", "badge"}]`, `cols` (4), `size` (150), `stagger`, `title`, `card`, `wallpaper` (fondo con el degradado) |
| `island` | píldora Dynamic Island que se expande con un dato (`place: top`) · `haptic` | `text`, `sub`, `logo`, `value` (cuenta hacia arriba), `color` (`"ok"` = verde), `width`, `open_at` |
| `iphone` | iPhone con una captura que hace scroll | `src` (captura, relativa al plan), `scroll` (0–1, default 1; `false` = quieto), `scroll_at`, `scroll_dur`, `height` (default: lo que cabe en la zona), `time`, `status` (`false` sin barra de estado), `tilt` (grados), `html` (pantalla a medida) |

Ejemplos:

```json
{"type": "notif", "at": "w:15", "logo": "claude", "title": "Claude", "text": "Tu plan cambió: ahora puedes empezar gratis"},
{"type": "imessage", "at": "w:22", "until": "w:31", "title": "Claude", "logo": "claude",
 "messages": [{"who": "me", "text": "¿Me ayudas con mi landing?", "at": "w:23"}, {"who": "them", "text": "¡Lista en segundos!", "at": "w:28"}]},
{"type": "punch", "at": "w:34", "text": "Gratis"},
{"type": "odometer", "id": "ahorro", "at": "w:52", "until": "w:61", "label": "Ahorro total", "to": "$1,037", "roll_at": "w:56"},
{"type": "sparkle", "at": "w:60", "attach": "ahorro", "corner": [0.5, 0.5]},
{"type": "chart", "kind": "line", "at": "w:43", "until": "w:50", "title": "Seguidores", "items": [{"label": "May", "value": "1,2k"}, {"label": "Oct", "value": "12k"}]}
```

### Componentes a medida (`html`)

Usa las clases del sistema: `card`, `card dark`, `pill acc|dark|danger|ok|light|grad`, `mono`, `strike` y `mk` (palabra subrayada: `<span class="mk"><i class="mk-u" data-in="underline" data-at="0.5"></i><span class="mk-t">gratis</span></span>`; con `mk-h` y `data-in="hl"` es marcador).

Las variables de tema disponibles son `var(--accent)`, `var(--accent-text)`, `var(--grad)`, `var(--text)`, `var(--muted)`, `var(--card)`, `var(--fill)`, `var(--radius)`, `var(--font-display)` y `var(--font-ui)`.

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

Tipos de `data-in`: `fade`, `pop`, `up`, `down`, `left`, `right`, `zoom`, `stamp`, `type`, `count`, `strike`, `dim`, `out`, `grow`, `draw` (paths SVG con `pathLength="1"`), `ripple`, y los nuevos:
- `bounce` (entra con resorte), `bubble` (burbuja que crece desde su esquina), `underline` (barra con `--p` de 0 a 1, como `strike`) y `hl` (marcador que crece de izquierda a derecha).
- `ring` (círculo SVG con `pathLength="1"` que se llena hasta `data-to`, 0–1), `bar` (alto de 0 a `data-h` px), `switch` (interruptor de iOS; `data-on` = color).

Atributos extra: `data-ease="lin|out|inout|back|spring"` (curva de `draw`), `data-hide="1"` (oculto hasta su `data-at`) y `data-sfx-at="0,0.4,0.8"` (repite el sonido en esos desfases).

Las animaciones son funciones puras del tiempo: **no uses `@keyframes` ni `transition` de CSS**, porque cada cuadro se dibuja por separado.
