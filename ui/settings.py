"""
Opal Desktop — Settings Page

Application settings organized into sections: Appearance, Behavior,
Notifications, Data Management, and Danger Zone.
"""

from __future__ import annotations

import os
import tkinter.filedialog as fd
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from themes.dark_theme import (
    BG_MID, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BG_INPUT,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_MUTED, ACCENT_SURFACE,
    CYAN, GREEN, GREEN_MUTED, AMBER, RED, RED_LIGHT, RED_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BORDER, BORDER_HOVER, BORDER_DIVIDER,
    font, font_bold,
    FONT_TITLE, FONT_HEADING, FONT_SUBHEADING, FONT_BODY, FONT_SMALL,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL, PAD_3XL,
    STYLE_CARD, STYLE_BUTTON_PRIMARY, STYLE_BUTTON_SECONDARY,
    STYLE_BUTTON_DANGER, STYLE_SWITCH,
    CARD_CORNER_RADIUS, BUTTON_CORNER_RADIUS,
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from database.database import DatabaseManager
    from services.app_tracker import AppTracker

logger = get_logger(__name__)

# Accent color swatches the user can pick from
_ACCENT_COLORS: list[tuple[str, str]] = [
    ("#8b5cf6", "Violet"),
    ("#3b82f6", "Blue"),
    ("#06b6d4", "Cyan"),
    ("#10b981", "Emerald"),
    ("#f59e0b", "Amber"),
    ("#ef4444", "Red"),
    ("#ec4899", "Pink"),
    ("#f97316", "Orange"),
]


class SettingsPage(ctk.CTkFrame):
    """Application settings page with grouped sections."""

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

        # ConfigManager (will be set from app.py or read from db settings)
        self._config: Optional[object] = None

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the settings page layout."""
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=60)
        header.grid(row=0, column=0, sticky="ew", padx=PAD_2XL, pady=(PAD_2XL, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Settings", font=FONT_TITLE, text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text="Configure Opal Desktop to your preferences",
            font=font(12), text_color=TEXT_TERTIARY,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_fg_color=BG_MID, scrollbar_button_color=BG_ELEVATED,
        )
        scroll.grid(row=1, column=0, sticky="nsew", padx=PAD_2XL, pady=PAD_LG)
        scroll.grid_columnconfigure(0, weight=1)

        row = 0

        # ── Appearance Section ────────────────────────────────────────
        row = self._build_section_header(scroll, "Appearance", "🎨", row)
        row = self._build_appearance_section(scroll, row)

        # ── Behavior Section ──────────────────────────────────────────
        row = self._build_section_header(scroll, "Behavior", "⚙", row)
        row = self._build_behavior_section(scroll, row)

        # ── Notifications Section ─────────────────────────────────────
        row = self._build_section_header(scroll, "Notifications", "🔔", row)
        row = self._build_notifications_section(scroll, row)

        # ── Data Section ──────────────────────────────────────────────
        row = self._build_section_header(scroll, "Data Management", "💾", row)
        row = self._build_data_section(scroll, row)

        # ── Danger Zone ───────────────────────────────────────────────
        row = self._build_section_header(scroll, "Danger Zone", "⚠", row)
        row = self._build_danger_section(scroll, row)

        # Bottom padding
        ctk.CTkLabel(scroll, text="", height=PAD_3XL, fg_color="transparent").grid(
            row=row, column=0
        )

    # ── Section builders ─────────────────────────────────────────────

    def _build_section_header(
        self, parent: ctk.CTkFrame, title: str, icon: str, row: int
    ) -> int:
        """Create a section header and return the next row index."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", pady=(PAD_XL, PAD_SM))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text=f"{icon}  {title}",
            font=font_bold(16), text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        # Divider line
        divider = ctk.CTkFrame(frame, height=1, fg_color=BORDER_DIVIDER)
        divider.grid(row=1, column=0, sticky="ew", pady=(PAD_SM, 0))

        return row + 1

    def _build_appearance_section(self, parent: ctk.CTkFrame, row: int) -> int:
        """Build appearance settings."""
        card = ctk.CTkFrame(parent, **STYLE_CARD)
        card.grid(row=row, column=0, sticky="ew", pady=PAD_SM)
        card.grid_columnconfigure(1, weight=1)

        # Theme selector
        ctk.CTkLabel(
            card, text="Theme", font=font(13), text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=PAD_XL, pady=(PAD_LG, PAD_SM))

        self._theme_var = ctk.StringVar(value="dark")
        theme_seg = ctk.CTkSegmentedButton(
            card, values=["Dark", "Light", "System"],
            variable=self._theme_var,
            command=self._on_theme_change,
            font=font(12),
            fg_color=BG_ELEVATED, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_INPUT,
            unselected_hover_color=BG_CARD_HOVER,
            text_color=TEXT_PRIMARY,
        )
        theme_seg.grid(row=0, column=1, sticky="e", padx=PAD_XL, pady=(PAD_LG, PAD_SM))

        # Accent color picker
        ctk.CTkLabel(
            card, text="Accent Color", font=font(13), text_color=TEXT_PRIMARY,
        ).grid(row=1, column=0, sticky="w", padx=PAD_XL, pady=PAD_SM)

        colors_frame = ctk.CTkFrame(card, fg_color="transparent")
        colors_frame.grid(row=1, column=1, sticky="e", padx=PAD_XL, pady=PAD_SM)

        self._color_buttons: list[ctk.CTkButton] = []
        for i, (color, name) in enumerate(_ACCENT_COLORS):
            btn = ctk.CTkButton(
                colors_frame, text="", width=28, height=28,
                fg_color=color, hover_color=color,
                corner_radius=6, border_width=2,
                border_color=BG_CARD if color != ACCENT else "#ffffff",
                command=lambda c=color: self._on_accent_change(c),
            )
            btn.grid(row=0, column=i, padx=3)
            self._color_buttons.append(btn)

        # Bottom padding
        ctk.CTkLabel(card, text="", height=PAD_SM, fg_color="transparent").grid(
            row=2, column=0
        )

        return row + 1

    def _build_behavior_section(self, parent: ctk.CTkFrame, row: int) -> int:
        """Build behavior settings."""
        card = ctk.CTkFrame(parent, **STYLE_CARD)
        card.grid(row=row, column=0, sticky="ew", pady=PAD_SM)
        card.grid_columnconfigure(0, weight=1)

        settings = [
            ("Start with Windows", "Launch Opal automatically on login", "_startup_var"),
            ("Launch Minimized", "Start minimized to system tray", "_minimized_var"),
            ("Minimize to Tray", "Hide to tray when closing the window", "_tray_var"),
        ]

        for i, (label, subtitle, var_name) in enumerate(settings):
            row_frame = ctk.CTkFrame(card, fg_color="transparent")
            row_frame.grid(row=i, column=0, sticky="ew", padx=PAD_XL, pady=PAD_SM)
            row_frame.grid_columnconfigure(0, weight=1)

            # Label + subtitle
            text_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            text_frame.grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(
                text_frame, text=label,
                font=font(13), text_color=TEXT_PRIMARY,
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_frame, text=subtitle,
                font=font(11), text_color=TEXT_TERTIARY,
            ).pack(anchor="w")

            # Switch
            var = ctk.BooleanVar(value=False)
            setattr(self, var_name, var)

            switch = ctk.CTkSwitch(
                row_frame, text="", variable=var,
                fg_color=BG_ELEVATED, progress_color=ACCENT,
                button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
                command=lambda v=var_name: self._on_behavior_change(v),
                width=44,
            )
            switch.grid(row=0, column=1, sticky="e", padx=(PAD_LG, 0))

        # Bottom padding
        ctk.CTkLabel(card, text="", height=PAD_SM, fg_color="transparent").grid(
            row=len(settings), column=0
        )

        return row + 1

    def _build_notifications_section(self, parent: ctk.CTkFrame, row: int) -> int:
        """Build notification settings."""
        card = ctk.CTkFrame(parent, **STYLE_CARD)
        card.grid(row=row, column=0, sticky="ew", pady=PAD_SM)
        card.grid_columnconfigure(0, weight=1)

        # Master toggle
        master_row = ctk.CTkFrame(card, fg_color="transparent")
        master_row.grid(row=0, column=0, sticky="ew", padx=PAD_XL, pady=(PAD_LG, PAD_SM))
        master_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            master_row, text="Enable Notifications",
            font=font_bold(13), text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        self._notify_master = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            master_row, text="", variable=self._notify_master,
            fg_color=BG_ELEVATED, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44,
        ).grid(row=0, column=1, sticky="e")

        # Threshold checkboxes
        ctk.CTkLabel(
            card, text="Notify when time remaining reaches:",
            font=font(12), text_color=TEXT_TERTIARY,
        ).grid(row=1, column=0, sticky="w", padx=PAD_XL, pady=(PAD_SM, PAD_SM))

        thresholds_frame = ctk.CTkFrame(card, fg_color="transparent")
        thresholds_frame.grid(row=2, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_LG))

        self._threshold_vars: dict[int, ctk.BooleanVar] = {}
        thresholds = [30, 15, 10, 5, 1]
        for i, mins in enumerate(thresholds):
            var = ctk.BooleanVar(value=True)
            self._threshold_vars[mins] = var
            ctk.CTkCheckBox(
                thresholds_frame, text=f"{mins} min",
                variable=var, font=font(12),
                fg_color=BG_ELEVATED, hover_color=ACCENT_MUTED,
                checkmark_color=ACCENT, text_color=TEXT_SECONDARY,
                border_color=BORDER,
            ).grid(row=0, column=i, padx=(0, PAD_LG), pady=PAD_SM)

        return row + 1

    def _build_data_section(self, parent: ctk.CTkFrame, row: int) -> int:
        """Build data management settings."""
        card = ctk.CTkFrame(parent, **STYLE_CARD)
        card.grid(row=row, column=0, sticky="ew", pady=PAD_SM)
        card.grid_columnconfigure(0, weight=1)

        buttons = [
            ("Backup Database", "Create a backup of your usage data", self._on_backup),
            ("Restore from Backup", "Restore data from a previous backup", self._on_restore),
            ("Export to CSV", "Export usage history as a CSV file", self._on_export_csv),
            ("Import from CSV", "Import usage data from a CSV file", self._on_import_csv),
        ]

        for i, (text, desc, cmd) in enumerate(buttons):
            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.grid(row=i, column=0, sticky="ew", padx=PAD_XL, pady=PAD_SM)
            btn_row.grid_columnconfigure(0, weight=1)

            text_frame = ctk.CTkFrame(btn_row, fg_color="transparent")
            text_frame.grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(
                text_frame, text=text,
                font=font(13), text_color=TEXT_PRIMARY,
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_frame, text=desc,
                font=font(11), text_color=TEXT_TERTIARY,
            ).pack(anchor="w")

            ctk.CTkButton(
                btn_row, text=text.split()[0],
                **STYLE_BUTTON_SECONDARY,
                width=100, command=cmd,
            ).grid(row=0, column=1, sticky="e", padx=(PAD_LG, 0))

        # Database path info
        if self.db:
            db_path = getattr(self.db, "_db_path", getattr(self.db, "db_path", "Unknown"))
            ctk.CTkLabel(
                card, text=f"Database: {db_path}",
                font=font(10), text_color=TEXT_TERTIARY,
            ).grid(row=len(buttons), column=0, sticky="w", padx=PAD_XL, pady=(PAD_SM, PAD_LG))

        return row + 1

    def _build_danger_section(self, parent: ctk.CTkFrame, row: int) -> int:
        """Build the danger zone section."""
        card = ctk.CTkFrame(
            parent, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS,
            border_width=1, border_color=RED_MUTED,
        )
        card.grid(row=row, column=0, sticky="ew", pady=PAD_SM)
        card.grid_columnconfigure(0, weight=1)

        danger_row = ctk.CTkFrame(card, fg_color="transparent")
        danger_row.grid(row=0, column=0, sticky="ew", padx=PAD_XL, pady=PAD_LG)
        danger_row.grid_columnconfigure(0, weight=1)

        text_frame = ctk.CTkFrame(danger_row, fg_color="transparent")
        text_frame.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            text_frame, text="Reset All Data",
            font=font_bold(13), text_color=RED_LIGHT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_frame, text="Permanently delete all tracked data, apps, and settings",
            font=font(11), text_color=TEXT_TERTIARY,
        ).pack(anchor="w")

        ctk.CTkButton(
            danger_row, text="Reset Everything",
            **STYLE_BUTTON_DANGER, width=140,
            command=self._on_reset_all,
        ).grid(row=0, column=1, sticky="e", padx=(PAD_LG, 0))

        return row + 1

    # ── Event handlers ───────────────────────────────────────────────

    def _on_theme_change(self, value: str) -> None:
        """Handle theme change."""
        mode = value.lower()
        try:
            ctk.set_appearance_mode(mode)
            logger.info("Theme changed to: %s", mode)
        except Exception:
            logger.exception("Failed to change theme")

    def _on_accent_change(self, color: str) -> None:
        """Handle accent color change."""
        # Update border highlights on swatches
        for btn in self._color_buttons:
            current_fg = btn.cget("fg_color")
            if current_fg == color:
                btn.configure(border_color="#ffffff")
            else:
                btn.configure(border_color=BG_CARD)
        logger.info("Accent color changed to: %s", color)

    def _on_behavior_change(self, var_name: str) -> None:
        """Handle behavior toggle changes."""
        if var_name == "_startup_var":
            enabled = self._startup_var.get()
            try:
                from services.startup_service import StartupService
                if enabled:
                    StartupService.register()
                    logger.info("Registered for Windows startup")
                else:
                    StartupService.unregister()
                    logger.info("Unregistered from Windows startup")
            except Exception:
                logger.exception("Failed to change startup registration")

    def _on_backup(self) -> None:
        """Create a database backup."""
        if not self.db:
            return
        try:
            backup_dir = os.path.join(os.path.dirname(
                getattr(self.db, "_db_path", getattr(self.db, "db_path", "data/opal.db"))
            ), "backups")
            os.makedirs(backup_dir, exist_ok=True)

            from utils.storage import backup_database
            db_path = getattr(self.db, "_db_path", getattr(self.db, "db_path", "data/opal.db"))
            backup_path = backup_database(db_path, backup_dir)
            if backup_path:
                self._show_info("Backup Created", f"Database backed up to:\n{backup_path}")
                logger.info("Backup created: %s", backup_path)
        except Exception:
            logger.exception("Backup failed")
            self._show_info("Backup Failed", "An error occurred while creating the backup.")

    def _on_restore(self) -> None:
        """Restore from a backup file."""
        path = fd.askopenfilename(
            title="Select Backup File",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
        )
        if path and self.db:
            try:
                success = self.db.restore(path)
                if success:
                    self._show_info("Restore Complete", "Database has been restored. Please restart the application.")
                else:
                    self._show_info("Restore Failed", "Could not restore from the selected file.")
            except Exception:
                logger.exception("Restore failed")
                self._show_info("Restore Failed", "An error occurred during restore.")

    def _on_export_csv(self) -> None:
        """Export usage data to CSV."""
        path = fd.asksaveasfilename(
            title="Export Usage Data",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if path and self.db:
            try:
                from utils.storage import export_usage_csv
                from utils.time_utils import days_ago, today_str

                records = self.db.get_all_usage_range(days_ago(365), today_str())
                record_dicts = [
                    {"app_id": r.app_id, "date": r.date, "usage_seconds": r.usage_seconds}
                    for r in records
                ]
                success = export_usage_csv(record_dicts, path)
                if success:
                    self._show_info("Export Complete", f"Data exported to:\n{path}")
                else:
                    self._show_info("Export Failed", "Could not export data.")
            except Exception:
                logger.exception("CSV export failed")
                self._show_info("Export Failed", "An error occurred during export.")

    def _on_import_csv(self) -> None:
        """Import usage data from CSV."""
        path = fd.askopenfilename(
            title="Import Usage Data",
            filetypes=[("CSV Files", "*.csv")],
        )
        if path:
            self._show_info("Import", f"Import from:\n{path}\n\n(Feature in development)")

    def _on_reset_all(self) -> None:
        """Reset all data after confirmation."""
        from ui.dialogs import ConfirmDialog

        def do_reset():
            if self.db:
                try:
                    # Clear all tables
                    for table in ["usage_history", "usage_sessions", "focus_sessions",
                                  "blocked_events", "applications", "settings"]:
                        self.db.execute(f"DELETE FROM {table}")
                    logger.info("All data has been reset")
                    self._show_info("Reset Complete", "All data has been cleared.")
                except Exception:
                    logger.exception("Reset failed")

        ConfirmDialog(
            self, title="Reset All Data",
            message="This will permanently delete ALL tracked data, monitored apps, "
                    "and settings.\n\nThis action cannot be undone.",
            confirm_text="Reset Everything",
            on_confirm=do_reset,
            is_destructive=True,
        )

    def _show_info(self, title: str, message: str) -> None:
        """Show a simple information dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.configure(fg_color=BG_CARD)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        parent = self.winfo_toplevel()
        px = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 200) // 2
        dialog.geometry(f"+{px}+{py}")

        ctk.CTkLabel(
            dialog, text=title, font=font_bold(16), text_color=TEXT_PRIMARY,
        ).pack(pady=(PAD_XL, PAD_SM))

        ctk.CTkLabel(
            dialog, text=message, font=font(12),
            text_color=TEXT_SECONDARY, wraplength=350,
        ).pack(pady=(0, PAD_XL), padx=PAD_XL)

        ctk.CTkButton(
            dialog, text="OK", **STYLE_BUTTON_PRIMARY,
            width=100, command=dialog.destroy,
        ).pack(pady=(0, PAD_LG))

    # ── Refresh ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload settings values from config/db."""
        # Load startup state
        try:
            from services.startup_service import StartupService
            self._startup_var.set(StartupService.is_registered())
        except Exception:
            pass
