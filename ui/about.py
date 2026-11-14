"""
Limitin Desktop — About Page

Displays application information, version, system details, and credits.
"""

from __future__ import annotations

import platform
import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk

from themes.dark_theme import (
    BG_MID, BG_CARD, BG_ELEVATED, ACCENT, ACCENT_LIGHT, ACCENT_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BORDER, BORDER_DIVIDER,
    font, font_bold,
    FONT_TITLE, FONT_HEADING, FONT_SUBHEADING, FONT_BODY, FONT_SMALL,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL, PAD_3XL,
    STYLE_CARD, CARD_CORNER_RADIUS,
)

if TYPE_CHECKING:
    from database.database import DatabaseManager
    from services.app_tracker import AppTracker

VERSION = "1.0.0"
APP_NAME = "Limitin Desktop"
DESCRIPTION = (
    "Digital wellness for Windows. Monitor, limit, and take control "
    "of your screen time with precision tracking and intelligent blocking."
)


class AboutPage(ctk.CTkFrame):
    """About / system information page."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        db: DatabaseManager | None = None,
        tracker: AppTracker | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=BG_MID, corner_radius=0, **kwargs)
        self.db = db
        self.tracker = tracker
        self._start_time = datetime.now()
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the about page layout."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Scrollable container
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_fg_color=BG_MID, scrollbar_button_color=BG_ELEVATED,
        )
        scroll.grid(row=0, column=0, sticky="nsew", padx=PAD_2XL, pady=PAD_2XL)
        scroll.grid_columnconfigure(0, weight=1)

        row = 0

        # ── Logo section ─────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        logo_frame.grid(row=row, column=0, pady=(PAD_3XL, PAD_LG), sticky="ew")
        logo_frame.grid_columnconfigure(0, weight=1)

        # Icon
        icon_container = ctk.CTkFrame(
            logo_frame, width=80, height=80,
            fg_color=ACCENT, corner_radius=20,
        )
        icon_container.grid(row=0, column=0, pady=(0, PAD_LG))
        icon_container.grid_propagate(False)
        ctk.CTkLabel(
            icon_container, text="◆", font=font_bold(36),
            text_color="#ffffff",
        ).place(relx=0.5, rely=0.5, anchor="center")

        # App name
        ctk.CTkLabel(
            logo_frame, text=APP_NAME,
            font=font_bold(28), text_color=ACCENT_LIGHT,
        ).grid(row=1, column=0, pady=(0, PAD_SM))

        # Version badge
        version_badge = ctk.CTkFrame(
            logo_frame, fg_color=ACCENT_MUTED, corner_radius=6,
        )
        version_badge.grid(row=2, column=0, pady=(0, PAD_LG))
        ctk.CTkLabel(
            version_badge, text=f"v{VERSION}",
            font=font(12), text_color=ACCENT_LIGHT,
        ).pack(padx=PAD_MD, pady=PAD_SM)

        # Description
        ctk.CTkLabel(
            logo_frame, text=DESCRIPTION,
            font=font(13), text_color=TEXT_SECONDARY,
            wraplength=500, justify="center",
        ).grid(row=3, column=0, pady=(0, PAD_SM))

        row += 1

        # ── System Info card ──────────────────────────────────────────
        sys_card = ctk.CTkFrame(scroll, **STYLE_CARD)
        sys_card.grid(row=row, column=0, sticky="ew", pady=(PAD_LG, PAD_MD))
        sys_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            sys_card, text="System Information",
            font=font_bold(15), text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, sticky="w",
               padx=PAD_XL, pady=(PAD_LG, PAD_MD))

        sys_info = self._get_system_info()
        for i, (label, value) in enumerate(sys_info, start=1):
            ctk.CTkLabel(
                sys_card, text=label,
                font=font(12), text_color=TEXT_TERTIARY, anchor="w",
            ).grid(row=i, column=0, sticky="w", padx=(PAD_XL, PAD_MD), pady=3)
            ctk.CTkLabel(
                sys_card, text=value,
                font=font(12), text_color=TEXT_SECONDARY, anchor="w",
            ).grid(row=i, column=1, sticky="w", padx=(0, PAD_XL), pady=3)

        # Bottom padding inside card
        ctk.CTkLabel(sys_card, text="", height=PAD_MD, fg_color="transparent").grid(
            row=len(sys_info) + 1, column=0
        )

        row += 1

        # ── Acknowledgements card ────────────────────────────────────
        ack_card = ctk.CTkFrame(scroll, **STYLE_CARD)
        ack_card.grid(row=row, column=0, sticky="ew", pady=PAD_MD)
        ack_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            ack_card, text="Built With",
            font=font_bold(15), text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=PAD_XL, pady=(PAD_LG, PAD_MD))

        libraries = [
            ("CustomTkinter", "Modern UI framework for Python"),
            ("psutil", "Process and system monitoring"),
            ("pywin32", "Windows API bindings"),
            ("matplotlib", "Charts and data visualization"),
            ("Pillow", "Image processing"),
            ("pystray", "System tray integration"),
            ("SQLite", "Embedded database engine"),
        ]

        for i, (lib, desc) in enumerate(libraries):
            lib_frame = ctk.CTkFrame(ack_card, fg_color="transparent")
            lib_frame.grid(row=i + 1, column=0, sticky="ew", padx=PAD_XL, pady=2)
            lib_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                lib_frame, text=f"•  {lib}",
                font=font_bold(12), text_color=ACCENT_LIGHT, anchor="w",
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                lib_frame, text=f"  —  {desc}",
                font=font(11), text_color=TEXT_TERTIARY, anchor="w",
            ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(ack_card, text="", height=PAD_LG, fg_color="transparent").grid(
            row=len(libraries) + 1, column=0
        )

        row += 1

        # ── Footer ───────────────────────────────────────────────────
        ctk.CTkLabel(
            scroll, text="Made with 💜 for digital wellness",
            font=font(11), text_color=TEXT_TERTIARY,
        ).grid(row=row, column=0, pady=PAD_2XL)

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_system_info(self) -> list[tuple[str, str]]:
        """Gather system information for display."""
        info: list[tuple[str, str]] = [
            ("Platform", f"{platform.system()} {platform.release()}"),
            ("OS Version", platform.version()),
            ("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
            ("Architecture", platform.machine()),
            ("Processor", platform.processor() or "Unknown"),
        ]

        # Database info
        if self.db:
            try:
                db_path = getattr(self.db, "_db_path", getattr(self.db, "db_path", "Unknown"))
                if os.path.isfile(db_path):
                    size_bytes = os.path.getsize(db_path)
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                    info.append(("Database Size", size_str))
                info.append(("Database Path", str(db_path)))
            except Exception:
                info.append(("Database", "Connected"))

        return info

    def refresh(self) -> None:
        """Refresh is a no-op for the about page (static content)."""
        pass
