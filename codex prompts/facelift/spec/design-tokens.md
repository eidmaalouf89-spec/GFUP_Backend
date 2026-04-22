# Design tokens

Copy `prototype/jansa/tokens.js` as-is into `frontend/src/tokens.ts`. Values below are reference only.

## Colors (CSS custom properties)

| Token | Dark | Light | Usage |
|---|---|---|---|
| `--bg` | `#0A0A0B` | `#FAFAFA` | page background |
| `--bg-elev` | `#111113` | `#FFFFFF` | cards |
| `--bg-elev-2` | `#18181B` | `#F4F4F5` | elevated / hover |
| `--bg-chip` | `#222226` | `#E8E8EA` | chip, track |
| `--line` | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.08)` | borders |
| `--text` | `#F5F5F7` | `#1C1C1E` | primary |
| `--text-2` | `#A1A1A6` | `#48484A` | secondary |
| `--text-3` | `#6E6E73` | `#8E8E93` | tertiary |
| `--accent` | `#0A84FF` | `#0A84FF` | Apple blue |
| `--good` | `#30D158` | `#1E8E3E` | VSO |
| `--warn` | `#FFD60A` | `#B58100` | VAO |
| `--bad` | `#FF453A` | `#D70015` | REF |
| `--neutral` | `#8E8E93` | `#636366` | HM |

## Status semantics (NEVER change)

- **VSO / FAV** → green `--good` — visa sans observation / favorable
- **VAO / SUS** → yellow `--warn` — visa avec observation / suspendu
- **REF / DEF** → red `--bad` — refusé / défavorable
- **HM** → gray `--neutral` — hors mission

## Typography

- UI: `'SF Pro Display', 'Inter', system-ui, sans-serif`
- Numbers: `'SF Mono', 'JetBrains Mono', monospace` — always `font-variant-numeric: tabular-nums`

## Type scale

| Role | Size | Weight | Letter-spacing |
|---|---|---|---|
| Hero number | 72–104px | 200–300 | -0.035em |
| Page title | 44px | 300 | -0.035em |
| Section title | 28px | 600 | -0.02em |
| Card title | 14–16px | 600 | -0.01em |
| Body | 13px | 400 | 0 |
| Eyebrow | 10–11px | 600 | 0.08–0.12em, uppercase |

## Motion

- Enter: `fadeInUp 0.4s cubic-bezier(.4,0,.2,1)`
- Hover lift: `transform: translateY(-2px)` + border brighten, `0.2s`
- Focus cinema: radial halo + 3 aperture rings + label, 650–700ms
- Theme toggle: sun↔moon crossfade/rotate, 400ms
- Chart lines: `drawLine` stroke-dashoffset 1000→0, 1.2s
