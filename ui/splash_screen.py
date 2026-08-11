"""
Opal Desktop — Splash Screen

Borderless loading screen shown during application startup.
Displays the Opal logo, a loading bar, and status messages while
the database and services are being initialized.
"""

from __future__ import annotations

import customtkinter as ctk

from themes.dark_theme import (
    BG_DARKEST, ACCENT, ACCENT_LIGHT, ACCENT_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BORDER, font, font_bold, PAD_LG, PAD_XL, PAD_2XL,
)


class SplashScreen(ctk.CTkToplevel):
    """Borderless splash window shown during app startup."""

    WIDTH = 420
    HEIGHT = 300

    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master)

        # ── Window setup ─────────────────────────────────────────────
        self.overrideredirect(True)
        self.configure(fg_color=BG_DARKEST)
        self.attributes("-topmost", True)

        # Centre on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - self.WIDTH) // 2
        y = (screen_h - self.HEIGHT) // 2
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        # Subtle border using a framing technique
        self._border_frame = ctk.CTkFrame(
            self, fg_color=BG_DARKEST,
            corner_radius=16, border_width=1, border_color=BORDER,
        )
        self._border_frame.pack(fill="both", expand=True, padx=1, pady=1)

        self._build_content()

    def _build_content(self) -> None:
        """Build the splash screen layout."""
        container = self._border_frame

        # ── Spacer top ───────────────────────────────────────────────
        ctk.CTkLabel(container, text="", height=40, fg_color="transparent").pack()

        # ── Logo ─────────────────────────────────────────────────────
        # Accent-colored gem icon
        icon_frame = ctk.CTkFrame(
            container, width=64, height=64,
            fg_color=ACCENT, corner_radius=16,
        )
        icon_frame.pack(pady=(0, PAD_LG))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(
            icon_frame, text="◆", font=font_bold(28), text_color="#ffffff",
        ).place(relx=0.5, rely=0.5, anchor="center")

        # ── App name ─────────────────────────────────────────────────
        ctk.CTkLabel(
            container, text="Opal",
            font=font_bold(32), text_color=ACCENT_LIGHT,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            container, text="Digital Wellness for Windows",
            font=font(12), text_color=TEXT_TERTIARY,
        ).pack(pady=(0, PAD_2XL))

        # ── Loading bar ──────────────────────────────────────────────
        self._progress = ctk.CTkProgressBar(
            container, width=260, height=4,
            fg_color=ACCENT_MUTED, progress_color=ACCENT,
            corner_radius=2, mode="indeterminate",
        )
        self._progress.pack(pady=(0, PAD_LG))
        self._progress.start()

        # ── Status text ──────────────────────────────────────────────
        self._status_label = ctk.CTkLabel(
            container, text="Starting...",
            font=font(11), text_color=TEXT_TERTIARY,
        )
        self._status_label.pack(pady=(0, PAD_LG))

    # ── Public API ───────────────────────────────────────────────────

    def set_status(self, text: str) -> None:
        """Update the loading status text.

        Args:
            text: New status message (e.g. 'Loading database...').
        """
        try:
            self._status_label.configure(text=text)
            self.update_idletasks()
        except Exception:
            pass  # Window may already be destroyed

    def close(self) -> None:
        """Stop the progress bar and destroy the splash window."""
        try:
            self._progress.stop()
            self.destroy()
        except Exception:
            pass
