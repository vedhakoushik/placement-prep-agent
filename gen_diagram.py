"""Generate architecture diagram for placement-prep-agent."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe

fig, ax = plt.subplots(figsize=(14, 24))
ax.set_xlim(0, 14)
ax.set_ylim(0, 24)
ax.axis('off')
fig.patch.set_facecolor('#F8F8F8')


# ── helpers ─────────────────────────────────────────────────────────
def bg(x, y, w, h, title, fc, ec, tc):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.15",
                                facecolor=fc, edgecolor=ec, lw=2, zorder=1))
    ax.text(x + w / 2, y + h - 0.22, title, ha='center', va='top',
            fontsize=10.5, fontweight='bold', color=tc, zorder=2)


def box(ax, x, y, w, h, line1, line2='',
        fc='#FFCDD2', ec='#E53935', fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.1",
                                facecolor=fc, edgecolor=ec, lw=1.8, zorder=3))
    cx, cy = x + w / 2, y + h / 2
    if line2:
        ax.text(cx, cy + 0.17, line1, ha='center', va='center',
                fontsize=fs, fontweight='bold', color='#1a1a1a', zorder=4,
                multialignment='center')
        ax.text(cx, cy - 0.2, line2, ha='center', va='center',
                fontsize=fs - 1.2, color='#555', style='italic', zorder=4)
    else:
        ax.text(cx, cy, line1, ha='center', va='center',
                fontsize=fs, fontweight='bold', color='#1a1a1a', zorder=4,
                multialignment='center')


def arr(x1, y1, x2, y2, label='', lc='#555555'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=lc, lw=1.3), zorder=5)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.08, my, label, ha='left', va='center',
                fontsize=7, color='#444', zorder=6,
                bbox=dict(fc='#F8F8F8', ec='none', pad=1))


# ── SECTION BACKGROUNDS ─────────────────────────────────────────────
# Quality & Ops  (top)
bg(0.3, 18.4, 13.4, 5.3,  'Quality and ops',     '#FFF5F5', '#FFCDD2', '#B71C1C')
# Runtime surfaces (middle-left)
bg(0.3, 11.6, 6.4, 6.3,   'Runtime surfaces',    '#EFF7FF', '#BBDEFB', '#1565C0')
# Learning progression (middle-right)
bg(7.3, 11.6, 6.4, 6.3,   'Learning progression','#F8F0FF', '#E1BEE7', '#6A1B9A')
# Core app (centre)
bg(1.0, 1.4,  12.0, 9.8,  'Core app',            '#FFFDF5', '#FFE0B2', '#E65100')
# Support systems (bottom)
bg(0.3, 0.1,  13.4, 1.1,  'Support systems',     '#F0FFF4', '#C8E6C9', '#1B5E20')


# ── QUALITY & OPS ───────────────────────────────────────────────────
box(ax, 9.5,  21.2, 3.5, 1.5, 'CI/CD automation',      '[ci.yml]',
    fc='#FFCDD2', ec='#E53935')
box(ax, 0.7,  21.2, 3.5, 1.5, 'Containers\ndeployment', '[Dockerfile]',
    fc='#FFCDD2', ec='#E53935')
box(ax, 4.7,  21.2, 4.3, 1.5, 'Observability\nlogging & audit', '[day36_audit.py]',
    fc='#FFCDD2', ec='#E53935')
box(ax, 9.5,  18.8, 3.5, 1.5, 'Tests quality',
    '[day37_unit_tests.py\nday38_integration_tests.py]',
    fc='#FFCDD2', ec='#E53935', fs=7.8)

arr(11.25, 21.2, 11.25, 20.3, 'runs')


# ── RUNTIME SURFACES ────────────────────────────────────────────────
box(ax, 1.8, 14.5, 3.2, 1.5, 'Web app\nui server', '[app.py]',
    fc='#BBDEFB', ec='#1976D2')
box(ax, 0.6, 12.1, 2.2, 1.4, 'Client JS\nfrontend', '[app.js]',
    fc='#BBDEFB', ec='#1976D2')
box(ax, 3.2, 12.1, 1.8, 1.4, 'CLI\nentrypoint', '[main.py]',
    fc='#BBDEFB', ec='#1976D2')
box(ax, 5.2, 12.1, 1.2, 1.4, 'Templates\nui views', '',
    fc='#BBDEFB', ec='#1976D2', fs=7.5)

arr(2.6, 14.5, 1.7, 13.5, 'serves')
arr(3.8, 14.5, 5.8, 13.5, 'renders')


# ── LEARNING PROGRESSION ────────────────────────────────────────────
box(ax, 7.8, 14.5, 5.3, 1.5, 'Earlier labs\nlearning modules', '',
    fc='#E1BEE7', ec='#8E24AA')
box(ax, 7.8, 12.1, 5.3, 1.5, 'App design\nworkflow design', '[day29_design.py]',
    fc='#E1BEE7', ec='#8E24AA')

arr(10.45, 14.5, 10.45, 13.6, 'evolves into')


# ── CORE APP ────────────────────────────────────────────────────────
# Main app box
box(ax, 3.8, 9.4, 6.0, 1.4, 'LangGraph app workflow', '[day34_35_app.py]',
    fc='#FFE0B2', ec='#F57C00', fs=9)

# Research state (right, hexagon-ish)
box(ax, 9.0, 8.0, 3.5, 1.3, 'Research state\ntyped state', '[day34_35_app.py]',
    fc='#FFF3E0', ec='#FF8F00', fs=8.2)

# Nodes
box(ax, 3.8, 7.9, 3.5, 1.3, 'Metadata\npipeline step', '[day34_35_app.py]',
    fc='#FFE0B2', ec='#F57C00')
box(ax, 3.8, 6.4, 5.8, 1.2, 'Web search\npipeline step', '[day34_35_app.py]',
    fc='#FFE0B2', ec='#F57C00')
box(ax, 3.8, 5.0, 5.8, 1.2, 'Briefing\npipeline step', '[day34_35_app.py]',
    fc='#FFE0B2', ec='#F57C00')
box(ax, 3.8, 3.6, 5.8, 1.2, 'Questions\npipeline step', '[day34_35_app.py]',
    fc='#FFE0B2', ec='#F57C00')

# Chat grounding (oval-ish)
box(ax, 3.1, 1.8, 7.2, 1.4, 'Chat grounding\nconversation flow', '[day34_35_app.py]',
    fc='#FFF8E1', ec='#F9A825', fs=9)

# Pipeline flow arrows
arr(6.8, 9.4,  5.55, 9.2,  'starts with')
arr(5.55, 7.9, 5.55, 7.6,  'feeds')
arr(5.55, 6.4, 5.55, 6.0,  'feeds')
arr(5.55, 5.0, 5.55, 4.6,  'feeds')
arr(5.55, 3.6, 5.55, 3.2,  'grounds')

# reads/writes: single diagonal arrow from LangGraph box to Research state
arr(9.8, 9.5, 10.0, 9.3, 'reads/writes')


# ── SUPPORT SYSTEMS ─────────────────────────────────────────────────
box(ax, 0.5,  0.2, 3.0, 0.75, 'Checkpointing persistence\n[SqliteSaver / SQLite]', '',
    fc='#C8E6C9', ec='#388E3C', fs=7.5)
box(ax, 3.8,  0.2, 2.8, 0.75, 'Local settings\n[.pp_settings.json]', '',
    fc='#C8E6C9', ec='#388E3C', fs=7.5)
box(ax, 6.9,  0.2, 2.8, 0.75, 'Shared utils\n[src/utils.py]', '',
    fc='#C8E6C9', ec='#388E3C', fs=7.5)
box(ax, 10.0, 0.2, 3.2, 0.75, 'Vector store\n[day16_chromadb.py]', '',
    fc='#C8E6C9', ec='#388E3C', fs=7.5)


# ── CROSS-SECTION ARROWS ────────────────────────────────────────────
# Quality → packages → Runtime surfaces
arr(5.0, 18.4, 4.5, 17.9, 'packages')

# Runtime: web app → invokes → Core app
arr(3.4, 12.1, 4.5, 10.8, 'invokes')
# Runtime: CLI → launches → Core app
arr(4.1, 12.1, 5.5, 10.8, 'launches')

# Learning: app design → shapes → Core app
arr(10.45, 12.1, 9.0, 10.5, 'shapes')

# Quality: CI/CD → validates → Learning progression
arr(11.25, 18.4, 11.0, 17.9, 'validates')

# Core → persists → Checkpointing
arr(4.0, 1.8, 2.0, 0.95, 'persists')
# Core → optionally uses → Vector store
arr(9.0, 1.8, 11.6, 0.95, 'optionally uses')

plt.savefig('diagram.png', dpi=180, bbox_inches='tight',
            facecolor='#F8F8F8', edgecolor='none')
print("Saved diagram.png")
