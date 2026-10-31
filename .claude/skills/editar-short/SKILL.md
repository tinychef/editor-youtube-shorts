---
name: editar-short
description: Edita un video vertical (o horizontal) para YouTube Shorts, Reels o TikTok. Corta pausas y muletillas y pone subtítulos palabra por palabra. Recorta a la persona con borde blanco sobre un fondo estilo iOS y agrega tarjetas y motion graphics animados (notificaciones, iMessage, anillos, gráficas, odómetro, corazones, confeti, palabra golpe) con logos de marcas, gancho, secciones numeradas, efectos de sonido y CTA final («Comenta PALABRA»). Úsala cuando el usuario pase un video (.mp4/.mov) y pida editarlo, hacerlo short o ponerle subtítulos, logos o tarjetas, o cuando diga «edítalo como los de IA» o «como @soyalonso.ai».
---

# Editar un Short

El pipeline tiene 2 etapas de máquina y 1 etapa creativa, que es la tuya:

1. **`prepare`**: transcribe con Whisper, corta pausas y muletillas, recorta a la persona y la sigue (cara y cabeza).
2. **Plan**: tú lees la transcripción y escribes `plan.json`, que es el storyboard. Ahí decides qué diseño, qué tarjeta y qué logo va en cada palabra.
3. **`render`**: compone a 1080x1920 con las tarjetas (Chromium), el recorte, los subtítulos, los efectos y la mezcla a -14 LUFS.

Todo se ejecuta desde la raíz de este repo. Si `shorts` está instalado con `pip install -e .`, se puede ejecutar desde cualquier carpeta con `python -m shorts`.

## 0 · Antes de empezar

- Corre `python -m shorts doctor` y arregla lo que marque con ✗.
- Si el usuario no dijo idioma, asume español (`--lang es`).
- No inventes contenido: las tarjetas solo dicen lo que la persona dice o lo que es verificable. Si un dato (precio, estrellas de GitHub) no está en el audio y no lo puedes verificar, deja ese campo fuera.

## 1 · Preparar

```bash
python -m shorts prepare RUTA/video.mp4 --name mi-short            # → work/mi-short/
```

Opciones:
- `--vocab "Nombre1, Marca2"`: nombres propios que Whisper suele escribir mal.
- `--fast`: recorte rápido, con más fugas del fondo.
- `--pause 0.2`: pausa máxima que se conserva.

**Lee `work/<nombre>/transcript.txt`.** Cada palabra lleva su índice `(N)`, que es el que usas en el plan como `"w:N"`.

Busca tres cosas:
- **Nombres mal escuchados.** «Cloud» casi siempre es *Claude*, «Gip» es *GIMP*, «Midly» es *Meetily*. Corrígelos en el plan con `fixes` (palabra por palabra) o con `captions.replace` (frases).
- **Tomas repetidas o errores** («perdón, otra vez…», frases dichas dos veces). Quítalas por índice de `transcript_src.txt` (no de `transcript.txt`) y vuelve a cortar sin re-transcribir:
  ```bash
  python -m shorts prepare RUTA/video.mp4 --name mi-short --drop "12-30,88-95" --recut
  ```
  Después de `--recut`, los índices de `transcript.txt` cambian: vuelve a leerlo antes de escribir el plan.
- **La estructura.** Identifica el gancho (primera frase), los puntos (lista numerada, pasos, apps) y el CTA («comenta X y te mando…»).

## 2 · Escribir el plan (storyboard)

Crea `plan.json` junto al video, o en `work/<nombre>/plan.json`. El ejemplo completo y comentado está en `examples/plan.ejemplo.json` y la referencia de cada campo en `reference.md` (en esta carpeta).

