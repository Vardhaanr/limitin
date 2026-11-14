"""
Limitin Desktop — Dark Theme

Premium violet-accent color palette inspired by Linear, Arc Browser, and Figma.
Every UI component references these constants for consistent styling.
"""

from __future__ import annotations


# ── Color Palette ─────────────────────────────────────────────────────────────

# Backgrounds (darkest → lightest)
BG_DARKEST = "#09090b"        # App background / window
BG_DARK = "#0c0c0f"           # Sidebar
BG_MID = "#111114"            # Main content area
BG_CARD = "#16161a"           # Cards, panels
BG_CARD_HOVER = "#1c1c21"    # Card hover state
BG_ELEVATED = "#1e1e24"      # Dropdowns, popovers
BG_INPUT = "#131316"          # Text inputs, entries

# Accent — Violet
ACCENT = "#8b5cf6"            # Primary accent (violet-500)
ACCENT_HOVER = "#7c3aed"     # Hover state (violet-600)
ACCENT_LIGHT = "#a78bfa"     # Light variant (violet-400)
ACCENT_MUTED = "#2e1065"     # Very subtle background tint
ACCENT_SURFACE = "#1a1035"   # Surface with accent tint
ACCENT_GLOW = "#8b5cf620"    # Glow effect (with alpha as hex for reference)

# Secondary — Cyan
CYAN = "#06b6d4"              # Secondary accent
CYAN_LIGHT = "#22d3ee"       # Light cyan
CYAN_MUTED = "#083344"       # Muted cyan background

# Status Colors
GREEN = "#10b981"             # Success, online, within limit
GREEN_LIGHT = "#34d399"      # Light green
GREEN_MUTED = "#052e16"      # Muted green background

AMBER = "#f59e0b"             # Warning, approaching limit
AMBER_LIGHT = "#fbbf24"      # Light amber
AMBER_MUTED = "#451a03"      # Muted amber background

RED = "#ef4444"               # Danger, blocked, over limit
RED_LIGHT = "#f87171"        # Light red
RED_MUTED = "#450a0a"        # Muted red background

# Text
TEXT_PRIMARY = "#f1f5f9"      # Primary text (slate-100)
TEXT_SECONDARY = "#94a3b8"   # Secondary / muted text (slate-400)
TEXT_TERTIARY = "#64748b"    # Tertiary / placeholder (slate-500)
TEXT_DISABLED = "#475569"    # Disabled text (slate-600)
TEXT_INVERSE = "#0f172a"     # Dark text on light backgrounds

# Borders
BORDER = "#1e1e24"            # Subtle border
BORDER_HOVER = "#2a2a32"    # Border on hover
BORDER_FOCUS = ACCENT        # Border when focused
BORDER_DIVIDER = "#1a1a20"  # Divider lines

# Shadows (for reference — not directly usable in Tkinter but useful for overlay effects)
SHADOW_SM = "#00000040"
SHADOW_MD = "#00000060"
SHADOW_LG = "#00000080"

# Scrollbar
SCROLLBAR_BG = "#16161a"
SCROLLBAR_FG = "#2a2a32"
SCROLLBAR_HOVER = "#3a3a44"


# ── Typography ────────────────────────────────────────────────────────────────

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Cascadia Code"

# Font helper: returns (family, size, weight)
def font(size: int, weight: str = "normal") -> tuple[str, int, str]:
    """Create a font tuple for CustomTkinter widgets."""
    return (FONT_FAMILY, size, weight)

def font_bold(size: int) -> tuple[str, int, str]:
    """Create a bold font tuple."""
    return (FONT_FAMILY, size, "bold")

def font_mono(size: int, weight: str = "normal") -> tuple[str, int, str]:
    """Create a monospace font tuple."""
    return (FONT_FAMILY_MONO, size, weight)

# Preset sizes
FONT_TITLE = font_bold(24)       # Page titles
FONT_HEADING = font_bold(18)     # Section headings
FONT_SUBHEADING = font_bold(14)  # Card titles
FONT_BODY = font(13)             # Body text
FONT_BODY_BOLD = font_bold(13)   # Emphasized body
FONT_SMALL = font(11)            # Small labels, captions
FONT_SMALL_BOLD = font_bold(11)  # Small bold labels
FONT_TINY = font(10)             # Very small text, badges
FONT_STAT_VALUE = font_bold(32)  # Large stat numbers
FONT_STAT_LABEL = font(11)       # Stat labels below numbers


# ── Spacing ───────────────────────────────────────────────────────────────────

PAD_XS = 4
PAD_SM = 8
PAD_MD = 12
PAD_LG = 16
PAD_XL = 24
PAD_2XL = 32
PAD_3XL = 48

# Layout constants
SIDEBAR_WIDTH = 220
CARD_CORNER_RADIUS = 12
BUTTON_CORNER_RADIUS = 8
INPUT_CORNER_RADIUS = 8
BADGE_CORNER_RADIUS = 6
PROGRESS_HEIGHT = 6
SCROLLBAR_WIDTH = 8


# ── Widget Style Presets ──────────────────────────────────────────────────────

# These dicts can be unpacked directly into widget constructors: **STYLE_CARD, etc.

STYLE_CARD = {
    "fg_color": BG_CARD,
    "corner_radius": CARD_CORNER_RADIUS,
    "border_width": 1,
    "border_color": BORDER,
}

STYLE_CARD_HOVER = {
    "fg_color": BG_CARD_HOVER,
    "corner_radius": CARD_CORNER_RADIUS,
    "border_width": 1,
    "border_color": BORDER_HOVER,
}

