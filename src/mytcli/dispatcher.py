"""Command dispatcher for the myt TUI.

Parses input strings, invokes Click commands, and captures output.
"""

import sys
import shlex
from io import StringIO

import click

import src.mytcli.constants as constants
from src.mytcli.constants import LOGGER
from src.mytcli.shorthand import expand_shorthand

# Commands that mutate data and should trigger a view refresh
MUTATION_COMMANDS = {
    "add", "modify", "delete", "done", "start", "stop",
    "revert", "reset", "now", "undo",
}

# Commands that show interactive prompts and must run in a background thread
# so they don't deadlock the TUI event loop via _tui_prompt_callback.
PROMPT_COMMANDS = {"urlopen"}


class TUIDispatcher:
    """Dispatches raw input to the myt Click commands, capturing output."""

    def __init__(self, myt_group, terminal_width=None):
        self._myt = myt_group
        self._width = terminal_width or 200

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value or 200

    def dispatch(self, input_text: str, width_override=None) -> tuple:
        """Dispatch a command string.

        Args:
            input_text: The command string to dispatch.
            width_override: Optional width to use instead of the default.

        Returns:
            (exit_code, output_text, is_mutation)
        """
        input_text = input_text.strip()
        if not input_text:
            return (0, "", False)

        # Expand shorthand syntax (e.g., +Group, @context, #tag)
        input_text = expand_shorthand(input_text)
        LOGGER.debug("Expanded input: %s", input_text)

        try:
            args = shlex.split(input_text)
        except ValueError as e:
            return (1, "Parse error: {}".format(str(e)), False)

        cmd_name = args[0]
        cmd_args = args[1:]

        is_mutation = cmd_name in MUTATION_COMMANDS

        cmd = self._myt.commands.get(cmd_name)
        if cmd is None:
            return (1, "Unknown command: '{}'. Available: {}".format(
                cmd_name, ", ".join(sorted(self._myt.commands.keys()))
            ), False)

        buf = StringIO()
        render_width = width_override if width_override is not None else self._width
        constants.CONSOLE.set_target(buf, width=render_width)
        # Redirect stdout to capture Click output (--help, click.echo, etc.)
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            parent_ctx = click.Context(self._myt, info_name="myt")
            ctx = click.Context(cmd, parent=parent_ctx, info_name=cmd_name)
            with parent_ctx:
                with ctx:
                    cmd.parse_args(ctx, list(cmd_args))
                    ctx.invoke(cmd, **ctx.params)
            return (0, buf.getvalue(), is_mutation)
        except SystemExit as e:
            return (e.code or 0, buf.getvalue(), is_mutation)
        except click.exceptions.Exit as e:
            return (e.exit_code or 0, buf.getvalue(), False)
        except click.UsageError as e:
            return (1, buf.getvalue() + "\nUsage error: " + str(e), False)
        except click.Abort:
            return (1, buf.getvalue() + "\nAborted.", False)
        except Exception as e:
            LOGGER.error("Dispatch error: %s", e, exc_info=True)
            return (1, buf.getvalue() + "\nError: " + str(e), False)
        finally:
            sys.stdout = old_stdout
            constants.CONSOLE.reset()
