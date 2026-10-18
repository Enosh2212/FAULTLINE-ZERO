# FAULTLINE ZERO — Design System & Visual Specification

## Aesthetic Philosophy: Synthora AI Agent Platform × Apple Liquid Glass

The visual language of FAULTLINE ZERO merges the high-density technical clarity of advanced AI agent platforms (Synthora) with the organic depth, optical refractions, and restrained elegance of Apple Liquid Glass.

---

## 1. Color Palette & Token Architecture

All colors are strictly mapped to CSS custom properties in `styles.css`. No raw hex codes are sprinkled inline.

### Base Backgrounds & Surfaces
- `--bg-canvas`: `#020403` — Ultra-deep, cold carbon base canvas.
- `--bg-surface`: `#0A100E` — Elevated liquid container surface.
- `--bg-surface-elevated`: `#111B17` — Floating card and panel surface.
- `--bg-surface-frosted`: `rgba(10, 16, 14, 0.72)` — Frosted glass overlay with `backdrop-filter: blur(16px)`.

### Synthora Emerald & Mint Accents
- `--accent-primary`: `#189260` — Deep electric emerald (primary actions, active states).
- `--accent-mint`: `#29C481` — High-visibility bright mint (key highlights, node borders).
- `--accent-dark`: `#15634F` — Deep forest green (subtle container glow, border undertones).
- `--accent-glow`: `rgba(41, 196, 129, 0.18)` — Soft ambient lighting.

### Status & Semantic Indicators
- `--status-danger`: `#E05244` — Pure coral (strictly reserved for empirical regressions, broken invariants, test failures).
- `--status-danger-glow`: `rgba(224, 82, 68, 0.22)` — Critical anomaly glow.
- `--status-warning`: `#E09F3E` — Warm amber (strictly reserved for dynamic counterexample synthesis and warnings).
- `--status-success`: `#29C481` — Mint green (clean gates, passed invariants, healthy connections).
- `--status-neutral`: `#696B97` — Muted violet (inconclusive verdicts, secondary metadata).

### Typography & Neutrals
- `--text-primary`: `#F1F7E8` — High-legibility warm off-white (headings, primary body text, contrast ratio > 12:1 against canvas).
- `--text-secondary`: `#A3B2AA` — Subtle mint-tinted gray (secondary descriptions, metadata labels).
- `--text-muted`: `#687770` — Muted timestamp text and inactive controls.
- `--border-subtle`: `rgba(241, 247, 232, 0.08)` — Translucent hairline border.
- `--border-glass`: `rgba(41, 196, 129, 0.18)` — Active glowing glass border.

---

## 2. Liquid Glass Specifications

All cards, headers, command bars, and modals employ layered liquid glass styling:
```css
background: rgba(10, 16, 14, 0.78);
backdrop-filter: blur(16px) saturate(140%);
-webkit-backdrop-filter: blur(16px) saturate(140%);
border: 1px solid rgba(241, 247, 232, 0.08);
box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.45),
            inset 0 1px 0 0 rgba(255, 255, 255, 0.08);
```

### Optical Refraction & Specular Highlights
- Liquid glass containers feature an inner specular highlight (`inset 0 1px 0 0 rgba(255, 255, 255, 0.08)`) simulating light hitting the top edge of curved crystal glass.
- Hover states transition the outer border to `--accent-mint` with a soft outer glow (`box-shadow: 0 0 20px rgba(41, 196, 129, 0.12)`).

---

## 3. Typography Hierarchy

- **Font Family**: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif.
- **Code Family**: "JetBrains Mono", "Fira Code", monospace.
- **Display Hero**: 48px / 1.1 line-height / Weight 800 / Tracking -0.03em
- **Section Heading**: 28px / 1.25 line-height / Weight 700 / Tracking -0.02em
- **Card Heading**: 16px / 1.4 line-height / Weight 600 / Tracking -0.01em
- **Body Regular**: 14px / 1.5 line-height / Weight 400
- **Code & Metrics**: 12px / 1.4 line-height / Weight 500

---

## 4. Professional Iconography (Zero-Emoji Policy)

Per engineering specifications, **emojis are strictly prohibited** throughout the user interface, status badges, buttons, logs, and notification toasts.

All icons are rendered as precise, inline scalable vector graphics (`SVG`) with clean 2px strokes and consistent geometry:
- **Brand / Run Action**: Lightning Bolt (`<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>`)
- **FalkorDB Graph / Topology**: Network Grid (`<rect x="3" y="3".../>`)
- **Audit Memory**: History Clock (`<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>`)
- **Invariants**: Shield / Rule Book (`<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>`)
- **Git Branch / Commits**: Git Branch / Commit (`<line x1="6" y1="3" x2="6" y2="15"/>...`)
- **Copy**: Dual Clipboard (`<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>...`)
