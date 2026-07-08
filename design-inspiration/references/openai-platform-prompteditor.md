# Reference: OpenAI Platform — Prompt Editor (detail view)

Source: Screenshot of platform.openai.com — prompt editor / playground view

## What to copy

### Layout (3-panel split)
- **Left panel** (sidebar): 192px, same #f7f7f7 as dashboard sidebar
- **Centre panel** (editor): fills remaining width, white bg
- **Right panel** (config/variables): ~280px, #f7f7f7 bg, 1px #e5e5e5 left border
- No heavy chrome — panels separated only by background + a hairline border

### Top bar
- Full-width, white, 48px tall, border-bottom 1px #e5e5e5
- Left: breadcrumb "Playground / Chat prompts / [name]" — 13px, #555
- Right: "Save" (black pill, 13px), "Test" (ghost outline, 13px), avatar

### Centre editor panel
- **Model selector tab row**: 13px labels, bottom border underline for active tab (2px #111), gray inactive
- **"System" textarea**: large, no border, font-size 14px, color #111, line-height 1.6, min-height 240px
  - Placeholder text: "You are a helpful assistant." — color #999
- **User / Assistant message blocks**: alternating gray (#f7f7f7) and white rows, each 14px #111
- **Add message** button: small ghost pill, "+ Add message", #555, border #e5e5e5
- Thin divider line (#e5e5e5) between message blocks

### Right config panel
- **Section label pattern**: 11px, weight 600, color #888, uppercase, letter-spacing 0.06em — same as sidebar section groupings
- **Model dropdown**: full-width, border 1px #e5e5e5, radius 6px, 13px, #111
- **Sliders** (Temperature, Max tokens): slim track (#e5e5e5), filled portion (#111), thumb circle 12px white with 1px #e5e5e5 border
- **Variables block**: shows `{{variable_name}}` tokens detected in the prompt
  - Each variable: pill shape, background #f0f0f0, 12px, #555, border-radius 4px
- **Tools / Functions toggle**: small toggle switch, indigo when ON (#0066ff), gray when OFF
- **Response format**: radio buttons (Text / JSON object / JSON Schema), 13px #111

### Colour palette (same light theme)
- Panel bg: #f7f7f7
- Editor bg: #ffffff
- Border: #e5e5e5
- Active tab underline: #111111
- Text primary: #111111
- Text secondary: #555555
- Text muted: #999999
- Slider fill: #111111 (or deep indigo #0066ff for tools)
- Variable chip bg: #f0f0f0
- Variable chip text: #555555

### Typography (same as dashboard)
- Section labels: 11px, 600, #888, uppercase, letter-spacing 0.06em
- Body / inputs: 14px, 400, #111
- Breadcrumb: 13px, #555
- Button: 13px, 500

## Key patterns to borrow
1. **3-panel shell** — sidebar + content + config/properties panel — applies to "Research" page (sidebar + form + live config strip)
2. **Section label style** in right panel — reuse exactly for focus area selectors and model controls
3. **Textarea with no border, just bg colour** — clean for the "Ask anything" chat input area
4. **Variable chip `{{syntax}}`** — apply to "Context chip" showing active company + role
5. **Tab row with bottom-border active state** — use on "Research / Chat / History" sub-tabs
6. **Slim slider** for any numeric config (confidence score threshold, etc.)
