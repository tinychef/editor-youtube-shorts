# Guía de estilo: qué hace que estos Shorts se vean profesionales

Esta guía resume el análisis de los 6 últimos videos de **@soyalonso.ai** (20–28 oct 2026) y de un post de **@sferro21** con el efecto de «salirse del marco». Los videos no se guardan en este repo. Aquí solo quedan las técnicas medidas y cómo las implementa el editor.

## Números medidos

| métrica | valor | cómo lo aplica el editor |
|---|---|---|
| Duración | 43–72 s | la skill pide confirmar recortes si pasa de 60 s |
| Ritmo de voz | 3,4–4,0 palabras/s | `prepare` deja pausas de ≤ 0,2 s y quita muletillas |
| Pausas entre palabras | mediana 0,0 s · p95 0,16–0,30 s · máx ~1 s | `--pause 0.20` + recorte con bordes ajustados a la energía de la voz |
| Primera palabra | en el cuadro 0 | el corte empieza 0,05 s antes de la primera palabra |
| Cortes / cambios visuales | cada 1–3 s (cortes de salto + animaciones de tarjetas) | zoom alterno en cada corte (`cut_zoom`) + una tarjeta por idea |
| Loudness | **-14,1 LUFS** integrado, rango 1,6–2,9 LU (voz muy comprimida) | cadena de voz + `loudnorm` a -14 LUFS / -1 dBTP |
| Resolución publicada | 720x1280 (lo que entrega Instagram) | el editor exporta 1080x1920 |

## Estructura de cada video (la fórmula)

1. **Gancho (0–3 s):** una afirmación con número o dinero.
   - Ejemplos: «Deja de pagar $900 al año por estas 5 apps», «Claude te puede traer clientes todos los días gratis».
   - En pantalla son dos líneas grandes, la segunda en color de acento: «5 APPS QUE PAGAS / YA SON GRATIS».
   - A veces aparece una fila de logos con precios o una lista de suscripciones que se tachan a $0.
2. **Cuerpo numerado:** «Número 1… Número 2…».
   - Siempre hay una etiqueta de sección visible: «1 de 5 · CRM», «2 · CLAUDE FILTRA».
   - Por cada punto: la tarjeta de la app (logo + nombre + precio) → la alternativa (repo de GitHub con estrellas, «$0») → una prueba visual (captura del navegador, terminal o chat).
3. **CTA (últimos 3–4 s):** «Si quieres X, comenta **PALABRA** y te lo mando por DM» + «tengo otras partes en mi perfil».

## Diseño (layouts)

- **Mitad y mitad:** gráficos arriba y la persona abajo (corte duro al 50%, o el video en un rectángulo redondeado sobre fondo oscuro). Es su diseño principal.
- **Persona a pantalla completa** con el título encima (gancho) o con una tarjeta sobre el pecho.
- **Solo gráficos** (la persona desaparece) con el subtítulo en texto oscuro abajo.
- **@sferro21: «salirse del marco».** El video va en un rectángulo redondeado abajo y la persona, recortada, se sale por arriba: la cabeza y las manos tapan el borde del marco y hasta las tarjetas de arriba.
- **Lo que pidió el dueño de este repo:** en vez de solo partir la pantalla, recortarlo a él con **borde blanco** (estilo sticker). Es el diseño `sticker`, y es el predeterminado. `popout` reproduce el «salirse del marco» y con `"outline": true` le pone borde blanco solo a lo que sale.

## Gráficos

- **Tarjetas tipo app**: blancas sobre crema o carbón sobre negro, radio ~26 px, sombra suave, tipografía de interfaz (tipo Inter).
- **Logos** en cuadros redondeados de color de marca: Photoshop «Ps», Otter, Asana, Bitly, 1Password, Salesforce, Slack, Miro, Claude…
- **Acento verde lima** (#C8F23A aprox.) para etiquetas «$0», «GRATIS», chips de verificado y números de sección, siempre con texto oscuro encima.
- **Precios que se tachan** (línea roja) y una etiqueta «$0» que aparece con un pop.
- **«Ahorro / año $864»** en una pastilla oscura.
- **Tarjetas de repo de GitHub** («owner/repo ★ 59,523 · MIT · CÓDIGO ABIERTO») y **navegador** con barra de URL y semáforos de macOS.
- **Terminal** tecleando comandos, **búsqueda** tecleándose («open source salesforce alternative»), **chat** con burbujas, **checklist** con palomitas y **sellos** rotados («SÍ A TODO»).
- **Una mascota pixel** propia aparece de vez en cuando junto a las tarjetas. Es identidad de marca: aquí se puede usar tu logo con `logo`/`badge`, o una imagen con `image`.

## Subtítulos

- 2–3 palabras a la vez, en minúsculas tal como se dicen.
- Tipografía redonda muy gruesa, blanca con sombra sobre el video y oscura sobre el fondo claro.
- Palabras clave en el color de acento («abierto.», «Excel.», «reseñas», «AI Fluency»).
- Altura: ~56–60% en mitad y mitad (justo debajo de la línea de corte) y ~70% a pantalla completa.
- Variante oscura: texto monoespaciado («gusta editar»).

## Sonido

- La voz no tiene silencios (los cortes se pegan) y está muy comprimida (rango de loudness ~2 LU).
- Hay una cama sonora suave y golpes o whooshes en las entradas de gráficos. En el espectrograma se ven como transitorios en cada animación.
- El editor sintetiza sus propios efectos, sin licencias de por medio: pop, whoosh, swoosh, tecleo, tick, caja registradora, ding y golpe de sello. Pone uno en cada entrada de tarjeta, logo, tachado y cambio de diseño. La música es opcional (`music`) y se agacha bajo la voz.
