# Typography System

## Font stack

```css
font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;

/* For keys, code, tokens, component labels */
font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
```

## Type scale

| Role | Size | Weight | Colour | Usage |
|------|------|--------|--------|-------|
| display | 28px | 800 | gradient | Page title (hero) |
| heading-1 | 22px | 800 | --text-hi | Section headings |
| heading-2 | 18px | 700 | --text-hi | Card titles, company name |
| heading-3 | 15px | 700 | --text-hi | Sub-section labels |
| label | 10px | 700 | --text-lo | UPPERCASE CAPS field labels |
| body | 13px | 400 | --text-mid | Descriptions, summaries |
| body-sm | 12px | 400 | --text-mid | Table cells, secondary info |
| caption | 11px | 400 | --text-lo | Timestamps, meta, footers |
| mono | 10px | 700 | --accent | Component keys, token names |
| mono-sm | 9px | 400 | --text-lo | Prop values, hex codes |

## Rules

1. **Never use pure white (#ffffff)** — use --text-hi (#f1f5f9).
2. **Labels are always uppercase + letter-spacing: 0.08em** — no exceptions.
3. **Gradient text** is reserved for page/section display titles only (h1-level).
4. **Line height** — body: 1.7, heading: 1.2, caption: 1.5.
5. **Font weight jumps** must be visible — 400 → 600 → 700 → 800. Never 500 alone.
6. **Monospace** is only used for: keys (A · SIDEBAR), hex codes, prop values, CLI output.

## CSS reference

```css
/* Display title with gradient */
.display {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, #818cf8, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Section label (UPPERCASE) */
.label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-lo);
}

/* Section title with trailing line */
.section-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-lo);
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-title::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border-subtle);
}

/* Mono annotation key */
.ann-key {
  font-size: 9px;
  font-weight: 700;
  font-family: monospace;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--primary);
}
```