STYLE_BUTTON_PRIMARY = {
    "fg_color": ACCENT,
    "hover_color": ACCENT_HOVER,
    "text_color": "#ffffff",
    "corner_radius": BUTTON_CORNER_RADIUS,
    "font": font_bold(13),
    "height": 36,
}

STYLE_BUTTON_SECONDARY = {
    "fg_color": BG_CARD,
    "hover_color": BG_CARD_HOVER,
    "text_color": TEXT_PRIMARY,
    "border_width": 1,
    "border_color": BORDER,
    "corner_radius": BUTTON_CORNER_RADIUS,
    "font": font(13),
    "height": 36,
}

STYLE_BUTTON_GHOST = {
    "fg_color": "transparent",
    "hover_color": BG_CARD,
    "text_color": TEXT_SECONDARY,
    "corner_radius": BUTTON_CORNER_RADIUS,
    "font": font(13),
    "height": 36,
}

STYLE_BUTTON_DANGER = {
    "fg_color": RED_MUTED,
    "hover_color": RED,
    "text_color": RED_LIGHT,
    "corner_radius": BUTTON_CORNER_RADIUS,
    "font": font_bold(13),
    "height": 36,
}

STYLE_INPUT = {
    "fg_color": BG_INPUT,
    "border_color": BORDER,
    "text_color": TEXT_PRIMARY,
    "placeholder_text_color": TEXT_TERTIARY,
    "corner_radius": INPUT_CORNER_RADIUS,
    "font": font(13),
    "height": 36,
    "border_width": 1,
}

STYLE_SIDEBAR = {
    "fg_color": BG_DARK,
    "corner_radius": 0,
}

STYLE_SIDEBAR_BUTTON = {
    "fg_color": "transparent",
    "hover_color": BG_CARD,
    "text_color": TEXT_SECONDARY,
    "corner_radius": BUTTON_CORNER_RADIUS,
    "font": font(13),
    "height": 40,
    "anchor": "w",
}

STYLE_SIDEBAR_BUTTON_ACTIVE = {
    "fg_color": ACCENT_SURFACE,
    "hover_color": ACCENT_SURFACE,
    "text_color": ACCENT_LIGHT,
    "corner_radius": BUTTON_CORNER_RADIUS,
    "font": font_bold(13),
    "height": 40,
    "anchor": "w",
}

STYLE_PROGRESS_BAR = {
    "fg_color": BG_ELEVATED,
    "progress_color": ACCENT,
    "corner_radius": 3,
    "height": PROGRESS_HEIGHT,
}

STYLE_SWITCH = {
    "fg_color": BG_ELEVATED,
    "progress_color": ACCENT,
    "button_color": TEXT_PRIMARY,
    "button_hover_color": "#ffffff",
    "font": font(13),
    "text_color": TEXT_PRIMARY,
}

STYLE_SCROLLABLE_FRAME = {
    "fg_color": "transparent",
    "scrollbar_fg_color": SCROLLBAR_FG,
    "scrollbar_button_color": SCROLLBAR_FG,
    "scrollbar_button_hover_color": SCROLLBAR_HOVER,
}


# ── Icon Unicode Characters ──────────────────────────────────────────────────
# Using Unicode symbols as lightweight icon replacements.
# These render in Segoe UI on Windows without needing external icon fonts.

ICONS = {
    "dashboard": "⬡",
    "apps": "⊞",
    "stats": "◔",
    "history": "⧗",
    "focus": "◉",
    "settings": "⚙",
    "about": "ℹ",
    "add": "+",
    "edit": "✎",
    "delete": "✕",
    "search": "⌕",
    "clock": "⏱",
    "check": "✓",
    "warning": "⚠",
    "block": "⊘",
    "play": "▶",
    "pause": "⏸",
    "stop": "■",
    "refresh": "↻",
    "export": "⤓",
    "import": "⤒",
    "backup": "⧉",
    "restore": "⟲",
    "minimize": "─",
    "maximize": "□",
    "close": "✕",
    "arrow_right": "→",
    "arrow_left": "←",
    "arrow_up": "↑",
    "arrow_down": "↓",
    "star": "★",
    "fire": "🔥",
    "shield": "🛡",
    "chart": "📊",
    "calendar": "📅",
    "folder": "📁",
    "target": "🎯",
    "trophy": "🏆",
    "streak": "⚡",
}


# ── Gradient Helper ──────────────────────────────────────────────────────────

def get_usage_color(percentage: float) -> str:
    """Return a color based on usage percentage (0.0 to 1.0+).
    
    Green → Amber → Red as usage approaches/exceeds the limit.
    """
    if percentage < 0.5:
        return GREEN
    elif percentage < 0.75:
        return AMBER
    elif percentage < 0.9:
        return AMBER_LIGHT
    elif percentage < 1.0:
        return RED_LIGHT
    else:
        return RED


def get_status_badge_colors(status: str) -> tuple[str, str]:
    """Return (bg_color, text_color) for a status badge.
    
    Args:
        status: One of 'active', 'blocked', 'paused', 'idle', 'warning'.
    """
    mapping = {
        "active": (GREEN_MUTED, GREEN),
        "blocked": (RED_MUTED, RED_LIGHT),
        "paused": (AMBER_MUTED, AMBER),
        "idle": (BG_ELEVATED, TEXT_TERTIARY),
        "warning": (AMBER_MUTED, AMBER_LIGHT),
    }
    return mapping.get(status, (BG_ELEVATED, TEXT_TERTIARY))
