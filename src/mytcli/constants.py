import os
import logging
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.theme import Theme

#Global - START
DB_SCHEMA_VER = 0.1
# SQL Connection Related
DEFAULT_FOLDER = os.path.join(str(Path.home()), "myt-cli")
DEFAULT_DB_NAME = "tasksdb.sqlite3"
# Return Statuses
SUCCESS = 0
FAILURE = 1
# Task Search Modifiers
TASK_OVERDUE = "OVERDUE"
TASK_TODAY = "TODAY"
TASK_TOMMR = "TOMORROW"
TASK_HIDDEN = "HIDDEN"
TASK_BIN = "BIN"
TASK_COMPLETE = "COMPLETE"
TASK_STARTED = "STARTED"
TASK_NOW = "NOW"
# For Search, when no filters are provided or only area filters provided
TASK_ALL = "ALL"
# For Search, when no task property filters are provided
HL_FILTERS_ONLY = "HL_FILTERS_ONLY"
# To print the number of tasks shown in the filtered view
PRNT_CURR_VW_CNT = "CURR_VIEW_CNT"
# To print task details after an operation
PRNT_TASK_DTLS = "TASK_DETAILS"
# Clear string
CLR_STR = "clr"
"""
Domain Values for the application
"""
# Task Status Domain
TASK_STATUS_TODO = "TO_DO"
TASK_STATUS_STARTED = "STARTED"
TASK_STATUS_DONE = "DONE"
TASK_STATUS_DELETED = "DELETED"
# Task Area Domain
WS_AREA_PENDING = "pending"
WS_AREA_COMPLETED = "completed"
WS_AREA_BIN = "bin"
# Task Priority Domain
PRIORITY_HIGH = ["H", "High", "HIGH", "h"]
PRIORITY_MEDIUM = ["M", "Medium", "MEDIUM", "m"]
PRIORITY_LOW = ["L", "Low", "LOW", "l"]
PRIORITY_NORMAL = ["N", "Normal", "NORMAL", "n"]
# Task Type Domain
TASK_TYPE_BASE = "BASE"
TASK_TYPE_DRVD = "DERIVED"
TASK_TYPE_NRML = "NORMAL"
# Recurring Task's Domain for MODE
MODE_DAILY = "D"
MODE_WEEKLY = "W"
MODE_YEARLY = "Y"
MODE_MONTHLY = "M"
MODE_WKDAY = "WD"
MODE_MTHDYS = "MD"
MODE_MONTHS = "MO"
# Recurring Task' domain for WHEN(range function's stop param is exclusive)
WHEN_WEEKDAYS = list(range(1, 8))
WHEN_MONTHDAYS = list(range(1, 32))
WHEN_MONTHS = list(range(1, 13))
"""
Domain Values End
"""
# Logger Config
lFormat = ("-------------|%(levelname)s|%(filename)s|%(lineno)d|%(funcName)s "
           "- %(message)s")
logging.basicConfig(format=lFormat, level=logging.ERROR)
LOGGER = logging.getLogger()
# Rich Formatting Config
# Styles
myt_theme = Theme({
    "repr.none": "italic",
    "default": "white",
    "today": "dark_orange",
    "overdue": "red",
    "started": "green",
    "done": "grey46",
    "binn": "grey46",
    "now": "magenta",
    "info": "yellow",
    "header": "bold black on white",
    "subheader": "bold black"
}, inherit=False)
CONSOLE = Console(theme=myt_theme, )
# Printable attributes
PRINT_ATTR = ["description", "priority", "due", "hide", "groups", "tags",
              "status", "now_flag", "recur_mode", "recur_when", "uuid",
              "task_type", "area"]
# Modes
VALID_MODES = [MODE_DAILY, MODE_WEEKLY, MODE_WKDAY, MODE_MONTHLY,
               MODE_MTHDYS, MODE_MONTHS, MODE_YEARLY]

# Until When config - Aligned to Recurring Task Mode Domains
UNTIL_WHEN = {MODE_DAILY: 2, MODE_WEEKLY: 8, MODE_MONTHLY: 32,
              MODE_YEARLY: 367, MODE_WKDAY: 2, MODE_MTHDYS: 5, MODE_MONTHS: 90}
# Future date for date and None comparisons
FUTDT = datetime.strptime("2300-01-01", "%Y-%m-%d").date()
# Indictor Symbols
INDC_PR_HIGH = "[H]"
INDC_PR_MED = "[M]"
INDC_PR_NRML = ""
INDC_PR_LOW = "[L]"
INDC_NOW = "[++]"
INDC_NOTES = "[^]"
INDC_RECUR = "[~]"
# Date formats
FMT_DATEONLY = "%Y-%m-%d"
FMT_DATETIME = "%Y-%m-%d %H:%M:%S"
FMT_EVENTID = "%Y%m%d%H%M%S%f"
FMT_DAY_DATEW = "%a %d%b%y"
FMT_DATEW_TIME = "%d%b%y %H%M"
#Operations
OPS_ADD = "add"
OPS_MODIFY = "modify"
OPS_START = "start"
OPS_STOP = "stop"
OPS_REVERT = "revert"
OPS_RESET = "reset"
OPS_DELETE = "delete"
OPS_NOW = "now"
OPS_UNLINK = "unlink"
OPS_DONE = "done"
# Changelog URL
CHANGELOG = "https://github.com/nsmathew/myt-cli/blob/master/CHANGELOG.txt"
