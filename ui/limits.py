"""
Limitin Desktop — Apps & Limits Page

Manage monitored applications: add, edit, delete, search, sort, and configure
daily usage limits for each app.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import filedialog

from themes.dark_theme import (
    BG_DARKEST, BG_DARK, BG_MID, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BG_INPUT,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_MUTED, ACCENT_SURFACE,
    CYAN, GREEN, GREEN_MUTED, AMBER, AMBER_MUTED, RED, RED_LIGHT, RED_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_DISABLED,
    BORDER, BORDER_HOVER, BORDER_FOCUS, BORDER_DIVIDER,
    font, font_bold,
    FONT_TITLE, FONT_HEADING, FONT_SUBHEADING, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_SMALL_BOLD, FONT_TINY,
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL, PAD_3XL,
    CARD_CORNER_RADIUS, BUTTON_CORNER_RADIUS, INPUT_CORNER_RADIUS,
    STYLE_CARD, STYLE_BUTTON_PRIMARY, STYLE_BUTTON_SECONDARY, STYLE_BUTTON_GHOST,
    STYLE_BUTTON_DANGER, STYLE_INPUT, STYLE_PROGRESS_BAR, STYLE_SWITCH,
    STYLE_SCROLLABLE_FRAME,
    ICONS, get_usage_color, get_status_badge_colors,
)
from utils.helpers import format_duration, format_percentage, clamp
from utils.time_utils import today_str
from services.logger import get_logger

if TYPE_CHECKING:
    from database.schema import Database

logger = get_logger("ui.limits")


# ── Dialogs ───────────────────────────────────────────────────────────────────

class AddAppDialog(ctk.CTkToplevel):
    """Dialog window for adding a new monitored application."""

    def __init__(self, master: ctk.CTkFrame, db: "Database | None" = None) -> None:
        super().__init__(master)
        self.db = db
        self.result: dict | None = None

        self.title("Add Application")
        self.geometry("480x400")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARKEST)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self._build_ui()
        self.after(50, self._center_on_parent)

    def _center_on_parent(self) -> None:
        """Center the dialog on its parent window."""
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        px = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    def _build_ui(self) -> None:
        """Construct the dialog widgets."""
        self.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(
            self, text="Add Application", font=FONT_HEADING,
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=PAD_XL, pady=(PAD_XL, PAD_LG), sticky="w")

        # App name
        ctk.CTkLabel(self, text="Application Name", font=FONT_SMALL_BOLD, text_color=TEXT_SECONDARY).grid(
            row=1, column=0, padx=PAD_XL, pady=(0, PAD_XS), sticky="w")
        self._name_entry = ctk.CTkEntry(self, placeholder_text="e.g. Chrome", **STYLE_INPUT, width=0)
        self._name_entry.grid(row=2, column=0, padx=PAD_XL, pady=(0, PAD_MD), sticky="ew")

        # Executable path
        ctk.CTkLabel(self, text="Executable Path", font=FONT_SMALL_BOLD, text_color=TEXT_SECONDARY).grid(
            row=3, column=0, padx=PAD_XL, pady=(0, PAD_XS), sticky="w")

        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.grid(row=4, column=0, padx=PAD_XL, pady=(0, PAD_MD), sticky="ew")
        path_frame.grid_columnconfigure(0, weight=1)

        self._path_entry = ctk.CTkEntry(path_frame, placeholder_text="C:\\...\\app.exe", **STYLE_INPUT, width=0)
        self._path_entry.grid(row=0, column=0, sticky="ew", padx=(0, PAD_SM))

        ctk.CTkButton(
            path_frame, text="Browse", **STYLE_BUTTON_SECONDARY, width=80,
            command=self._browse_exe,
        ).grid(row=0, column=1)

        # Daily limit (minutes)
        ctk.CTkLabel(self, text="Daily Limit (minutes)", font=FONT_SMALL_BOLD, text_color=TEXT_SECONDARY).grid(
            row=5, column=0, padx=PAD_XL, pady=(0, PAD_XS), sticky="w")
        self._limit_entry = ctk.CTkEntry(self, placeholder_text="60", **STYLE_INPUT, width=0)
        self._limit_entry.grid(row=6, column=0, padx=PAD_XL, pady=(0, PAD_MD), sticky="ew")
        self._limit_entry.insert(0, "60")

        # Error label
        self._error_label = ctk.CTkLabel(
            self, text="", font=FONT_SMALL, text_color=RED_LIGHT,
        )
        self._error_label.grid(row=7, column=0, padx=PAD_XL, pady=0, sticky="w")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=8, column=0, padx=PAD_XL, pady=(PAD_MD, PAD_XL), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_frame, text="Cancel", **STYLE_BUTTON_GHOST, width=100,
            command=self.destroy,
        ).grid(row=0, column=0, sticky="e", padx=(0, PAD_SM))

        ctk.CTkButton(
            btn_frame, text=f"{ICONS['check']}  Add App", **STYLE_BUTTON_PRIMARY, width=120,
            command=self._on_confirm,
        ).grid(row=0, column=1, sticky="e")

    def _browse_exe(self) -> None:
        """Open file dialog to select an executable."""
        path = filedialog.askopenfilename(
            title="Select Application",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self._path_entry.delete(0, "end")
            self._path_entry.insert(0, path)
            # Auto-fill name if empty
            if not self._name_entry.get().strip():
                name = os.path.splitext(os.path.basename(path))[0].title()
                self._name_entry.delete(0, "end")
                self._name_entry.insert(0, name)

    def _on_confirm(self) -> None:
        """Validate and add the application."""
        name = self._name_entry.get().strip()
        path = self._path_entry.get().strip()
        limit_str = self._limit_entry.get().strip()

        if not name:
            self._error_label.configure(text="Application name is required.")
            return
        if not path:
            self._error_label.configure(text="Executable path is required.")
            return
        try:
            limit_min = int(limit_str)
            if limit_min <= 0:
                raise ValueError
        except ValueError:
            self._error_label.configure(text="Limit must be a positive integer.")
            return

        if self.db is not None:
            try:
                # Check for duplicates
                existing = self.db.fetch_one(
                    "SELECT id FROM applications WHERE name = ? OR exe_path = ?",
                    (name, path),
                )
                if existing:
                    self._error_label.configure(text="This app is already being monitored.")
                    return

                from utils.time_utils import now_iso
                self.db.execute(
                    "INSERT INTO applications (name, exe_path, daily_limit_seconds, created_at) VALUES (?, ?, ?, ?)",
                    (name, path, limit_min * 60, now_iso()),
                )
                self.result = {"name": name, "path": path, "limit": limit_min}
                logger.info(f"Added app: {name} with {limit_min}m limit")
            except Exception as exc:
                logger.error(f"Error adding app: {exc}", exc_info=True)
                self._error_label.configure(text=f"Error: {exc}")
                return

        self.destroy()


class EditAppDialog(ctk.CTkToplevel):
    """Dialog for editing an existing monitored application's limit."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        db: "Database | None" = None,
        app_id: int = 0,
        app_name: str = "",
        current_limit: int = 60,
    ) -> None:
        super().__init__(master)
        self.db = db
        self._app_id = app_id
        self.result: dict | None = None

        self.title(f"Edit — {app_name}")
        self.geometry("420x280")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARKEST)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self._build_ui(app_name, current_limit)
        self.after(50, self._center_on_parent)

    def _center_on_parent(self) -> None:
        """Center on parent."""
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        px = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    def _build_ui(self, app_name: str, current_limit: int) -> None:
        """Construct dialog widgets."""
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text=f"Edit {app_name}", font=FONT_HEADING, text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=PAD_XL, pady=(PAD_XL, PAD_LG), sticky="w")

        ctk.CTkLabel(self, text="Daily Limit (minutes)", font=FONT_SMALL_BOLD, text_color=TEXT_SECONDARY).grid(
            row=1, column=0, padx=PAD_XL, pady=(0, PAD_XS), sticky="w")

        self._limit_entry = ctk.CTkEntry(self, **STYLE_INPUT, width=0)
        self._limit_entry.grid(row=2, column=0, padx=PAD_XL, pady=(0, PAD_SM), sticky="ew")
        self._limit_entry.insert(0, str(current_limit))

        # Preset buttons
        preset_frame = ctk.CTkFrame(self, fg_color="transparent")
        preset_frame.grid(row=3, column=0, padx=PAD_XL, pady=(0, PAD_MD), sticky="ew")
        for i, mins in enumerate([15, 30, 60, 120, 180]):
            label = f"{mins}m" if mins < 60 else f"{mins // 60}h"
            ctk.CTkButton(
                preset_frame, text=label, **STYLE_BUTTON_GHOST, width=50,
                command=lambda m=mins: self._set_preset(m),
            ).grid(row=0, column=i, padx=(0, PAD_XS))

        self._error_label = ctk.CTkLabel(self, text="", font=FONT_SMALL, text_color=RED_LIGHT)
        self._error_label.grid(row=4, column=0, padx=PAD_XL, sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=PAD_XL, pady=(PAD_MD, PAD_XL), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(btn_frame, text="Cancel", **STYLE_BUTTON_GHOST, width=100, command=self.destroy).grid(
            row=0, column=0, sticky="e", padx=(0, PAD_SM))
        ctk.CTkButton(btn_frame, text=f"{ICONS['check']}  Save", **STYLE_BUTTON_PRIMARY, width=100,
                       command=self._on_save).grid(row=0, column=1, sticky="e")

    def _set_preset(self, minutes: int) -> None:
        """Set the limit entry to a preset value."""
        self._limit_entry.delete(0, "end")
        self._limit_entry.insert(0, str(minutes))

    def _on_save(self) -> None:
        """Validate and save the new limit."""
        try:
            limit_min = int(self._limit_entry.get().strip())
            if limit_min <= 0:
                raise ValueError
        except ValueError:
            self._error_label.configure(text="Limit must be a positive integer.")
            return

        if self.db is not None and self._app_id:
            try:
                self.db.execute(
                    "UPDATE applications SET daily_limit_seconds = ? WHERE id = ?",
                    (limit_min * 60, self._app_id),
                )
                self.result = {"limit": limit_min}
                logger.info(f"Updated limit for app_id={self._app_id} to {limit_min}m")
            except Exception as exc:
                logger.error(f"Error updating limit: {exc}", exc_info=True)
                self._error_label.configure(text=f"Error: {exc}")
                return
        self.destroy()


class ConfirmDialog(ctk.CTkToplevel):
    """A simple Yes/No confirmation dialog."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        title: str = "Confirm",
        message: str = "Are you sure?",
        confirm_text: str = "Delete",
        danger: bool = True,
    ) -> None:
        super().__init__(master)
        self.confirmed = False

        self.title(title)
        self.geometry("380x200")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARKEST)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=title, font=FONT_HEADING, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, padx=PAD_XL, pady=(PAD_XL, PAD_SM), sticky="w")
        ctk.CTkLabel(self, text=message, font=FONT_BODY, text_color=TEXT_SECONDARY, wraplength=320).grid(
            row=1, column=0, padx=PAD_XL, pady=(0, PAD_LG), sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=PAD_XL, pady=(0, PAD_XL), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(btn_frame, text="Cancel", **STYLE_BUTTON_GHOST, width=100, command=self.destroy).grid(
            row=0, column=0, sticky="e", padx=(0, PAD_SM))

        btn_style = STYLE_BUTTON_DANGER if danger else STYLE_BUTTON_PRIMARY
        ctk.CTkButton(btn_frame, text=confirm_text, **btn_style, width=120, command=self._on_confirm).grid(
            row=0, column=1, sticky="e")

        self.after(50, self._center)

    def _center(self) -> None:
        """Center on parent."""
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        px = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    def _on_confirm(self) -> None:
        """Mark as confirmed and close."""
        self.confirmed = True
        self.destroy()


# ── App List Item Widget ──────────────────────────────────────────────────────

class AppListItem(ctk.CTkFrame):
    """A single row in the app list showing name, usage, limit, and actions."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        app_id: int = 0,
        app_name: str = "",
        process_name: str = "",
        usage_seconds: int = 0,
        limit_minutes: int = 60,
        is_active: bool = True,
        on_edit: "callable | None" = None,
        on_delete: "callable | None" = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **STYLE_CARD, height=72, **kwargs)
        self.grid_propagate(False)

        self.app_id = app_id
        self._limit_seconds = limit_minutes * 60
        self._on_edit = on_edit
        self._on_delete = on_delete

        self.grid_columnconfigure(1, weight=1)

        # Status indicator
        bg_color, text_color = get_status_badge_colors("active" if is_active else "idle")
        self._status_dot = ctk.CTkLabel(self, text="●", font=font(12), text_color=text_color, width=24)
        self._status_dot.grid(row=0, column=0, rowspan=2, padx=(PAD_MD, PAD_XS), pady=PAD_MD)

        # Name & process
        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.grid(row=0, column=1, rowspan=2, sticky="nsw", padx=(0, PAD_SM), pady=PAD_MD)

        self._name_label = ctk.CTkLabel(
            name_frame, text=app_name, font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY, anchor="w",
        )
        self._name_label.pack(anchor="w")

        self._process_label = ctk.CTkLabel(
            name_frame, text=process_name, font=FONT_TINY,
            text_color=TEXT_TERTIARY, anchor="w",
        )
        self._process_label.pack(anchor="w")

        # Usage / Limit
        pct = usage_seconds / max(self._limit_seconds, 1)
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=2, rowspan=2, sticky="nse", padx=(0, PAD_SM), pady=PAD_MD)

        self._usage_label = ctk.CTkLabel(
            info_frame,
            text=f"{format_duration(usage_seconds)} / {format_duration(self._limit_seconds)}",
            font=FONT_SMALL, text_color=TEXT_SECONDARY, anchor="e",
        )
        self._usage_label.pack(anchor="e")

        self._pct_label = ctk.CTkLabel(
            info_frame, text=format_percentage(pct),
            font=FONT_SMALL_BOLD, text_color=get_usage_color(pct), anchor="e",
        )
        self._pct_label.pack(anchor="e")

        # Edit button
        ctk.CTkButton(
            self, text=ICONS["edit"], **STYLE_BUTTON_GHOST, width=36,
            command=self._handle_edit,
        ).grid(row=0, column=3, rowspan=2, padx=(0, PAD_XS), pady=PAD_MD)

        # Delete button
        ctk.CTkButton(
            self, text=ICONS["delete"], fg_color="transparent",
            hover_color=RED_MUTED, text_color=RED_LIGHT,
            corner_radius=BUTTON_CORNER_RADIUS, width=36, height=36, font=font(13),
            command=self._handle_delete,
        ).grid(row=0, column=4, rowspan=2, padx=(0, PAD_MD), pady=PAD_MD)

    def update_usage(self, usage_seconds: int) -> None:
        """Update the usage display in-place without rebuilding the widget."""
        pct = usage_seconds / max(self._limit_seconds, 1)
        self._usage_label.configure(
            text=f"{format_duration(usage_seconds)} / {format_duration(self._limit_seconds)}"
        )
        self._pct_label.configure(
            text=format_percentage(pct),
            text_color=get_usage_color(pct),
        )

    def _handle_edit(self) -> None:
        """Trigger edit callback."""
        if self._on_edit:
            self._on_edit(self.app_id)

    def _handle_delete(self) -> None:
        """Trigger delete callback."""
        if self._on_delete:
            self._on_delete(self.app_id)


