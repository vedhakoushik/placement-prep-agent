# Spacing, Radius & Shadow System

## Spacing scale (px)

| Token | Value | Use case |
|-------|-------|----------|
| --space-1 | 4px | Icon gap, tight inline |
| --space-2 | 8px | Between label and input, nav icon gap |
| --space-3 | 12px | Grid gap inside cards |
| --space-4 | 16px | Card padding (compact) |
| --space-5 | 20px | Card padding (standard) |
| --space-6 | 24px | Section padding |
| --space-7 | 32px | Between major sections |
| --space-8 | 48px | Page section separation |

## Border radius

| Token | Value | Use case |
|-------|-------|----------|
| --r-xs | 4px | Badges, chips, small tags |
| --r-sm | 6px | Inputs, small buttons, metric chips |
| --r-md | 8px | Nav items, annotation cards, dropdowns |
| --r-lg | 12px | Main cards, panels |
| --r-xl | 14px | Page frames, modals |
| --r-full | 20px | Pills (context chip, MNC badge) |
| --r-circle | 50% | Avatars, step icons, spinners |

## Shadows

```css
/* Primary button glow */
box-shadow: 0 4px 16px rgba(79, 70, 229, 0.4);

/* Active nav item */
box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);

/* Hover button (stronger) */
box-shadow: 0 6px 20px rgba(79, 70, 229, 0.55);

/* Page frame / modal */
box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);

/* Card subtle */
box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
```

## Layout grid

- **Sidebar**: fixed 220px (200px compact)
- **Main content**: `flex: 1`, max-width 960px on wide screens
- **Two-column form grid**: `grid-template-columns: 1fr 1fr`, gap 12px
- **Metrics row**: `grid-template-columns: repeat(3, 1fr)`, gap 8px–10px
- **Component map**: `grid-template-columns: repeat(3, 1fr)`, gap 16px

## Rules

1. **No odd spacing values** (e.g., 7px, 11px, 15px) — always use the scale.
2. **Card padding** is 16px (compact) or 20px (standard). Never 24px inside a card.
3. **Gap between stacked cards** is 12px–14px. Never 8px (too tight) or 20px (too loose).
4. **Section separation** (between major h1-level blocks) is always 48px.
5. **Border radius escalates** with component size — small buttons get --r-sm, full cards get --r-lg.