```json
{
  "work": "work/mi-short",
  "output": "out/mi-short.mp4",
  "theme": "ios",
  "fixes": {"Cloud": "Claude"},
  "captions": {"emphasis": ["gratis", "Claude"]},
  "layout": [
    {"at": 0, "mode": "full"},
    {"at": "w:14", "mode": "sticker", "transition": "zoom"},
    {"at": "w:120", "mode": "full", "transition": "slide"}
  ],
  "zooms": [{"at": "w:33", "scale": 1.12}],
  "overlays": [
    {"type": "hook", "at": 0, "until": "w:9", "lines": ["Deja de pagar $900", "por estas 5 apps"]},
    {"type": "section", "at": "w:14", "until": "w:60", "n": 1, "of": 5, "label": "Edición de fotos"},
    {"type": "notif", "at": "w:16", "logo": "photoshop", "title": "Adobe", "text": "Tu suscripción se renueva: $22.99"},
    {"type": "app", "at": "w:16", "until": "w:60", "logo": "photoshop", "name": "Photoshop", "price": "$22.99", "per": "al mes",
     "states": [{"at": "w:30", "state": "cancelado"}]},
    {"type": "punch", "at": "w:30", "text": "Cancelado"},
    {"type": "repo", "id": "gimp", "at": "w:40", "until": "w:60", "repo": "GNOME/gimp", "stars": "5,812", "badge": "$0"},
    {"type": "confetti", "at": "w:41", "attach": "gimp", "corner": [0.85, 0.3]},
    {"type": "cta", "at": "w:118", "until": "end", "keyword": "REPOS", "text": "y te mando los 5 links"}
  ]
}
```

**Tiempos.** Puedes escribir:
- `"w:N"`: inicio de la palabra N.
- `"w:N.e"`: final de la palabra N.
- `"w:N+0.3"`: con desfase en segundos.
- Segundos del video ya cortado.
- `"end"`.
- `"+1.5"`: relativo al `at` del mismo elemento; solo vale en `until`.

### Reglas de estilo (lo que hace que se vea profesional)

Salen del análisis de @soyalonso.ai. Ver `docs/estilo-referencia.md`.

1. **Gancho en 0–2,5 s.**
   - Usa `hook` de 2 líneas, con la 2.ª en color de acento.
   - Máximo unas 5 palabras por línea, con un número o una cifra si existe («$900», «3 apps», «en 1 hora»).
   - Diseño `full` mientras dura el gancho.
2. **El diseño por defecto es `sticker`**: la persona recortada con borde blanco y la zona de arriba libre para tarjetas. Es lo que pidió el dueño de este repo, en lugar de partir la pantalla a la mitad. Los otros diseños:
   - `full` para el gancho, el CTA o un remate emocional.
   - `broll` para mostrar algo largo (navegador, terminal, lista grande).
   - `split` (mitad y mitad) o `popout` (marco con la cabeza saliéndose, con `"outline": true` para borde blanco solo afuera) para variar.
   - `pip` para una demo a pantalla completa con la cara en una esquina.
3. **Ritmo del diseño.** Cambia de modo cada 6–12 s, nunca antes de 2 s.
   - Transición por defecto: el marco se transforma (`morph`).
   - Para variar, en la clave de `layout`: `"transition": "zoom"` (zoom con desenfoque, ideal para entrar a un remate) o `"transition": "slide"` (el diseño nuevo empuja al anterior; `"dir": "left"|"right"|"up"|"down"`). Máximo una de cada 3 transiciones debería ser `zoom`.
4. **Una tarjeta por idea, sincronizada con la palabra.**
   - Entra en la palabra clave (`"at": "w:N"`) y sale cuando cambia el tema.
   - Que no haya más de 2–3 tarjetas visibles a la vez: se apilan solas en la zona gráfica.
5. **Cada marca o herramienta mencionada lleva su logo en el momento exacto en que se nombra.** Usa `logo`, `app`, `logos` o `compare`.
   - Logos por nombre: `"claude"`, `"chatgpt"`, `"photoshop"`, `"github"`, `"notion"`…
   - Por dominio: `"meetily.ai"`.
   - Por archivo: `"logos/mi-marca.png"`.
   - Revisa los dudosos con `python -m shorts logo nombre1 nombre2`.
