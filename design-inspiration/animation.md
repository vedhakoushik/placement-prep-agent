# Animation & Motion System

## Principles

- **Fast and purposeful.** No animation > 400ms. Nothing animates without a reason.
- **Ease, not linear.** Always `ease`, `ease-in-out`, or a cubic-bezier. Never `linear` except for spinners.
- **Enter = fade up. Exit = fade down.** Content entering the page slides in from below (translateY positive → 0).
- **Hover = subtle lift.** Buttons and interactive cards rise slightly on hover (`translateY(-1px)` or `translateX(2px)`).
- **State changes = colour transition.** Border colour, background, text colour transitions are always `0.15s`.

---

## Keyframes library

```css
/* Page / card entrance */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Loading state pulse (text, skeleton) */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.5; }
}

/* Spinner rotation */
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Success bounce (for checkmarks) */
@keyframes bounceIn {
  0%   { transform: scale(0.6); opacity: 0; }
  60%  { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(1); }
}
```

---

## Usage map

| Animation | Duration | Easing | Used on |
|-----------|----------|--------|---------|
| fadeInUp | 0.4s | ease | Cards entering after graph runs |
| fadeInUp (staggered) | 0.4s + 0.1s delay per item | ease | Multiple cards in sequence |
| pulse | 1.5s | ease-in-out | Running step label in progress tracker |
| spin | 0.8s | linear | CSS spinner element |
| bounceIn | 0.3s | ease | Step icon when it completes |
| colour transition | 0.15s | ease | Border, background, text colour on hover/state change |
| transform (hover) | 0.2s | ease | Button lift, question item slide |

---

## CSS patterns

```css
/* Staggered card entrance */
.result-card:nth-child(1) { animation: fadeInUp 0.4s ease both; }
.result-card:nth-child(2) { animation: fadeInUp 0.4s 0.1s ease both; }
.result-card:nth-child(3) { animation: fadeInUp 0.4s 0.2s ease both; }

/* CSS spinner */
.spinner {
  width: 13px;
  height: 13px;
  border: 2px solid #312e81;
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

/* Interactive element hover */
.btn-primary {
  transition: transform 0.2s, box-shadow 0.2s;
}
.btn-primary:hover {
  transform: translateY(-1px);
}

/* Question item slide */
.question-item {
  transition: border-color 0.15s, transform 0.15s;
}
.question-item:hover {
  transform: translateX(2px);
}

/* State colour transition */
.input-field {
  transition: border-color 0.2s;
}
.nav-item {
  transition: all 0.15s;
}
```

---

## Rules

1. **Never use CSS `animation: all`** — it tanks performance. Specify exact properties.
2. **Stagger delays max at 0.2s** for 3 items. Beyond that, it feels slow.
3. **Spinners always use `linear`** — any easing makes them look broken.
4. **State transitions (border, background)** are always `0.15s ease`.
5. **Entrance animations** use `animation-fill-mode: both` so the element starts invisible.
6. **Don't animate layout properties** (width, height, padding) — animate `transform` and `opacity` only.
