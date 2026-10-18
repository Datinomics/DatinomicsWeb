# Datinomics — Paquete completo

Sistema de identidad + landing + plataforma + iconset.
Mayo 2026.

## Contenido

### 📂 Archivos HTML principales
- **Datinomics Platform.html** — Plataforma interactiva navegable (explorador, empresas, alertas, API)
- **Datinomics Landing.html** — Landing page profesional
- **Datinomics Logo System.html** — Brand book con 6 direcciones de logo
- **Datinomics Iconset.html** — Showcase de los 22 iconos geométricos

### 📂 Carpetas de assets
- `platform/` — Source code de la plataforma (data.js, shell.jsx, charts.jsx, etc.)
- `icons/` — 22 iconos geométricos en SVG individual
- `brand/` — Brand system: 11 SVG (marcas, lockups, mono) + README + brand book

## Cómo abrirlo

Cualquier archivo .html se abre directamente en el navegador (doble-click).
La plataforma carga sus scripts desde `platform/` — mantené la estructura de carpetas.

## Sistema de diseño

- **Tipografía:** Space Grotesk (display) · DM Sans (UI) · JetBrains Mono (datos)
- **Color primario:** Violeta profundo · oklch(0.42 0.18 290)
- **Acento:** Ámbar · oklch(0.78 0.16 70)
- **Iconos:** 24×24 · stroke 2px · primitivas geométricas (□ ○ |)

## Para implementar

El frontend está construido en React 18 + Babel standalone (sin build step).
Si lo vas a integrar en un stack real, los archivos JSX se pueden transpilar
con Vite/Webpack y los datos en `platform/data.js` se reemplazan por tu API.

Un producto de **BERÁ**.