6. **Listas numeradas → `section`** (`n`, `of`, `label`) que dura todo el punto. Así el espectador siempre sabe en qué número va.
7. **Dinero y comparaciones.**
   - `app` con `states` → `cancelado` (tacha y atenúa) o `gratis` (tacha y pone la etiqueta «$0»).
   - `compare` para «antes → ahora».
   - `list` con `strike` para el resumen final («$86 → $0») y `savings`.
8. **Prueba visual.**
   - `repo` (repos de GitHub), `browser` (captura de una web) y `terminal` (comandos tecleándose).
   - `chat` (conversación con una IA), `checklist` y `stat` (cifras que cuentan hacia arriba).
   - Para algo único, usa `html`: tarjetas a medida con hijos animados por `data-in`. Ver `reference.md`.
9. **Énfasis.**
   - `badge` pegado a una tarjeta (`attach`: id de la tarjeta, `corner`: [x, y]) para «GRATIS», «100% local», «NUEVO».
   - `stamp` para un golpe («RATEROS», «SÍ A TODO»), máximo 1–2 por video.
   - `zooms` de 1,08–1,15 en 1–3 remates.
10. **Subtítulos.**
    - Salen solos (2–3 palabras) y nunca tapan la cara.
    - Pon en `captions.emphasis` las marcas y palabras clave, que salen en color de acento. Los números se resaltan solos.
    - Se silencian durante el `hook` y el `cta`.
11. **Cierre.** Usa `cta` con la palabra exacta que dice la persona («Comenta **REPOS**…») desde que la empieza a decir hasta `"end"`. En el tema `ios` la palabra va con el degradado de Instagram.
12. **Motion graphics (densidad).** Es lo que hace que el video se sienta vivo. Reglas:
    - **Un cambio visual cada 1–2 s, siempre amarrado a una palabra** (`"at": "w:N"`): una tarjeta que entra, un número que cuenta, un interruptor que se enciende, un subrayado…
    - **Una «palabra golpe» (`punch`) por idea principal**: la palabra clave gigante a pantalla completa por ~0,6 s, justo cuando se dice. No más de una cada ~8 s.
    - **Partículas (`confetti`, `sparkle`, `hearts`) en dinero o «gratis»**: `confetti` o `sparkle` pegado (`attach`) a la tarjeta del «$0», `hearts` cuando algo «encanta».
    - **Una notificación (`notif`) cuando se menciona una app**, con su logo, en la palabra exacta. Si la app ya tiene tarjeta, la notificación va antes.
    - **Máximo 3 gráficos a la vez**, nunca sobre la cara y siempre dentro de las zonas seguras (abajo). Las partículas de `confetti` caen detrás de la persona; `hearts` sube por la derecha, fuera de la cara.
    - Qué usar para cada cosa:
      - App mencionada → `notif` (+ `app`/`logo`). Varias apps → `homescreen`.
      - Conversación o «le escribes y te contesta» → `imessage` (con «escribiendo…»).
      - «Actívalo», «enciende», «modo X» → `toggle`.
      - Porcentajes o metas → `rings`. Crecimiento o comparación en el tiempo → `chart` (`"kind": "bar"` o `"line"`).
      - Precio o ahorro grande → `odometer`. Dato rápido («subiendo…», «100%») → `island`.
      - Mostrar una app o una web en el celular → `iphone` con una captura que hace scroll.
      - La frase clave → `marker` (subrayado o marcador) o `captions.marker` para subrayarla en los subtítulos.
13. **Zonas seguras de Shorts.** El 20% inferior y la franja derecha los tapan los botones y el título de YouTube. El motor ya ubica todo fuera, pero si usas `x`/`y` a mano, mantente entre y = 200 y 1550 y x < 920.
14. **Duración.** Ideal 30–60 s. Si después de los cortes pasa de 60 s, propón al usuario qué quitar antes de renderizar.

### Temas

