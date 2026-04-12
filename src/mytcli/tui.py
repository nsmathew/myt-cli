"""Interactive TUI for myt-cli using prompt_toolkit."""

import asyncio
import os
import re
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import (
    HSplit, VSplit, Window, FloatContainer, Float,
)
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.history import FileHistory
from prompt_toolkit.widgets import SearchToolbar

import src.mytcli.constants as constants
from src.mytcli.constants import (LOGGER, HISTORY_FILE, REFRESH_INTERVAL,
                                  SUCCESS)
from src.mytcli.db import connect_to_tasksdb
from src.mytcli.dispatcher import TUIDispatcher, MUTATION_COMMANDS
from src.mytcli.completer import MytCompleter


class MytTUI:
    """Full-screen interactive TUI for myt-cli."""

    def __init__(self):
        self._display_text = ""
        self._filter_args = []
        self._last_command = None  # last command that produced the display
        self._last_refresh = None
        self._status_message = ""
        self._completer = MytCompleter()
        self._dispatcher = None
        self._app = None
        self._display_window = None
        self._input_window = None
        self._table_focused = False
        self._selected_row = 0
        self._data_row_indices = []
        # Dialog state
        self._dialog_visible = False
        self._dialog_float = None
        self._dialog_choices = []
        self._dialog_default = None
        self._dialog_selected = 0
        self._prompt_event = threading.Event()
        self._prompt_result = None
        self._dispatching = False
        # Notification popup state (F8)
        self._notification_visible = False
        self._notification_float = None

    def _get_task_counts(self):
        """Get pending task counts for the toolbar."""
        try:
            from sqlalchemy import and_, func, distinct, case
            from src.mytcli.models import Workspace
            from src.mytcli.constants import (WS_AREA_PENDING, TASK_TYPE_NRML,
                                              TASK_TYPE_DRVD)
            import src.mytcli.db as db
            from datetime import datetime as dt
            curr_day = dt.now()
            visib_xpr = (case((and_(Workspace.hide > curr_day.date(),
                                    Workspace.hide != None),
                               "HIDDEN"), else_="VISIBLE")
                         .label("VISIBILITY"))
            max_ver_sqr = (db.SESSION.query(Workspace.uuid,
                                            func.max(Workspace.version)
                                            .label("maxver"))
                           .group_by(Workspace.uuid).subquery())
            results = (db.SESSION.query(visib_xpr,
                                        func.count(distinct(Workspace.uuid))
                                        .label("CNT"))
                        .join(max_ver_sqr, Workspace.uuid ==
                              max_ver_sqr.c.uuid)
                        .filter(and_(Workspace.area == WS_AREA_PENDING,
                                     Workspace.version ==
                                     max_ver_sqr.c.maxver,
                                     Workspace.task_type.in_(
                                         [TASK_TYPE_NRML, TASK_TYPE_DRVD])))
                        .group_by(visib_xpr)
                        .all())
            vis = hid = 0
            for r in results:
                if r[0] == "HIDDEN":
                    hid = r[1]
                elif r[0] == "VISIBLE":
                    vis = r[1]
            return vis + hid, hid
        except Exception:
            return None, None

    def _get_toolbar_text(self):
        filter_str = " ".join(self._filter_args) if self._filter_args else "(none)"
        refresh_str = self._last_refresh or "--:--:--"
        total, hidden = self._get_task_counts()
        counts = ""
        if total is not None:
            displayed = constants.TUI_DISPLAYED_COUNT
            if displayed is not None:
                counts = " | Displayed: {} | Pending: {} | Hidden: {}".format(
                    displayed, total, hidden)
            else:
                counts = " | Pending: {} | Hidden: {}".format(total, hidden)
        status = ""
        if self._status_message:
            status = "  |  " + self._status_message + "  [F8]"
        nav = ""
        if self._table_focused:
            nav = " | [F5] TABLE NAV"
        if constants.COMPACT_VIEW:
            nav += " | [F7] COMPACT"
        return [
            ("class:toolbar", " Filter: {} | Refresh: {}{}{}{}  ".format(
                filter_str, refresh_str, counts, status, nav)),
        ]

    def _parse_data_rows(self):
        """Identify line indices in display text that are data rows."""
        if not self._display_text:
            self._data_row_indices = []
            return
        lines = self._display_text.split("\n")
        indices = []
        # Strip ANSI to inspect content
        ansi_re = re.compile(r"\x1b\[[0-9;]*m")
        header_found = False
        past_header_sep = False
        in_data = False
        id_col_end = 6  # fallback
        for i, line in enumerate(lines):
            plain = ansi_re.sub("", line).strip()
            if not plain:
                continue
            is_separator = all(c in "─ " for c in plain)
            if not header_found and not is_separator:
                header_found = True
                # Derive ID column width from the header line.
                # The header has "id" (or "uuid") followed by spaces then
                # the next column name like "description".  Everything up
                # to that second column belongs to the ID column area.
                plain_raw = ansi_re.sub("", line)
                desc_pos = plain_raw.lower().find("desc")
                if desc_pos > 0:
                    id_col_end = desc_pos
                continue
            if header_found and not past_header_sep and is_separator:
                past_header_sep = True
                in_data = True
                continue
            if in_data:
                if is_separator:
                    # Closing separator — end of data rows
                    break
                # Only count lines that start a new task row (ID column has a digit).
                # Wrapped continuation lines have blank space in the ID column area.
                plain_raw = ansi_re.sub("", line)
                if any(c.isdigit() for c in plain_raw[:id_col_end]):
                    indices.append(i)
        self._data_row_indices = indices

    def _get_display_text(self):
        if not self._display_text:
            return [("", "Type 'view' to see your tasks, or any myt command.\n"
                        "Tab: autocomplete | Ctrl-R: refresh | Ctrl-Q: quit\n"
                        "F6: open pager for scrolling (j/k/arrows/search)")]
        if self._table_focused and self._data_row_indices:
            lines = self._display_text.split("\n")
            idx = self._data_row_indices[self._selected_row]
            if idx < len(lines):
                # Highlight with background color, re-applying after resets
                hl = "\x1b[48;5;238m"
                lines[idx] = hl + lines[idx].replace(
                    "\x1b[0m", "\x1b[0m" + hl) + "\x1b[49m"
            return ANSI("\n".join(lines))
        return ANSI(self._display_text)

    _NON_TABLE_FLAGS = frozenset({
        "--full", "--history", "--tags", "--groups",
        "--dates", "--notes", "--7day",
    })

    @property
    def _is_table_view(self):
        """True when the current view is the default table view."""
        return not any(f in self._NON_TABLE_FLAGS for f in self._filter_args)

    def _update_display(self, text):
        self._display_text = text
        self._last_refresh = datetime.now().strftime("%H:%M:%S")
        self._parse_data_rows()
        # Disable table nav and compact mode for non-table views
        if not self._is_table_view:
            self._table_focused = False
            if constants.COMPACT_VIEW:
                constants.COMPACT_VIEW = False
        # Clamp selected row to valid range
        if self._data_row_indices:
            self._selected_row = min(self._selected_row,
                                     len(self._data_row_indices) - 1)
        else:
            self._selected_row = 0
        if self._app:
            self._app.invalidate()

    def _get_terminal_width(self):
        """Get current terminal width."""
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 120

    def _refresh_view(self):
        """Re-run the view command with saved filters."""
        filter_str = " ".join(self._filter_args)
        cmd = "view {}".format(filter_str) if filter_str else "view"
        self._last_command = cmd
        width = self._get_terminal_width()
        code, output, _ = self._dispatcher.dispatch(cmd, width_override=width)
        self._update_display(output)

    async def _open_pager(self):
        """Open current display content in a pager (less).

        Re-renders the last command at full 200-col width for the pager.
        """
        if self._last_command:
            code, pager_text, _ = self._dispatcher.dispatch(
                self._last_command, width_override=200)
        elif self._display_text:
            pager_text = self._display_text
        else:
            return
        pager = os.environ.get("PAGER", "less")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                         delete=False) as f:
            f.write(pager_text)
            tmp_path = f.name
        try:
            await run_in_terminal(
                lambda: subprocess.call([pager, "-RS", "+g", tmp_path])
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _handle_command(self, buff):
        """Called when Enter is pressed in the input buffer."""
        text = buff.text.strip()
        if not text:
            return

        # Ignore input while a command is being dispatched in a thread
        if self._dispatching:
            return

        # Special exit commands
        if text in ("quit", "exit", "q"):
            self._app.exit()
            return

        # Special: clear
        if text == "clear":
            self._display_text = ""
            self._status_message = ""
            if self._app:
                self._app.invalidate()
            return

        cmd_name = text.split()[0] if text.split() else ""

        # Check if this command might need interactive prompts
        if cmd_name in MUTATION_COMMANDS:
            self._dispatch_in_thread(text, cmd_name)
        else:
            self._dispatch_sync(text, cmd_name)

    def _dispatch_sync(self, text, cmd_name):
        """Dispatch a command synchronously (no dialog support needed)."""
        width = self._get_terminal_width()
        code, output, is_mutation = self._dispatcher.dispatch(text, width_override=width)
        self._apply_result(text, cmd_name, output, is_mutation)

    def _dispatch_in_thread(self, text, cmd_name):
        """Dispatch a mutation command in a background thread.

        This allows the command to block on _tui_prompt_callback while the
        main event loop keeps rendering (and showing dialogs).
        """
        self._dispatching = True

        def _run():
            try:
                width = self._get_terminal_width()
                code, output, is_mutation = self._dispatcher.dispatch(
                    text, width_override=width)
            except Exception as e:
                code, output, is_mutation = 1, "Error: {}".format(e), False

            # Post the result back to the main loop
            def _finish():
                self._dispatching = False
                self._apply_result(text, cmd_name, output, is_mutation)
            self._app.loop.call_soon_threadsafe(_finish)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _apply_result(self, text, cmd_name, output, is_mutation):
        """Apply command results to the display."""
        if cmd_name == "view":
            parts = text.split()[1:]
            self._filter_args = parts
            self._last_command = text
            self._update_display(output)
            self._status_message = ""
        elif is_mutation:
            # Strip ANSI escapes — the toolbar renders plain text fragments
            # and would otherwise show raw color codes for styled messages.
            # Covers SGR and other CSI sequences (e.g. cursor moves) plus
            # OSC sequences (e.g. hyperlinks) that Rich may emit with
            # force_terminal=True.
            stripped = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
            stripped = re.sub(
                r"\x1b\].*?(?:\x07|\x1b\\)", "", stripped, flags=re.DOTALL)
            # Collapse any whitespace runs — Rich wraps long messages to
            # the console width so newlines and padding are common.
            stripped = " ".join(stripped.split())
            self._status_message = stripped
            self._completer.invalidate_cache()
            self._refresh_view()
        else:
            self._last_command = text
            self._update_display(output)

    def _tui_prompt_callback(self, message, choices, default):
        """Called from operations code (in a worker thread) when user input is needed.

        Shows a dialog in the TUI and blocks until the user responds.
        """
        self._prompt_event.clear()
        self._prompt_result = default

        # Schedule dialog creation on the main event loop
        def _show():
            self._show_dialog(message, choices, default)

        self._app.loop.call_soon_threadsafe(_show)

        # Block the worker thread until the user responds
        self._prompt_event.wait()
        return self._prompt_result

    def _get_dialog_text(self):
        """Build formatted text for the dialog overlay."""
        if not self._dialog_visible:
            return []
        fragments = []
        fragments.append(("class:dialog.border", "┌" + "─" * 58 + "┐\n"))
        # Message line(s) — word-wrap to fit inside the box
        msg = self._dialog_message
        max_w = 56
        while msg:
            line = msg[:max_w]
            msg = msg[max_w:]
            fragments.append(("class:dialog.border", "│ "))
            fragments.append(("class:dialog.text", "{:<56}".format(line)))
            fragments.append(("class:dialog.border", " │\n"))
        fragments.append(("class:dialog.border", "│" + " " * 58 + "│\n"))
        # Choices
        for i, choice in enumerate(self._dialog_choices):
            prefix = " ● " if i == self._dialog_selected else " ○ "
            style = "class:dialog.selected" if i == self._dialog_selected else "class:dialog.text"
            fragments.append(("class:dialog.border", "│ "))
            fragments.append((style, "{:<56}".format(prefix + choice)))
            fragments.append(("class:dialog.border", " │\n"))
        fragments.append(("class:dialog.border", "│" + " " * 58 + "│\n"))
        # Hint
        hint = "↑/↓: select  Enter: confirm  Esc: cancel"
        fragments.append(("class:dialog.border", "│ "))
        fragments.append(("class:dialog.hint", "{:<56}".format(hint)))
        fragments.append(("class:dialog.border", " │\n"))
        fragments.append(("class:dialog.border", "└" + "─" * 58 + "┘"))
        return fragments

    def _show_dialog(self, message, choices, default):
        """Show a choice dialog as a floating overlay."""
        self._dialog_message = message
        self._dialog_choices = choices
        self._dialog_default = default
        # Pre-select the default choice
        if default in choices:
            self._dialog_selected = choices.index(default)
        else:
            self._dialog_selected = 0

        dialog_window = Window(
            content=FormattedTextControl(self._get_dialog_text),
            dont_extend_width=True,
            dont_extend_height=True,
        )
        self._dialog_float = Float(content=dialog_window)
        self._dialog_visible = True
        self._float_container.floats.append(self._dialog_float)
        self._app.invalidate()

    def _dismiss_dialog(self):
        """Remove the dialog and unblock the waiting thread."""
        if self._dialog_float and self._dialog_float in self._float_container.floats:
            self._float_container.floats.remove(self._dialog_float)
        self._dialog_visible = False
        self._dialog_float = None
        self._app.invalidate()
        self._prompt_event.set()

    def _get_notification_text(self):
        """Build formatted text for the F8 notification popup."""
        if not self._notification_visible:
            return []
        msg = self._status_message or "(no message)"
        max_w = 74
        fragments = []
        fragments.append(("class:dialog.border", "┌" + "─" * (max_w + 2) + "┐\n"))
        # Word-wrap message into lines
        words = msg.split()
        lines = []
        current = ""
        for word in words:
            if current and len(current) + 1 + len(word) > max_w:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        if current:
            lines.append(current)
        for line in lines:
            fragments.append(("class:dialog.border", "│ "))
            fragments.append(("class:dialog.text", "{:<{}}".format(line, max_w)))
            fragments.append(("class:dialog.border", " │\n"))
        fragments.append(("class:dialog.border", "│" + " " * (max_w + 2) + "│\n"))
        hint = "Esc / F8: close"
        fragments.append(("class:dialog.border", "│ "))
        fragments.append(("class:dialog.hint", "{:<{}}".format(hint, max_w)))
        fragments.append(("class:dialog.border", " │\n"))
        fragments.append(("class:dialog.border", "└" + "─" * (max_w + 2) + "┘"))
        return fragments

    def _show_notification(self):
        """Show the last status message in a floating popup."""
        notification_window = Window(
            content=FormattedTextControl(self._get_notification_text),
            dont_extend_width=True,
            dont_extend_height=True,
        )
        self._notification_float = Float(content=notification_window)
        self._notification_visible = True
        self._float_container.floats.append(self._notification_float)
        self._app.invalidate()

    def _dismiss_notification(self):
        """Hide the notification popup."""
        if (self._notification_float and
                self._notification_float in self._float_container.floats):
            self._float_container.floats.remove(self._notification_float)
        self._notification_visible = False
        self._notification_float = None
        self._app.invalidate()

    def _build_layout(self):
        toolbar = Window(
            content=FormattedTextControl(self._get_toolbar_text),
            height=1,
            style="class:toolbar",
        )

        self._display_window = Window(
            content=FormattedTextControl(
                self._get_display_text,
                focusable=False,
            ),
            wrap_lines=True,
        )

        separator = Window(height=1, char="─", style="class:separator")

        search_toolbar = SearchToolbar()

        history_dir = os.path.dirname(HISTORY_FILE)
        Path(history_dir).mkdir(parents=True, exist_ok=True)

        input_buffer = Buffer(
            name="input",
            completer=self._completer,
            history=FileHistory(HISTORY_FILE),
            accept_handler=self._handle_command,
            multiline=False,
            complete_while_typing=True,
            read_only=Condition(lambda: self._table_focused or self._dialog_visible),
        )

        self._input_window = Window(
            content=BufferControl(
                buffer=input_buffer,
                search_buffer_control=search_toolbar.control,
            ),
            height=1,
        )

        prompt_label = Window(
            content=FormattedTextControl([("class:prompt", "myt> ")]),
            width=5,
            height=1,
        )

        input_row = VSplit([prompt_label, self._input_window])

        self._completions_float = Float(
            xcursor=True,
            ycursor=True,
            content=CompletionsMenu(max_height=12, scroll_offset=1),
        )

        self._float_container = FloatContainer(
            content=HSplit([
                toolbar,
                separator,
                self._display_window,
                separator,
                input_row,
                search_toolbar,
            ]),
            floats=[self._completions_float],
        )
        body = self._float_container

        return Layout(body, focused_element=self._input_window)

    def _build_keybindings(self):
        kb = KeyBindings()

        @kb.add("c-q")
        def exit_(event):
            event.app.exit()

        @kb.add("c-c")
        def exit_cc(event):
            event.app.exit()

        @kb.add("c-r")
        def refresh(event):
            self._refresh_view()

        @kb.add("escape", eager=True)
        def dismiss_completions(event):
            """Escape: close autocomplete menu, dismiss dialog/notification, or exit table nav."""
            if self._notification_visible:
                self._dismiss_notification()
                return
            if self._dialog_visible:
                # Leave _prompt_result as its default (set during callback init)
                self._dismiss_dialog()
                return
            if self._table_focused:
                self._table_focused = False
                event.app.invalidate()
                return
            buff = event.app.current_buffer
            if buff.complete_state:
                buff.cancel_completion()

        # -- Dialog keybindings --
        dialog_filter = Condition(lambda: self._dialog_visible)

        @kb.add("up", filter=dialog_filter, eager=True)
        @kb.add("k", filter=dialog_filter, eager=True)
        def dialog_up(event):
            if self._dialog_selected > 0:
                self._dialog_selected -= 1
                event.app.invalidate()

        @kb.add("down", filter=dialog_filter, eager=True)
        @kb.add("j", filter=dialog_filter, eager=True)
        def dialog_down(event):
            if self._dialog_selected < len(self._dialog_choices) - 1:
                self._dialog_selected += 1
                event.app.invalidate()

        @kb.add("enter", filter=dialog_filter, eager=True)
        def dialog_accept(event):
            self._prompt_result = self._dialog_choices[self._dialog_selected]
            self._dismiss_dialog()

        # -- Table navigation keybindings --
        @kb.add("f5", filter=Condition(lambda: self._is_table_view))
        def toggle_table_focus(event):
            """F5: toggle table row navigation."""
            self._table_focused = not self._table_focused
            if self._table_focused and self._data_row_indices:
                self._selected_row = min(self._selected_row,
                                         len(self._data_row_indices) - 1)
            event.app.invalidate()

        @kb.add("up", filter=Condition(lambda: self._table_focused
                                       and not self._dialog_visible))
        @kb.add("k", filter=Condition(lambda: self._table_focused
                                      and not self._dialog_visible))
        def nav_up(event):
            if self._selected_row > 0:
                self._selected_row -= 1
                event.app.invalidate()

        @kb.add("down", filter=Condition(lambda: self._table_focused
                                         and not self._dialog_visible))
        @kb.add("j", filter=Condition(lambda: self._table_focused
                                      and not self._dialog_visible))
        def nav_down(event):
            if (self._data_row_indices and
                    self._selected_row < len(self._data_row_indices) - 1):
                self._selected_row += 1
                event.app.invalidate()

        @kb.add("f6")
        async def open_pager(event):
            """F6: open current display in pager for scrolling."""
            await self._open_pager()

        @kb.add("f7", filter=Condition(lambda: bool(self._display_text)
                                       and self._is_table_view))
        def toggle_concise_view(event):
            """F7: toggle compact view (hide end/duration/hide/version/age/date/score)."""
            constants.COMPACT_VIEW = not constants.COMPACT_VIEW
            self._refresh_view()

        @kb.add("f8", filter=Condition(lambda: bool(self._status_message)))
        def toggle_notification(event):
            """F8: show/hide last status message in a popup."""
            if self._notification_visible:
                self._dismiss_notification()
            else:
                self._show_notification()

        return kb

    def _build_style(self):
        from prompt_toolkit.styles import Style
        return Style.from_dict({
            "toolbar": "bg:#333333 #ffffff",
            "toolbar.key": "bg:#555555 #ffffff bold",
            "separator": "#666666",
            "prompt": "bold #00aa00",
            "dialog.border": "bg:#1a1a2e #666666",
            "dialog.text": "bg:#1a1a2e #ffffff",
            "dialog.selected": "bg:#1a1a2e bold #00aa00",
            "dialog.hint": "bg:#1a1a2e #888888 italic",
        })

    def run(self):
        """Launch the TUI application."""
        ret = connect_to_tasksdb()
        if ret != SUCCESS:
            print("Failed to connect to tasks database.")
            return

        from src.mytcli.myt import myt as myt_group
        self._dispatcher = TUIDispatcher(myt_group)

        # Register the prompt callback so operations can show dialogs
        constants.TUI_PROMPT_CALLBACK = self._tui_prompt_callback

        layout = self._build_layout()
        kb = self._build_keybindings()
        style = self._build_style()

        self._app = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=True,
            mouse_support=False,
            after_render=self._auto_refresh_once,
        )

        self._refresh_view()
        try:
            self._app.run()
        finally:
            constants.TUI_PROMPT_CALLBACK = None

    def _auto_refresh_once(self, app):
        """Set up auto-refresh after first render (called once)."""
        if hasattr(self, "_refresh_task_started"):
            return
        self._refresh_task_started = True

        import asyncio

        async def _refresh_loop():
            while True:
                await asyncio.sleep(REFRESH_INTERVAL)
                if self._last_command:
                    width = self._get_terminal_width()
                    code, output, _ = self._dispatcher.dispatch(
                        self._last_command, width_override=width)
                    self._update_display(output)

        asyncio.ensure_future(_refresh_loop())
