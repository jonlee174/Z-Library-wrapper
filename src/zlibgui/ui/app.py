"""The tkinter application window.

Layout: a search bar with filter fields on top, a results table on the left, a
detail pane on the right, and a status bar at the bottom. All widget updates
happen here on the Tk main thread; the backend feeds us Message envelopes via a
queue that we drain with root.after().
"""

from __future__ import annotations

import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Optional

import zlibrary

from ..backend import Backend
from ..config import AppConfig
from ..models import Book, Filters
from ..util import default_download_dir

POLL_MS = 100
FORMATS = [""] + [e.name for e in zlibrary.Extension]


class App(tk.Tk):
    def __init__(self, backend: Backend, config: AppConfig) -> None:
        super().__init__()
        self.backend = backend
        self.config_ = config

        self.title("Z-Library")
        self.geometry("1000x640")
        self.minsize(820, 520)

        self._books: Dict[str, Book] = {}   # tree row id -> Book
        self._detail_token: object = None   # guards async detail fetches
        self._download_token: object = None
        self._logged_in = False

        self._build_style()
        self._build_search_bar()
        self._build_body()
        self._build_status_bar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._poll_queue)
        self._set_status("Logging in…")

    # -------------------------------------------------------------- construction
    def _build_style(self) -> None:
        style = ttk.Style(self)
        # 'clam' is available on all platforms and themes cleanly.
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Search.TButton", padding=6)

    def _build_search_bar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 10, 10, 6))
        bar.pack(fill=tk.X)

        # Row 1: the main search box + Search button.
        top = ttk.Frame(bar)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Search").pack(side=tk.LEFT, padx=(0, 6))
        self.var_title = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.var_title)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.bind("<Return>", lambda _e: self._do_search())
        self.search_btn = ttk.Button(
            top, text="Search", style="Search.TButton", command=self._do_search
        )
        self.search_btn.pack(side=tk.LEFT, padx=(8, 0))
        entry.focus_set()

        # Row 2: the filter fields.
        filt = ttk.Frame(bar, padding=(0, 8, 0, 0))
        filt.pack(fill=tk.X)

        self.var_author = tk.StringVar()
        self.var_publisher = tk.StringVar()
        self.var_edition = tk.StringVar()
        self.var_year_from = tk.StringVar()
        self.var_year_to = tk.StringVar()
        self.var_format = tk.StringVar(value=self.config_.default_format or "")
        self.var_count = tk.StringVar(value=str(self.config_.default_count))

        def field(parent, label, var, width):
            cell = ttk.Frame(parent)
            ttk.Label(cell, text=label).pack(anchor="w")
            e = ttk.Entry(cell, textvariable=var, width=width)
            e.pack()
            e.bind("<Return>", lambda _ev: self._do_search())
            return cell

        field(filt, "Author", self.var_author, 22).grid(row=0, column=0, padx=(0, 10))
        field(filt, "Publisher", self.var_publisher, 20).grid(row=0, column=1, padx=(0, 10))
        field(filt, "Edition", self.var_edition, 12).grid(row=0, column=2, padx=(0, 10))
        field(filt, "Year from", self.var_year_from, 8).grid(row=0, column=3, padx=(0, 10))
        field(filt, "Year to", self.var_year_to, 8).grid(row=0, column=4, padx=(0, 10))

        fmt_cell = ttk.Frame(filt)
        ttk.Label(fmt_cell, text="Format").pack(anchor="w")
        ttk.Combobox(
            fmt_cell, textvariable=self.var_format, values=FORMATS,
            width=8, state="readonly",
        ).pack()
        fmt_cell.grid(row=0, column=5, padx=(0, 10))

        cnt_cell = ttk.Frame(filt)
        ttk.Label(cnt_cell, text="Results").pack(anchor="w")
        ttk.Spinbox(
            cnt_cell, from_=1, to=100, textvariable=self.var_count, width=6,
        ).pack()
        cnt_cell.grid(row=0, column=6)

    def _build_body(self) -> None:
        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        # Left: results table.
        left = ttk.Frame(body)
        columns = ("title", "author", "year", "ext", "size")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        headings = {
            "title": ("Title", 320),
            "author": ("Author", 180),
            "year": ("Year", 60),
            "ext": ("Format", 70),
            "size": ("Size", 90),
        }
        for key, (text, width) in headings.items():
            self.tree.heading(key, text=text)
            anchor = tk.W if key in ("title", "author") else tk.CENTER
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=(key == "title"))
        vsb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self._do_download())
        body.add(left, weight=3)

        # Right: detail pane.
        right = ttk.Frame(body, padding=(10, 0, 0, 0))
        self.detail_title = ttk.Label(right, text="Select a book",
                                      font=("", 12, "bold"), wraplength=280)
        self.detail_title.pack(anchor="w", pady=(0, 8))
        self.detail_text = tk.Text(right, width=36, height=18, wrap=tk.WORD,
                                   state=tk.DISABLED, relief=tk.FLAT,
                                   background=self.cget("background"))
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.download_btn = ttk.Button(
            right, text="Download", command=self._do_download, state=tk.DISABLED
        )
        self.download_btn.pack(fill=tk.X, pady=(8, 0))
        body.add(right, weight=2)

    def _build_status_bar(self) -> None:
        bar = ttk.Frame(self, relief=tk.SUNKEN, padding=(8, 4))
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="")
        self.limits_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Label(bar, textvariable=self.limits_var).pack(side=tk.RIGHT)
        self.progress = ttk.Progressbar(bar, mode="determinate", length=180)

    # -------------------------------------------------------------------- actions
    def _current_filters(self) -> Filters:
        def as_int(s: str) -> Optional[int]:
            s = s.strip()
            return int(s) if s.isdigit() else None

        try:
            count = int(self.var_count.get())
        except ValueError:
            count = self.config_.default_count

        return Filters(
            title=self.var_title.get(),
            author=self.var_author.get(),
            year_from=as_int(self.var_year_from.get()),
            year_to=as_int(self.var_year_to.get()),
            publisher=self.var_publisher.get(),
            edition=self.var_edition.get(),
            fmt=self.var_format.get(),
            count=max(1, min(count, 100)),
        )

    def _do_search(self) -> None:
        if not self._logged_in:
            self._set_status("Please wait — still logging in…")
            return
        filters = self._current_filters()
        if not filters.query() and not filters.needs_detail_fetch():
            self._set_status("Type a title or author to search.")
            return
        self.tree.delete(*self.tree.get_children())
        self._books.clear()
        self._clear_detail()
        self.search_btn.configure(state=tk.DISABLED)
        note = " (fetching details to filter…)" if filters.needs_detail_fetch() else ""
        self._set_status("Searching…" + note)
        self.backend.search(filters)

    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        book = self._books.get(sel[0])
        if not book:
            return
        self._show_detail(book)
        if book.detail is None:
            token = object()
            self._detail_token = token
            self.backend.fetch_detail(book, token)

    def _do_download(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        book = self._books.get(sel[0])
        if not book:
            return
        dest = Path(self.config_.download_dir) if self.config_.download_dir else default_download_dir()
        chosen = filedialog.askdirectory(
            title="Save book to…", initialdir=str(dest)
        )
        if not chosen:
            return
        token = object()
        self._download_token = token
        self.download_btn.configure(state=tk.DISABLED)
        self._show_progress(0, 0)
        self._set_status(f"Downloading “{book.name}”…")
        self.backend.download(book, Path(chosen), token)

    def _on_close(self) -> None:
        self.backend.shutdown()
        self.destroy()

    # -------------------------------------------------------------- detail pane
    def _clear_detail(self) -> None:
        self.detail_title.configure(text="Select a book")
        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.configure(state=tk.DISABLED)
        self.download_btn.configure(state=tk.DISABLED)

    def _show_detail(self, book: Book) -> None:
        self.detail_title.configure(text=book.name)
        lines = [
            ("Author", book.authors),
            ("Year", book.year),
            ("Publisher", book.publisher),
            ("Edition", book.edition),
            ("Language", book.language),
            ("Format", book.extension),
            ("Size", book.size),
        ]
        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        for label, value in lines:
            if value:
                self.detail_text.insert(tk.END, f"{label}: {value}\n")
        if book.description:
            self.detail_text.insert(tk.END, "\n" + book.description.strip() + "\n")
        elif book.detail is None:
            self.detail_text.insert(tk.END, "\nLoading details…\n")
        self.detail_text.configure(state=tk.DISABLED)
        self.download_btn.configure(state=tk.NORMAL)

    # -------------------------------------------------------------- status/progress
    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _show_progress(self, done: int, total: int) -> None:
        if not self.progress.winfo_ismapped():
            self.progress.pack(side=tk.RIGHT, padx=(0, 12))
        if total > 0:
            self.progress.configure(mode="determinate", maximum=total, value=done)
        else:
            self.progress.configure(mode="indeterminate")
            self.progress.start(60)

    def _hide_progress(self) -> None:
        self.progress.stop()
        if self.progress.winfo_ismapped():
            self.progress.pack_forget()

    # -------------------------------------------------------------- queue polling
    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self.backend.queue.get_nowait()
                self._dispatch(msg.kind, msg.payload)
        except queue.Empty:
            pass
        self.after(POLL_MS, self._poll_queue)

    def _dispatch(self, kind: str, payload) -> None:
        if kind == "login_ok":
            self._logged_in = True
            self._set_status("Logged in. Ready to search.")
        elif kind == "login_err":
            self._set_status("Login failed.")
            messagebox.showerror(
                "Login failed",
                "Could not log in to Z-Library. Check your email and password "
                f"in:\n\n{self.config_.path}\n\nDetails:\n{payload}",
            )
        elif kind == "limits":
            self._update_limits(payload)
        elif kind == "search_started":
            self._search_expected = payload
            self._set_status(f"Found up to {payload} results…")
        elif kind == "result":
            self._add_result(payload)
        elif kind == "search_done":
            self.search_btn.configure(state=tk.NORMAL)
            n = len(self._books)
            self._set_status(f"{n} result{'s' if n != 1 else ''}."
                             if n else "No matching books found.")
        elif kind == "search_err":
            self.search_btn.configure(state=tk.NORMAL)
            self._set_status("Search failed.")
            messagebox.showerror("Search failed", str(payload))
        elif kind == "detail":
            token, book = payload
            if token is self._detail_token and self._is_selected(book):
                self._show_detail(book)
        elif kind == "detail_err":
            pass  # detail is best-effort; stub info is already shown
        elif kind == "download_progress":
            token, done, total = payload
            if token is self._download_token:
                self._show_progress(done, total)
                if total > 0:
                    pct = int(done * 100 / total)
                    self._set_status(f"Downloading… {pct}%")
        elif kind == "download_done":
            token, path = payload
            if token is self._download_token:
                self._hide_progress()
                self.download_btn.configure(state=tk.NORMAL)
                self._set_status("Download complete.")
                messagebox.showinfo("Download complete", f"Saved to:\n\n{path}")
        elif kind == "download_err":
            token, err = payload
            if token is self._download_token:
                self._hide_progress()
                self.download_btn.configure(state=tk.NORMAL)
                self._set_status("Download failed.")
                messagebox.showerror("Download failed", str(err))
        elif kind == "status":
            self._set_status(str(payload))

    # -------------------------------------------------------------- helpers
    def _add_result(self, book: Book) -> None:
        row = self.tree.insert(
            "", tk.END,
            values=(book.name, book.authors, book.year, book.extension, book.size),
        )
        self._books[row] = book

    def _is_selected(self, book: Book) -> bool:
        sel = self.tree.selection()
        return bool(sel) and self._books.get(sel[0]) is book

    def _update_limits(self, limits: dict) -> None:
        remaining = limits.get("daily_remaining")
        allowed = limits.get("daily_allowed")
        if remaining is not None and allowed is not None:
            self.limits_var.set(f"Downloads today: {allowed - remaining}/{allowed}")
