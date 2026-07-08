# Component Patterns

Every reusable component, its exact CSS, and its states. Copy these directly.

---

## SIDEBAR
```css
.sidebar {
  width: 220px;
  min-height: 100vh;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  padding: 22px 14px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex-shrink: 0;
}
```

---

## NAV-ITEM (3 states)
```css
.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 11px;
  border-radius: var(--r-md);   /* 8px */
  font-size: 13px;
  color: var(--text-mid);
  cursor: pointer;
  transition: all 0.15s;
}
/* Default hover */
.nav-item:hover { background: var(--bg-elevated); color: var(--text-hi); }

/* Active state */
.nav-item.active {
  background: linear-gradient(135deg, var(--primary), var(--primary-2));
  color: #fff;
  font-weight: 600;
  box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);
}
```

---

## CARD (base)
```css
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);   /* 12px */
  padding: 18px;
  margin-bottom: 12px;
}
/* Highlighted card (active border) */
.card.active { border-color: var(--border-active); border-width: 1.5px; }
```

---

## BTN-PRIMARY
```css
.btn-primary {
  background: linear-gradient(135deg, var(--primary), var(--primary-2));
  color: #fff;
  border: none;
  border-radius: var(--r-sm);   /* 6px */
  padding: 10px 24px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 16px var(--primary-shadow);
  transition: transform 0.2s, box-shadow 0.2s;
  font-family: inherit;
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(79, 70, 229, 0.55);
}
```

---

## BTN-SECONDARY (ghost)
```css
.btn-secondary {
  background: var(--purple-surface);
  color: var(--purple-text);
  border: 1px solid var(--purple-border);
  border-radius: var(--r-sm);
  padding: 9px 18px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}
.btn-secondary:hover { background: var(--purple-surface-2); }
```

---

## INPUT-FIELD
```css
.input-field {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 9px 12px;
  color: var(--text-hi);
  font-size: 13px;
  font-family: inherit;
  transition: border-color 0.2s;
  width: 100%;
  outline: none;
}
/* Filled / focused state */
.input-field:focus,
.input-field.filled { border-color: var(--border-active); }
```

---

## METRIC-CHIP
```css
.metric-chip {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 10px 12px;
  text-align: center;
}
.metric-chip .label { font-size: 9px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 3px; }
.metric-chip .value { font-size: 15px; font-weight: 800; color: var(--text-hi); }
```

---

## DIFFICULTY-BADGE (3 variants)
```css
.badge { font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 10px; flex-shrink: 0; }

.badge-easy   { background: var(--green-bg);  color: var(--green);  border: 1px solid var(--green-border); }
.badge-medium { background: var(--orange-bg); color: var(--orange); border: 1px solid var(--orange-border); }
.badge-hard   { background: var(--red-bg);    color: var(--red);    border: 1px solid var(--red-border); }
```

---

## QUESTION-ITEM
```css
.question-item {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 11px 13px;
  display: flex;
  align-items: flex-start;
  gap: 9px;
  transition: border-color 0.15s, transform 0.15s;
}
.question-item:hover { border-color: var(--border-active); transform: translateX(2px); }
.question-item .q-num  { font-size: 10px; font-weight: 700; color: var(--text-muted); min-width: 18px; margin-top: 1px; }
.question-item .q-text { font-size: 12px; color: var(--text-mid); line-height: 1.5; flex: 1; }
```

---

## PROGRESS-TRACKER
```css
.progress-card {
  background: var(--bg-surface);
  border: 1.5px solid var(--border-active);
  border-radius: var(--r-lg);
  padding: 16px 18px;
  margin-bottom: 12px;
}
.progress-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
/* Step states */
.step.done   .step-icon { background: var(--green-bg); color: var(--green); }
.step.done   .step-label { color: var(--green); }
.step.running .step-label { color: var(--accent); animation: pulse 1.5s ease-in-out infinite; }
.step.pending .step-icon { background: #1f2937; color: var(--text-muted); }
.step.pending .step-label { color: var(--text-muted); }
```

---

## CHAT-BUBBLE (2 variants)
```css
/* User message — left aligned */
.chat-bubble.user {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 10px 10px 10px 2px;
  color: var(--text-hi);
}

/* Assistant message — right aligned */
.chat-bubble.assistant {
  background: linear-gradient(135deg, var(--purple-surface), var(--purple-surface-2));
  border: 1px solid var(--purple-border);
  border-radius: 10px 10px 2px 10px;
  color: var(--purple-text-2);
}

.chat-bubble {
  max-width: 75%;
  padding: 10px 13px;
  font-size: 12px;
  line-height: 1.6;
}
```

---

## CONTEXT-CHIP
```css
.context-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--purple-surface);
  border: 1px solid var(--purple-border);
  border-radius: var(--r-full);
  font-size: 11px;
  color: var(--accent);
  padding: 4px 10px;
  margin-bottom: 14px;
}
```

---

## MNC-BADGE / TYPE-BADGE (pill)
```css
.badge-pill {
  background: linear-gradient(135deg, var(--purple-surface), var(--purple-surface-2));
  color: var(--purple-text);
  font-size: 10px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: var(--r-full);
  border: 1px solid var(--purple-border);
}
```

---

## STATUS-DOT
```css
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 6px;
}
.status-dot.complete { background: var(--green); }
.status-dot.partial  { background: var(--orange); }
.status-dot.error    { background: var(--red); }
```

---

## DATA-TABLE
```css
.data-table { width: 100%; border-collapse: collapse; }
.data-table th {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 9px 12px;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-lo);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  text-align: left;
}
.data-table td { padding: 10px 12px; font-size: 12px; color: var(--text-mid); border-bottom: 1px solid var(--border-subtle); }
.data-table tr:hover td { background: var(--bg-surface); }
```
