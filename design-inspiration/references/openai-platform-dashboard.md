# Reference: OpenAI Platform — Dashboard (Chat Prompts page)

Source: Screenshot of platform.openai.com — "Chat prompts" page

## What to copy

### Layout
- **Light theme** — pure white (#ffffff) main bg, very light gray sidebar (#f7f7f7 approx)
- **Sidebar is 192px wide**, no border — sits flush, separated only by background colour difference
- **Section groupings** in the sidebar: small gray caps labels ("Create", "Manage", "Optimize") above nav items
- **Nav items**: icon (16px, gray) + label (14px, #111), no background by default. Active item gets a very subtle gray pill background (#efefef)
- **Top breadcrumb bar**: "[Workspace] / [Page title]" in muted text, action buttons right-aligned
- **Content area**: centred, max-width ~740px, lots of breathing room

### Typography
- Font: system-ui / -apple-system (San Francisco on Mac, Segoe UI on Windows)
- Section grouping labels: 11px, font-weight 500, color #888, text-transform uppercase, letter-spacing 0.06em
- Nav item labels: 14px, weight 400, color #111
- Active nav: 14px, weight 500, color #111
- Page heading ("Chat prompts"): 22px, weight 600, color #111
- Sub-heading ("Create a chat prompt"): 18px, weight 500, color #111
- Card title: 14px, weight 500
- Card meta (date, user): 12px, color #888

### Cards ("Your prompts")
- White bg (#fff)
- Border: 1px solid #e5e5e5
- Border-radius: 10px
- Padding: 20px
- Shadow: very subtle — box-shadow: 0 1px 3px rgba(0,0,0,0.06)
- Icon: 32×32 rounded square, solid blue (#1971c2 or similar) with white chat icon inside
- Title: 14px 500 #111
- Meta line: 12px #999, space-between layout (date left, user right)
- Hover: border-color darkens slightly (#ccc)

### Create prompt area (centred hero)
- Large centered title
- Black pill button "+ Create" with white text
- Ghost input field "Generate…" with send arrow icon
- Suggestion chips below: pill shaped, border: 1px solid #e5e5e5, 12px text, #555 color, radius 20px

### Colour palette (light theme)
- Canvas: #ffffff
- Sidebar bg: #f7f7f7
- Border default: #e5e5e5
- Border hover: #cccccc
- Text primary: #111111
- Text secondary: #555555
- Text muted: #999999
- Active nav bg: #efefef
- Primary button: #000000 (black)
- Primary button text: #ffffff
- Blue icon: #1971c2
- Accent blue (light): #e8f0fe

## Key patterns to borrow
1. Sidebar section groupings with small-caps labels — much cleaner than flat nav lists
2. Black primary button — no gradient, high contrast, confident
3. Suggestion chip tags below inputs — great for "Focus: DSA / System Design / Behavioral"
4. Card layout with icon + title + meta — applies directly to "My Companies" page
5. Top breadcrumb: "Placement Prep / Research" with draft status badge
