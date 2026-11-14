"""
Opal Desktop — Modal Dialog Windows

Production-ready dialog collection for confirmations, application management,
grace-period overlays, data export, and backup/restore operations. All dialogs
are modal, centered on their parent, and styled with the dark theme.
"""

from __future__ import annotations

import logging
import os
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from themes.dark_theme import (
    BG_CARD,
    BG_CARD_HOVER,
    BG_DARKEST,
    BG_DARK,
    BG_ELEVATED,
    BG_INPUT,
    BG_MID,
    ACCENT,
    ACCENT_HOVER,
    ACCENT_LIGHT,
    ACCENT_MUTED,
    ACCENT_SURFACE,
    BORDER,
    BORDER_DIVIDER,
    BORDER_FOCUS,
    BORDER_HOVER,
    GREEN,
    GREEN_LIGHT,
    AMBER,
    AMBER_LIGHT,
    AMBER_MUTED,
    RED,
    RED_LIGHT,
    RED_MUTED,
    TEXT_DISABLED,
    TEXT_INVERSE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    CARD_CORNER_RADIUS,
    BUTTON_CORNER_RADIUS,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_SMALL,
    FONT_SMALL_BOLD,
    FONT_SUBHEADING,
    FONT_TINY,
    FONT_TITLE,
    ICONS,
    PAD_XS,
    PAD_SM,
    PAD_MD,
    PAD_LG,
    PAD_XL,
    PAD_2XL,
    PAD_3XL,
    STYLE_BUTTON_DANGER,
    STYLE_BUTTON_GHOST,
    STYLE_BUTTON_PRIMARY,
    STYLE_BUTTON_SECONDARY,
    STYLE_CARD,
    STYLE_INPUT,
    STYLE_SWITCH,
    font,
    font_bold,
    font_mono,
    get_usage_color,
)
from database.models import Application
from ui.widgets import TimePicker

logger = logging.getLogger("opal.ui.dialogs")


# ── Helper: center a toplevel on its parent ──────────────────────────────────


def _center_on_parent(dialog: ctk.CTkToplevel, width: int, height: int) -> None:
    """Position a dialog in the center of its parent window.

    Args:
        dialog: The toplevel dialog to position.
        width: Dialog width in pixels.
        height: Dialog height in pixels.
    """
    try:
        dialog.update_idletasks()
        parent = dialog.master
        if parent is not None and parent.winfo_exists():
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - width) // 2
            y = py + (ph - height) // 2
        else:
            # Fall back to screen center
            sw = dialog.winfo_screenwidth()
            sh = dialog.winfo_screenheight()
            x = (sw - width) // 2
            y = (sh - height) // 2

        dialog.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        logger.exception("Failed to center dialog on parent")
        dialog.geometry(f"{width}x{height}")


def _make_modal(dialog: ctk.CTkToplevel) -> None:
    """Configure a toplevel as a modal dialog.

    Args:
        dialog: The toplevel to make modal.
    """
    try:
        dialog.transient(dialog.master)
        dialog.grab_set()
        dialog.focus_force()
        dialog.lift()
    except Exception:
        logger.exception("Failed to make dialog modal")


# ── Helper: safely extract exe icon ──────────────────────────────────────────


def _try_extract_icon(exe_path: str) -> Optional[ctk.CTkImage]:
    """Attempt to extract an application icon from an executable.

    Args:
        exe_path: Path to the .exe file.

    Returns:
        A CTkImage if extraction succeeded, None otherwise.
    """
    try:
        from utils.helpers import extract_exe_icon
        return extract_exe_icon(exe_path)
    except ImportError:
        logger.debug("utils.helpers.extract_exe_icon not available")
        return None
    except Exception:
        logger.warning("Failed to extract icon from '%s'", exe_path)
        return None


# ── ConfirmDialog ─────────────────────────────────────────────────────────────


