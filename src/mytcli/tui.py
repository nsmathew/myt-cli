"""Interactive TUI for myt-cli using prompt_toolkit."""

import os
import time
from datetime import datetime
from pathlib import Path

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import (
    HSplit, VSplit, Window, FloatContainer, Float,
)
from prompt_toolkit.layout import ScrollablePane
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
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
        self._last_refresh = None
        self._status_message = ""
        self._completer = MytCompleter()
        self._dispatcher = None
        self._app = None
        self._display_window = None
        self._input_window = None

    def _get_toolbar_text(self):
        filter_str = " ".join(self._filter_args) if self._filter_args else "(none)"
        refresh_str = self._last_refresh or "--:--:--"
        status = ""
        if self._status_message:
            status = "  |  " + self._status_message
        # Show focus hint
        focused = self._app and self._app.layout.has_focus(self._display_window)
        focus_hint = "[SCROLL MODE - F6 to return to input]" if focused else ""
        return [
            ("class:toolbar", " Filter: {} | Last refresh: {}  {} ".format(
                filter_str, refresh_str, focus_hint)),
        ]

    def _get_display_text(self):
        if not self._display_text:
            return [("", "Type 'view' to see your tasks, or any myt command.\n"
                        "Tab: autocomplete | Ctrl-R: refresh | Ctrl-Q: quit\n"
                        "F6: toggle scroll mode")]
        return ANSI(self._display_text)

    def _update_display(self, text):
        self._display_text = text
        self._last_refresh = datetime.now().strftime("%H:%M:%S")
        if self._app:
            self._app.invalidate()

    def _refresh_view(self):
        """Re-run the view command with saved filters."""
        filter_str = " ".join(self._filter_args)
        cmd = "view {}".format(filter_str) if filter_str else "view"
        code, output, _ = self._dispatcher.dispatch(cmd)
        self._update_display(output)

    def _handle_command(self, buff):
        """Called when Enter is pressed in the input buffer."""
        text = buff.text.strip()
        if not text:
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

        code, output, is_mutation = self._dispatcher.dispatch(text)

        if cmd_name == "view":
            # Update display with view output and save filters
            parts = text.split()[1:]  # everything after "view"
            self._filter_args = parts
            self._update_display(output)
            self._status_message = ""
        elif is_mutation:
            # Show mutation output briefly then refresh view
            self._status_message = output.strip().replace("\n", " ")[:80] if output.strip() else ""
            self._completer.invalidate_cache()
            self._refresh_view()
        else:
            # Non-view, non-mutation: just show output
            self._update_display(output)

    def _build_layout(self):
        # Toolbar at top
        toolbar = Window(
            content=FormattedTextControl(self._get_toolbar_text),
            height=1,
            style="class:toolbar",
        )

        # Main display area — wrapped in ScrollablePane for scrolling
        display_content = Window(
            content=FormattedTextControl(
                self._get_display_text,
                focusable=True,
            ),
            wrap_lines=True,
        )
        self._display_window = display_content

        display_area = ScrollablePane(
            content=display_content,
        )

        # Separator
        separator = Window(height=1, char="─", style="class:separator")

        # Input area
        search_toolbar = SearchToolbar()

        # Ensure history directory exists
        history_dir = os.path.dirname(HISTORY_FILE)
        Path(history_dir).mkdir(parents=True, exist_ok=True)

        input_buffer = Buffer(
            name="input",
            completer=self._completer,
            history=FileHistory(HISTORY_FILE),
            accept_handler=self._handle_command,
            multiline=False,
            complete_while_typing=True,
        )

        self._input_window = Window(
            content=BufferControl(
                buffer=input_buffer,
                search_buffer_control=search_toolbar.control,
            ),
            height=1,
        )

        # Prompt label
        prompt_label = Window(
            content=FormattedTextControl([("class:prompt", "myt> ")]),
            width=5,
            height=1,
        )

        input_row = VSplit([prompt_label, self._input_window])

        body = FloatContainer(
            content=HSplit([
                toolbar,
                separator,
                display_area,
                separator,
                input_row,
                search_toolbar,
            ]),
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=12, scroll_offset=1),
                ),
            ],
        )

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
            """Escape: close autocomplete menu if open."""
            buff = event.app.current_buffer
            if buff.complete_state:
                buff.cancel_completion()

        @kb.add("f6")
        def toggle_focus(event):
            """F6: toggle focus between display and input."""
            layout = event.app.layout
            if layout.has_focus(self._display_window):
                layout.focus(self._input_window)
            else:
                layout.focus(self._display_window)

        return kb

    def _build_style(self):
        from prompt_toolkit.styles import Style
        return Style.from_dict({
            "toolbar": "bg:#333333 #ffffff",
            "separator": "#666666",
            "prompt": "bold #00aa00",
        })

    def run(self):
        """Launch the TUI application."""
        # Initialize DB connection
        ret = connect_to_tasksdb()
        if ret != SUCCESS:
            print("Failed to connect to tasks database.")
            return

        # Import the myt group for dispatching
        from src.mytcli.myt import myt as myt_group
        self._dispatcher = TUIDispatcher(myt_group)

        layout = self._build_layout()
        kb = self._build_keybindings()
        style = self._build_style()

        self._app = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=True,
            mouse_support=True,
            after_render=self._auto_refresh_once,
        )

        # Run initial view
        self._refresh_view()

        self._app.run()

    def _auto_refresh_once(self, app):
        """Set up auto-refresh after first render (called once)."""
        if hasattr(self, "_refresh_task_started"):
            return
        self._refresh_task_started = True

        import asyncio

        async def _refresh_loop():
            while True:
                await asyncio.sleep(REFRESH_INTERVAL)
                if self._display_text:
                    self._refresh_view()

        asyncio.ensure_future(_refresh_loop())