# ── Limits Page ───────────────────────────────────────────────────────────────

class LimitsPage(ctk.CTkFrame):
    """App management page for adding, editing, and deleting monitored apps."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        db: "Database | None" = None,
        tracker: object | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=BG_MID, corner_radius=0, **kwargs)
        self.db = db
        self.tracker = tracker

        self._search_text: str = ""
        self._sort_mode: str = "Name"
        self._list_items: list[AppListItem] = []

        self._build_ui()
        logger.info("Limits page initialized")

    def _build_ui(self) -> None:
        """Construct the page layout."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ── Header ───────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=PAD_XL, pady=(PAD_XL, PAD_MD))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=f"{ICONS['apps']}  Apps & Limits", font=FONT_TITLE,
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text=f"{ICONS['add']}  Add App", **STYLE_BUTTON_PRIMARY, width=120,
            command=self._on_add_app,
        ).grid(row=0, column=1, sticky="e")

        # ── Search bar ───────────────────────────────────────────────────
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_MD))
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(
            search_frame, placeholder_text=f"{ICONS['search']}  Search apps…",
            **STYLE_INPUT, width=0,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, PAD_SM))
        self._search_entry.bind("<KeyRelease>", self._on_search_changed)

        # ── Sort buttons ─────────────────────────────────────────────────
        sort_frame = ctk.CTkFrame(self, fg_color="transparent")
        sort_frame.grid(row=2, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_MD))

        ctk.CTkLabel(
            sort_frame, text="Sort by:", font=FONT_SMALL, text_color=TEXT_TERTIARY,
        ).grid(row=0, column=0, padx=(0, PAD_SM))

        self._sort_seg = ctk.CTkSegmentedButton(
            sort_frame, values=["Name", "Usage", "Limit", "Status"],
            font=FONT_SMALL, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_ELEVATED,
            unselected_hover_color=BG_CARD_HOVER,
            text_color=TEXT_PRIMARY,
            command=self._on_sort_changed,
        )
        self._sort_seg.set("Name")
        self._sort_seg.grid(row=0, column=1)

        # ── Scrollable app list ──────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, **STYLE_SCROLLABLE_FRAME)
        self._scroll.grid(row=3, column=0, sticky="nsew", padx=PAD_XL, pady=(0, PAD_XL))
        self._scroll.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(
            self._scroll,
            text=f"{ICONS['apps']}\n\nNo apps being monitored.\n"
                 f"Click 'Add App' to start tracking an application.",
            font=FONT_BODY, text_color=TEXT_TERTIARY, justify="center",
        )

    # ── Data ──────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Update usage counters in-place, or rebuild if the list changed."""
        # If we have existing items, try to update in-place
        if self._list_items and self.tracker is not None and hasattr(self.tracker, 'timer'):
            live_usage = self.tracker.timer.get_all_usage()
            for item in self._list_items:
                usage = live_usage.get(item.app_id, 0)
                try:
                    item.update_usage(usage)
                except Exception:
                    pass
            return
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Destroy and recreate app list items."""
        for item in self._list_items:
            item.destroy()
        self._list_items.clear()

        if self.db is None:
            self._show_empty()
            return

        try:
            search = self._search_text.lower()

            # Get app definitions from DB
            rows = self.db.fetch_all(
                """SELECT id, name, exe_path,
                          daily_limit_seconds,
                          is_active as limit_active
                   FROM applications"""
            )

            # Get live usage from the tracker's in-memory counters
            live_usage: dict[int, int] = {}
            if self.tracker is not None and hasattr(self.tracker, 'timer'):
                live_usage = self.tracker.timer.get_all_usage()

            # Enrich rows with live usage
            enriched = []
            for r in rows:
                app_id = r["id"]
                used = live_usage.get(app_id, 0)
                enriched.append({**dict(r), "used_secs": used})

            # Filter by search
            if search:
                enriched = [r for r in enriched if search in r["name"].lower()]

            # Sort
            if self._sort_mode == "Name":
                enriched.sort(key=lambda r: r["name"].lower())
            elif self._sort_mode == "Usage":
                enriched.sort(key=lambda r: r["used_secs"], reverse=True)
            elif self._sort_mode == "Limit":
                enriched.sort(key=lambda r: r["daily_limit_seconds"])
            elif self._sort_mode == "Status":
                enriched.sort(key=lambda r: (not bool(r["limit_active"]), r["name"].lower()))

            if not enriched:
                self._show_empty()
                return

            self._empty_label.grid_forget()

            for i, r in enumerate(enriched):
                limit_min = r["daily_limit_seconds"] // 60
                item = AppListItem(
                    self._scroll,
                    app_id=r["id"],
                    app_name=r["name"],
                    process_name=os.path.basename(r["exe_path"] or ""),
                    usage_seconds=r["used_secs"],
                    limit_minutes=limit_min,
                    is_active=bool(r["limit_active"]) if r["limit_active"] is not None else True,
                    on_edit=self._on_edit_app,
                    on_delete=self._on_delete_app,
                )
                item.grid(row=i, column=0, sticky="ew", pady=(0, PAD_SM))
                self._list_items.append(item)

        except Exception as exc:
            logger.error(f"Error rebuilding app list: {exc}", exc_info=True)
            self._show_empty()

    def _show_empty(self) -> None:
        """Display the empty state."""
        for item in self._list_items:
            item.destroy()
        self._list_items.clear()
        self._empty_label.grid(row=0, column=0, pady=PAD_3XL)

    # ── Event Handlers ────────────────────────────────────────────────────

    def _on_search_changed(self, event: object = None) -> None:
        """Handle search text changes."""
        self._search_text = self._search_entry.get().strip()
        self._rebuild_list()

    def _on_sort_changed(self, mode: str) -> None:
        """Handle sort mode changes."""
        self._sort_mode = mode
        self._rebuild_list()

    def _on_add_app(self) -> None:
        """Open the Add App dialog."""
        dialog = AddAppDialog(self, db=self.db)
        self.wait_window(dialog)
        if dialog.result:
            self._rebuild_list()

    def _on_edit_app(self, app_id: int) -> None:
        """Open the Edit App dialog for the given app."""
        if self.db is None:
            return

        try:
            row = self.db.fetch_one(
                """SELECT name, daily_limit_seconds
                   FROM applications
                   WHERE id = ?""",
                (app_id,),
            )
            if not row:
                return

            dialog = EditAppDialog(
                self, db=self.db, app_id=app_id,
                app_name=row["name"], current_limit=row["daily_limit_seconds"] // 60,
            )
            self.wait_window(dialog)
            if dialog.result:
                self._rebuild_list()
        except Exception as exc:
            logger.error(f"Error opening edit dialog: {exc}", exc_info=True)

    def _on_delete_app(self, app_id: int) -> None:
        """Confirm and delete an app from monitoring."""
        if self.db is None:
            return

        try:
            row = self.db.fetch_one("SELECT name FROM applications WHERE id = ?", (app_id,))
            name = row["name"] if row else "this app"
        except Exception:
            name = "this app"

        dialog = ConfirmDialog(
            self,
            title="Remove App",
            message=f"Stop monitoring '{name}'? Usage history will be preserved.",
            confirm_text="Remove",
        )
        self.wait_window(dialog)

        if dialog.confirmed and self.db is not None:
            try:
                self.db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
                logger.info(f"Deleted app id={app_id} ({name})")
                self._rebuild_list()
            except Exception as exc:
                logger.error(f"Error deleting app: {exc}", exc_info=True)

    def destroy(self) -> None:
        """Clean up."""
        super().destroy()
