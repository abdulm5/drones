# AgriForce brand kit

For UI touch-up. Everything here is taken from the pitch deck so the product and the slides match.
Deck: https://app.paper.design/file/01M7V1NGXEP1RNND34PFNT28TF

Files in this folder
- `logo-mark-on-light.svg`, `logo-mark-on-dark.svg`: sprout mark only (transparent background)
- `logo-lockup-on-light.svg`, `logo-lockup-on-dark.svg`: mark + "AgriForce" wordmark
- `tokens.css`: all values below as CSS variables

## Colors

| Name | Hex | Use |
|---|---|---|
| Evergreen | `#0E2A1B` | Dark background; main text on light |
| Forest | `#1B4D30` | Panels and dividers on dark |
| Fern | `#2F7D4F` | Accent on light: labels, links, icons, primary button |
| New leaf | `#BDE8A4` | Accent on dark; highlight background |
| Frost | `#EEF6EA` | App background on light |
| Snow | `#FFFFFF` | Cards, base |

Supporting
| Name | Hex | Use |
|---|---|---|
| Soft text on dark | `#DCEBDD` | Body copy on evergreen |
| Muted text on dark | `#9CC2A8` | Captions on evergreen |
| Muted text on light | `#4E6B58` | Captions on white / frost |
| Divider on light | `#DDEBD6` | Row separators |

### Safe text pairings (WCAG contrast ratio)

| Text | Background | Ratio | OK for |
|---|---|---|---|
| Snow | Evergreen | 15.4 | everything |
| New leaf | Evergreen | 11.2 | everything |
| Muted on dark `#9CC2A8` | Evergreen | 7.8 | everything |
| Evergreen | Snow | 15.4 | everything |
| Evergreen | Frost | 13.9 | everything |
| Evergreen | New leaf | 11.2 | everything |
| Forest | New leaf | 7.1 | everything |
| Snow | Forest | 9.8 | everything |
| Muted on light `#4E6B58` | Snow | 5.9 | body text |
| Fern | Snow | 5.0 | body text |
| Snow | Fern (button) | 5.0 | body text |
| Fern | Frost | 4.6 | body text (just passes) |

Do not use
- New leaf text on white or frost (1.4, unreadable).
- Fern text on new leaf (3.7, large headlines only).

### Status colors (suggested, not in the deck)

The product flags abnormal fields, so it needs warning and danger colors. These are my suggestion; adjust freely.

| Role | On dark | On light |
|---|---|---|
| Warning | `#F2B84B` (8.6 on evergreen) | `#8A5A00` (5.9 on white) |
| Danger | `#F0705A` (5.3 on evergreen) | `#B3261E` (6.5 on white) |

"Healthy" can stay fern / new leaf. Keep red and amber for fields that need attention so green never means "problem".

## Type

- Sans: Geist. Fallback: Inter Tight, Inter, system-ui.
- Mono: Geist Mono, for data labels, timestamps, sources, coordinates. All caps, tracking 0.08em.
- Headlines: weight 800, tracking -0.04em, tight line height (about 0.95).
- Titles: weight 700, tracking -0.02em.
- Body: weight 400, line height about 1.4.
- Both fonts are free on Google Fonts.

## Logo

- Sprout mark: stem and left leaf in the accent color, right leaf in the contrast color.
  - On light: fern `#2F7D4F` + evergreen `#0E2A1B`.
  - On dark: new leaf `#BDE8A4` + snow `#FFFFFF`.
- Wordmark: "AgriForce", Geist Bold 700, tracking -0.02em, capital A and F.
- The wordmark in the lockup SVGs is live text, so it needs Geist installed to render correctly. Outline it in a design tool before using it anywhere fonts can't load.
- Clear space: at least the width of one leaf on all sides. Minimum mark size 20px.

## Style rules used in the deck

- One big statement per screen; small mono caps for metadata.
- Flat color, no gradients, no shadows.
- Cards: white on frost, radius 20px; one dark evergreen card to mark the key step (the human approval).
- Show the source and age of every data value in mono (for example `NASA FIRMS · 38 SEC AGO`).
