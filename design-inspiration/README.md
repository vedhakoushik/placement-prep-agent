# Design Inspiration — Reference System

## Philosophy

Dark, dense, precise. Inspired by **Linear**, **Vercel**, and **Raycast**.

- Every surface is a step darker or lighter than its parent — no flat same-colour stacks.
- Colour carries meaning: indigo/violet = action, green = success, orange = warning, red = danger.
- Text is never pure white. Use token hierarchy: --text-hi → --text-mid → --text-lo.
- Spacing is deliberate. Nothing is centred by accident or padded to breathe — every gap has a reason.
- Animations are fast (150ms–400ms) and purposeful (fade-in, slide, pulse). No spin-for-spin's-sake.

## When to use what

| Situation | Pattern to apply |
|-----------|-----------------|
| Page background | --bg-canvas (#080b14) |
| Card / panel | --bg-surface (#1a1d27) on top of --bg-base |
| Interactive element background | --bg-elevated (#22263a) on hover |
| Primary action | gradient --primary → --primary-2 with shadow |
| Destructive action | --red text, --red-bg background |
| Success state | --green, --green-bg |
| Inline code / keys | monospace, --accent colour |
| Section dividers | 1px solid --border — never use a thick rule |

## Reference designs that inspired this system

- **Linear app** — sidebar, card density, typography weight contrast
- **Vercel dashboard** — metric chips, dark table rows, status dots
- **Raycast** — command palette style, compact nav items, mono keys
- **Tailwind UI dark** — spacing scale, component composition