class ConfirmDialog(ctk.CTkToplevel):
    """Centered modal confirmation dialog with two buttons.

    Used for confirming destructive or important actions. The confirm button
    can optionally use a red/danger style.

    Args:
        master: Parent widget.
        title: Dialog title text.
        message: Body message text.
        confirm_text: Label for the confirm button.
        cancel_text: Label for the cancel button.
        on_confirm: Callback invoked when the user clicks confirm.
        is_destructive: If True, the confirm button uses danger styling.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        title: str,
        message: str,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        on_confirm: Optional[callable] = None,
        is_destructive: bool = False,
    ) -> None:
        super().__init__(master)

        self._on_confirm = on_confirm
        self._result = False

        # ── Window configuration ─────────────────────────────────────────
        self.title(title)
        self.configure(fg_color=BG_DARKEST)
        self.resizable(False, False)

        dialog_width, dialog_height = 420, 220
        _center_on_parent(self, dialog_width, dialog_height)
        _make_modal(self)

        # ── Content ──────────────────────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color=BG_DARKEST)
        content.pack(fill="both", expand=True, padx=PAD_2XL, pady=PAD_2XL)
        content.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            content,
            text=title,
            font=FONT_HEADING,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        )
        title_label.grid(row=0, column=0, sticky="w", pady=(0, PAD_MD))

        # Message
        message_label = ctk.CTkLabel(
            content,
            text=message,
            font=FONT_BODY,
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=360,
            fg_color="transparent",
        )
        message_label.grid(row=1, column=0, sticky="w", pady=(0, PAD_XL))

        # ── Buttons ──────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="e")

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text=cancel_text,
            command=self._on_cancel,
            **STYLE_BUTTON_SECONDARY,
        )
        cancel_btn.pack(side="left", padx=(0, PAD_SM))

        confirm_style = STYLE_BUTTON_DANGER if is_destructive else STYLE_BUTTON_PRIMARY
        confirm_btn = ctk.CTkButton(
            btn_frame,
            text=confirm_text,
            command=self._on_confirm_click,
            **confirm_style,
        )
        confirm_btn.pack(side="left")

        # Handle window close via 'X' button
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Keyboard shortcuts
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.bind("<Return>", lambda _e: self._on_confirm_click())

        logger.debug("ConfirmDialog created: title='%s'", title)

    def _on_confirm_click(self) -> None:
        """Handle confirm button click."""
        self._result = True
        try:
            if self._on_confirm is not None:
                self._on_confirm()
        except Exception:
            logger.exception("Error in ConfirmDialog on_confirm callback")
        finally:
            self.destroy()

    def _on_cancel(self) -> None:
        """Handle cancel button click or window close."""
        self._result = False
        self.destroy()


# ── AddAppDialog ──────────────────────────────────────────────────────────────


class AddAppDialog(ctk.CTkToplevel):
    """Dialog for adding a new monitored application.

    Provides a two-step workflow:
      1. Select an .exe file via a file picker.
      2. Configure the monitoring settings (daily limit, grace period,
         block mode, notifications, schedule).

    Args:
        master: Parent widget.
        on_save: Callback(Application) invoked when the user saves.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_save: callable,
    ) -> None:
        super().__init__(master)

        self._on_save = on_save
        self._selected_exe: Optional[str] = None
        self._selected_name: str = ""
        self._icon_image: Optional[ctk.CTkImage] = None

        # ── Window configuration ─────────────────────────────────────────
        self.title("Add Application")
        self.configure(fg_color=BG_DARKEST)
        self.resizable(False, False)

        dialog_width, dialog_height = 500, 650
        _center_on_parent(self, dialog_width, dialog_height)
        _make_modal(self)

        # ── Scrollable content ───────────────────────────────────────────
        self._content = ctk.CTkScrollableFrame(
            self,
            fg_color=BG_DARKEST,
            scrollbar_fg_color=BG_DARKEST,
            scrollbar_button_color=BG_ELEVATED,
            scrollbar_button_hover_color=BG_CARD_HOVER,
        )
        self._content.pack(fill="both", expand=True, padx=PAD_XL, pady=(PAD_XL, 0))
        self._content.grid_columnconfigure(0, weight=1)

        self._current_row = 0

        # ── Title ────────────────────────────────────────────────────────
        self._add_section_title("Add Application")

        # ── Step 1: File picker ──────────────────────────────────────────
        self._add_label("Select Executable")

        picker_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        picker_frame.grid(
            row=self._current_row, column=0, sticky="ew",
            pady=(0, PAD_MD),
        )
        self._current_row += 1
        picker_frame.grid_columnconfigure(1, weight=1)

        self._app_icon_label = ctk.CTkLabel(
            picker_frame,
            text="⊞",
            font=font_bold(28),
            text_color=TEXT_TERTIARY,
            width=48,
            height=48,
            fg_color=BG_CARD,
            corner_radius=CARD_CORNER_RADIUS,
        )
        self._app_icon_label.grid(row=0, column=0, rowspan=2, padx=(0, PAD_MD))

        self._app_name_label = ctk.CTkLabel(
            picker_frame,
            text="No application selected",
            font=FONT_BODY_BOLD,
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
        )
        self._app_name_label.grid(row=0, column=1, sticky="w")

        self._app_path_label = ctk.CTkLabel(
            picker_frame,
            text="Click 'Browse' to select an .exe file",
            font=FONT_TINY,
            text_color=TEXT_TERTIARY,
            anchor="w",
            fg_color="transparent",
        )
        self._app_path_label.grid(row=1, column=1, sticky="w")

        browse_btn = ctk.CTkButton(
            picker_frame,
            text="Browse…",
            command=self._browse_exe,
            width=90,
            **STYLE_BUTTON_SECONDARY,
        )
        browse_btn.grid(row=0, column=2, rowspan=2, padx=(PAD_MD, 0))

        # ── Step 2: Configuration ────────────────────────────────────────
        self._add_divider()
        self._add_label("Daily Time Limit")

        self._time_picker = TimePicker(
            self._content, initial_hours=1, initial_minutes=0
        )
        self._time_picker.grid(
            row=self._current_row, column=0, sticky="w",
            pady=(0, PAD_MD),
        )
        self._current_row += 1

        # Grace period
        self._add_label("Grace Period")

        self._grace_var = ctk.StringVar(value="60s")
        grace_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        grace_frame.grid(
            row=self._current_row, column=0, sticky="ew",
            pady=(0, PAD_MD),
        )
        self._current_row += 1

        grace_options = ["30s", "60s", "120s", "300s"]
        self._grace_menu = ctk.CTkOptionMenu(
            grace_frame,
            values=grace_options,
            variable=self._grace_var,
            fg_color=BG_INPUT,
            button_color=BG_ELEVATED,
            button_hover_color=BG_CARD_HOVER,
            dropdown_fg_color=BG_CARD,
            dropdown_hover_color=BG_CARD_HOVER,
            dropdown_text_color=TEXT_PRIMARY,
            text_color=TEXT_PRIMARY,
            font=FONT_BODY,
            width=120,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._grace_menu.pack(anchor="w")

        # Block mode
        self._add_label("Block Mode")

        self._block_mode_var = ctk.StringVar(value="Warn First")
        block_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        block_frame.grid(
            row=self._current_row, column=0, sticky="ew",
            pady=(0, PAD_MD),
        )
        self._current_row += 1

        self._block_mode_seg = ctk.CTkSegmentedButton(
            block_frame,
            values=["Warn First", "Block Immediately"],
            variable=self._block_mode_var,
            font=FONT_SMALL,
            fg_color=BG_INPUT,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_INPUT,
            unselected_hover_color=BG_CARD_HOVER,
            text_color=TEXT_PRIMARY,
            text_color_disabled=TEXT_DISABLED,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._block_mode_seg.pack(anchor="w")

        # Notifications
        self._add_label("Notifications")

        notify_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        notify_frame.grid(
            row=self._current_row, column=0, sticky="ew",
            pady=(0, PAD_MD),
        )
        self._current_row += 1

        self._notify_var = ctk.BooleanVar(value=True)
        self._notify_switch = ctk.CTkSwitch(
            notify_frame,
            text="Enable notifications",
            variable=self._notify_var,
            **STYLE_SWITCH,
        )
        self._notify_switch.pack(anchor="w")

        # Schedule (optional)
        self._add_divider()
        self._add_label("Schedule (Optional)")

        schedule_desc = ctk.CTkLabel(
            self._content,
            text="Only monitor during specific hours of the day.",
            font=FONT_TINY,
            text_color=TEXT_TERTIARY,
            anchor="w",
            fg_color="transparent",
        )
        schedule_desc.grid(
            row=self._current_row, column=0, sticky="w",
            pady=(0, PAD_SM),
        )
        self._current_row += 1

        schedule_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        schedule_frame.grid(
            row=self._current_row, column=0, sticky="ew",
            pady=(0, PAD_MD),
        )
        self._current_row += 1

        ctk.CTkLabel(
            schedule_frame, text="Start:", font=FONT_SMALL,
            text_color=TEXT_SECONDARY, fg_color="transparent",
        ).pack(side="left", padx=(0, PAD_XS))

        self._schedule_start_entry = ctk.CTkEntry(
            schedule_frame,
            placeholder_text="HH:MM",
            width=70,
            height=30,
            font=FONT_SMALL,
            fg_color=BG_INPUT,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_TERTIARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._schedule_start_entry.pack(side="left", padx=(0, PAD_MD))

        ctk.CTkLabel(
            schedule_frame, text="End:", font=FONT_SMALL,
            text_color=TEXT_SECONDARY, fg_color="transparent",
        ).pack(side="left", padx=(0, PAD_XS))

        self._schedule_end_entry = ctk.CTkEntry(
            schedule_frame,
            placeholder_text="HH:MM",
            width=70,
            height=30,
            font=FONT_SMALL,
            fg_color=BG_INPUT,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_TERTIARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._schedule_end_entry.pack(side="left")

        # ── Bottom buttons ───────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=PAD_XL, pady=PAD_LG)

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save",
            command=self._on_save_click,
            **STYLE_BUTTON_PRIMARY,
        )
        save_btn.pack(side="right")

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            **STYLE_BUTTON_SECONDARY,
        )
        cancel_btn.pack(side="right", padx=(0, PAD_SM))

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        logger.debug("AddAppDialog created")

    # ── UI Helpers ───────────────────────────────────────────────────────

    def _add_section_title(self, text: str) -> None:
        """Add a section title label to the form.

        Args:
            text: Title text.
        """
        label = ctk.CTkLabel(
            self._content,
            text=text,
            font=FONT_HEADING,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        )
        label.grid(
            row=self._current_row, column=0, sticky="w",
            pady=(0, PAD_LG),
        )
        self._current_row += 1

    def _add_label(self, text: str) -> None:
        """Add a field label to the form.

        Args:
            text: Label text.
        """
        label = ctk.CTkLabel(
            self._content,
            text=text,
            font=FONT_SMALL_BOLD,
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
        )
        label.grid(
            row=self._current_row, column=0, sticky="w",
            pady=(0, PAD_XS),
        )
        self._current_row += 1

    def _add_divider(self) -> None:
        """Add a horizontal divider line."""
        divider = ctk.CTkFrame(
            self._content, height=1, fg_color=BORDER_DIVIDER, corner_radius=0
        )
        divider.grid(
            row=self._current_row, column=0, sticky="ew",
            pady=PAD_MD,
        )
        self._current_row += 1

    # ── File Picker ──────────────────────────────────────────────────────

    def _browse_exe(self) -> None:
        """Open a Windows file dialog to select an executable."""
        try:
            filepath = filedialog.askopenfilename(
                title="Select Application",
                filetypes=[("Executables", "*.exe"), ("All Files", "*.*")],
                parent=self,
            )
            if not filepath:
                return

            self._selected_exe = filepath
            # Extract app name from the filename without extension
            basename = os.path.basename(filepath)
            self._selected_name = os.path.splitext(basename)[0].replace("_", " ").title()

            # Update UI
            self._app_name_label.configure(
                text=self._selected_name, text_color=TEXT_PRIMARY
            )
            self._app_path_label.configure(text=filepath)

            # Try to extract icon
            self._icon_image = _try_extract_icon(filepath)
            if self._icon_image is not None:
                self._app_icon_label.configure(
                    image=self._icon_image, text=""
                )
            else:
                self._app_icon_label.configure(text="⊞", text_color=ACCENT_LIGHT)

            logger.info("Selected executable: %s", filepath)
        except Exception:
            logger.exception("Error browsing for executable")

    # ── Save ─────────────────────────────────────────────────────────────

    def _on_save_click(self) -> None:
        """Validate inputs and invoke the on_save callback."""
        try:
            if not self._selected_exe:
                self._flash_error("Please select an executable file first.")
                return

            # Parse grace period
            grace_str = self._grace_var.get()
            grace_seconds = int(grace_str.rstrip("s"))

            # Parse block mode
            block_mode_display = self._block_mode_var.get()
            block_mode = (
                "warn_then_block"
                if block_mode_display == "Warn First"
                else "immediate"
            )

            # Parse schedule
            schedule_start: Optional[str] = None
            schedule_end: Optional[str] = None
            start_text = self._schedule_start_entry.get().strip()
            end_text = self._schedule_end_entry.get().strip()
            if start_text and end_text:
                # Validate HH:MM format
                if self._validate_time(start_text) and self._validate_time(end_text):
                    schedule_start = start_text
                    schedule_end = end_text
                else:
                    self._flash_error("Schedule times must be in HH:MM format.")
                    return

            # Build the Application model
            app = Application(
                name=self._selected_name,
                exe_path=self._selected_exe,
                daily_limit_seconds=self._time_picker.get_total_seconds(),
                icon_path=None,
                is_active=True,
                notify_enabled=self._notify_var.get(),
                grace_period_seconds=grace_seconds,
                block_mode=block_mode,
                schedule_start=schedule_start,
                schedule_end=schedule_end,
            )

            logger.info(
                "Saving new application: name='%s', limit=%ds",
                app.name,
                app.daily_limit_seconds,
            )
            self._on_save(app)
            self.destroy()

        except Exception:
            logger.exception("Error saving application")

    def _validate_time(self, time_str: str) -> bool:
        """Validate a string is in HH:MM format.

        Args:
            time_str: Time string to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return False
            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except (ValueError, IndexError):
            return False

    def _flash_error(self, message: str) -> None:
        """Show a brief error message in the dialog.

        Args:
            message: Error text to display.
        """
        try:
            error_label = ctk.CTkLabel(
                self._content,
                text=f"⚠ {message}",
                font=FONT_SMALL,
                text_color=RED_LIGHT,
                fg_color=RED_MUTED,
                corner_radius=6,
                height=30,
            )
            error_label.grid(
                row=self._current_row, column=0, sticky="ew",
                pady=(0, PAD_SM),
            )
            # Auto-remove after 4 seconds
            self.after(4000, lambda: error_label.destroy())
        except Exception:
            logger.exception("Failed to show error flash message")


# ── EditAppDialog ─────────────────────────────────────────────────────────────


class EditAppDialog(ctk.CTkToplevel):
    """Dialog for editing an existing monitored application.

    Pre-fills all fields with the current Application values and allows
    modifying the configuration. Layout mirrors AddAppDialog.

    Args:
        master: Parent widget.
        app: The existing Application to edit.
        on_save: Callback(Application) invoked when the user saves.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        app: Application,
        on_save: callable,
    ) -> None:
        super().__init__(master)

        self._app = app
        self._on_save = on_save

        # ── Window configuration ─────────────────────────────────────────
        self.title(f"Edit — {app.name}")
        self.configure(fg_color=BG_DARKEST)
        self.resizable(False, False)

        dialog_width, dialog_height = 500, 600
        _center_on_parent(self, dialog_width, dialog_height)
        _make_modal(self)

        # ── Content ──────────────────────────────────────────────────────
        self._content = ctk.CTkScrollableFrame(
            self,
            fg_color=BG_DARKEST,
            scrollbar_fg_color=BG_DARKEST,
            scrollbar_button_color=BG_ELEVATED,
            scrollbar_button_hover_color=BG_CARD_HOVER,
        )
        self._content.pack(fill="both", expand=True, padx=PAD_XL, pady=(PAD_XL, 0))
        self._content.grid_columnconfigure(0, weight=1)

        self._current_row = 0

        # ── Title ────────────────────────────────────────────────────────
        title_label = ctk.CTkLabel(
            self._content,
            text=f"Edit {app.name}",
            font=FONT_HEADING,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        )
        title_label.grid(
            row=self._current_row, column=0, sticky="w", pady=(0, PAD_SM)
        )
        self._current_row += 1

        # App info (read-only)
        info_frame = ctk.CTkFrame(
            self._content, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS
        )
        info_frame.grid(
            row=self._current_row, column=0, sticky="ew", pady=(0, PAD_MD)
        )
        self._current_row += 1
        info_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            info_frame,
            text="⊞",
            font=font_bold(22),
            text_color=ACCENT_LIGHT,
            width=40,
            height=40,
            fg_color="transparent",
        ).grid(row=0, column=0, rowspan=2, padx=PAD_MD, pady=PAD_MD)

        ctk.CTkLabel(
            info_frame,
            text=app.name,
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        ).grid(row=0, column=1, sticky="w", padx=(0, PAD_MD), pady=(PAD_MD, 0))

        ctk.CTkLabel(
            info_frame,
            text=app.exe_path,
            font=FONT_TINY,
            text_color=TEXT_TERTIARY,
            anchor="w",
            fg_color="transparent",
        ).grid(row=1, column=1, sticky="w", padx=(0, PAD_MD), pady=(0, PAD_MD))

        # ── Daily limit ──────────────────────────────────────────────────
        self._add_label("Daily Time Limit")

        initial_h = app.daily_limit_seconds // 3600
        initial_m = (app.daily_limit_seconds % 3600) // 60
        self._time_picker = TimePicker(
            self._content, initial_hours=initial_h, initial_minutes=initial_m
        )
        self._time_picker.grid(
            row=self._current_row, column=0, sticky="w", pady=(0, PAD_MD)
        )
        self._current_row += 1

        # ── Grace period ─────────────────────────────────────────────────
        self._add_label("Grace Period")

        grace_val = f"{app.grace_period_seconds}s"
        self._grace_var = ctk.StringVar(value=grace_val)
        grace_options = ["30s", "60s", "120s", "300s"]
        if grace_val not in grace_options:
            grace_options.insert(0, grace_val)

        self._grace_menu = ctk.CTkOptionMenu(
            self._content,
            values=grace_options,
            variable=self._grace_var,
            fg_color=BG_INPUT,
            button_color=BG_ELEVATED,
            button_hover_color=BG_CARD_HOVER,
            dropdown_fg_color=BG_CARD,
            dropdown_hover_color=BG_CARD_HOVER,
            dropdown_text_color=TEXT_PRIMARY,
            text_color=TEXT_PRIMARY,
            font=FONT_BODY,
            width=120,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._grace_menu.grid(
            row=self._current_row, column=0, sticky="w", pady=(0, PAD_MD)
        )
        self._current_row += 1

        # ── Block mode ───────────────────────────────────────────────────
        self._add_label("Block Mode")

        block_display = (
            "Warn First" if app.block_mode == "warn_then_block" else "Block Immediately"
        )
        self._block_mode_var = ctk.StringVar(value=block_display)
        self._block_mode_seg = ctk.CTkSegmentedButton(
            self._content,
            values=["Warn First", "Block Immediately"],
            variable=self._block_mode_var,
            font=FONT_SMALL,
            fg_color=BG_INPUT,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_INPUT,
            unselected_hover_color=BG_CARD_HOVER,
            text_color=TEXT_PRIMARY,
            text_color_disabled=TEXT_DISABLED,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._block_mode_seg.grid(
            row=self._current_row, column=0, sticky="w", pady=(0, PAD_MD)
        )
        self._current_row += 1

        # ── Notifications ────────────────────────────────────────────────
        self._add_label("Notifications")

        self._notify_var = ctk.BooleanVar(value=app.notify_enabled)
        self._notify_switch = ctk.CTkSwitch(
            self._content,
            text="Enable notifications",
            variable=self._notify_var,
            **STYLE_SWITCH,
        )
        self._notify_switch.grid(
            row=self._current_row, column=0, sticky="w", pady=(0, PAD_MD)
        )
        self._current_row += 1

        # ── Schedule ─────────────────────────────────────────────────────
        self._add_label("Schedule (Optional)")

        schedule_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        schedule_frame.grid(
            row=self._current_row, column=0, sticky="ew", pady=(0, PAD_MD)
        )
        self._current_row += 1

        ctk.CTkLabel(
            schedule_frame, text="Start:", font=FONT_SMALL,
            text_color=TEXT_SECONDARY, fg_color="transparent",
        ).pack(side="left", padx=(0, PAD_XS))

        self._schedule_start_entry = ctk.CTkEntry(
            schedule_frame,
            placeholder_text="HH:MM",
            width=70, height=30, font=FONT_SMALL,
            fg_color=BG_INPUT, border_color=BORDER,
            text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_TERTIARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._schedule_start_entry.pack(side="left", padx=(0, PAD_MD))
        if app.schedule_start:
            self._schedule_start_entry.insert(0, app.schedule_start)

        ctk.CTkLabel(
            schedule_frame, text="End:", font=FONT_SMALL,
            text_color=TEXT_SECONDARY, fg_color="transparent",
        ).pack(side="left", padx=(0, PAD_XS))

        self._schedule_end_entry = ctk.CTkEntry(
            schedule_frame,
            placeholder_text="HH:MM",
            width=70, height=30, font=FONT_SMALL,
            fg_color=BG_INPUT, border_color=BORDER,
            text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_TERTIARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._schedule_end_entry.pack(side="left")
        if app.schedule_end:
            self._schedule_end_entry.insert(0, app.schedule_end)

        # ── Bottom buttons ───────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=PAD_XL, pady=PAD_LG)

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Changes",
            command=self._on_save_click,
            **STYLE_BUTTON_PRIMARY,
        )
        save_btn.pack(side="right")

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            **STYLE_BUTTON_SECONDARY,
        )
        cancel_btn.pack(side="right", padx=(0, PAD_SM))

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        logger.debug("EditAppDialog created for '%s'", app.name)

    # ── UI Helpers ───────────────────────────────────────────────────────

    def _add_label(self, text: str) -> None:
        """Add a field label to the form.

        Args:
            text: Label text.
        """
        label = ctk.CTkLabel(
            self._content,
            text=text,
            font=FONT_SMALL_BOLD,
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
        )
        label.grid(
            row=self._current_row, column=0, sticky="w", pady=(0, PAD_XS)
        )
        self._current_row += 1

    # ── Save ─────────────────────────────────────────────────────────────

    def _on_save_click(self) -> None:
        """Validate inputs, update the Application, and invoke on_save."""
        try:
            # Parse grace period
            grace_str = self._grace_var.get()
            grace_seconds = int(grace_str.rstrip("s"))

            # Parse block mode
            block_mode_display = self._block_mode_var.get()
            block_mode = (
                "warn_then_block"
                if block_mode_display == "Warn First"
                else "immediate"
            )

            # Parse schedule
            schedule_start: Optional[str] = None
            schedule_end: Optional[str] = None
            start_text = self._schedule_start_entry.get().strip()
            end_text = self._schedule_end_entry.get().strip()
            if start_text and end_text:
                if self._validate_time(start_text) and self._validate_time(end_text):
                    schedule_start = start_text
                    schedule_end = end_text
                else:
                    self._flash_error("Schedule times must be in HH:MM format.")
                    return

            # Update the application fields
            updated_app = Application(
                id=self._app.id,
                name=self._app.name,
                exe_path=self._app.exe_path,
                daily_limit_seconds=self._time_picker.get_total_seconds(),
                icon_path=self._app.icon_path,
                is_active=self._app.is_active,
                notify_enabled=self._notify_var.get(),
                grace_period_seconds=grace_seconds,
                block_mode=block_mode,
                schedule_start=schedule_start,
                schedule_end=schedule_end,
                created_at=self._app.created_at,
            )

            logger.info(
                "Saving edited application: name='%s', limit=%ds",
                updated_app.name,
                updated_app.daily_limit_seconds,
            )
            self._on_save(updated_app)
            self.destroy()

        except Exception:
            logger.exception("Error saving edited application")

    def _validate_time(self, time_str: str) -> bool:
        """Validate a string is in HH:MM format.

        Args:
            time_str: Time string to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return False
            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except (ValueError, IndexError):
            return False

    def _flash_error(self, message: str) -> None:
        """Show a brief error message in the dialog.

        Args:
            message: Error text to display.
        """
        try:
            error_label = ctk.CTkLabel(
                self._content,
                text=f"⚠ {message}",
                font=FONT_SMALL,
                text_color=RED_LIGHT,
                fg_color=RED_MUTED,
                corner_radius=6,
                height=30,
            )
            error_label.grid(
                row=self._current_row, column=0, sticky="ew", pady=(0, PAD_SM)
            )
            self.after(4000, lambda: error_label.destroy())
        except Exception:
            logger.exception("Failed to show error flash message")


# ── GracePeriodOverlay ────────────────────────────────────────────────────────


class GracePeriodOverlay(ctk.CTkToplevel):
    """Full-screen-feel overlay showing a countdown before an app is blocked.

    Displays a dramatic, always-on-top warning with a large countdown timer
    that ticks every second. When the countdown reaches zero, the
    on_close_app callback is fired automatically.

    The 'I need more time' button shows a minute picker so the user can
    extend their daily limit. The popup is a true modal — it cannot be
    dismissed without selecting an option.

    Args:
        master: Parent widget.
        app_name: Name of the application about to be blocked.
        seconds: Initial countdown duration in seconds.
        on_close_app: Callback invoked when the countdown reaches zero or
                      when the user clicks 'Close App Now'.
        on_extend: Callback(extra_minutes: int) invoked when the user
                   selects an extension duration.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        app_name: str,
        seconds: int,
        on_close_app: callable,
        on_extend: callable,
    ) -> None:
        super().__init__(master)

        self._app_name = app_name
        self._remaining = max(1, seconds)
        self._on_close_app = on_close_app
        self._on_extend = on_extend
        self._timer_id: str | None = None
        self._pulse_id: str | None = None
        self._pulse_step: int = 0
        self._showing_picker: bool = False

        # ── Window configuration ─────────────────────────────────────────
        self.title("Time Limit Warning")
        self.configure(fg_color=BG_DARKEST)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.overrideredirect(False)

        dialog_width, dialog_height = 440, 520
        _center_on_parent(self, dialog_width, dialog_height)

        try:
            self.transient(master)
            self.grab_set()
            self.focus_force()
        except Exception:
            logger.debug("Could not set overlay as modal")

        # ── Content ──────────────────────────────────────────────────────
        self._content = ctk.CTkFrame(self, fg_color=BG_DARKEST)
        self._content.pack(fill="both", expand=True, padx=PAD_2XL, pady=PAD_2XL)
        self._content.grid_columnconfigure(0, weight=1)

        # Warning icon
        warning_label = ctk.CTkLabel(
            self._content,
            text=ICONS.get("warning", "!"),
            font=font(48),
            text_color=RED,
            fg_color="transparent",
        )
        warning_label.grid(row=0, column=0, pady=(0, PAD_SM))

        # Title
        title_label = ctk.CTkLabel(
            self._content,
            text="Time Limit Reached",
            font=FONT_HEADING,
            text_color=RED_LIGHT,
            fg_color="transparent",
        )
        title_label.grid(row=1, column=0, pady=(0, PAD_XS))

        # App name
        app_label = ctk.CTkLabel(
            self._content,
            text=app_name,
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
            fg_color="transparent",
        )
        app_label.grid(row=2, column=0, pady=(0, PAD_MD))

        # Countdown timer — large, dramatic
        self._countdown_label = ctk.CTkLabel(
            self._content,
            text=self._format_countdown(self._remaining),
            font=font_bold(56),
            text_color=RED,
            fg_color="transparent",
        )
        self._countdown_label.grid(row=3, column=0, pady=(0, PAD_SM))

        # Countdown message
        self._message_label = ctk.CTkLabel(
            self._content,
            text=f"{app_name} will be closed when the timer reaches zero.",
            font=FONT_SMALL,
            text_color=TEXT_SECONDARY,
            wraplength=350,
            fg_color="transparent",
        )
        self._message_label.grid(row=4, column=0, pady=(0, PAD_XL))

        # ── Buttons frame ────────────────────────────────────────────────
        self._btn_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        self._btn_frame.grid(row=5, column=0)

        self._extend_btn = ctk.CTkButton(
            self._btn_frame,
            text="I need more time",
            command=self._show_time_picker,
            **STYLE_BUTTON_SECONDARY,
        )
        self._extend_btn.pack(side="left", padx=(0, PAD_SM))

        close_btn = ctk.CTkButton(
            self._btn_frame,
            text="Close App Now",
            command=self._handle_close_app,
            **STYLE_BUTTON_DANGER,
        )
        close_btn.pack(side="left")

        # ── Time picker frame (hidden initially) ─────────────────────────
        self._picker_frame = ctk.CTkFrame(self._content, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)

        ctk.CTkLabel(
            self._picker_frame,
            text="How much more time do you need?",
            font=FONT_SMALL_BOLD,
            text_color=TEXT_PRIMARY,
            fg_color="transparent",
        ).pack(pady=(PAD_MD, PAD_SM))

        minutes_row = ctk.CTkFrame(self._picker_frame, fg_color="transparent")
        minutes_row.pack(pady=(0, PAD_MD))

        for mins in [1, 5, 10, 15, 30]:
            ctk.CTkButton(
                minutes_row,
                text=f"{mins} min",
                width=60,
                height=32,
                font=FONT_SMALL_BOLD,
                fg_color=ACCENT_SURFACE,
                hover_color=ACCENT_MUTED,
                text_color=ACCENT_LIGHT,
                corner_radius=BUTTON_CORNER_RADIUS,
                command=lambda m=mins: self._handle_extend(m),
            ).pack(side="left", padx=PAD_XS)

        # Back button in picker
        ctk.CTkButton(
            self._picker_frame,
            text="Back",
            width=60,
            height=28,
            font=FONT_SMALL,
            fg_color="transparent",
            hover_color=BG_CARD_HOVER,
            text_color=TEXT_TERTIARY,
            corner_radius=BUTTON_CORNER_RADIUS,
            command=self._hide_time_picker,
        ).pack(pady=(0, PAD_SM))

        # Prevent closing via 'X' or Escape — must choose an option
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.bind("<Escape>", lambda _e: None)

        # ── Start countdown and pulse ────────────────────────────────────
        self._start_countdown()
        self._start_pulse()

        logger.info(
            "GracePeriodOverlay shown for '%s' with %d seconds",
            app_name,
            seconds,
        )

    # ── Time picker toggle ───────────────────────────────────────────────

    def _show_time_picker(self) -> None:
        """Show the minute selection buttons."""
        self._showing_picker = True
        self._btn_frame.grid_forget()
        self._picker_frame.grid(row=5, column=0, sticky="ew", padx=PAD_SM, pady=(0, PAD_SM))

    def _hide_time_picker(self) -> None:
        """Hide the minute picker, show original buttons."""
        self._showing_picker = False
        self._picker_frame.grid_forget()
        self._btn_frame.grid(row=5, column=0)

    def _handle_extend(self, minutes: int) -> None:
        """User selected an extension duration."""
        self._cancel_timers()
        try:
            self._on_extend(minutes)
        except Exception:
            logger.exception("Error in on_extend callback")
        # The callback handles destroying the overlay

    # ── Countdown ────────────────────────────────────────────────────────

    def _format_countdown(self, seconds: int) -> str:
        """Format seconds as MM:SS."""
        m, s = divmod(max(0, seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _start_countdown(self) -> None:
        """Begin the per-second countdown tick."""
        self._tick()

    def _tick(self) -> None:
        """Decrement the countdown by one second."""
        try:
            if not self.winfo_exists():
                return

            self._countdown_label.configure(
                text=self._format_countdown(self._remaining)
            )

            if self._remaining <= 0:
                self._handle_close_app()
                return

            # Color escalation in the last 10 seconds
            if self._remaining <= 10:
                self._countdown_label.configure(text_color=RED)
            elif self._remaining <= 30:
                self._countdown_label.configure(text_color=RED_LIGHT)

            self._remaining -= 1
            self._timer_id = self.after(1000, self._tick)
        except Exception:
            # Overlay may have been destroyed
            logger.debug("Countdown tick interrupted")

    def _start_pulse(self) -> None:
        """Create a pulsing visual effect on the countdown label."""
        self._pulse()

    def _pulse(self) -> None:
        """Alternate the countdown font size for a subtle pulse effect."""
        try:
            if not self.winfo_exists():
                return

            self._pulse_step = (self._pulse_step + 1) % 2
            size = 56 if self._pulse_step == 0 else 58
            self._countdown_label.configure(font=font_bold(size))
            self._pulse_id = self.after(800, self._pulse)
        except Exception:
            pass

    # ── Button handlers ──────────────────────────────────────────────────

    def _handle_close_app(self) -> None:
        """Close the monitored app and destroy the overlay."""
        self._cancel_timers()
        try:
            self._on_close_app()
        except Exception:
            logger.exception("Error in on_close_app callback")
        finally:
            try:
                self.destroy()
            except Exception:
                pass

    def _cancel_timers(self) -> None:
        """Cancel all pending after() callbacks."""
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        if self._pulse_id is not None:
            try:
                self.after_cancel(self._pulse_id)
            except Exception:
                pass
            self._pulse_id = None


# ── ExportDialog ──────────────────────────────────────────────────────────────


class ExportDialog(ctk.CTkToplevel):
    """Dialog for exporting usage data to CSV.

    Provides date range selection and a format picker. The actual export
    logic is delegated to the on_export callback.

    Args:
        master: Parent widget.
        on_export: Callback(format: str, start_date: str, end_date: str)
                   invoked when the user clicks Export.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_export: callable,
    ) -> None:
        super().__init__(master)

        self._on_export = on_export

        # ── Window configuration ─────────────────────────────────────────
        self.title("Export Data")
        self.configure(fg_color=BG_DARKEST)
        self.resizable(False, False)

        dialog_width, dialog_height = 420, 380
        _center_on_parent(self, dialog_width, dialog_height)
        _make_modal(self)

        # ── Content ──────────────────────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color=BG_DARKEST)
        content.pack(fill="both", expand=True, padx=PAD_2XL, pady=PAD_2XL)
        content.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(
            content,
            text="Export Data",
            font=FONT_HEADING,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        ).grid(row=0, column=0, sticky="w", pady=(0, PAD_LG))

        # Format selection
        ctk.CTkLabel(
            content,
            text="Export Format",
            font=FONT_SMALL_BOLD,
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
        ).grid(row=1, column=0, sticky="w", pady=(0, PAD_XS))

        self._format_var = ctk.StringVar(value="CSV")
        format_seg = ctk.CTkSegmentedButton(
            content,
            values=["CSV", "JSON"],
            variable=self._format_var,
            font=FONT_SMALL,
            fg_color=BG_INPUT,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_INPUT,
            unselected_hover_color=BG_CARD_HOVER,
            text_color=TEXT_PRIMARY,
            text_color_disabled=TEXT_DISABLED,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        format_seg.grid(row=2, column=0, sticky="w", pady=(0, PAD_LG))

        # Date range
        ctk.CTkLabel(
            content,
            text="Date Range",
            font=FONT_SMALL_BOLD,
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
        ).grid(row=3, column=0, sticky="w", pady=(0, PAD_XS))

        date_frame = ctk.CTkFrame(content, fg_color="transparent")
        date_frame.grid(row=4, column=0, sticky="ew", pady=(0, PAD_LG))

        # Default: last 30 days
        today = datetime.now()
        default_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        default_end = today.strftime("%Y-%m-%d")

        ctk.CTkLabel(
            date_frame, text="From:", font=FONT_SMALL,
            text_color=TEXT_SECONDARY, fg_color="transparent",
        ).pack(side="left", padx=(0, PAD_XS))

        self._start_entry = ctk.CTkEntry(
            date_frame,
            placeholder_text="YYYY-MM-DD",
            width=110, height=30, font=FONT_SMALL,
            fg_color=BG_INPUT, border_color=BORDER,
            text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_TERTIARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._start_entry.insert(0, default_start)
        self._start_entry.pack(side="left", padx=(0, PAD_MD))

        ctk.CTkLabel(
            date_frame, text="To:", font=FONT_SMALL,
            text_color=TEXT_SECONDARY, fg_color="transparent",
        ).pack(side="left", padx=(0, PAD_XS))

        self._end_entry = ctk.CTkEntry(
            date_frame,
            placeholder_text="YYYY-MM-DD",
            width=110, height=30, font=FONT_SMALL,
            fg_color=BG_INPUT, border_color=BORDER,
            text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_TERTIARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._end_entry.insert(0, default_end)
        self._end_entry.pack(side="left")

        # Quick range buttons
        quick_frame = ctk.CTkFrame(content, fg_color="transparent")
        quick_frame.grid(row=5, column=0, sticky="w", pady=(0, PAD_XL))

        for label, days in [("7 days", 7), ("30 days", 30), ("90 days", 90), ("All", 365)]:
            ctk.CTkButton(
                quick_frame,
                text=label,
                width=65,
                height=28,
                font=FONT_TINY,
                command=lambda d=days: self._set_quick_range(d),
                **STYLE_BUTTON_GHOST,
            ).pack(side="left", padx=(0, PAD_XS))

        # ── Buttons ──────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.grid(row=6, column=0, sticky="e")

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            **STYLE_BUTTON_SECONDARY,
        ).pack(side="left", padx=(0, PAD_SM))

        ctk.CTkButton(
            btn_frame,
            text=f"{ICONS.get('export', '⤓')} Export",
            command=self._on_export_click,
            **STYLE_BUTTON_PRIMARY,
        ).pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        logger.debug("ExportDialog created")

    def _set_quick_range(self, days: int) -> None:
        """Set the date range to the last N days.

        Args:
            days: Number of days to go back.
        """
        try:
            today = datetime.now()
            start = (today - timedelta(days=days)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            self._start_entry.delete(0, "end")
            self._start_entry.insert(0, start)
            self._end_entry.delete(0, "end")
            self._end_entry.insert(0, end)
        except Exception:
            logger.exception("Failed to set quick date range")

    def _on_export_click(self) -> None:
        """Validate and invoke the export callback."""
        try:
            fmt = self._format_var.get()
            start_date = self._start_entry.get().strip()
            end_date = self._end_entry.get().strip()

            if not start_date or not end_date:
                return

            # Validate dates
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                logger.warning("Invalid date format in export dialog")
                return

            logger.info("Exporting %s data: %s to %s", fmt, start_date, end_date)
            self._on_export(fmt, start_date, end_date)
            self.destroy()
        except Exception:
            logger.exception("Error in export")


# ── BackupDialog ──────────────────────────────────────────────────────────────


class BackupDialog(ctk.CTkToplevel):
    """Dialog showing available backups with backup and restore controls.

    Lists existing backup files and provides buttons to create a new backup
    or restore from a selected one.

    Args:
        master: Parent widget.
        backups: List of dicts with keys: 'name' (str), 'date' (str),
                 'size' (str), 'path' (str).
        on_backup: Callback() invoked to create a new backup.
        on_restore: Callback(path: str) invoked to restore a backup.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        backups: list[dict],
        on_backup: callable,
        on_restore: callable,
    ) -> None:
        super().__init__(master)

        self._backups = backups
        self._on_backup = on_backup
        self._on_restore = on_restore
        self._selected_backup: Optional[str] = None

        # ── Window configuration ─────────────────────────────────────────
        self.title("Backup & Restore")
        self.configure(fg_color=BG_DARKEST)
        self.resizable(False, False)

        dialog_width, dialog_height = 500, 480
        _center_on_parent(self, dialog_width, dialog_height)
        _make_modal(self)

        # ── Content ──────────────────────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color=BG_DARKEST)
        content.pack(fill="both", expand=True, padx=PAD_2XL, pady=PAD_2XL)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)

        # Title
        ctk.CTkLabel(
            content,
            text="Backup & Restore",
            font=FONT_HEADING,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        ).grid(row=0, column=0, sticky="w", pady=(0, PAD_SM))

        # Description
        ctk.CTkLabel(
            content,
            text="Create backups of your data or restore from a previous backup.",
            font=FONT_SMALL,
            text_color=TEXT_SECONDARY,
            anchor="w",
            wraplength=420,
            fg_color="transparent",
        ).grid(row=1, column=0, sticky="w", pady=(0, PAD_LG))

        # Create backup button
        ctk.CTkButton(
            content,
            text=f"{ICONS.get('backup', '⧉')} Create New Backup",
            command=self._handle_backup,
            **STYLE_BUTTON_PRIMARY,
        ).grid(row=2, column=0, sticky="w", pady=(0, PAD_LG))

        # ── Backup list ──────────────────────────────────────────────────
        ctk.CTkLabel(
            content,
            text="Available Backups",
            font=FONT_SMALL_BOLD,
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
        ).grid(row=3, column=0, sticky="nw", pady=(0, PAD_SM))

        list_frame = ctk.CTkScrollableFrame(
            content,
            fg_color=BG_MID,
            corner_radius=CARD_CORNER_RADIUS,
            scrollbar_fg_color=BG_MID,
            scrollbar_button_color=BG_ELEVATED,
            scrollbar_button_hover_color=BG_CARD_HOVER,
        )
        list_frame.grid(row=4, column=0, sticky="nsew", pady=(0, PAD_LG))
        list_frame.grid_columnconfigure(0, weight=1)

        if not backups:
            ctk.CTkLabel(
                list_frame,
                text="No backups found",
                font=FONT_SMALL,
                text_color=TEXT_TERTIARY,
                fg_color="transparent",
            ).pack(pady=PAD_XL)
        else:
            for idx, backup in enumerate(backups):
                self._create_backup_row(list_frame, backup, idx)

        # ── Bottom buttons ───────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.grid(row=5, column=0, sticky="e")

        ctk.CTkButton(
            btn_frame,
            text="Close",
            command=self.destroy,
            **STYLE_BUTTON_SECONDARY,
        ).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        logger.debug("BackupDialog created with %d backups", len(backups))

    def _create_backup_row(
        self, parent: ctk.CTkFrame, backup: dict, index: int
    ) -> None:
        """Create a single row for a backup entry.

        Args:
            parent: Parent scrollable frame.
            backup: Dict with 'name', 'date', 'size', 'path' keys.
            index: Row index for alternating styling.
        """
        row_color = BG_CARD if index % 2 == 0 else BG_MID
        row = ctk.CTkFrame(
            parent,
            fg_color=row_color,
            corner_radius=8,
            height=48,
        )
        row.pack(fill="x", pady=2, padx=PAD_XS)
        row.grid_columnconfigure(1, weight=1)

        # Backup icon
        ctk.CTkLabel(
            row,
            text=ICONS.get("backup", "⧉"),
            font=font(14),
            text_color=ACCENT_LIGHT,
            width=24,
            fg_color="transparent",
        ).grid(row=0, column=0, padx=(PAD_SM, PAD_XS), pady=PAD_SM)

        # Backup info
        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", pady=PAD_XS)

        ctk.CTkLabel(
            info_frame,
            text=backup.get("name", "Backup"),
            font=FONT_SMALL_BOLD,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        ).pack(anchor="w")

        detail_parts = []
        if backup.get("date"):
            detail_parts.append(backup["date"])
        if backup.get("size"):
            detail_parts.append(backup["size"])
        detail_text = " · ".join(detail_parts) if detail_parts else ""

        ctk.CTkLabel(
            info_frame,
            text=detail_text,
            font=FONT_TINY,
            text_color=TEXT_TERTIARY,
            anchor="w",
            fg_color="transparent",
        ).pack(anchor="w")

        # Restore button
        backup_path = backup.get("path", "")
        ctk.CTkButton(
            row,
            text=f"{ICONS.get('restore', '⟲')} Restore",
            width=80,
            height=28,
            font=FONT_TINY,
            command=lambda p=backup_path: self._handle_restore(p),
            **STYLE_BUTTON_GHOST,
        ).grid(row=0, column=2, padx=(PAD_XS, PAD_SM), pady=PAD_SM)

    def _handle_backup(self) -> None:
        """Create a new backup and close the dialog."""
        try:
            self._on_backup()
            logger.info("Backup creation requested")
            self.destroy()
        except Exception:
            logger.exception("Error creating backup")

    def _handle_restore(self, path: str) -> None:
        """Confirm and restore from a backup.

        Args:
            path: Path to the backup file to restore.
        """
        try:
            if not path:
                logger.warning("No backup path provided for restore")
                return

            # Confirm before restoring
            ConfirmDialog(
                self,
                title="Restore Backup",
                message=(
                    "Are you sure you want to restore from this backup? "
                    "This will replace your current data."
                ),
                confirm_text="Restore",
                is_destructive=True,
                on_confirm=lambda: self._do_restore(path),
            )
        except Exception:
            logger.exception("Error initiating restore")

    def _do_restore(self, path: str) -> None:
        """Execute the restore after confirmation.

        Args:
            path: Path to the backup file.
        """
        try:
            self._on_restore(path)
            logger.info("Restore requested from: %s", path)
            self.destroy()
        except Exception:
            logger.exception("Error restoring backup from '%s'", path)
