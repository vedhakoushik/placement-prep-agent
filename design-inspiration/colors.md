# Colour Tokens

Copy these as CSS custom properties onto `:root`. Never hardcode hex values in component code.

```css
:root {
  /* ── Backgrounds (darkest → lightest) ── */
  --bg-canvas:   #080b14;   /* outermost page background */
  --bg-base:     #0f1117;   /* main content area */
  --bg-surface:  #1a1d27;   /* cards, sidebar, panels */
  --bg-elevated: #22263a;   /* hover state, tooltips, dropdowns */

  /* ── Borders ── */
  --border:        #2a2d3a;   /* default border */
  --border-active: #4F46E5;   /* focused input, highlighted card */
  --border-subtle: #1f2937;   /* internal dividers inside cards */

  /* ── Primary (indigo → violet gradient) ── */
  --primary:   #4F46E5;
  --primary-2: #7C3AED;
  --primary-shadow: rgba(79, 70, 229, 0.4);

  /* ── Accent (for text, keys, mono labels) ── */
  --accent:      #818cf8;
  --accent-dim:  #6366f1;

  /* ── Semantic colours ── */
  --green:       #4ade80;
  --green-bg:    #052e16;
  --green-border:#14532d;

  --orange:       #fb923c;
  --orange-bg:    #431407;
  --orange-border:#7c2d12;

  --red:          #f87171;
  --red-bg:       #450a0a;
  --red-border:   #7f1d1d;

  --blue:         #60a5fa;
  --blue-bg:      #1e3a5f;
  --blue-border:  #1d4ed8;

  /* ── Text hierarchy ── */
  --text-hi:  #f1f5f9;   /* headings, important values */
  --text-mid: #94a3b8;   /* body, descriptions */
  --text-lo:  #4b5563;   /* placeholders, disabled, captions */
  --text-muted: #374151; /* timestamps, meta */

  /* ── Purple accent (used in AI/bot elements) ── */
  --purple-surface: #1e1b4b;
  --purple-surface-2: #2e1065;
  --purple-border:  #3730a3;
  --purple-text:    #a78bfa;
  --purple-text-2:  #c4b5fd;
}
```

## Gradient recipes

```css
/* Primary button / active nav */
background: linear-gradient(135deg, var(--primary), var(--primary-2));

/* Page title text */
background: linear-gradient(135deg, #818cf8, #a78bfa);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
background-clip: text;

/* AI/bot card */
background: linear-gradient(135deg, var(--purple-surface), var(--purple-surface-2));

/* App header / doc header */
background: linear-gradient(135deg, #12101f 0%, #1a1030 100%);
```

## Colour decisions log

| Token | Hex | Inspired by |
|-------|-----|-------------|
| --bg-canvas | #080b14 | Raycast background |
| --primary | #4F46E5 | Tailwind indigo-600 |
| --accent | #818cf8 | Tailwind indigo-400 |
| --green | #4ade80 | Tailwind green-400 |
| --orange | #fb923c | Tailwind orange-400 |
| --red | #f87171 | Tailwind red-400 |
