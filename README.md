# myt-cli

My Tasks - A personal task manager

[![GitHub Release](https://img.shields.io/github/v/release/nsmathew/myt-cli)](https://github.com/nsmathew/myt-cli/releases/latest)
[![GitHub License](https://img.shields.io/github/license/nsmathew/myt-cli)](https://raw.githubusercontent.com/nsmathew/myt-cli/master/LICENSE)
![App Type](https://img.shields.io/badge/app_type-cli-blue)
[![PyPI - Status](https://img.shields.io/pypi/status/myt-cli)](https://pypi.org/project/myt-cli/)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fnsmathew%2Fmyt-cli%2Fmaster%2Fpyproject.toml)
![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/nsmathew/myt-cli)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

### What is it

A simple command line task manager written in python. It is inspired from taskwarrior but with no where near as much functionality.

It can be used in two ways. As a one-shot command line app where you run individual commands directly from your shell. Or as an interactive TUI by running `myt` with no subcommand, which launches a persistent full-screen session with a command input, autocomplete, and auto-refresh.

### What can it do

You can add tasks with descriptions, due dates and notes. You can group tasks together, add tags to them and classify them with a context such as `@phone` or `@home`. Tasks can be modified. Tasks can also be set to indicate they are currently being worked on. There is functionality to set recurring tasks.

You can also run myt as an interactive TUI with IDE-style autocomplete, command history, filter persistence, and interactive prompts for recurring task operations.

### Screenshots

1. The default view in TUI mode
   ![TaskView](https://github.com/nsmathew/myt-cli/blob/master/images/TaskView.png?raw=true)
   &nbsp;
2. A 7 day view of tasks - `view --7day`
   ![TaskView7Day](https://github.com/nsmathew/myt-cli/blob/master/images/TaskView7Day.png?raw=true)
   &nbsp;
3. Basic statistics - `stats`
   ![TaskStats](https://github.com/nsmathew/myt-cli/blob/master/images/TaskStats.png?raw=true)

### Interactive TUI Mode

Run `myt` with no subcommand to enter the interactive TUI. All the same commands available in one-shot CLI mode work here, typed at the `myt>` prompt at the bottom of the screen. The toolbar at the top shows the active filter, last refresh time and task counts.

**Shorthand syntax**

In TUI mode, common flags can be replaced with single-character prefixes for faster input. Quoted text without a prefix becomes the task description. Standard flags like `-gr` and `-tg` also continue to work.

| Shorthand | Flag | Field |
|-----------|------|-------|
| `+value` | `-gr` | Group |
| `@value` | `-cx` | Context |
| `#value` | `-tg` | Tag |
| `^value` | `-du` | Due date |
| `!value` | `-pr` | Priority |
| `~value` | `-hi` | Hide until |
| `"text"` | `-de` | Description |

**Keyboard shortcuts**

| Key | Action |
|-----|--------|
| `F5` | Toggle row highlight/navigation mode. Use Up/Down or `j`/`k` to move between tasks |
| `F6` | Open current view in a pager for scrolling with full colour support |
| `F7` | Toggle compact mode which hides non-essential columns such as duration, version, age and score |

The TUI auto-refreshes every 60 seconds, re-running the last command. Interactive dialog overlays are shown for recurring task prompts and confirmations.

### Examples

**One-shot CLI mode**

1. Add a simple task
   `myt add -de "Buy gifts" -du 2026-06-25 -gr PERS.SHOPPING -tg birthday,occasions -cx home`
   &nbsp;
2. Add a recurring task
   `myt add -de "Pay the rent" -re M -du 2026-06-25 -hi -5 -gr PERS.FINANCES -tg bills`
   This task is scheduled for the 25th of every month. Using the 'hide' option the task will be hidden until 5 days from the due date for every occurrence in the tasks default view
   &nbsp;
3. Add a recurring task with an end date
   `myt add -de "Project weekly catch ups" -re WD1,2,5 -du +0 -en +30 -gr WORK.PROJECTS`
   This adds a recurring task for every Monday, Tuesday and Friday and ending in 30 days from today

**TUI mode with shorthand**

1. Add a task using shorthand
   `add "Buy gifts" ^2026-06-25 +PERS.SHOPPING #birthday #occasions @home`
   &nbsp;
2. View tasks filtered by context
   `view cx:phone`
   &nbsp;
3. Modify a task using shorthand
   `modify id:3 !H ~-3`
   Sets task 3 to High priority and hides it until 3 days before its due date

Other functionality in the app can be explored using the app's help

### Installation

Install using pip: `pip install myt-cli`

### Development Setup

```bash
git clone https://github.com/nsmathew/myt-cli.git
cd myt-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run tests: `pytest tests/`

Run security scan: `bandit --recursive --severity-level all src/`

### Technology

- Python 3
- Sqlite3
- Rich
- prompt_toolkit

### Links

- Github - <https://github.com/nsmathew/myt-cli>
- PyPi - <https://pypi.org/project/myt-cli>

### Contact

Nitin Mathew, <nitn_mathew2000@hotmail.com>
