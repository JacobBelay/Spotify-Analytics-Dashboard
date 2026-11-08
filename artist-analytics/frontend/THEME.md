# Theme & front-end guide

A short orientation for anyone new to CSS or React working on this app. The
code itself is commented in detail — this file is the map.

## The design, in four moves

Copy these four and anything you add will fit:

1. **Midnight black everywhere, lit by one aurora.** A single glow rises from
   the bottom centre of the viewport — blue, with a hot orange core. It is the
   only light source on the page.
2. **Electric blue is the accent; orange is its rare counterweight.** If
   everything glows, nothing does.
3. **Serif for display, sans for everything else.** The page headline and the
   big numbers are serif. That contrast is what makes it look designed rather
   than assembled.
4. **Labels are small, uppercase, letterspaced, with a dot in front.** Every
   panel carries one. It is what makes separate cards read as one system.

## Palette

Three source colors, taken as exact hex values:

| | Hex | Role |
| --- | --- | --- |
| Midnight Black | `#02070A` | the page, and text on blue fills |
| Electric Blue | `#0297DE` | the accent — buttons, links, focus, primary series |
| Cantaloupe Orange | `#FC734D` | counterweight — second series, warnings |

Measured against midnight black: blue is **6.25:1** and orange is **7.42:1**,
so both clear WCAG AA for normal text. Midnight-on-blue is also 6.25:1, which
is why buttons use dark text rather than white (white on blue is only 3.24:1).

Everything else derives from those three and lives in the `:root` block at the
top of `src/styles.css`. Nothing below that block hard-codes a color.

| Token | Value | Used for |
| --- | --- | --- |
| `--bg` | `#02070A` | the page |
| `--surface` / `--surface-2` | `#080E16` / `#0F1822` | cards / inputs and chips |
| `--border` | `#1A2633` | hairlines between layers |
| `--text` / `--text-2` / `--muted` | `#EAF2F9` / `#9FB2C4` / `#64788C` | three levels of emphasis |
| `--accent-strong` / `--accent-deep` | `#41B6EC` / `#026FA6` | hover / pressed |
| `--accent-soft` | `rgb(2 151 222 / 14%)` | tinted backgrounds |
| `--on-accent` | `#02070A` | text on a blue fill |
| `--spotify` / `--apple_music` / `--youtube` | blue / orange / `#3DDC97` | chart series |
| `--font-display` / `--font-ui` | system serif / Inter | headline and numerals / everything else |

Two deliberate departures from the source palette, both documented in the CSS:

- **Mint `#3DDC97` exists for data only.** The reference is a two-accent
  system, but three platforms need three separable hues on a chart. Mint never
  appears in UI chrome.
- **The serif is a system stack**, so the app needs no network at runtime. To
  swap in a webfont (Instrument Serif, Playfair), load it in `index.html` and
  change `--font-display` — one line.

### Changing the theme

Edit `--midnight`, `--blue` and `--ember`. Everything else — buttons, focus
rings, pills, the drop zone, the tooltip border, the aurora, the chart lines —
is derived from those three and follows automatically.

## How the aurora works

No markup: it is two pseudo-elements on `<body>`, both `position: fixed` so
the light stays put while the page scrolls.

- `body::before` — five stacked `radial-gradient`s. An `ellipse at 50% 92%` is
  centred near the bottom edge so most of it is on screen. Smallest and
  hottest is the orange core; the blue body sits over it, then two faint
  washes stop the edge being visible.
- `body::after` — the rays. `repeating-linear-gradient` makes infinite evenly
  spaced stripes; `mask-image` fades them out everywhere except inside the
  glow, and `skewX` fans them.

Cards are translucent with `backdrop-filter`, so the light reads through them
instead of being blocked.

## File map

| File | What it does |
| --- | --- |
| `index.html` | The one static page. Holds the empty `<div id="root">`. |
| `src/main.tsx` | Starts React and renders `<App />` into that div. |
| `src/styles.css` | Every style in the app, tokens first. |
| `src/App.tsx` | Root component. Picks which screen to show. |
| `src/api.ts` | All server calls in one place. |
| `src/types.ts` | TypeScript shapes of the server's data. |
| `src/format.ts` | Number and date formatting helpers. |
| `src/components/` | One file per screen or panel. |

## React concepts, and where to read each one

Each file's header comment teaches the idea it best demonstrates:

1. **`main.tsx`** — how React attaches to a page at all.
2. **`App.tsx`** — components, `useState`, `useEffect`, props, conditional
   rendering, list keys.
3. **`components/KpiRow.tsx`** — a pure presentational component: props in,
   JSX out, callback up.
4. **`components/ConnectForm.tsx`** — controlled form inputs, and the hero.
5. **`components/Dashboard.tsx`** — two effects with different dependency
   arrays, and why splitting them matters.
6. **`components/UploadBox.tsx`** — `useRef`, and drag-and-drop.
7. **`components/ScenarioPanel.tsx`** — editing a list in state without
   mutating it.
8. **`components/TrendChart.tsx`** — describing a chart declaratively.

## Useful classes

| Class | What it gives you |
| --- | --- |
| `.card` | translucent panel, hairline border, lit top edge |
| `.eyebrow` | the dotted micro-label. Add `.ember` for an orange dot |
| `.btn` / `.btn.secondary` | glowing blue pill / quiet outline |
| `.btn-orb` | the circular ringed CTA |
| `.wordmark` | the corner logotype with its glowing dot |
| `.hero` / `.hero-row` / `.rail` / `.stat` | the headline block and its stat rails |
| `.display` + `<em>` | serif headline treatment anywhere, with one italic word |

## Accessibility rules this theme follows

- Anything clickable is a real `<button>` or `<a>`, never a styled `<div>` —
  with one exception, the drop zone, which hand-rolls the keyboard handling a
  button gives free.
- Focus rings are never removed, only restyled (`--ring`).
- Color is never the only signal: deltas carry ▲/▼, status rows carry words.
- The three chart hues stay distinguishable for color-blind readers.
- Animation is disabled under `prefers-reduced-motion`.
- Numbers use `font-variant-numeric: tabular-nums` so they don't jiggle.

## Running it

```bash
npm install
npm run dev      # dev server with hot reload
npm run build    # type-check, then produce dist/
```

The dashboard needs the backend (`docker compose up` in `artist-analytics/`).
Without it the app still loads and shows a "backend isn't running" banner.