- `ios` (**predeterminado**): gris de app de iOS (`#F2F2F7`) con una cuadrícula de puntos que sube despacio (con parallax), tarjetas blancas con esquinas de iOS, tipografía de Apple (SF Pro en Mac; Inter en Linux y Windows), acento rosa de Instagram `#FF0069`, el degradado de Instagram solo en destacados (palabra del CTA, badges y anillos), rojo y verde de iOS para tachados y palomitas. Los subtítulos marcan las palabras clave en rosa.
- `claro`: papel crema con cuadrícula y acento lima.
- `oscuro`: carbón con puntos y acento lima.
- `tonyciencia`: la marca del usuario. Ámbar `#C8922A`, esquinas duras, sombras pixel y fuente pixel en etiquetas.

Para personalizar: `{"base": "oscuro", "accent": "#FF5A1F"}`. El fondo de `ios` también: `{"base": "ios", "bg": {"scroll": -25, "parallax": 0}}` (ver `reference.md`).

## 3 · Render

1. **Mira cuadros sueltos primero.** Es rápido y sirve para corregir posiciones y textos:
   ```bash
   python -m shorts render plan.json --frames "1.0,w:20,w:45,w:80"
   ```
   Los PNG quedan en `work/<nombre>/stills/`. **Míralos con la herramienta de lectura de imágenes.**
2. **Render final:**
   ```bash
   python -m shorts render plan.json                   # MP4 1080x1920 30 fps, audio -14 LUFS
   python -m shorts render plan.json --draft           # borrador 540x960, más rápido
   python -m shorts render plan.json --from 10 --to 25 # solo un tramo
   ```

## 4 · Revisar (siempre, antes de entregar)

```bash
python -m shorts qa out/mi-short.mp4    # hoja de contactos cada 2 s + loudness
```

Abre el `*_qa.jpg` y comprueba:
- [ ] Hay un cambio visual cada 1–2 s y ninguna parte del video se queda quieta más de ~3 s.
- [ ] El gancho se lee en el primer cuadro, sin cortarse ni salirse.
- [ ] Ninguna tarjeta tapa la cara, y los subtítulos no caen en los recuadros rojos (zona de YouTube).
- [ ] Cada logo corresponde a lo que se dice en ese momento y no hay texto mal escrito (sobre todo marcas).
- [ ] El recorte no deja trozos del fondo pegados: si los hay, prueba sin `--fast` o pide un fondo más liso.
- [ ] Loudness cerca de -14 LUFS y pico ≤ -1 dBTP.

Corrige el plan y vuelve a renderizar el tramo afectado con `--from/--to` para verificar. Después haz el render completo.

## 5 · Entregar

Pasa el MP4 al usuario. Resume en 3–5 líneas qué se cortó y qué tarjetas o logos se pusieron, y ofrece cambios concretos (otro tema, más o menos tarjetas, otra palabra para el CTA).

## Problemas comunes

| Síntoma | Causa · arreglo |
|---|---|
| Palabras mal escritas en subtítulos | `fixes` / `captions.replace` en el plan; `--vocab` en prepare |
| Se cortó una sílaba al final | sube `--pause` a 0.25 o vuelve a preparar; los bordes ya se ajustan a la energía de la voz |
| Una tarjeta no aparece | su `at` cae después de su `until`, o la tapa el diseño `full` (en `full` van encima solas) |
| Logo genérico (2 letras) | no está en Simple Icons: usa el dominio (`"marca.com"`) o pon `logos/marca.png` junto al plan |
| Recorte con fondo pegado | quita `--fast`; fondos lisos y buena luz ayudan mucho |
| Colores lavados (iPhone HDR) | se convierte solo a SDR si ffmpeg tiene `zscale` (`doctor` lo revisa) |
| Render lento | `--draft` para iterar; `--jobs N` para usar más núcleos |
| El fondo no se mueve | solo el tema `ios` lo trae; en otro tema agrega `"bg": {"scroll": 30}` (y `"parallax": 0.5`) |
| Demasiados gráficos o se tapan | máximo 3 a la vez; separa los `at` 1–2 s y quita partículas que no caigan en dinero o «gratis» |
