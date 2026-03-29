"""Shorthand syntax preprocessor for the myt TUI.

Expands shorthand tokens into Click-compatible flag+value pairs.
Only used in TUI mode — the CLI remains unchanged.

Shorthand map:
    +value   ->  -gr value    (group)
    @value   ->  -cx value    (context)
    #value   ->  -tg value    (tag)
    ^value   ->  -du value    (due date)
    !value   ->  -pr value    (priority: H, M, L, N)
    ~value   ->  -hi value    (hide until)
    "text"   ->  -de "text"   (description, for add/modify)

Filters (key:value) are passed through unchanged.
Standard flags (-de, --group, etc.) are also passed through unchanged.
"""

import shlex

from src.mytcli.constants import LOGGER

# Shorthand prefix -> Click flag
SHORTHAND_MAP = {
    "+": "-gr",
    "@": "-cx",
    "#": "-tg",
    "^": "-du",
    "!": "-pr",
    "~": "-hi",
}

# Flags that consume the next token as their value (not shorthand-expanded)
VALUE_FLAGS = {
    "-de", "--desc", "-pr", "--priority", "-du", "--due",
    "-hi", "--hide", "-gr", "--group", "-cx", "--context",
    "-tg", "--tag", "-re", "--recur", "-en", "--end",
    "-no", "--notes", "-ur", "--urlno", "-t", "--top", "-db",
}

# Commands that accept shorthand setters
SETTER_COMMANDS = {"add", "modify"}


def expand_shorthand(input_text):
    """Expand shorthand tokens in a TUI input string.

    Args:
        input_text: Raw input string from the TUI command line.

    Returns:
        Expanded string with shorthand replaced by Click flags.
        Non-setter commands are returned unchanged.
    """
    input_text = input_text.strip()
    if not input_text:
        return input_text

    try:
        tokens = shlex.split(input_text)
    except ValueError:
        return input_text

    if not tokens:
        return input_text

    cmd_name = tokens[0]
    if cmd_name not in SETTER_COMMANDS:
        return input_text

    expanded = [cmd_name]
    i = 1
    while i < len(tokens):
        token = tokens[i]

        # Check if this token is a quoted description (was quoted in original)
        # We detect this by checking if the original input had this token quoted
        # Standard flags pass through unchanged; value-taking flags also
        # consume the next token as their value to prevent shorthand expansion
        # of things like `-du +1` where `+1` is a date, not a group.
        if token.startswith("-"):
            expanded.append(token)
            i += 1
            if token in VALUE_FLAGS and i < len(tokens):
                expanded.append(tokens[i])
                i += 1
            continue

        # Filter tokens (key:value) pass through unchanged
        if ":" in token and not token.startswith(":"):
            expanded.append(token)
            i += 1
            continue

        # Check for shorthand prefixes
        prefix = token[0] if token else ""
        if prefix in SHORTHAND_MAP and len(token) > 1:
            flag = SHORTHAND_MAP[prefix]
            value = token[1:]
            expanded.append(flag)
            expanded.append(value)
            i += 1
            continue

        # Bare quoted strings become the description
        # Check if this token was quoted in the original input by looking
        # for it in the raw text
        if _was_quoted(input_text, token, tokens, i):
            expanded.append("-de")
            expanded.append(token)
            i += 1
            continue

        # Unrecognized token — pass through as-is (could be a filter
        # keyword like "overdue", "today", etc.)
        expanded.append(token)
        i += 1

    return _rebuild_command(expanded)


def _was_quoted(raw_input, token, tokens, token_index):
    """Check if a token was quoted in the original input string.

    Scans the raw input to find whether the token at the given index
    appeared inside quotes (single or double).
    """
    # Walk through the raw input character by character to find each token
    pos = 0
    # Skip past the command name
    current_token_idx = 0
    in_quote = None

    while pos < len(raw_input) and current_token_idx < token_index:
        ch = raw_input[pos]
        if in_quote:
            if ch == in_quote:
                in_quote = None
            pos += 1
            continue
        if ch in ('"', "'"):
            in_quote = ch
            pos += 1
            continue
        if ch == ' ':
            # Skip whitespace between tokens
            while pos < len(raw_input) and raw_input[pos] == ' ':
                pos += 1
            current_token_idx += 1
            continue
        pos += 1

    # Now pos should be at the start of our target token
    if pos < len(raw_input) and raw_input[pos] in ('"', "'"):
        return True
    return False


def _rebuild_command(tokens):
    """Rebuild a command string from tokens, quoting values that need it."""
    parts = []
    for token in tokens:
        if token is None:
            continue
        if ' ' in token or '"' in token or "'" in token:
            # Quote the token
            escaped = token.replace('"', '\\"')
            parts.append('"{}"'.format(escaped))
        else:
            parts.append(token)
    return " ".join(parts)
