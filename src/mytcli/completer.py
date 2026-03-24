"""Custom prompt_toolkit Completer for the myt TUI."""

import shlex

from prompt_toolkit.completion import Completer, Completion

from src.mytcli.constants import LOGGER


# Command definitions: command_name -> list of flags
COMMAND_FLAGS = {
    "add": ["-de", "-pr", "-du", "-hi", "-gr", "-tg", "-re", "-en", "-no",
            "--desc", "--priority", "--due", "--hide", "--group", "--tag",
            "--recur", "--end", "--notes"],
    "modify": ["-de", "-pr", "-du", "-hi", "-gr", "-tg", "-re", "-en", "-no",
               "--desc", "--priority", "--due", "--hide", "--group", "--tag",
               "--recur", "--end", "--notes"],
    "view": ["-p", "-t", "--pager", "--top", "--default", "--full",
             "--history", "--tags", "--groups", "--dates", "--notes", "--7day"],
    "done": [],
    "start": [],
    "stop": [],
    "revert": [],
    "reset": [],
    "now": [],
    "delete": [],
    "undo": [],
    "urlopen": ["-ur", "--urlno"],
    "admin": ["--empty", "--reinit", "--tags", "--groups"],
    "stats": [],
    "version": [],
}

# Flags that accept priority values
PRIORITY_FLAGS = {"-pr", "--priority"}
PRIORITY_VALUES = ["H", "M", "L", "N"]

# Flags that accept date-like values
DATE_FLAGS = {"-du", "--due", "-hi", "--hide", "-en", "--end"}
DATE_HINTS = ["+0", "+1", "+2", "+7", "+14", "+30", "today", "tomorrow"]

# Filter prefixes for view/modify and commands with filter arguments
FILTER_PREFIXES = ["id:", "gr:", "tg:", "pr:", "de:", "du:", "no:", "uuid:"]
HIGH_LEVEL_FILTERS = [
    "overdue", "today", "tomorrow", "hidden", "complete", "bin",
    "started", "now",
]

# Commands that accept filter arguments (positional)
FILTER_COMMANDS = {"view", "modify", "done", "start", "stop", "revert",
                   "reset", "now", "delete", "urlopen"}


class MytCompleter(Completer):
    """IDE-style autocomplete for the myt TUI.

    Levels:
    1. Command names
    2. Flags per command
    3. Values per flag (priorities, dates, groups, tags)
    4. Filter completions (id:, gr:, etc.)
    5. Filter values (after gr: -> groups, after tg: -> tags)
    """

    def __init__(self):
        self._groups_cache = None
        self._tags_cache = None
        self._ids_cache = None

    def invalidate_cache(self):
        self._groups_cache = None
        self._tags_cache = None
        self._ids_cache = None

    def _get_groups(self):
        if self._groups_cache is None:
            try:
                from src.mytcli.queries import get_all_groups
                self._groups_cache = get_all_groups()
            except Exception:
                self._groups_cache = []
        return self._groups_cache

    def _get_tags(self):
        if self._tags_cache is None:
            try:
                from src.mytcli.queries import get_all_tags
                self._tags_cache = get_all_tags()
            except Exception:
                self._tags_cache = []
        return self._tags_cache

    def _get_ids(self):
        if self._ids_cache is None:
            try:
                from src.mytcli.queries import get_all_ids
                self._ids_cache = get_all_ids()
            except Exception:
                self._ids_cache = []
        return self._ids_cache

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        word = document.get_word_before_cursor(WORD=True)

        try:
            parts = shlex.split(text)
        except ValueError:
            parts = text.split()

        # If cursor is right after a space, we're starting a new token
        if text and text[-1] == " ":
            parts.append("")

        if not parts or (len(parts) == 1 and not text.endswith(" ")):
            # Level 1: command name completion
            prefix = parts[0] if parts else ""
            commands = list(COMMAND_FLAGS.keys()) + ["quit", "exit", "q"]
            for cmd in commands:
                if cmd.startswith(prefix):
                    yield Completion(cmd, start_position=-len(prefix))
            return

        cmd_name = parts[0]
        if cmd_name not in COMMAND_FLAGS:
            return

        current = parts[-1] if parts else ""
        prev = parts[-2] if len(parts) >= 2 else ""

        # Level 3: value completion for known flags
        if prev in PRIORITY_FLAGS:
            for v in PRIORITY_VALUES:
                if v.startswith(current.upper()) or not current:
                    yield Completion(v, start_position=-len(current))
            return

        if prev in DATE_FLAGS:
            for v in DATE_HINTS:
                if v.startswith(current):
                    yield Completion(v, start_position=-len(current))
            return

        if prev in {"-gr", "--group"}:
            for g in self._get_groups():
                if g.lower().startswith(current.lower()):
                    yield Completion(g, start_position=-len(current))
            return

        if prev in {"-tg", "--tag"}:
            for t in self._get_tags():
                if t.lower().startswith(current.lower()):
                    yield Completion(t, start_position=-len(current))
            return

        # Level 5: filter value completion (e.g., after typing "gr:")
        if cmd_name in FILTER_COMMANDS and ":" in current:
            prefix_part, _, val_part = current.partition(":")
            filter_key = prefix_part + ":"
            if filter_key == "gr:":
                for g in self._get_groups():
                    if g.lower().startswith(val_part.lower()):
                        yield Completion(filter_key + g,
                                         start_position=-len(current))
                return
            elif filter_key == "tg:":
                for t in self._get_tags():
                    if t.lower().startswith(val_part.lower()):
                        yield Completion(filter_key + t,
                                         start_position=-len(current))
                return
            elif filter_key == "id:":
                for i in self._get_ids():
                    if i.startswith(val_part):
                        yield Completion(filter_key + i,
                                         start_position=-len(current))
                return
            elif filter_key == "pr:":
                for v in PRIORITY_VALUES:
                    if v.startswith(val_part.upper()) or not val_part:
                        yield Completion(filter_key + v,
                                         start_position=-len(current))
                return

        # Level 2: flag completion
        if current.startswith("-"):
            flags = COMMAND_FLAGS.get(cmd_name, [])
            for flag in flags:
                if flag.startswith(current):
                    yield Completion(flag, start_position=-len(current))
            return

        # Level 4: filter prefix/high-level filter completion
        if cmd_name in FILTER_COMMANDS:
            for fp in FILTER_PREFIXES:
                if fp.startswith(current):
                    yield Completion(fp, start_position=-len(current))
            for hlf in HIGH_LEVEL_FILTERS:
                if hlf.startswith(current):
                    yield Completion(hlf, start_position=-len(current))
