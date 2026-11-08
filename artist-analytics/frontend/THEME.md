# Theme & front-end guide

A short orientation for anyone new to CSS or React working on this app. The
code itself is commented in detail — this file is the map.

## The palette: midnight black + sky blue

Midnight black carries the layout, sky blue carries meaning. The rule is: if
something is sky blue, you can click it or you should look at it. Everything
else stays in the blacks and greys.

Every color lives in one place — the `:root` block at the top of
`src/styles.css` — as a CSS custom property. Nothing below that block hard-codes
a color, so changing the theme means editing those lines and nothing else.

| Token | Value | Used for |
| --- | --- | --- |
| `--bg` | `#05060a` | the page — the deepest black |
| `--surface` | `#0d1017` | cards |
| `--surface-2` | `#161b25` | inputs, chips, hover states |
| `--border` | `#212a38` | hairlines between layers |
| `--text` | `#e9f1fa` | headings and numbers |
| `--text-2` | `#a5b4c8` | body copy and labels |
| `--muted` | `#6d7f97` | captions, axis ticks |
| `--accent` | `#38bdf8` | **sky blue** — buttons, links, focus |
| `--accent-strong` | `#7dd3fc` | hover (lighter reads as closer on dark) |
| `--accent-deep` | `#0284c7` | pressed states, subtle borders |
| `--accent-soft` | `rgb(56 189 248 / 12%)` | tinted backgrounds |
| `--on-accent` | `#04121c` | text on a sky-blue button |
| `--spotify` / `--apple_music` / `--youtube` | sky blue / amber / mint | chart series |
| `--good` / `--bad` / `--warn-text` | mint / rose / amber | status |

Three conventions worth keeping:

- **Depth comes from stacking surfaces, not shadows.** On a near-black page a
  drop shadow is invisible; a slightly lighter panel with a hairline border is
  what reads as "raised".
- **Never pure `#fff` on pure black** — it vibrates. The text tokens are
  blue-tinted off-whites so they belong to the same family as the accent.
- **Chart colors come from CSS variables, not literals.** React builds the
  string `var(--spotify)` from the platform name, so retheming the chart means
  editing the variable.

### Changing the theme

Want a different accent? Edit `--accent`, `--accent-strong`, `--accent-deep`,
`--accent-soft`, `--on-accent` and `--spotify` (the primary series shares the
accent hue). That is the whole change — the buttons, focus rings, pills, drop
zone highlight, tooltip border and main chart line all follow.

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

Each file's header comment teaches the idea it best demonstrates. Read them in
this order:

1. **`main.tsx`** — how React attaches to a page at all.
2. **`App.tsx`** — components, `useState`, `useEffect`, props, conditional
   rendering, list keys.
3. **`components/KpiRow.tsx`** — a pure presentational component: props in,
   JSX out, callback up.
4. **`components/ConnectForm.tsx`** — controlled form inputs.
5. **`components/Dashboard.tsx`** — two effects with different dependency
   arrays, and why splitting them matters.
6. **`components/UploadBox.tsx`** — `useRef`, and drag-and-drop.
7. **`components/ScenarioPanel.tsx`** — editing a list in state without
   mutating it.
8. **`components/TrendChart.tsx`** — describing a chart declaratively.

## Accessibility rules this theme follows

- Anything clickable is a real `<button>` or `<a>`, never a styled `<div>` —
  with one exception, the drop zone, which hand-rolls the keyboard handling a
  button gives free.
- Focus rings are never removed, only restyled (`--ring`).
- Color is never the only signal: deltas carry ▲/▼, status rows carry words.
- The three chart hues stay distinguishable for color-blind readers.
- Animation is disabled under `prefers-reduced-motion`.

## Running it

```bash
npm install
npm run dev      # dev server with hot reload
npm run build    # type-check, then produce dist/
```

The dashboard needs the backend (`docker compose up` in `artist-analytics/`).
Without it the app still loads and shows a "backend isn't running" banner.
