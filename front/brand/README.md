# Datinomics — Brand System v1

Sistema de identidad refinado. Mayo 2026.

## Estructura

- `Datinomics Logo System.html` — Brand book completo (abrir en navegador)
- `svg/` — Archivos vectoriales individuales
  - `mark-A-pulse.svg` ⭐ Marca principal recomendada
  - `mark-B-d-bars.svg` — Monograma D con barras
  - `mark-C-nodes.svg` — Constelación de nodos
  - `mark-D-spike.svg` — Línea de tendencia
  - `mark-E-matrix.svg` — Matriz de puntos
  - `mark-F-badge.svg` — Badge "Dn" para favicon/avatar
  - `mark-A-pulse-mono-black.svg` — Versión monocroma negra
  - `mark-A-pulse-mono-white.svg` — Versión monocroma blanca
  - `lockup-horizontal-color.svg` — Lockup completo a color
  - `lockup-horizontal-reverse.svg` — Lockup sobre fondo oscuro
  - `wordmark-only.svg` — Solo wordmark

## Tipografía

- **Wordmark:** Space Grotesk 700
- **UI:** DM Sans
- **Mono:** JetBrains Mono

Todas disponibles gratis en Google Fonts.

## Paleta

| Token        | Hex      | OKLCH                  | Uso             |
|--------------|----------|------------------------|-----------------|
| Indigo 900   | #241046  | oklch(.28 .13 290)     | Primario oscuro |
| Violet 700   | #5B2BC9  | oklch(.42 .18 290)     | Mark base       |
| Violet 500   | #8A5FF0  | oklch(.58 .20 290)     | Mark medio      |
| Violet 100   | #E8DEFF  | oklch(.94 .04 290)     | Fondo suave     |
| Amber 500    | #E8A53A  | oklch(.78 .16 70)      | Acento data     |

## Notas

- Los SVG usan `oklch()`. Para máxima compatibilidad navegador-antiguo,
  reemplazar con los hex del cuadro de paleta.
- Espacio libre mínimo: 1 barra completa alrededor del lockup.
- Tamaño mínimo del lockup horizontal: 80 px de alto.
- Para favicon usar `mark-F-badge.svg` o reducciones de `mark-A-pulse.svg`.
