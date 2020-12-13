try:
    from importlib import metadata
except ImportError:
    # Running on pre-3.8 Python; use importlib-metadata package
    import importlib_metadata as metadata
import re
import os
import uuid
import sys
from pathlib import Path
import logging
import calendar

import click
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from dateutil.rrule import *
from rich.console import Console
from rich.table import Column, Table as RichTable, box
from rich.style import Style
from rich.theme import Theme
from rich.prompt import Prompt
from rich.columns import Columns
from sqlalchemy import (create_engine, Column, Integer, String, Table, Index,
                        ForeignKeyConstraint, tuple_, and_, case, func, 
                        BOOLEAN, distinct, cast, Date, inspect, or_)
from sqlalchemy.orm import relationship, sessionmaker, make_transient
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import literal_column

#Global - START
DB_SCHEMA_VER = 0.1
# SQL Connection Related
DEFAULT_FOLDER = os.path.join(str(Path.home()), "myt-cli")
DEFAULT_DB_NAME = "tasksdb.sqlite3"
ENGINE = None
SESSION = None
Session = None
# Return Statuses
SUCCESS = 0
FAILURE = 1
# Task Search Modifiers
TASK_OVERDUE = "OVERDUE"
TASK_TODAY = "TODAY"
TASK_TOMMR = "TOMORROW"
TASK_HIDDEN = "HIDDEN"
TASK_BIN = "BIN"
TASK_DONE = "DONE"
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
MODE_WKDAY = "WD"
MODE_FRTNGHT = "F"
MODE_MONTHLY = "M"
MODE_MTHDYS = "MD"
MODE_MONTHS = "MO"
MODE_QRTR = "Q"
MODE_SEMIANL = "S"
MODE_ANNUAL = "A"
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
    "header": "bold black on white"
}, inherit=False)
CONSOLE = Console(theme=myt_theme, )
# Printable attributes
PRINT_ATTR = ["description", "priority", "due", "hide", "groups", "tags", 
              "status", "now_flag", "recur_mode", "recur_when", "uuid", 
              "task_type", "area"]
# Modes
VALID_MODES = [MODE_DAILY, MODE_WEEKLY, MODE_WKDAY, MODE_FRTNGHT, MODE_MONTHLY,
               MODE_MTHDYS, MODE_MONTHS, MODE_QRTR, MODE_SEMIANL, MODE_ANNUAL]

# Until When config - Aligned to Recurring Task Mode Domains
UNTIL_WHEN = {MODE_DAILY: 2, MODE_WEEKLY: 8, MODE_MONTHLY: 32, 
              MODE_FRTNGHT: 16, MODE_SEMIANL: 184, MODE_QRTR: 93, 
              MODE_ANNUAL: 367, MODE_WKDAY: 2, MODE_MTHDYS: 5, 
              MODE_MONTHS: 90}
# Future date for date and None comparisons
FUTDT = datetime.strptime("2300-01-01", "%Y-%m-%d").date()
# Indictor Symbols
INDC_PR_HIGH = "[**]"
INDC_PR_MED = "[*]"
INDC_PR_NRML = ""
INDC_PR_LOW = "[.]"
INDC_NOW = "[++]"
# Date formats
FMT_DATEONLY = "%Y-%m-%d"
FMT_DATETIME = "%Y-%m-%d %H:%M"
FMT_EVENTID = "%Y%m-%d%H-%M%S-"
FMT_DAY_DATEW = "%a %d%b%y"
FMT_DATEW_TIME = "%d%b%y %H%M"
# ORM Definition
Base = declarative_base()


class Workspace(Base):
    """
    ORM for the 'workspace' table which holds all primary information
    for the tasks.
        Primary Key: uuid, version
        Indexes: idx_ws_due(due)
    """
    __tablename__ = "workspace"
    uuid = Column(String, primary_key=True)
    version = Column(Integer, primary_key=True)
    id = Column(Integer)
    description = Column(String)
    priority = Column(String)
    status = Column(String)
    due = Column(String)
    hide = Column(String)
    area = Column(String)
    created = Column(String)
    groups = Column(String)
    event_id = Column(String)
    now_flag = Column(BOOLEAN)
    task_type = Column(String)
    base_uuid = Column(String)
    recur_mode = Column(String)
    recur_when = Column(String)
    recur_end = Column(String)
    inception = Column(String)
    score = Column(Integer)

    # To get due date difference to today
    @hybrid_property
    def due_diff_today(self):
        curr_date = datetime.now().date()
        return (datetime.strptime(self.due, "%Y-%m-%d").date() 
                    - curr_date).days

    @due_diff_today.expression
    def due_diff_today(cls):
        curr_date = datetime.now().date().strftime("%Y-%m-%d")
        # julianday is an sqlite function
        date_diff = func.julianday(cls.due) - func.julianday(curr_date)
        """
        For some reason cast as Integer forces an addition in the sql
        when trying to concatenate with a string. Forcing as string causes
        the expression to be returned as a literal string rather than the 
        result. Hence using substr and instr instead.
        """
        return func.substr(date_diff, 1, func.instr(date_diff, ".")-1)
    
    # To get date difference of inception to today
    @hybrid_property
    def incep_diff_today(self):
        curr_date = datetime.now()
        return round((datetime.strptime(self.inception, FMT_DATETIME)
                    - curr_date).seconds / 60)

    @incep_diff_today.expression
    def incep_diff_today(cls):
        curr_date = datetime.now().date().strftime(FMT_DATEONLY)
        # julianday is an sqlite function
        date_diff = round(((func.julianday(cls.inception) 
                        - func.julianday(curr_date)) * 24 * 60))
        return func.substr(date_diff, 1, func.instr(date_diff, ".")-1)

Index("idx_ws_due", Workspace.due)


class WorkspaceTags(Base):
    """
    ORM for the 'workspace_tags' table which holds all the tags for each task.
    Every tags is stored as a row.
        Primary Key: uuid, version, tag
        Foreign Key: uuid->workspace.uuid, version->workspace.version
        Indexes: idx_ws_tg_uuid_ver(uuid, version)
    """
    __tablename__ = "workspace_tags"
    uuid = Column(String, primary_key=True)
    tags = Column(String, primary_key=True)
    version = Column(Integer, primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(["uuid", "version"],
                             ["workspace.uuid", "workspace.version"]), {})


Index("idx_ws_tg_uuid_ver", WorkspaceTags.uuid, WorkspaceTags.version)


class WorkspaceRecurDates(Base):
    """
    ORM for the table 'workspace_recur_dates' which holds all due dates for 
    which a task has been created.
    Every due date is stored as a row.
        Primary Key: uuid, version, due
        Foreign Key: uuid->workspace.uuid, version->workspace.version
    """
    __tablename__ = "workspace_recur_dates"
    uuid = Column(String, primary_key=True)
    version = Column(Integer, primary_key=True)
    due = Column(String, primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(["uuid", "version"],
                             ["workspace.uuid", "workspace.version"]), {})


Index("idx_ws_recr_uuid_ver", WorkspaceRecurDates.uuid,
      WorkspaceRecurDates.version)


class AppMetadata(Base):
    __tablename__ = "app_metadata"
    key = Column(String, primary_key=True)
    value = Column(String)
#Global - END


# Start Commands Config
@click.group()
def myt():
    """
    myt - my tASK MANAGER

    An application to manage your tasks through the command line using
    simple options.
    """
    pass

# Version
@myt.command()
def version():
    """
    Prints the application version number
    """
    CONSOLE.print(metadata.version('myt-cli'))
    exit_app(SUCCESS)

# Add
@myt.command()
@click.option("--desc",
              "-de",
              type=str,
              help="Short description of task",
              )
@click.option("--priority",
              "-pr",
              type=str,
              help="Priority for Task -H, M, L or leave empty for Normal",
              )
@click.option("--due",
              "-du",
              type=str,
              help="Due date for the task",
              )
@click.option("--hide",
              "-hi",
              type=str,
              help="Date until when task should be hidden from Task views",
              )
@click.option("--group",
              "-gr",
              type=str,
              help="Hierachical grouping for tasks using '.'",
              )
@click.option("--tag",
              "-tg",
              type=str,
              help="Comma separated tags for the task",
              )
@click.option("--recur",
              "-re",
              type=str,
              help="Set recurrence for the task",
              )
@click.option("--end",
              "-en",
              type=str,
              help="Set end date for recurrence, valid for recurring tasks.",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def add(desc, priority, due, hide, group, tag, recur, end, verbose):
    """
    Add a task. Provide details of task using the various options available.
    Task gets added with a TO_DO status and as a 'pending' task.
    
    Ex: myt add -de "Pay the bills" -du +2 -gr HOME -tg bills,expenses
    
    This adds a task with description 'Pay the bills', due in 2 days and 
    grouped under 'HOME' with tags of 'bills' and 'expenses'.
    Use the 'myt view' command to view tasks.
    
    Ex: myt add -de "Complete the timesheet" -du 2020-11-29 -hi -2 
    -gr WORK.PROJA -tg timesheets
    
    Adds a task to 'Complete the timesheets' due on 29th Nov 2020 under the
    group 'WORK' and sub group 'PROJA' with a tag 'timesheets'. This task will
    be hidden until 2 days before the due date in the 'myt view' command.
    Use 'myt view HIDDEN' to view such hidden tasks.
    
    --- DATE FORMAT ---
    
    The standard date format is YYYY-MM-DD
    There are shorter formats available to provide the date in a relative
    manner. This differs on if the format is used for due/end or hide dates
    
    For due/end: +X or -X where X is no. of days, set the due or end date as 
    today + X or today - X(past) 
    
    For hide: +X where X is no. of days, set hide date as today + X
    
    For hide: -X where X is no. of days, set the hide date as due date - X
    
    --- PRIORITY ---
    
    Priority can take input in various forms. If not set it defaults to 
    NORMAL priority which is higher than LOW priority in the task scoring.
    
    HIGH - HIGH/high/H/h
    
    MEDIUM - MEDIUM/medium/M/m
    
    NORMAL - NORMAL/normal/N/n
    
    LOW - LOW/low/L/l
    
    --- RECURRENCE ---
    
    Recurring tasks can be created by using BASIC or EXTENDED mode using the 
    '-re' option along with an optional 'end' date using '-en'
    
    BASIC Mode:
    DAILY - D, MONTHLY - M, WEEKLY - W, FORNIGHTLY - F,
    MONTHLY - M, QUARTERLY - Q, SEMI_ANUALLY - A and YEARLY - Y
    
    Ex: myt add -de "Pay the rent" -du 2020-11-01 -re M
    
    Here we add a task that will recur on the 1st of every month starting from 
    1st Nov 2020.
    
    EXTENDED Mode:
    WEEKDAYS - WD[1-7], MONTHDAYS - MD[1-31], MONTHS - MO[1-12]
    
    Ex: myt add -de 'Buy groceries online' -du 2020-12-03 -re MD3,13,24,30
    -en +182
    
    Here we add a task starting from 3rd Dec 2020 and recurring on 
    the 3rd, 13th, 24th and 30th of every month for upto half a year. 
    If the day is not valid for a month then it will be skipped. If the 
    due date provided does not match the days provided then the first 
    occurence will be on the next valid date.
    
    If a hide date is provided with -hi option then for every task the hide 
    value will be calculated based on the date difference between provided hide
    and the original due date.
    """
    if verbose:
        LOGGER.setLevel(level=logging.DEBUG)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if desc is None:
        CONSOLE.print("No task information provided. Nothing to do...",
                      style="default")
        return SUCCESS
    else:
        event_id = get_event_id()
        ws_task = Workspace(description=desc, priority=priority,
                            due=due, hide=hide, groups=group, now_flag=False)
        if tag is not None:
            ws_tags_list = generate_tags((tag.lstrip(",")).rstrip(","))
        else:
            ws_tags_list = None
        due = convert_date(due)
        end = convert_date(end)
        hide = convert_date_rel(hide, parse(due))
        if recur is not None:
            LOGGER.debug("Recur: {}".format(recur))
            if due is None or due == CLR_STR:
                CONSOLE.print("Need a due date for recurring tasks")
                exit_app(SUCCESS)
            if (end is not None and end != CLR_STR and
                    (datetime.strptime(end, "%Y-%m-%d") <
                        datetime.strptime(due, "%Y-%m-%d"))):
                CONSOLE.print("End date is less than due date, cannot create "
                              "recurring task")
                exit_app(SUCCESS)
            ret, mode, when = parse_n_validate_recur(recur)
            if ret == FAILURE:
                #Application behaved as expected so returning SUCCESS to exit
                exit_app(SUCCESS)
            LOGGER.debug("After parse and validate, Mode: {} and When: {}"
                         .format(mode, when))
            ws_task.recur_mode = mode
            ws_task.recur_when = when
            ws_task.recur_end = end
            ret, return_list = prep_recurring_tasks(ws_task, ws_tags_list,
                                                    False, event_id)
            print(ret)
            if ret == SUCCESS:
                """
                Compared to other operations, adding recurring tasks requires  
                adding multiple tasks by copying the 'same' base tasks. In  
                otheroperations although there are multiple tasks added each  
                is using 'different' task extracted from the database. So this 
                requires converting the object to tranisent state. Due to 
                this we are returning only the keys from the add recurring 
                tasks function and then querying the database to fetch the  
                task attributes to pass onto the print function
                """
                task_tags_print = []
                # First item in
                task_list = get_tasks((return_list[0])[0])
                tags_str = (return_list[0])[1]
                # List of tuples
                #[(task_list[0], tags_str), (task_list[1], tags_str), ...]
                task_tags_print = zip(*[task_list, [tags_str]*len(task_list)])
                get_and_print_task_count({WS_AREA_PENDING: "yes",
                                          PRNT_TASK_DTLS: task_tags_print})
                SESSION.commit()
        else:
            ws_task.task_type = TASK_TYPE_NRML
            ret, ws_task, tags_str = add_task_and_tags(ws_task, ws_tags_list,
                                                       event_id)
            if ret == SUCCESS:
                SESSION.commit()
                get_and_print_task_count({WS_AREA_PENDING: "yes",
                                          PRNT_TASK_DTLS: [(ws_task, 
                                                                tags_str)]})
        exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--desc",
              "-de",
              type=str,
              help="Short description of task",
              )
@click.option("--priority",
              "-pr",
              type=str,
              help="Priority for Task -H, M, L or leave empty for Normal",
              )
@click.option("--due",
              "-du",
              type=str,
              help="Due date for the task",
              )
@click.option("--hide",
              "-hi",
              type=str,
              help="Date until when task should be hidden from Task views",
              )
@click.option("--group",
              "-gr",
              type=str,
              help="Hierachical grouping for tasks using '.'",
              )
@click.option("--tag",
              "-tg",
              type=str,
              help="Comma separated tags for the task",
              )
@click.option("--recur",
              "-re",
              type=str,
              help="Set recurrence for the task",
              )
@click.option("--end",
              "-en",
              type=str,
              help="Set end date for recurrence, valid for recurring tasks.",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def modify(filters, desc, priority, due, hide, group, tag, recur, end,
           verbose):
    """
    Modify task details. Specify 1 or more filters and provide the details to
    be modified using the options. FILTERS can take various forms, some 
    examples are given below. Format is 'field:value'.

    id:2 - Filter task id =1 and apply modification

    tg:bills,finance - Filter on tasks tagged as bills or finance and modify

    id and tags can take comma separated values
    group takes only a single value
    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    LOGGER.debug("Values for update: desc - {} due - {} hide - {} group - {}"
                 " tag - {} now - {}"
                 .format(desc, due, hide, group, tag, toggle_now))
    # Perform validations
    if (desc is None and priority is None and due is None and hide is None
            and group is None and tag is None and toggle_now is False):
        CONSOLE.print("No modification values provided. Nothing to do...",
                      style="default")
        exit_app(SUCCESS)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for modifying tasks,"
                              " are you sure?"):
            exit_app(SUCCESS)
    if recur is not None:
        ret, mode, when = parse_n_validate_recur(recur)
        if ret == FAILURE:
            exit_app(ret)
    else:
        when = None
        mode = None
    if tag is not None:
        tag = (tag.lstrip(",")).rstrip(",")
    else:
        tag = None
    ws_task = Workspace(description=desc, priority=priority,
                        due=due, hide=hide, groups=group, recur_end=end,
                        recur_when=when, recur_mode=mode)
    ret, task_tags_print = prep_modify(potential_filters, ws_task, tag)
    if ret == SUCCESS:
        SESSION.commit()
        get_and_print_task_count({WS_AREA_PENDING: "yes",
                                  PRNT_TASK_DTLS: task_tags_print})
    exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def now(filters, verbose):
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if potential_filters.get("id") is None:
        CONSOLE.print("NOW flag can be modified only with a task ID filter",
                      style="default")
        exit_app(SUCCESS)
    if len(potential_filters.get("id").split(",")) > 1:
        CONSOLE.print("NOW flag can be modified for only 1 task at a time",
                      style="default")
        exit_app(SUCCESS)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    ret = toggle_now(potential_filters)
    exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def start(filters, verbose):
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for starting tasks,"
                              " are you sure?"):
            exit_app(SUCCESS)
    ret = start_task(potential_filters)
    exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def done(filters, verbose):
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for marking tasks as done,"
                              " are you sure?"):
            exit_app(SUCCESS)
    ret = complete_task(potential_filters)
    exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def revert(filters, verbose):
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(HL_FILTERS_ONLY) == "yes":
        if not confirm_prompt("No detailed filters given for reverting tasks "
                              "to TO_DO status, are you sure?"):
            exit_app(SUCCESS)
    ret = revert_task(potential_filters)
    exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def stop(filters, verbose):
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for stopping tasks, "
                              "are you sure?"):
            exit_app(SUCCESS)
    ret = stop_task(potential_filters)
    exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--pager",
              "-p",
              is_flag=True,
              help="Determine if task should be displayed via a pager",
              )
@click.option("--top",
              "-t",
              help="Display only the top 'x' number of tasks",
              )
@click.option("--default",
              "viewmode",
              flag_value="default",
              default=True,
              help="Viewmode - Default view of tasks sorted by the task's "
                   "score",
              )
@click.option("--full",
              "viewmode",
              flag_value="full",
              help="Viewmode - Display all attributes of the task stored in "
                   "the backend",
              )
@click.option("--history",
              "viewmode",
              flag_value="history",
              help="Viewmode - Display all versions of the task across "
              "irrespective of their status",
              )
@click.option("--tags",
              "viewmode",
              flag_value="tags",
              help="Viewmode - Display tags and the number of tasks against "
                   "each of them",
              )
@click.option("--projects",
              "viewmode",
              flag_value="projects",
              help="Viewmode - Display projects and the number of tasks "
                   "against each of them",
              )
@click.option("--dates",
              "viewmode",
              flag_value="dates",
              help="Viewmode - Display the future dates for recurring tasks",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def view(filters, verbose, pager, top, viewmode):
    """
    Display tasks using various views and filters
    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if top is not None:
        try:
            top = int(top)
        except ValueError:
            print("Invalid value provided for --top/-t. Should be a number.")
            exit_app(FAILURE)
    if viewmode == "default":
        ret = display_default(potential_filters, pager, top)
    elif viewmode == "full":
        ret = display_full(potential_filters, pager, top)
        ret = SUCCESS
    elif viewmode == "history":
        ret = SUCCESS
    elif viewmode == "tags":
        ret = display_by_tags(potential_filters, pager, top)
    elif viewmode == "projects":
        ret = SUCCESS
    elif viewmode == "dates":
        ret = display_dates(potential_filters, pager, top)
    exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def delete(filters, verbose):
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if potential_filters.get(HL_FILTERS_ONLY) == "yes":
        if not confirm_prompt("No detailed filters given for deleting tasks, "
                              "are you sure?"):
            exit_app(SUCCESS)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    ret, task_tags_print = delete_tasks(potential_filters)
    if ret == SUCCESS:
        SESSION.commit()
        get_and_print_task_count({WS_AREA_PENDING: "yes",
                                  PRNT_TASK_DTLS: task_tags_print})
        CONSOLE.print("{} task(s) deleted".format(str(len(task_tags_print))),
                      style="info")
    exit_app(ret)


@myt.command()
@click.option("--empty",
              is_flag=True,
              help="Empty the bin area.",
              )
@click.option("--vaccum",
              is_flag=True,
              help="Apply vaccum operation on database.",
              )
@click.option("--reinit",
              is_flag=True,
              help="Reinitialize the database.",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def admin(verbose, empty, vaccum, reinit):
    if verbose:
        set_versbose_logging()
    if reinit:
        if not confirm_prompt("This will delete the database including all "
                              "tasks and create an empty database. "
                              "Are you sure?"):
            exit_app(SUCCESS)
        ret = reinitialize_db(verbose)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if empty:
        ret = empty_bin()
    if vaccum:
        ret = vaccum_db()
    exit_app(ret)


def confirm_prompt(prompt_msg):
    res = Prompt.ask(prompt_msg, choices=["yes", "no"], default="no")
    if res == "no":
        return False
    else:
        return True


def reinitialize_db(verbose):
    full_db_path = os.path.join(DEFAULT_FOLDER, DEFAULT_DB_NAME)
    try:
        if os.path.exists(full_db_path):
            discard_db_resources()
            os.remove(full_db_path)
    except OSError as e:
        LOGGER.error("Unable to remove database.")
        LOGGER.error(str(e))
        return FAILURE
    with CONSOLE.capture() as capture:
        CONSOLE.print("Database removed...", style="info")
    click.echo(capture.get(), nl=False)
    ret = connect_to_tasksdb(verbose=verbose, legacy=False)
    return ret


def connect_to_tasksdb(verbose=False, legacy=True):
    global Session, SESSION, ENGINE
    full_db_path = os.path.join(DEFAULT_FOLDER, DEFAULT_DB_NAME)
    ENGINE = create_engine("sqlite:///"+full_db_path, echo=verbose)
    db_init = False
    if not os.path.exists(full_db_path):
        CONSOLE.print("No tasks database exists, intializing at {}"
                      .format(full_db_path), style="info")
        try:
            Path(DEFAULT_FOLDER).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            LOGGER.error("Error in creating tasks database")
            LOGGER.error(str(e))
            return FAILURE
        try:
            Base.metadata.create_all(bind=ENGINE)
        except SQLAlchemyError as e:
            LOGGER.error("Error in creating tables")
            LOGGER.error(str(e))
            return FAILURE
        with CONSOLE.capture() as capture:
            CONSOLE.print("Tasks database initialized...", style="info")
        click.echo(capture.get(), nl=False)
        db_init = True
    LOGGER.debug("Now using tasks database at {}".format(full_db_path))

    LOGGER.debug("Creating session...")
    try:
        Session = sessionmaker(bind=ENGINE)
        SESSION = Session()
    except SQLAlchemyError as e:
        LOGGER.error("Error in creating session")
        LOGGER.error(str(e))
        return FAILURE
    try:
        curr_day = datetime.now().date()
        if db_init:
            mtdt = AppMetadata(key="DB_SCHEMA_VERSION", value=DB_SCHEMA_VER)
            rcdt = AppMetadata(key="LAST_RECUR_CREATE_DT",
                               value=curr_day.strftime(FMT_DATEONLY))
            SESSION.add(rcdt)
            SESSION.add(mtdt)
        results = (SESSION.query(AppMetadata.value)
                          .filter(AppMetadata.key == "LAST_RECUR_CREATE_DT")
                          .all())
        if results is not None:
            last = datetime.strptime((results[0])[0], FMT_DATEONLY).date()
            if last < curr_day:
                ret = create_recur_inst()
                if ret == FAILURE:
                    return ret
                rcdt = (SESSION.query(AppMetadata)
                        .filter(AppMetadata.key
                                == "LAST_RECUR_CREATE_DT")
                        .one())
                rcdt.value = curr_day.strftime(FMT_DATEONLY)
                SESSION.add(rcdt)
        SESSION.commit()
    except SQLAlchemyError as e:
        LOGGER.error("Error in executing post intialization acitivities")
        LOGGER.error(str(e))
        return FAILURE
    return SUCCESS


def create_recur_inst():
    LOGGER.debug("In create_recur_tasks now")
    potential_filters = {}
    potential_filters["osrecur"] = "yes"
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if uuid_version_results is None:
        LOGGER.debug("No recurring tasks instances to create in first "
                     "run of the day")
        return
    tasks_list = get_tasks(uuid_version_results)
    for task in tasks_list:
        LOGGER.debug("Trying to add recurring tasks as part of startup for "
                     " UUID {} and version {}".format(task.uuid, task.version))
        ws_tags_list = get_tags(task.uuid, task.version)
        ret, tasks_tags_print = prep_recurring_tasks(
            task, ws_tags_list, True, None)
        if ret == FAILURE:
            return ret
    return SUCCESS


def get_event_id():
    return datetime.now().strftime(FMT_EVENTID) + str(uuid.uuid4())


def set_versbose_logging():
    LOGGER.setLevel(level=logging.DEBUG)


def generate_tags(tags):
    ws_tags_list = []
    if tags is not None:
        tag_list = tags.split(",")
        for t in tag_list:
            ws_tags = WorkspaceTags()
            ws_tags.tags = t
            ws_tags_list.append(ws_tags)
        return ws_tags_list
    return None


def is_date_short_format(string):
    """
    To determine if the string is expected shortformat of date

    The short format is used by the program to assign a date or
    make relative adjustments to a date and then derive a date.
    Ex: +5 is Today + days or +0 is Today

    Parameters:
        string(str): The string to perform this check on.

    Returns:
        bool: True if input is shortformat else False
    """
    if string and re.match(r"^[\-\+][0-9]*$", string):
        return True
    else:
        return False


def is_date(string):
    """
    To determine whether the string can be interpreted as a date.

    Takes a date string and validates if it is a valid date using
    the parse fnction from dateutil.parser

    Parameters:
        string(str): String to check for date

    Returns:
        bool: True if a valid date else False
    """
    try:
        parse(string, False)
        return True

    except ValueError:
        return False


def adjust_date(refdate, num, timeunit="days"):
    """
    Return a date post a relative adjustment to a reference date

    An adjustment of say +10 days or -2 Months is applied to a 
    reference date. The adjusted date is then returned

    Parameters:
        refdate(date): Date to apply relative adjustment 

        num(str): The adjustment value as +x or -x 

        timeunit(str): The unit for the adjustments, days, months, etc.
        The default is 'days'

    Returns: 
        date: The adjusted date
    """
    dd = relativedelta(**{timeunit: int(num)})
    conv_dt = refdate + relativedelta(**{timeunit: int(num)})
    return conv_dt


def convert_date(value):
    if value == CLR_STR:
        return CLR_STR
    if value and is_date_short_format(value):
        if not value[1:]:  # No number specified after sign, append a 0
            value = value[0] + "0"
        return adjust_date(date.today(), value).strftime("%Y-%m-%d")
    elif value and is_date(value):
        return parse(value).date().strftime("%Y-%m-%d")
    else:
        return None


def convert_date_rel(value, due):
    if value == CLR_STR:
        return CLR_STR
    if value and is_date_short_format(value):
        if not value[1:]:  # No number specified after sign, append a 0
            value = value[0] + "0"
        if value[0:1] == "+":
            return adjust_date(date.today(), value)
        elif due is not None and value[0:1] == "-":
            return adjust_date(due, value).strftime("%Y-%m-%d")
    elif value and is_date(value):
        return parse(value).date().strftime("%Y-%m-%d")
    else:
        return None


def empty_bin():
    """
    Empty the bin area. All tasks are deleted permanently.
    Undo operation does not work here. No filters are accepted
    by this operation.
    
    Parameters:
        None
        
    Returns:
        None
    """
    uuid_version_results = get_task_uuid_n_ver({TASK_BIN: "yes"})
    LOGGER.debug("Got list of UUID and Version for emptying:")
    LOGGER.debug(uuid_version_results)
    if uuid_version_results:
        if not confirm_prompt("Deleting all versions of {} task(s),"
                              " are your sure?"
                              .format(str(len(uuid_version_results)))):
            return SUCCESS
        uuid_list = [uuid[0] for uuid in uuid_version_results]
        LOGGER.debug("List of UUIDs in bin:")
        LOGGER.debug(uuid_list)
        try:
            (SESSION.query(WorkspaceTags)
             .filter(WorkspaceTags.uuid.in_(uuid_list))
             .delete(synchronize_session=False))
            (SESSION.query(Workspace)
             .filter(Workspace.uuid.in_(uuid_list))
             .delete(synchronize_session=False))
        except SQLAlchemyError as e:
            LOGGER.error(str(e))
            return FAILURE
        SESSION.commit()
        with CONSOLE.capture() as capture:
            CONSOLE.print("Bin emptied!", style="info")
        click.echo(capture.get(), nl=False)
        return SUCCESS
    else:
        CONSOLE.print("Bin is already empty, nothing to do", style="default")
        return SUCCESS


def delete_tasks(potential_filters, event_id=None):
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    task_tags_print = []
    if not uuid_version_results:
        with CONSOLE.capture() as capture:
            CONSOLE.print("No applicable tasks to delete", style="default")
        click.echo(capture.get(), nl=False)
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        make_transient(task)
        ws_task = task
        ws_task.id = "-"
        ws_task.area = WS_AREA_BIN
        if event_id is None:
            ws_task.event_id = None
        else:
            # Use an inherited event_id if available
            ws_task.event_id = event_id
        ws_task.now_flag = False
        LOGGER.debug("Deleting Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task, ws_tags_list)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None, None
    return ret, task_tags_print


def unlink_tasks(potential_filters, event_id=None):
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    task_tags_print = []
    if not uuid_version_results:
        return SUCCESS, None
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        make_transient(task)
        ws_task = task
        ws_task.base_uuid = None
        ws_task.recur_end = None
        ws_task.recur_mode = None
        ws_task.recur_when = None
        if event_id is None:
            ws_task.event_id = None
        else:
            # Use an inherited event_id if available
            ws_task.event_id = event_id
        LOGGER.debug("Unlinking Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task, ws_tags_list)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None
    return ret, task_tags_print


def revert_task(potential_filters, event_id=None):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to revert", style="default")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        make_transient(task)
        ws_task = task
        if ws_task.id == '-':
            ws_task.id = None
        ws_task.area = WS_AREA_PENDING
        ws_task.status = TASK_STATUS_TODO
        if event_id is None:
            ws_task.event_id = None
        else:
            # Use an inherited event_id if available
            ws_task.event_id = event_id
        LOGGER.debug("Reverting Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task, ws_tags_list)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
    SESSION.commit()
    get_and_print_task_count({WS_AREA_PENDING: "yes",
                              PRNT_TASK_DTLS: task_tags_print})
    return SUCCESS


def start_task(potential_filters, event_id=None):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to start", style="default")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    LOGGER.debug("Total Tasks to Start {}".format(len(task_list)))
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        make_transient(task)
        ws_task = task
        ws_task.status = TASK_STATUS_STARTED
        if event_id is None:
            ws_task.event_id = None
        else:
            # Use an inherited event_id if available
            ws_task.event_id = event_id
        LOGGER.debug("Starting Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task, ws_tags_list)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
    SESSION.commit()
    get_and_print_task_count({WS_AREA_PENDING: "yes",
                              PRNT_TASK_DTLS: task_tags_print})
    return SUCCESS


def stop_task(potential_filters, event_id=None):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to stop", style="default")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    LOGGER.debug("Total Tasks to Stop {}".format(len(task_list)))
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        make_transient(task)
        ws_task = task
        ws_task.status = TASK_STATUS_TODO
        if event_id is None:
            ws_task.event_id = None
        else:
            # Use an inherited event_id if available
            ws_task.event_id = event_id
        LOGGER.debug("Stopping Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task, ws_tags_list)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
    SESSION.commit()
    get_and_print_task_count({WS_AREA_PENDING: "yes",
                              PRNT_TASK_DTLS: task_tags_print})
    return SUCCESS


def complete_task(potential_filters, event_id=None):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to complete", style="default")
        return
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        make_transient(task)
        ws_task = task
        ws_task.id = "-"
        ws_task.area = WS_AREA_COMPLETED
        ws_task.status = TASK_STATUS_DONE
        if event_id is None:
            ws_task.event_id = None
        else:
            # Use an inherited event_id if available
            ws_task.event_id = event_id
        ws_task.now_flag = False
        LOGGER.debug("Completing Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task, ws_tags_list)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
    SESSION.commit()
    get_and_print_task_count({WS_AREA_PENDING: "yes",
                              PRNT_TASK_DTLS: task_tags_print})
    return SUCCESS


def toggle_now(potential_filters, event_id=None):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable task to set as NOW", style="default")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        make_transient(task)
        ws_task = task
        if ws_task.now_flag == True:
            ws_task.now_flag = False
        else:
            ws_task.now_flag = True
        if event_id is None:
            ws_task.event_id = None
        else:
            # Use an inherited event_id if available
            ws_task.event_id = event_id
        LOGGER.debug("Setting Task UUID {} and Task ID {} as NOW"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task, ws_tags_list)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
        """
        Next, any other task having its NOW as True should be set to False.
        For this we will first identify the task UUID and version and then
        create a new version. New version will have same 'event_id' and 
        'created' as the task being added and with NOW set to false
        """
        uuid_ver = (SESSION.query(Workspace.uuid,
                                  Workspace.version)
                    .filter(and_(Workspace.area == WS_AREA_PENDING,
                                 Workspace.now_flag == True,
                                 Workspace.id != '-',
                                 Workspace.task_type
                                 .in_([TASK_TYPE_DRVD,
                                       TASK_TYPE_NRML]),
                                 Workspace.uuid != ws_task.uuid))
                    .all())
        if uuid_ver:
            task_list = get_tasks(uuid_ver)
            LOGGER.debug("Previous task which is set as NOW: {}"
                         .format(task_list[0]))
            for task in task_list:
                LOGGER.debug("To reset NOW:Working on Task UUID {} and "
                             "Task ID {}"
                             .format(task.uuid, task.id))
                make_transient(task)
                ws_task_innr = task
                ws_task_innr.event_id = ws_task.event_id
                ws_task_innr.created = now
                ws_task_innr.now_flag = False
                LOGGER.debug("Resetting NOW: Task UUID {} and Task ID {}"
                             .format(ws_task_innr.uuid, ws_task_innr.id))
                ws_tags_innr_list = get_tags(ws_task_innr.uuid,
                                             ws_task_innr.version)
                ret, ws_task, tags_str = add_task_and_tags(ws_task_innr,
                                                           ws_tags_innr_list)
                task_tags_print.append((ws_task, tags_str))
                if ret == FAILURE:
                    # Rollback already performed from nested
                    LOGGER.error("Error encountered in reset of NOW")
                    return FAILURE
    SESSION.commit()
    get_and_print_task_count({WS_AREA_PENDING: "yes",
                              PRNT_TASK_DTLS: task_tags_print})
    return SUCCESS


def parse_filters(filters):
    """
    Converts the user provided filters into a dictionary of 'potential' 
    filters that can be run on the tasks database. It is 'potential' as the 
    filters are not validated at this point. If the filter is meant to have
    values like 1 or more ids then the dictionary will be for ex: "id":"1,3,4".
    For filters which are not value based, for example a filter for 'hidden'
    tasks the dictionary will be populated as "HIDDEN":"yes".
    
    Parameters:
        filters(str): Filters provided by the user as arguments in the CLI
    
    Returns:
        dictionary: Dictionary with keys indicating type of filters and value 
        will the filter value
    """
    potential_filters = {}
    if filters:
        for fl in filters:
            if str(fl).upper() == TASK_OVERDUE:
                potential_filters[TASK_OVERDUE] = "yes"
            if str(fl).upper() == TASK_TODAY:
                potential_filters[TASK_TODAY] = "yes"
            if str(fl).upper() == TASK_HIDDEN:
                potential_filters[TASK_HIDDEN] = "yes"
            if str(fl).upper() == TASK_DONE:
                potential_filters[TASK_DONE] = "yes"
            if str(fl).upper() == TASK_BIN:
                potential_filters[TASK_BIN] = "yes"
            if str(fl).upper() == TASK_STARTED:
                potential_filters[TASK_STARTED] = "yes"
            if str(fl).upper() == TASK_NOW:
                potential_filters[TASK_NOW] = "yes"
            if str(fl).startswith("id:"):
                potential_filters["id"] = (((str(fl).split(":"))[1])
                                           .rstrip(","))
            if str(fl).startswith("pr:") or str(fl).startswith("priority:"):
                potential_filters["priority"] = (((str(fl).split(":"))[1])
                                                 .rstrip(","))
            if str(fl).startswith("gr:") or str(fl).startswith("group:"):
                potential_filters["group"] = (str(fl).split(":"))[1]
            if str(fl).startswith("tg:") or str(fl).startswith("tag:"):
                potential_filters["tag"] = (((str(fl).split(":"))[1])
                                            .rstrip(","))
            if str(fl).startswith("uuid:"):
                potential_filters["uuid"] = (((str(fl).split(":"))[1])
                                             .rstrip(","))
            if str(fl).startswith("de:") or str(fl).startswith("desc:"):
                potential_filters["desc"] = (str(fl).split(":"))[1]
            if str(fl).startswith("du:") or str(fl).startswith("due:"):
                potential_filters["due"] = parse_date_filters(str(fl)
                                                              .split(":"))
            if str(fl).startswith("hi:") or str(fl).startswith("hide:"):
                #For filters usage of date short form for hide works
                #the same as 'due' and 'end' is not relative to 'due' date
                potential_filters["hide"] = parse_date_filters(str(fl)
                                                               .split(":"))
            if str(fl).startswith("en:") or str(fl).startswith("end:"):
                potential_filters["end"] = parse_date_filters(str(fl)
                                                              .split(":"))
                              
    if not potential_filters:
        potential_filters = {TASK_ALL: "yes"}
    """
    If only High Level Filters provided then set a key to use to warn users
    as such actions could change properties for a large number of tasks
    """
    if ("id" not in potential_filters 
            and "priority" not in potential_filters
            and "group" not in potential_filters
            and "tag" not in potential_filters
            and "uuid" not in potential_filters
            and TASK_NOW not in potential_filters
            and TASK_STARTED not in potential_filters
            and "desc"  not in potential_filters
            and "due"  not in potential_filters
            and "hide"  not in potential_filters
            and "end"  not in potential_filters):
        potential_filters[HL_FILTERS_ONLY] = "yes"
    return potential_filters


def parse_date_filters(comp_list):
    opr = None
    dt1 = None
    dt2 = None
    try:
        opr = comp_list[1]
        dt1 = convert_date(comp_list[2])
        dt2 = convert_date(comp_list[3])
    except IndexError:
        pass
    if opr in ["lt","le","gt","ge","bt","eq"]:
        #Run validations
        if opr == "bt" and (dt1 is None or dt2 is None):
            #between requires both date1 and date 2
            opr = None
        elif opr in ["lt","le","gt","ge","eq"] and dt1 is None:
            "the other operators require date1"
            opr = None
    else:
        #Not a valid operator so set it as None
        opr = None
    return [opr, dt1, dt2]


def get_tasks(uuid_version=None, expunge=True):
    """
    Returns the task details for a list of task uuid and versions.

    Retrieves tasks details from the database for he provided
    list of task UUIDs and Versions.

    Parameters:
        task_uuid_and_version(list): List of uuid and versions

    Returns:
        list: List with Workspace objects representing  each task
    """
    try:
        ws_task_list = (SESSION.query(Workspace)
                        .filter(tuple_(Workspace.uuid, Workspace.version)
                                .in_(uuid_version))
                        .order_by(Workspace.task_type)
                        .all())
        if expunge:
            SESSION.expunge_all()
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return None
    else:
        return ws_task_list


def get_tags(task_uuid, task_version, expunge=True):
    try:
        ws_tags_list = (SESSION.query(WorkspaceTags)
                        .filter(and_(WorkspaceTags.uuid == task_uuid,
                                     WorkspaceTags.version == task_version))
                        .all())
        if expunge:
            SESSION.expunge_all()
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return None
    else:
        return ws_tags_list


def prep_modify(potential_filters, ws_task_src, tag):
    multi_change = False
    rec_chg = False
    hide_chg = False
    due_chg = False
    modifed_recur_list = []
    task_tags_print = []
    LOGGER.debug("Incoming values for task to modify:")
    LOGGER.debug("\n" + reflect_object_n_print(ws_task_src, to_print=False,
                                               print_all=True))
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to modify", style="default")
        return SUCCESS, None
    event_id = get_event_id()
    ws_task_src.event_id = event_id
    task_list = get_tasks(uuid_version_results)
    for ws_task in task_list:
        r_tsk_tg_prnt = []
        uuidn = ws_task.uuid
        base_uuid = ws_task.base_uuid
        if base_uuid in modifed_recur_list:
            continue
        make_transient(ws_task)
        ws_task.uuid = uuidn
        if ws_task.task_type == TASK_TYPE_DRVD:
            res = Prompt.ask("This is a recurring task, do you want "
                             "to modify 'all' pending instances or "
                             "just 'this' instance",
                             choices=["all", "this", "none"], default="none")
            if (ws_task_src.recur_end is not None
                    or ws_task_src.recur_mode is not None
                    or ws_task_src.recur_when is not None):
                rec_chg = True
            if ws_task_src.due is not None:
                due_chg = True
            if ws_task_src.hide is not None:
                hide_chg = True
            if res == "none":
                ret = SUCCESS
                continue
            elif res == "all":
                LOGGER.debug("Performing logic related to 'all' task modify")
                # To change all occurences of a recurring task
                multi_change = True
                modifed_recur_list.append(base_uuid)
                r_tsk_tg_prnt1 = []
                r_tsk_tg_prnt2 = []
                r_tsk_tg_prnt3 = []
                r_tsk_tg_prnt4 = []
                r_tsk_tg_prnt5 = []
                if (due_chg or hide_chg or rec_chg):
                    """
                    Involves change in recurrence properties or due or hide
                    related properties. In this case the below will be done
                    1. All existing pending versions of the task including
                    the base task will be deleted
                    2. All done tasks under this base task will be unlinked
                    from the base task. (This is done so that they can then
                    be reverted individually if required)
                    3. Re-create the base task from the due date provided. If
                    no due date is provided then the original due date is used
                    """
                    LOGGER.debug("Change requested in due:{} or hide:{} or "
                                 "recur:{}".format(due_chg, hide_chg,
                                                   recur_chg))
                    potential_filters = {}
                    potential_filters["baseuuidonly"] = base_uuid
                    uuid_ver_res_innr = get_task_uuid_n_ver(potential_filters)
                    tasks_innr = get_tasks(uuid_ver_res_innr)
                    ws_task_innr = tasks_innr[0]
                    make_transient(ws_task_innr)
                    # Preserve a version of the base task before deleting
                    ws_task_innr.uuid = base_uuid
                    ws_task_innr.event_id = event_id
                    potential_filters["bybaseuuid"] = base_uuid
                    # Delete base and derived tasks
                    ret, r_tsk_tg_prnt1 = delete_tasks(potential_filters,
                                                       event_id)
                    if ret == FAILURE:
                        LOGGER.error("Failure recived while trying to delete "
                                     "old pending occurences of this task. "
                                     "Stopping adding of base and derived "
                                     "tasks.")
                        return FAILURE, None
                    # Unlink done tasks
                    potential_filters[TASK_DONE] = "yes"
                    ret, r_tsk_tg_prnt2 = unlink_tasks(potential_filters,
                                                       event_id)
                    if ret == FAILURE:
                        LOGGER.error("Failure recived while trying to unlink "
                                     "done occurences of this task. Stopping "
                                     "adding of base and derived tasks.")
                        return FAILURE, None
                    # Next call modify to merge user changes and
                    # recreate the recurring task
                    LOGGER.debug("Sending this task for RECREATION to "
                                 "modify_task - UUID: {}"
                                 .format(ws_task_innr.uuid))
                    ret, r_tsk_tg_prnt3 = modify_task(ws_task_src,
                                                      ws_task_innr,
                                                      tag,
                                                      multi_change,
                                                      rec_chg,
                                                      due_chg,
                                                      hide_chg,
                                                      None)
                else:
                    """
                    We need to modify the base task and any pending instances
                    for the base task. We will only create a new version
                    and not re-create the complete set of recurring tasks
                    """
                    """
                    First add a new version for base task with updated 
                    task properties. For this retrieve the base task
                    and send it to modify_task to merge and the add
                    """
                    LOGGER.debug("Change requested in something other than "
                                 "due, hide or change")
                    potential_filters = {}
                    potential_filters["baseuuidonly"] = base_uuid
                    uuid_ver_res_innr = get_task_uuid_n_ver(potential_filters)
                    tasks_innr = get_tasks(uuid_ver_res_innr)
                    ws_task_innr = tasks_innr[0]
                    make_transient(ws_task_innr)
                    ws_task_innr.uuid = base_uuid
                    ws_task_innr.event_id = event_id
                    LOGGER.debug("Sending this BASE task for modification to "
                                 "modify_task - UUID: {}"
                                 .format(ws_task_innr.uuid))
                    ret, r_tsk_tg_prnt4 = modify_task(ws_task_src,
                                                      ws_task_innr,
                                                      tag,
                                                      multi_change,
                                                      rec_chg,
                                                      due_chg,
                                                      hide_chg,
                                                      None)
                    if ret == FAILURE:
                        LOGGER.error("Failure recived while trying to modify "
                                     "base task. Stopping adding of derived "
                                     "tasks.")
                        return FAILURE, None
                    """
                    Now that base task's new version is added, use that ver. 
                    num for the WorkspaceRecurDates object for each derived 
                    task being added next
                    """
                    base_ver = (r_tsk_tg_prnt4[0])[0].version
                    LOGGER.debug("After BASE task modification version of "
                                 "BASE task is no {}".format(base_ver))

                    # Add a new version for each derived task that exists
                    # and is pending
                    potential_filters = {}
                    potential_filters["bybaseuuid"] = base_uuid
                    uuid_ver_res_innr = get_task_uuid_n_ver(potential_filters)
                    tasks_innr = get_tasks(uuid_ver_res_innr)
                    LOGGER.debug("Attempting to now modify the DERIVED tasks. "
                                 "Total of {} tasks require modification"
                                 .format(len(tasks_innr)))
                    for ws_task_innr in tasks_innr:
                        uuidn = ws_task_innr.uuid
                        make_transient(ws_task_innr)
                        ws_task_innr.uuid = uuidn
                        ws_task_innr.event_id = event_id
                        LOGGER.debug("Working on DERIVED task {}"
                                     .format(uuidn))
                        ws_rec_dt = WorkspaceRecurDates(
                            uuid=ws_task_innr.base_uuid,
                            version=base_ver,
                            due=ws_task_innr.due)
                        LOGGER.debug("Created a WorkspaceRecurDates object "
                                     "for this task:")
                        LOGGER.debug("\n" + 
                                      reflect_object_n_print(ws_rec_dt,
                                                             to_print=False,
                                                             print_all=True))
                        LOGGER.debug("Sending the DERIVED task for "
                                     "modification to modify_task - UUID: {}"
                                     .format(ws_task_innr.uuid))
                        ret, r_tsk_tg_prnt5_1 = modify_task(ws_task_src,
                                                            ws_task_innr,
                                                            tag,
                                                            multi_change,
                                                            rec_chg,
                                                            due_chg,
                                                            hide_chg,
                                                            ws_rec_dt)
                        r_tsk_tg_prnt5 = (r_tsk_tg_prnt5
                                          + (r_tsk_tg_prnt5_1 or []))
                # Collect all task's for printing
                r_tsk_tg_prnt = ((r_tsk_tg_prnt1 or [])
                                 + (r_tsk_tg_prnt2 or [])
                                 + (r_tsk_tg_prnt3 or [])
                                 + (r_tsk_tg_prnt4 or [])
                                 + (r_tsk_tg_prnt5 or []))
            elif res == "this":
                """
                Only 1 task being modified at a time
                """
                LOGGER.debug("Modification requested only for 'this' instance "
                             "of the recurring task")
                if rec_chg:
                    # Recurrence cannot be changed for an individual task
                    CONSOLE.print("Cannot change the reccurence for 'this' "
                                  "task only")
                    return SUCCESS, None
                multi_change = False
                ws_task.event_id = event_id
                LOGGER.debug("Sending 'this' DERIVED task for "
                             "modification to modify_task - UUID: {}"
                             .format(ws_task.uuid))
                ret, r_tsk_tg_prnt = modify_task(ws_task_src,
                                                 ws_task,
                                                 tag,
                                                 multi_change,
                                                 rec_chg,
                                                 due_chg,
                                                 hide_chg,
                                                 None)
        else:
            """
            This is modification for a non recurring task
            """
            LOGGER.debug("Modification requested a NORMAL task")
            multi_change = False
            ws_task.event_id = event_id
            LOGGER.debug("Sending the NORMAL task for "
                         "modification to modify_task - UUID: {}"
                         .format(ws_task.uuid))
            ret, r_tsk_tg_prnt = modify_task(ws_task_src,
                                             ws_task,
                                             tag,
                                             multi_change,
                                             rec_chg,
                                             due_chg,
                                             hide_chg,
                                             None)
        if ret == FAILURE:
            LOGGER.error("Failure returned while trying to modify task.")
            return ret, None
        if r_tsk_tg_prnt is not None:
            task_tags_print = task_tags_print + r_tsk_tg_prnt
    return ret, task_tags_print


def modify_task(ws_task_src, ws_task, tag, multi_change, rec_chg, due_chg,
                hide_chg, ws_rec_dt=None):
    """
    Function to merge the changes provided by the user into the task
    that already exists. 
    This function does not decide which task has to be modified, which is
    done by prep_modify. This function gets tasks from prep_modify and
    merges the changes with the version from the database and passess it
    on to add_task_tags to create a new version or to prep_recurring_tasks
    for recurring tasks which in certain scenarios need some more prep work
    before a new version is added.
    General logic followed is:
    If user requested update or clearing then overwrite
    If user has not requested update for field then retain original value
    """
    task_tags_print = []
    # Start merge related activties
    uuidn = ws_task.uuid
    base_uuid = ws_task.base_uuid
    make_transient(ws_task)
    ws_task.uuid = uuidn
    LOGGER.debug("Modification for Task UUID {} and Task ID {}"
                 .format(ws_task.uuid, ws_task.id))
    if ws_task_src.description == CLR_STR:
        ws_task.description = None
    elif ws_task_src.description is not None:
        ws_task.description = ws_task_src.description

    if ws_task_src.priority == CLR_STR:
        ws_task.priority = PRIORITY_NORMAL
    elif ws_task_src.priority is not None:
        ws_task.priority = ws_task_src.priority

    if ws_task_src.due == CLR_STR:
        ws_task.due = None
    elif ws_task_src.due is not None:
        ws_task.due = ws_task_src.due

    if ws_task_src.hide == CLR_STR:
        ws_task.hide = None
    elif ws_task_src.hide is not None:
        ws_task.hide = ws_task_src.hide

    if ws_task_src.groups == CLR_STR:
        ws_task.groups = None
    elif ws_task_src.groups is not None:
        ws_task.groups = ws_task_src.groups

    if ws_task_src.recur_end is not None:
        ws_task.recur_end = ws_task_src.recur_end
    if ws_task_src.recur_mode is not None:
        ws_task.recur_mode = ws_task_src.recur_mode
    if ws_task_src.recur_when is not None:
        ws_task.recur_when = ws_task_src.recur_when

    if ws_task_src.event_id is not None:
        ws_task.event_id = ws_task_src.event_id

    # If operation is not to clear tags then retrieve current tags
    tag_u = []
    ws_tags_list = []
    if tag != CLR_STR:
        LOGGER.debug("For Task ID {} and UUID {} and version {}"
                     "attempting to retreive tags"
                     .format(ws_task.id, ws_task.uuid, ws_task.version))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        tag_u = [temptag.tags for temptag in ws_tags_list]
        LOGGER.debug("Retrieved Tags: {}".format(tag_u))
    # Apply the user requested update
    if tag != CLR_STR and tag is not None:
        tag_list = tag.split(",")
        for t in tag_list:
            if t[0] == "-":
                t = str(t[1:])
                if t in tag_u:
                    LOGGER.debug("Removing tag in list for new version {}"
                                 .format(t))
                    tag_u.remove(t)
            elif t not in tag_u:
                LOGGER.debug("Adding tag in list for new version {}"
                             .format(t))
                tag_u.append(t)
        LOGGER.debug("Final Tag List for new version: {}".format(tag_u))
        ws_tags_list = []
        for t in tag_u:
            ws_tags_list.append(WorkspaceTags(uuid=ws_task.uuid,
                                              version=ws_task.version, tags=t))
    # All merge related activties are complete
    # Next either add a version of the task or send it for further prep for
    # recurring tasks
    if not multi_change:
        LOGGER.debug("Sending values from modify to add_task_and_tags for a "
                     "normal task or a single recurring task change:")
        LOGGER.debug("\n" + reflect_object_n_print(ws_task, to_print=False,
                                                   print_all=True))
        ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                   ws_tags_list,
                                                   None)
        task_tags_print.append((ws_task, tags_str))
    else:
        # A set of recurring tasks need change
        if (due_chg or hide_chg or rec_chg):
            LOGGER.debug("Sending values from modify to prep_recurring_tasks "
                         "for a recurring task change:")
            LOGGER.debug("\n" + reflect_object_n_print(ws_task, to_print=False,
                                                       print_all=True))
            ret, return_list = prep_recurring_tasks(ws_task,
                                                    ws_tags_list,
                                                    False,
                                                    None)
            task_list = get_tasks((return_list[0])[0])
            tags_str = (return_list[0])[1]
            # List of tuples
            #[(task_list[0], tags_str), (task_list[1], tags_str), ...]
            task_tags_print = list(
                zip(*[task_list, [tags_str]*len(task_list)]))
        else:
            LOGGER.debug("Sending values from modify to add_task_and_tags "
                         "for a recurring task but without recur changes:")
            LOGGER.debug("\n" + reflect_object_n_print(ws_task, to_print=False,
                                                       print_all=True))
            ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                       ws_tags_list,
                                                       None,
                                                       ws_rec_dt)
            task_tags_print.append((ws_task, tags_str))

    if ret == FAILURE:
        LOGGER.error("Error encountered in adding task version, stopping")
        return ret
    return SUCCESS, task_tags_print


def display_full(potential_filters, pager=False, top=None):
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    CONSOLE.print("Preparing view...", style="default")
    task_list = get_tasks(uuid_version_results)
    if top is None:
        top = len(task_list)
    else:
        top = int(top)
    out_str = ""
    for cnt, task in enumerate(task_list, start=1):
        if cnt > top:
            break
        tags_list = get_tags(task.uuid, task.version)
        if tags_list:
            tags_str = ""
            for tag in tags_list:
                tags_str = tags_str + "," + tag.tags
        else:
            tags_str = "--"
        # Gather all output into a string
        # This is done to allow to print all at once via a pager
        out_str = out_str + "\n" + reflect_object_n_print(task,
                                                          to_print=False,
                                                          print_all=True)
        with CONSOLE.capture() as capture:
            CONSOLE.print("tags : [magenta]{}[/magenta]"
                          .format(tags_str[1:]), style="info")
        out_str = out_str + capture.get() + "\n" + "--"
    if pager:
        with CONSOLE.pager(styles=True):
            CONSOLE.print(out_str)
    else:
        CONSOLE.print(out_str)
    return SUCCESS


def display_dates(potential_filters, pager=False, top=None):
    curr_date = datetime.now().date()
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    task_list = [task for task in task_list if task.task_type==TASK_TYPE_DRVD]
    if task_list:
        CONSOLE.print("Preparing view...", style="default")
    else:
        CONSOLE.print("No tasks to display")
        return SUCCESS
    if top is None:
        top = len(task_list)
    else:
        top = int(top)
    out_str = ""
    prcsd_baseuuid = []
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=False)
    table.add_column("description", justify="left")
    table.add_column("due", justify="left")
    for cnt, task in enumerate(task_list, start=1):
        if cnt > top:
            break
        if task.base_uuid in prcsd_baseuuid:
            break
        if cnt > 1:
            table.add_row(None, None)
        potential_filters = {}
        potential_filters["bybaseuuid"] = task.base_uuid
        uuid_version_results = get_task_uuid_n_ver(potential_filters)
        task_list = get_tasks(uuid_version_results)
        for innrcnt, task in enumerate(task_list, start=1):
            due = datetime(int(task.due[0:4]), int(task.due[5:7]),
                           int(task.due[8:])).strftime(FMT_DAY_DATEW)
            table.add_row(task.description, due,style="default")
        if innrcnt > 10:
            continue
        potential_filters = {}
        potential_filters["baseuuidonly"] = task.base_uuid
        uuid_version_results = get_task_uuid_n_ver(potential_filters)
        task_list = get_tasks(uuid_version_results)
        base_task = task_list[0]
        if base_task.recur_end is not None:
            end_dt = (datetime.strptime(base_task.recur_end, FMT_DATEONLY)
                    .date())
        else:
            end_dt = FUTDT
        due_list =  calc_next_inst_date(base_task.recur_mode, 
                                        base_task.recur_when,
                                        datetime.strptime(base_task.due
                                                          ,FMT_DATEONLY),
                                        end_dt,
                                        10 - innrcnt)
        if due_list is not None:
            due_list = [day  for day in due_list if day >= curr_date]
        for day in due_list:
            table.add_row(base_task.description, 
                          day.strftime(FMT_DAY_DATEW),style="default")
        prcsd_baseuuid.append(task.base_uuid)
    if pager:
        with CONSOLE.pager(styles=True):
            CONSOLE.print(table, soft_wrap=True)
    else:
        CONSOLE.print(table, soft_wrap=True)
    return SUCCESS

def display_by_tags(potential_filters, pager=False, top=None):
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    CONSOLE.print("Preparing view...", style="default")
    try:
        tasksubqr = (SESSION.query(Workspace.uuid,
                                Workspace.version,
                                Workspace.area,
                                Workspace.status)
                            .filter(tuple_(Workspace.uuid, Workspace.version)
                                    .in_(uuid_version_results)).subquery())
        
        tags_list = (SESSION.query(WorkspaceTags.tags.label("tags"), 
                                tasksubqr.c.area.label("area"), 
                                tasksubqr.c.status.label("status"),
                                func.count(WorkspaceTags.uuid).label("count"))
                            .join(tasksubqr, and_(WorkspaceTags.uuid 
                                                    == tasksubqr.c.uuid,
                                                WorkspaceTags.version 
                                                    == tasksubqr.c.version))
                            .group_by(WorkspaceTags.tags, tasksubqr.c.area, 
                                    tasksubqr.c.status)
                            .order_by(WorkspaceTags.tags).all())
    except SQLAlchemyError as e:
        CONSOLE.print("Error while trying to print by tags")
        LOGGER.error(str(e))
        return FAILURE
    LOGGER.debug("Total tags to print {}".format(len(tags_list)))
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=False)
    table.add_column("tag", justify="left")
    table.add_column("area", justify="left")
    table.add_column("status", justify="left")
    table.add_column("no. of tasks", justify="left")
    prev_tag = None
    if top is None:
        top = len(tags_list)
    else:
        top = int(top)
    for cnt, tag in enumerate(tags_list, start=1):
        if cnt > top:
            break
        trow = []
        LOGGER.debug(tag.tags + " " + tag.area + " " + tag.status + " " 
                     + str(tag.count))
        if tag.tags == prev_tag:
            trow.append(None)
        else:
            trow.append(tag.tags)
            prev_tag = tag.tags
        trow.append(tag.area)
        trow.append(tag.status)
        trow.append(str(tag.count))
        if tag.status == TASK_STATUS_DONE:
            table.add_row(*trow, style="done")
        elif tag.area == WS_AREA_BIN:
            table.add_row(*trow, style="binn")
        else:
            table.add_row(*trow, style="default")
    if pager:
        with CONSOLE.pager(styles=True):
            CONSOLE.print(table, soft_wrap=True)
    else:
        CONSOLE.print(table, soft_wrap=True)        
    return SUCCESS


def display_default(potential_filters, pager=False, top=None):
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    CONSOLE.print("Preparing view...", style="default")
    #Calculate the task score and write back to database
    #The score is written to the ORM Workspace objects which we then commit
    calc_task_scores(get_tasks(uuid_version_results, expunge=False))
    SESSION.commit()
    curr_day = datetime.now().date()
    tommr = curr_day + relativedelta(days=1)
    try:
        id_xpr = (case([(Workspace.area == WS_AREA_PENDING, Workspace.id),
                        (Workspace.area.in_([WS_AREA_COMPLETED, WS_AREA_BIN]),
                            Workspace.uuid), ]))
        due_xpr = (case([(Workspace.due == None, None), ], 
                        else_=Workspace.due))
        hide_xpr = (case([(Workspace.hide == None, None),], 
                         else_=Workspace.hide))
        groups_xpr = (case([(Workspace.groups == None, None)],
                           else_=Workspace.groups))
        now_flag_xpr = (case([(Workspace.now_flag == True, INDC_NOW), ],
                             else_=""))
        recur_xpr = (case([(Workspace.recur_mode != None, Workspace.recur_mode
                            + " " + func.ifnull(Workspace.recur_when, ""))],
                          else_=None))
        end_xpr = (case([(Workspace.recur_end == None, None)],
                        else_=Workspace.recur_end))
        pri_xpr = (case([(Workspace.priority == PRIORITY_HIGH[0],
                          INDC_PR_HIGH),
                         (Workspace.priority == PRIORITY_MEDIUM[0],
                          INDC_PR_MED),
                         (Workspace.priority == PRIORITY_LOW[0],
                          INDC_PR_LOW)],
                        else_=INDC_PR_NRML))
        score_xpr = (case([(Workspace.area == WS_AREA_PENDING, 
                            Workspace.score),],
                          else_=""))

        # Sub Query for Tags - START
        tags_subqr = (SESSION.query(WorkspaceTags.uuid, WorkspaceTags.version,
                                    func.group_concat(WorkspaceTags.tags, " ")
                                    .label("tags"))
                      .group_by(WorkspaceTags.uuid,
                                WorkspaceTags.version)
                      .subquery())
        # Sub Query for Tags - END
        # Additional information
        addl_info_xpr = (case([(Workspace.area == WS_AREA_COMPLETED,
                                'IS DONE'),
                               (Workspace.area == WS_AREA_BIN,
                                'IS DELETED'),
                               (Workspace.due < curr_day, TASK_OVERDUE),
                               (Workspace.due == curr_day, TASK_TODAY),
                               (Workspace.due == tommr, TASK_TOMMR),
                               (Workspace.due != None,
                                Workspace.due_diff_today + " DAYS"), ],
                              else_=""))
        # Main query
        task_list = (SESSION.query(id_xpr.label("id_or_uuid"),
                                   Workspace.description.label("description"),
                                   addl_info_xpr.label("due_in"),
                                   due_xpr.label("due"),
                                   recur_xpr.label("recur"),
                                   end_xpr.label("end"),
                                   groups_xpr.label("groups"),
                                   case([(tags_subqr.c.tags == None, None), ],
                                        else_=tags_subqr.c.tags).label("tags"),
                                   Workspace.status.label("status"),
                                   pri_xpr.label("priority_flg"),
                                   now_flag_xpr.label("now"),
                                   hide_xpr.label("hide"),
                                   Workspace.version.label("version"),
                                   Workspace.area.label("area"),
                                   Workspace.created.label("created"),
                                   score_xpr.label("score"))
                     .outerjoin(tags_subqr,
                                and_(Workspace.uuid ==
                                     tags_subqr.c.uuid,
                                     Workspace.version ==
                                     tags_subqr.c.version))
                     .filter(tuple_(Workspace.uuid, Workspace.version)
                             .in_(uuid_version_results))
                     .order_by(Workspace.score.desc())
                     .all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return FAILURE

    LOGGER.debug("Task Details for display:\n{}".format(task_list))
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=True)
    # Column and Header Names
    # Only uuid has fxied column width to ensure uuid does not get cropped
    if (task_list[0]).area == WS_AREA_PENDING:
        table.add_column("id", justify="right")
    else:
        table.add_column("uuid", justify="right", width=36)
    table.add_column("description", justify="left")
    table.add_column("due in", justify="right")
    table.add_column("due date", justify="left")
    table.add_column("recur", justify="left")
    table.add_column("end", justify="left")
    table.add_column("groups", justify="right")
    table.add_column("tags", justify="right")
    table.add_column("status", justify="left")
    table.add_column("priority", justify="center")
    table.add_column("now", justify="center")
    table.add_column("hide until", justify="left")
    table.add_column("version", justify="right")
    if(task_list[0].area == WS_AREA_COMPLETED):
        table.add_column("done_date", justify="left")
    elif(task_list[0].area == WS_AREA_BIN):
        table.add_column("deleted_date", justify="left")
    else:
        table.add_column("modifed_date", justify="left")
    table.add_column("score", justify="right")
    if top is None:
        top = len(task_list)
    else:
        top = int(top)
    
    for cnt, task in enumerate(task_list, start=1):
        if cnt > top:
            break
        # Format the dates to
        # YYYY-MM-DD
        # 0:4 - YYYY, 5:7 - MM, 8: - DD
        if task.due is not None:
            due = datetime(int(task.due[0:4]), int(task.due[5:7]),
                           int(task.due[8:])).strftime(FMT_DAY_DATEW)
        else:
            due = ""

        if task.hide is not None:
            hide = datetime(int(task.hide[0:4]), int(task.hide[5:7]),
                            int(task.hide[8:])).strftime(FMT_DAY_DATEW)
        else:
            hide = ""

        if task.end is not None:
            end = datetime(int(task.end[0:4]), int(task.end[5:7]),
                           int(task.end[8:])).strftime(FMT_DAY_DATEW)
        else:
            end = ""
        # YYYY-MM-DD HH:MM
        # 0:4 - YYYY, 5:7 - MM, 8:10 - DD, 11:13 - HH, 14: - MM
        created = datetime(int(task.created[0:4]), int(task.created[5:7]),
                           int(task.created[8:10]), int(task.created[11:13]),
                           int(task.created[14:])).strftime(FMT_DATEW_TIME)
        # Create a list to print
        trow = [str(task.id_or_uuid), task.description, task.due_in, due,
                task.recur, end, task.groups, task.tags, task.status,
                task.priority_flg, task.now, hide, str(task.version), created,
                str(task.score)]
                #str(score_dict.get(task.uuid))]
        # Next Display the tasks with formatting based on various conditions
        if task.status == TASK_STATUS_DONE:
            table.add_row(*trow, style="done")
        elif task.area == WS_AREA_BIN:
            table.add_row(*trow, style="binn")
        elif task.due_in == TASK_OVERDUE:
            table.add_row(*trow, style="overdue")
        elif task.due_in == TASK_TODAY:
            table.add_row(*trow, style="today")
        elif task.status == TASK_STATUS_STARTED:
            table.add_row(*trow, style="started")
        elif task.now == INDC_NOW:
            table.add_row(*trow, style="now")
        else:
            table.add_row(*trow, style="default")

    # Print a legend on the indicators used for priority and now
    grid = RichTable.grid(padding=3)
    grid.add_column(style="overdue", justify="center")
    grid.add_column(style="today", justify="center")
    grid.add_column(style="started", justify="center")
    grid.add_column(style="now", justify="center")
    grid.add_column(style="done", justify="center")
    grid.add_column(style="binn", justify="center")
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_row("OVERDUE", "TODAY", "STARTED", "NOW", "DONE", "BIN",
                 INDC_PR_HIGH + " High Priority",
                 INDC_PR_MED + " Medium Priority",
                 INDC_PR_LOW + " Low Priority",
                 INDC_NOW + " Now Task")

    if pager:
        with CONSOLE.pager(styles=True):
            CONSOLE.print(table, soft_wrap=True)
            CONSOLE.print(grid, justify="right")
    else:
        CONSOLE.print(table, soft_wrap=True)
        CONSOLE.print(grid, justify="right")

    print_dict = {}
    print_dict[PRNT_CURR_VW_CNT] = len(task_list)
    print_dict[WS_AREA_PENDING] = "yes"
    if potential_filters.get(TASK_DONE) == "yes":
        print_dict[WS_AREA_COMPLETED] = "yes"
    elif potential_filters.get(TASK_BIN) == "yes":
        print_dict[WS_AREA_BIN] = "yes"
    get_and_print_task_count(print_dict)
    return SUCCESS

def calc_task_scores(task_list):
    """
    Assigns a score for tasks based on the below task properties. Each property
    has a weight assigned to it. The final score for the task is then written
    back to the Workspace object.
    
    Now - Yes then 100 else 0. Weight of 15
    Priority - High, Medium, Normal, Low - 100, 75, 
    """
    ret_task_list = []
    sc_now = {1:100}
    sc_priority = {PRIORITY_HIGH[0]:100, PRIORITY_MEDIUM[0]:75, 
                   PRIORITY_NORMAL[0]:50, PRIORITY_LOW[0]:20}
    sc_status = {TASK_STATUS_STARTED:100, TASK_STATUS_TODO:75}
    sc_groups = {"yes":100}
    sc_tags = {"yes":100}
    sc_due = {"today":100, "past":110, "fut":90}
    weights = {"now":15, "due":45, "priority":15, "status":15, "inception":8,
               "groups":1,"tags":1}
    curr_day = datetime.now().date()
    fut_sum = 0
    due_sum = 0
    incep_sum = 0
    for task in task_list:
        if task.due is not None:
            #For Due scoring
            due_sum = (due_sum + abs(task.due_diff_today))  
        #For inception scoring
        incep_sum = (incep_sum + task.incep_diff_today)
    for task in task_list:
        tags = get_tags(task.uuid, task.version, expunge=False)
        score = 0
        #Now
        score = score + ((sc_now.get(task.now_flag) or 0)) * weights.get("now")
        #Priority
        score = (score + ((sc_priority.get(task.priority) or 0))
                            * weights.get("priority"))
        #Status
        score = (score + ((sc_status.get(task.status) or 0))
                            * weights.get("status"))
        #Groups
        if task.groups:
            score = score + (sc_groups.get("yes")) * weights.get("groups")
        #Tags
        if tags:
            score = score + (sc_tags.get("yes")) * weights.get("tags")
        #Inception
        print(task.incep_diff_today)
        score = (score + (sc_due.get("today") * int(task.incep_diff_today)
                            /incep_sum)
                         * weights.get("inception"))
        #Due
        if task.due is not None:
            if int(task.due_diff_today) == 0:
                score = score + (sc_due.get("today")) * weights.get("due")
            elif int(task.due_diff_today) < 0:
                score = (score + (sc_due.get("today")
                                  + (sc_due.get("past")
                                     *int(task.due_diff_today)/due_sum))
                         * weights.get("due"))
            else:
                score = (score + (sc_due.get("today")
                                  - (sc_due.get("fut")
                                     *int(task.due_diff_today)/due_sum))
                         * weights.get("due"))
        task.score = round(score/100,2)
        ret_task_list.append(task)
    return ret_task_list
    
def get_and_print_task_count(print_dict):
    # Print Task Details
    if print_dict.get(PRNT_TASK_DTLS):
        task_tags_list = print_dict.get(PRNT_TASK_DTLS)
        for item in task_tags_list:
            ws_task = item[0]
            tags_str = item[1]
            with CONSOLE.capture() as capture:
                if ws_task.task_type != TASK_TYPE_BASE:
                    if ws_task.id == '-':
                        """
                        Using a context manager to capture output from print 
                        and pass it onto click's echo for the pytests to 
                        receive the input. This is done only where the output 
                        is required for pytest. CONSOLE.print gives a simpler 
                        management of coloured printing compared to click's 
                        echo. Suppress the newline for echo to ensure double 
                        line breaks are not printed, 1 from print and another 
                        from echo.
                        """
                        CONSOLE.print("Updated Task UUID: "
                                      "[magenta]{}[/magenta]"
                                      .format(ws_task.uuid), style="info")
                    else:
                        CONSOLE.print("Added/Updated Task ID: "
                                      "[magenta]{}[/magenta]"
                                      .format(ws_task.id), style="info")
                    if not tags_str:
                        tags_str = "-..."
                    reflect_object_n_print(
                        ws_task, to_print=True, print_all=False)
                    CONSOLE.print("tags : [magenta]{}[/magenta]"
                                  .format(tags_str[1:]), style="info")
                else:
                    CONSOLE.print("Recurring task add/updated from "
                                  "[magenta]{}[/magenta] "
                                  "until [magenta]{}[/magenta] for "
                                  "recurrence type [magenta]{}-{}[/magenta]"
                                  .format(ws_task.due, ws_task.recur_end,
                                          ws_task.recur_mode, 
                                          ws_task.recur_when),
                                  style="info")
            click.echo(capture.get(), nl=False)
            CONSOLE.print("--")
            LOGGER.debug("Added/Updated Task UUID: {} and Area: {}"
                         .format(ws_task.uuid, ws_task.area))
    # Print No. of Tasks Displayed in the view
    if print_dict.get(PRNT_CURR_VW_CNT):
        with CONSOLE.capture() as capture:
            CONSOLE.print(("Displayed Tasks: [magenta]{}[/magenta]"
                           .format(print_dict.get(PRNT_CURR_VW_CNT))),
                          style="info")
        click.echo(capture.get(), nl=False)

    # Print Pending, Complted and Bin Tasks
    curr_day = datetime.now()
    try:
        # Pending Tasks
        if print_dict.get(WS_AREA_PENDING) == "yes":
            # Get count of pending tasks split by HIDDEN and VISIBLE
            # Build case expression separately to simplify readability
            visib_xpr = (case([(and_(Workspace.hide > curr_day.date(),
                                    Workspace.hide != None),
                               "HIDDEN"), ], else_="VISIBLE")
                         .label("VISIBILITY"))
            # Inner query to match max version for a UUID
            max_ver_xpr = (SESSION.query(Workspace.uuid,
                                         func.max(Workspace.version)
                                         .label("maxver"))
                           .group_by(Workspace.uuid).subquery())
            # Final Query
            results_pend = (SESSION.query(visib_xpr,
                                          func.count(distinct(Workspace.uuid))
                                          .label("CNT"))
                            .join(max_ver_xpr, Workspace.uuid ==
                                  max_ver_xpr.c.uuid)
                            .filter(and_(Workspace.area ==
                                         WS_AREA_PENDING,
                                         Workspace.version ==
                                         max_ver_xpr.c.maxver,
                                         Workspace.task_type.in_(
                                             [TASK_TYPE_NRML,
                                              TASK_TYPE_DRVD])))
                            .group_by(visib_xpr)
                            .all())
            LOGGER.debug("Pending: {}".format(results_pend))
            """
            VISIBILITY | CNT
            ----------   ---
            VISIBLE    |  3
            HIDDEN     |  2
            """
            total = 0
            vis = 0
            hid = 0
            if results_pend:
                for r in results_pend:
                    if r[0] == "HIDDEN":
                        hid = r[1]
                    elif r[0] == "VISIBLE":
                        vis = r[1]
                total = vis + hid
            with CONSOLE.capture() as capture:
                if print_dict.get(WS_AREA_PENDING) == "yes":
                    CONSOLE.print("Total Pending Tasks: "
                                  "[magenta]{}[/magenta], "
                                  "of which Hidden: "
                                  "[magenta]{}[/magenta]"
                                  .format(total, hid), style="info")
            click.echo(capture.get(), nl=False)
        # Completed Tasks
        if print_dict.get(WS_AREA_COMPLETED) == "yes":
            # Get count of completed tasks
            # Inner query to match max version for a UUID
            max_ver2_xpr = (SESSION.query(Workspace.uuid,
                                          func.max(Workspace.version)
                                          .label("maxver"))
                            .filter(Workspace.area != WS_AREA_COMPLETED)
                            .group_by(Workspace.uuid).subquery())
            # Final Query
            results_compl = (SESSION.query(func.count(distinct(Workspace.uuid))
                                           .label("CNT"))
                                    .join(max_ver2_xpr, Workspace.uuid ==
                                          max_ver2_xpr.c.uuid)
                                    .filter(and_(Workspace.area ==
                                                 WS_AREA_COMPLETED,
                                                 Workspace.version >
                                                 max_ver2_xpr.c.maxver))
                                    .all())
            LOGGER.debug("Completed: {}".format(results_compl))
            compl = (results_compl[0])[0]
            with CONSOLE.capture() as capture:
                CONSOLE.print("Total Completed tasks: [magenta]{}[/magenta]"
                              .format(compl), style="info")
            click.echo(capture.get(), nl=False)
        # Bin Tasks
        if print_dict.get(WS_AREA_BIN) == "yes":
            # Get count of tasks in bin
            # Inner query to match max version for a UUID
            max_ver3_xpr = (SESSION.query(Workspace.uuid,
                                          func.max(Workspace.version)
                                          .label("maxver"))
                            .filter(Workspace.area != WS_AREA_BIN)
                            .group_by(Workspace.uuid).subquery())
            # Final Query
            results_bin = (SESSION.query(func.count(distinct(Workspace.uuid))
                                         .label("CNT"))
                           .join(max_ver3_xpr, Workspace.uuid ==
                                 max_ver3_xpr.c.uuid)
                           .filter(and_(Workspace.area == WS_AREA_BIN,
                                        Workspace.version 
                                            > max_ver3_xpr.c.maxver))
                           .all())
            LOGGER.debug("Bin: {}".format(results_bin))
            binn = (results_bin[0])[0]
            with CONSOLE.capture() as capture:
                CONSOLE.print("Total tasks in Bin: [magenta]{}[/magenta]"
                              .format(binn), style="info")
            click.echo(capture.get(), nl=False)

    except SQLAlchemyError as e:
        LOGGER.error(str(e))
    return


def derive_task_id():
    """Get next available task ID from pending area in the workspace"""
    try:
        results = (SESSION.query(Workspace.id)
                          .filter(and_(Workspace.area == WS_AREA_PENDING,
                                       Workspace.id != '-',
                                       Workspace.task_type
                                                .in_([TASK_TYPE_NRML,
                                                      TASK_TYPE_DRVD])))
                          .all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return None

    LOGGER.debug("Returned list of task IDs {}".format(results))
    id_list = [row[0] for row in results]
    id_list.insert(0, 0)
    id_list.sort()
    available_list = sorted(set(range(id_list[0], id_list[-1]))-set(id_list))
    if not available_list:  # If no tasks exist/no available intermediate seq
        return id_list[-1] + 1
    return available_list[0]


def get_task_uuid_n_ver(potential_filters):
    """
    Return task UUID and version by applying filters on tasks

    Using a list of filters identify the relevant task UUIDs and their
    latest versions. The filters come in the form of a dictionary and
    expected keys include:
        - For all pending - Default when non filter provided
        - Overdue Tasks - Works only on pending
        - Tasks due today - Works only on pending
        - Hidden Tasks - Works only on pending
        - Done Tasks - Works only on completed
        - Started tasks - Works only on pending
        - Now task - Works only on pending
        - Task in Bin - Works only on tasks in the bin
        - Task id based filters - Works only on pending
        - Task group based filters - Works in pending, completed or bin
        - Task tags based filters - Works in pending, completed or bin
    No validations are performed on the filters. Using the priority set 
    in function the filters are applied onto the tasks table.
    As multiple filters can be provided, priority is followed as below.
    Filters indicated with numbers are mutually exclusive.
        1. No Filters - Decision is made in parse_filters function
                        to be more efficient
        2. IDs for Pending tasks only
        3. NOW task
        4. Outstanding Recurring Tasks (Not User Callable)
        5. UUIDs Based
            5.1 For Completed or Bin tasks only
            5.2 Derived Tasks with the base uuid (Not User Callable)
            5.3 Base Task with baseuuid (Not User Callable)
        6. Groups, Tags. Description, Due
            a. Overdue, Today, Hidden, Started
            b. Done tasks
            c. Bin Tasks
            d. Defaults to all Pending Tasks

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters
        area(str): Area from which the tasks have to be retrieved
                   Default - 'pending'

    Returns:
        list: List of tuples of (task UUID,Version) or None if there
              is an exception or no results found

    """
    
    """
    The filters work  by running an intersect across all applicable filters.
    For ex. if the ask is to filter where group is 'HOME' in the completed
    area then it will run the query as 
    all tasks where group like 'HOME%'
    INTERSECT
    all tasks in the 'completed' area 
    """
    LOGGER.debug("Incoming Filters: ")
    LOGGER.debug(potential_filters)
    innrqr_list = []
    all_tasks = potential_filters.get(TASK_ALL)
    overdue_task = potential_filters.get(TASK_OVERDUE)
    today_task = potential_filters.get(TASK_TODAY)
    hidden_task = potential_filters.get(TASK_HIDDEN)
    done_task = potential_filters.get(TASK_DONE)
    bin_task = potential_filters.get(TASK_BIN)
    started_task = potential_filters.get(TASK_STARTED)
    now_task = potential_filters.get(TASK_NOW)
    idn = potential_filters.get("id")
    uuidn = potential_filters.get("uuid")
    group = potential_filters.get("group")
    tag = potential_filters.get("tag")
    desc = potential_filters.get("desc")
    due_list = potential_filters.get("due")
    hide_list = potential_filters.get("hide")
    end_list = potential_filters.get("end")
    bybaseuuid = potential_filters.get("bybaseuuid")
    baseuuidonly = potential_filters.get("baseuuidonly")
    osrecur = potential_filters.get("osrecur")
    curr_date = datetime.now().date()
    # Inner query to match max version for a UUID
    max_ver_xpr = (SESSION.query(Workspace.uuid,
                                 func.max(Workspace.version)
                                 .label("maxver"))
                   .filter(Workspace.task_type.in_([TASK_TYPE_DRVD,
                                                    TASK_TYPE_NRML]))
                   .group_by(Workspace.uuid).subquery())
    
    if all_tasks:
        """
        When no filter is provided retrieve all tasks from pending area
        """
        LOGGER.debug("Inside all_tasks filter")
        try:
            results = (SESSION.query(Workspace.uuid, Workspace.version)
                       .join(max_ver_xpr, and_(Workspace.version ==
                                               max_ver_xpr.c.maxver,
                                               Workspace.uuid ==
                                               max_ver_xpr.c.uuid))
                       .filter(and_(Workspace.area == WS_AREA_PENDING,
                                    or_(Workspace.hide <= curr_date,
                                        Workspace.hide == None)))
                       .all())
        except (SQLAlchemyError) as e:
            LOGGER.error(str(e))
            return None
        else:
            LOGGER.debug("List of resulting Task UUIDs and Versions:")
            LOGGER.debug("------------- {}".format(results))
            return results
    elif idn is not None:
        """
        If id(s) is provided extract tasks only based on ID as it is most 
        specific. Works only in pending area
        """
        id_list = idn.split(",")
        LOGGER.debug("Inside id filter with below params")
        LOGGER.debug(id_list)
        try:
            results = (SESSION.query(Workspace.uuid, Workspace.version)
                       .join(max_ver_xpr, and_(Workspace.version ==
                                               max_ver_xpr.c.maxver,
                                               Workspace.uuid ==
                                               max_ver_xpr.c.uuid))
                       .filter(and_(Workspace.area == WS_AREA_PENDING,
                                    Workspace.id.in_(id_list)))
                       .all())
        except (SQLAlchemyError) as e:
            LOGGER.error(str(e))
            return None
        else:
            LOGGER.debug("List of resulting Task UUIDs and Versions:")
            LOGGER.debug("------------- {}".format(results))
            return results
    elif now_task is not None:
        """
        If now task filter then return the task marked as now_flag = True from 
        pending area
        """
        LOGGER.debug("Inside now filter")
        try:
            results = (SESSION.query(Workspace.uuid, Workspace.version)
                       .filter(and_(Workspace.area == WS_AREA_PENDING,
                                    Workspace.now_flag == True,
                                    Workspace.id != '-',
                                    Workspace.task_type
                                    .in_([TASK_TYPE_DRVD,
                                          TASK_TYPE_NRML])))
                       .all())
        except (SQLAlchemyError) as e:
            LOGGER.error(str(e))
            return None
        else:
            LOGGER.debug("List of resulting Task UUIDs and Versions:")
            LOGGER.debug("------------- {}".format(results))
            return results
    elif osrecur is not None:
        LOGGER.debug("Inside Outstanding Recurring Tasks filter")
        try:
            max_ver_xpr1 = (SESSION.query(Workspace.uuid,
                                          func.max(Workspace.version)
                                          .label("maxver"))
                            .filter(and_(Workspace.task_type == TASK_TYPE_BASE,
                                         Workspace.area == WS_AREA_PENDING))
                            .group_by(Workspace.uuid).subquery())
            results = (SESSION.query(Workspace.uuid, Workspace.version)
                       .join(max_ver_xpr1,
                             and_(Workspace.version ==
                                  max_ver_xpr1.c.maxver,
                                  Workspace.uuid ==
                                  max_ver_xpr1.c.uuid))
                       .filter(and_(Workspace.area == WS_AREA_PENDING,
                                    Workspace.id == '*',
                                    Workspace.task_type ==
                                    TASK_TYPE_BASE,
                                    or_(Workspace.recur_end == None,
                                        Workspace.recur_end >=
                                        curr_date)))
                       .all())
        except (SQLAlchemyError) as e:
            LOGGER.error(str(e))
            return None
        else:
            LOGGER.debug("List of resulting Task UUIDs and Versions:")
            LOGGER.debug("------------- {}".format(results))
            return results
    else:
        """
        Filter provided is not a ID, so try to get task list from 
        combination of other filters provided by user
        Preference given to UUID filter which can be used in combination
        with area modifiers of DONE and BIN
        """
        if uuidn is not None:
            """
            If uuid(s) is provided extract tasks only based on UUID as 
            it is most specific. Works only in completed or bin area
            """
            uuid_list = uuidn.split(",")
            LOGGER.debug("Inside UUID filter with below params")
            LOGGER.debug(uuid_list)
            innrqr_uuid = (SESSION.query(Workspace.uuid, Workspace.version)
                           .join(max_ver_xpr, and_(Workspace.version ==
                                                   max_ver_xpr.c.maxver,
                                                   Workspace.uuid ==
                                                   max_ver_xpr.c.uuid))
                           .filter(Workspace.uuid.
                                   in_(uuid_list)))
            innrqr_list.append(innrqr_uuid)
        elif bybaseuuid is not None:
            LOGGER.debug("Inside By Base UUID filter with below params")
            LOGGER.debug(bybaseuuid)
            max_ver_xpr = (SESSION.query(Workspace.uuid,
                                         func.max(Workspace.version)
                                         .label("maxver"))
                           .filter(Workspace.task_type.in_([TASK_TYPE_DRVD]))
                           .group_by(Workspace.uuid).subquery())
            innrqr_buuid = (SESSION.query(Workspace.uuid, Workspace.version)
                            .join(max_ver_xpr, and_(Workspace.version ==
                                                    max_ver_xpr.c.maxver,
                                                    Workspace.uuid ==
                                                    max_ver_xpr.c.uuid))
                            .filter(and_(Workspace.task_type ==
                                         TASK_TYPE_DRVD,
                                         Workspace.base_uuid == bybaseuuid)))
            innrqr_list.append(innrqr_buuid)
        elif baseuuidonly is not None:
            LOGGER.debug("Inside Base UUID Only filter with below params")
            LOGGER.debug(baseuuidonly)
            max_ver_xpr = (SESSION.query(Workspace.uuid,
                                         func.max(Workspace.version)
                                         .label("maxver"))
                           .filter(Workspace.task_type == TASK_TYPE_BASE)
                           .group_by(Workspace.uuid).subquery())
            innrqr_buuido = (SESSION.query(Workspace.uuid, Workspace.version)
                             .join(max_ver_xpr, and_(Workspace.version ==
                                                     max_ver_xpr.c.maxver,
                                                     Workspace.uuid ==
                                                     max_ver_xpr.c.uuid))
                             .filter(and_(Workspace.task_type == TASK_TYPE_BASE,
                                          Workspace.uuid == baseuuidonly)))
            innrqr_list.append(innrqr_buuido)
        else:
            if group is not None:
                """
                Query to get a list of uuid and version for matchiing groups
                from all 3 areas. Will be case insensitive
                """
                LOGGER.debug("Inside group filter with below params")
                LOGGER.debug(group + "%")
                innrqr_groups = (SESSION.query(Workspace.uuid,
                                               Workspace.version)
                                 .join(max_ver_xpr,
                                       and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                 .filter(Workspace.groups.like(group+"%")))
                innrqr_list.append(innrqr_groups)
            if tag is not None:
                """
                Query to get a list of uuid and version for matchiing tags
                from all 3 areas
                """
                tag_list = tag.split(",")
                LOGGER.debug("Inside tag filter with below params")
                LOGGER.debug(tag_list)
                if tag:
                    #If tag is provided search by tag
                    innrqr_tags = (SESSION.query(WorkspaceTags.uuid,
                                                WorkspaceTags.version)
                                .join(max_ver_xpr,
                                        and_(WorkspaceTags.version ==
                                            max_ver_xpr.c.maxver,
                                            WorkspaceTags.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(WorkspaceTags.tags.
                                        in_(tag_list)))
                else:
                    #No tag provided, so any task that has a tag
                    innrqr_tags = (SESSION.query(WorkspaceTags.uuid,
                                                WorkspaceTags.version)
                                .join(max_ver_xpr,
                                        and_(WorkspaceTags.version ==
                                            max_ver_xpr.c.maxver,
                                            WorkspaceTags.uuid ==
                                            max_ver_xpr.c.uuid)))
                innrqr_list.append(innrqr_tags)
            if desc is not None:
                """
                Query to get a list of uuid and version for tasks which match
                the description as a substring. Will be case insensitive
                """
                LOGGER.debug("Inside description filter with below params")
                LOGGER.debug("%" + desc + "%")
                innrqr_desc = (SESSION.query(Workspace.uuid,
                                               Workspace.version)
                                 .join(max_ver_xpr,
                                       and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                 .filter(Workspace.description
                                            .like("%"+desc+"%")))
                innrqr_list.append(innrqr_desc)
            if due_list is not None and due_list[0] is not None:
                """
                Query to get a list of uuid and version for tasks which meet
                the due date filters provided
                """
                LOGGER.debug("Inside due filter with below params")
                LOGGER.debug(due_list)
                if due_list[0] == "eq":
                    #If tag is provided search by tag
                    innrqr_due = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.due == due_list[1]))
                elif due_list[0] == "gt":
                    innrqr_due = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.due > due_list[1]))
                elif due_list[0] == "ge":
                    innrqr_due = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.due >= due_list[1]))   
                elif due_list[0] == "lt":
                    innrqr_due = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.due < due_list[1]))
                elif due_list[0] == "le":
                    innrqr_due = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.due <= due_list[1]))
                elif due_list[0] == "bt":
                    innrqr_due = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                            .join(max_ver_xpr,
                                            and_(Workspace.version ==
                                                max_ver_xpr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_xpr.c.uuid))
                                            .filter(and_(Workspace.due >= 
                                                        due_list[1],
                                                        Workspace.due <= 
                                                        due_list[2])))
                else:
                    #No valid due filter, so any task that has a due date
                    innrqr_due = (SESSION.query(Workspace.uuid,
                                                Workspace.version)
                                    .join(max_ver_xpr,
                                        and_(Workspace.version ==
                                                max_ver_xpr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_xpr.c.uuid))
                                    .filter(Workspace.due != None))
                innrqr_list.append(innrqr_due) 
            if hide_list is not None and hide_list[0] is not None:
                """
                Query to get a list of uuid and version for tasks which meet
                the hide date filters provided
                """
                LOGGER.debug("Inside hdie filter with below params")
                LOGGER.debug(hide_list)
                if hide_list[0] == "eq":
                    #If tag is provided search by tag
                    innrqr_hide = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.hide == hide_list[1]))
                elif hide_list[0] == "gt":
                    innrqr_hide = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.hide > hide_list[1]))
                elif hide_list[0] == "ge":
                    innrqr_hide = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.hide >= hide_list[1]))   
                elif hide_list[0] == "lt":
                    innrqr_hide = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.hide < hide_list[1]))
                elif hide_list[0] == "le":
                    innrqr_hide = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_xpr,
                                    and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                .filter(Workspace.hide <= hide_list[1]))
                elif hide_list[0] == "bt":
                    innrqr_hide = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                            .join(max_ver_xpr,
                                            and_(Workspace.version ==
                                                max_ver_xpr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_xpr.c.uuid))
                                            .filter(and_(Workspace.hide >= 
                                                        hide_list[1],
                                                        Workspace.hide <= 
                                                        hide_list[2])))
                else:
                    #No valid hide filter, so any task that has a hide date
                    innrqr_hide = (SESSION.query(Workspace.uuid,
                                                Workspace.version)
                                    .join(max_ver_xpr,
                                        and_(Workspace.version ==
                                                max_ver_xpr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_xpr.c.uuid))
                                    .filter(Workspace.hide != None))
                innrqr_list.append(innrqr_hide)
            if end_list is not None and end_list[0] is not None:
                """
                Query to get a list of uuid and version for tasks which meet
                the recur end date filters provided
                """                
                LOGGER.debug("Inside recur end filter with below params")
                LOGGER.debug(end_list)
                if end_list[0] == "eq":
                    #If tag is provided search by tag
                    innrqr_end = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                            .join(max_ver_xpr,
                                                and_(Workspace.version ==
                                                        max_ver_xpr.c.maxver,
                                                    Workspace.uuid ==
                                                        max_ver_xpr.c.uuid))
                                            .filter(Workspace.recur_end == 
                                                    end_list[1]))
                elif end_list[0] == "gt":
                    innrqr_end = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                        .join(max_ver_xpr,
                                            and_(Workspace.version ==
                                                    max_ver_xpr.c.maxver,
                                                    Workspace.uuid ==
                                                    max_ver_xpr.c.uuid))
                                        .filter(Workspace.recur_end > 
                                                    end_list[1]))
                elif end_list[0] == "ge":
                    innrqr_end = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                        .join(max_ver_xpr,
                                            and_(Workspace.version ==
                                                    max_ver_xpr.c.maxver,
                                                    Workspace.uuid ==
                                                    max_ver_xpr.c.uuid))
                                        .filter(Workspace.recur_end >= 
                                                    end_list[1]))   
                elif end_list[0] == "lt":
                    innrqr_end = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                        .join(max_ver_xpr,
                                            and_(Workspace.version ==
                                                    max_ver_xpr.c.maxver,
                                                    Workspace.uuid ==
                                                    max_ver_xpr.c.uuid))
                                        .filter(Workspace.recur_end < 
                                                    end_list[1]))
                elif end_list[0] == "le":
                    innrqr_end = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                        .join(max_ver_xpr,
                                            and_(Workspace.version ==
                                                    max_ver_xpr.c.maxver,
                                                    Workspace.uuid ==
                                                    max_ver_xpr.c.uuid))
                                        .filter(Workspace.recur_end <= 
                                                    end_list[1]))
                elif end_list[0] == "bt":
                    innrqr_end = (SESSION.query(Workspace.uuid,
                                                        Workspace.version)
                                            .join(max_ver_xpr,
                                            and_(Workspace.version ==
                                                max_ver_xpr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_xpr.c.uuid))
                                            .filter(and_(Workspace.recur_end 
                                                    >= end_list[1],
                                                    Workspace.recur_end 
                                                    <= end_list[2])))
                else:
                    #No valid recur end filter, so any task that has a 
                    #recur end date
                    innrqr_end = (SESSION.query(Workspace.uuid,
                                                Workspace.version)
                                    .join(max_ver_xpr,
                                        and_(Workspace.version ==
                                                max_ver_xpr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_xpr.c.uuid))
                                    .filter(Workspace.recur_end != None))
                innrqr_list.append(innrqr_end)
        """
        Look for modifiers that work in the pending area
        """
        LOGGER.debug("Status for OVERDUE {}, TODAY {}, HIDDEN {}, STARTED{}"
                     .format(overdue_task, today_task, hidden_task,
                             started_task))
        if (overdue_task is not None or today_task is not None or
                hidden_task is not None or started_task is not None):
            if overdue_task is not None:
                LOGGER.debug("Inside overdue filter")
                innrqr_overdue = (SESSION.query(Workspace.uuid,
                                                Workspace.version)
                                  .join(max_ver_xpr,
                                        and_(Workspace.version ==
                                             max_ver_xpr.c.maxver,
                                             Workspace.uuid ==
                                             max_ver_xpr.c.uuid))
                                  .filter(and_(Workspace.area ==
                                               WS_AREA_PENDING,
                                               Workspace.due < curr_date,
                                               or_(Workspace.hide <=
                                                   curr_date,
                                                   Workspace.hide ==
                                                   None))))
                innrqr_list.append(innrqr_overdue)
            if today_task is not None:
                LOGGER.debug("Inside today filter")
                innrqr_today = (SESSION.query(Workspace.uuid,
                                              Workspace.version)
                                .join(max_ver_xpr,
                                      and_(Workspace.version ==
                                           max_ver_xpr.c.maxver,
                                           Workspace.uuid ==
                                           max_ver_xpr.c.uuid))
                                .filter(and_(Workspace.area ==
                                             WS_AREA_PENDING,
                                             Workspace.due == curr_date,
                                             or_(Workspace.hide <=
                                                 curr_date,
                                                 Workspace.hide ==
                                                 None))))
                innrqr_list.append(innrqr_today)
            if hidden_task is not None:
                LOGGER.debug("Inside hidden filter")
                innrqr_hidden = (SESSION.query(Workspace.uuid,
                                               Workspace.version)
                                 .join(max_ver_xpr,
                                       and_(Workspace.version ==
                                            max_ver_xpr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_xpr.c.uuid))
                                 .filter(and_(Workspace.area ==
                                              WS_AREA_PENDING,
                                              and_(Workspace.hide >
                                                   curr_date,
                                                   Workspace.hide !=
                                                   None))))
                innrqr_list.append(innrqr_hidden)
            if started_task is not None:
                LOGGER.debug("Inside started filter")
                innrqr_started = (SESSION.query(Workspace.uuid,
                                                Workspace.version)
                                  .join(max_ver_xpr,
                                        and_(Workspace.version ==
                                             max_ver_xpr.c.maxver,
                                             Workspace.uuid ==
                                             max_ver_xpr.c.uuid))
                                  .filter(and_(Workspace.area ==
                                               WS_AREA_PENDING,
                                               Workspace.status ==
                                               TASK_STATUS_STARTED
                                               )))
                innrqr_list.append(innrqr_started)
        elif done_task is not None:
            """
            If none of the pending area modifiers are given look for other 
            modifiers. Preference is given to DONE over BIN and they are 
            mutually exclusive
            """
            # Get all completed tasks
            LOGGER.debug("Inside done filter")
            max_ver_xpr2 = (SESSION.query(Workspace.uuid,
                                          func.max(Workspace.version)
                                          .label("maxver"))
                            .filter(Workspace.area !=
                                    WS_AREA_COMPLETED)
                            .group_by(Workspace.uuid).subquery())
            innrqr_done = (SESSION.query(Workspace.uuid, Workspace.version)
                           .join(max_ver_xpr2,
                                 and_(Workspace.uuid ==
                                      max_ver_xpr2.c.uuid,
                                      Workspace.version >
                                      max_ver_xpr2.c.maxver))
                           .filter(Workspace.area ==
                                   WS_AREA_COMPLETED))
            innrqr_list.append(innrqr_done)
        elif bin_task is not None:
            # Get all tasks in the bin
            LOGGER.debug("Inside bin filter")
            max_ver_xpr3 = (SESSION.query(Workspace.uuid,
                                          func.max(Workspace.version)
                                          .label("maxver"))
                            .filter(Workspace.area != WS_AREA_BIN)
                            .group_by(Workspace.uuid).subquery())
            innrqr_bin = (SESSION.query(Workspace.uuid, Workspace.version)
                          .join(max_ver_xpr3,
                                and_(Workspace.uuid ==
                                     max_ver_xpr3.c.uuid,
                                     Workspace.version >
                                     max_ver_xpr3.c.maxver))
                          .filter(Workspace.area ==
                                  WS_AREA_BIN))
            innrqr_list.append(innrqr_bin)
        else:
            """
            If no modifiers provided then default to tasks in pending area
            Ensure this query is the same as that used in the default for
            all_tasks
            """
            LOGGER.debug("Inside default filter")
            innrqr_all = (SESSION.query(Workspace.uuid, Workspace.version)
                          .join(max_ver_xpr,
                                and_(Workspace.version ==
                                     max_ver_xpr.c.maxver,
                                     Workspace.uuid ==
                                     max_ver_xpr.c.uuid))
                          .filter(and_(Workspace.area ==
                                       WS_AREA_PENDING,
                                  or_(Workspace.hide <= curr_date,
                                        Workspace.hide == None))))
            innrqr_list.append(innrqr_all)
        if innrqr_list is None:
            return None
    try:
        # Tuple of rows, UUID,Version
        firstqr = innrqr_list.pop(0)
        results = firstqr.intersect(*innrqr_list).all()
    except (SQLAlchemyError) as e:
        LOGGER.error(str(e))
        return None
    else:
        LOGGER.debug("List of resulting Task UUIDs and Versions:")
        LOGGER.debug("------------- {}".format(results))
        return results


def get_task_new_version(task_uuid):
    try:
        results = (SESSION.query(func.max(Workspace.version))
                          .filter(Workspace.uuid == task_uuid).all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return None

    LOGGER.debug("Returned Version {} for UUID {}".format(results, task_uuid))
    if (results[0])[0] is not None:  # Tasks exists so increment version
        LOGGER.debug("Task exists, so incrementing version")
        return (results[0][0]) + 1
    else:   # New task so return 1
        LOGGER.debug("Task does not exist, so returning 1")
        return "1"


def translate_priority(priority):
    """
    Determine if the priority requested is valid and accordingly return
    the right domain value as below. If the priority is not a valid priority
    it defaults to Nomral priority.

        High - High, H, h
        Medium - Medium, M, m
        Low - Low, L, l
        Normal - Normal, N, n (This is the default)

    Parameters:
        priority(str): Priority to translate

    Returns:
        priority(str): Priority as a valid domain value
    """
    if priority in PRIORITY_HIGH:
        return PRIORITY_HIGH[0]
    if priority in PRIORITY_MEDIUM:
        return PRIORITY_MEDIUM[0]
    if priority in PRIORITY_LOW:
        return PRIORITY_LOW[0]
    if priority in PRIORITY_NORMAL:
        return PRIORITY_NORMAL[0]
    else:
        return PRIORITY_NORMAL[0]


def reflect_object_n_print(src_object, to_print=False, print_all=False):
    if src_object is None:
        return "-"
    out_str = ""
    """
    For debug(when to_print=False) retain a None value and while printing 
    for user info(to_print=True) use an empty string to make it more readable.
    """
    dummy = "..."
    inst = inspect(src_object)
    attr_names = [c_attr.key for c_attr in inst.mapper.column_attrs]
    if not print_all:
        for attr in attr_names:
            if attr in PRINT_ATTR:
                with CONSOLE.capture() as capture:
                    CONSOLE.print("{} : [magenta]{}[/magenta]"
                                  .format(attr, (getattr(src_object, attr)
                                                 or dummy)),
                                  style="info")
                out_str = out_str + capture.get()
    elif print_all:
        for attr in attr_names:
            with CONSOLE.capture() as capture:
                CONSOLE.print("{} : [magenta]{}[/magenta]"
                              .format(attr, (getattr(src_object, attr)
                                             or dummy)),
                              style="info")
            out_str = out_str + capture.get()
    if to_print:
        click.echo(out_str, nl=False)
        return
    else:
        return out_str


def prep_recurring_tasks(ws_task_src, ws_tags_list, add_recur_inst, event_id):
    uuid_version_list = []
    del_uuid_ver_list = []
    ulnk_uuid_ver_list = []
    tags_str = ""
    del_tags_str = ""
    ulnk_tags_str = ""
    curr_date = datetime.now().date()
    """
    The base task is there to hold a verion of the task using which the 
    actual recurring tasks can be derived. This task is not visible to the 
    users but get modified with any change that applies to the complete set of 
    recurring tasks
    """
    ws_task_base = ws_task_src
    results = None
    if add_recur_inst:
        # Get last done or pending task whichever is the latest. Create
        # the next occurence from the next due date
        max_ver_xpr = (SESSION.query(Workspace.uuid,
                                     func.max(Workspace.version)
                                     .label("maxver"))
                       .filter(and_(Workspace.task_type == TASK_TYPE_BASE,
                                    Workspace.area.in_([WS_AREA_PENDING])))
                       .group_by(Workspace.uuid).subquery())
        results = (SESSION.query(func.max(WorkspaceRecurDates.due))
                   .join(max_ver_xpr, and_(WorkspaceRecurDates.version ==
                                           max_ver_xpr.c.maxver,
                                           WorkspaceRecurDates.uuid ==
                                           max_ver_xpr.c.uuid))
                   .filter(WorkspaceRecurDates.uuid ==
                           ws_task_base.uuid)
                   .all())
    else:
        # Create a new base task - from add or
        # version for the base task - from modify
        ws_task_base.uuid = None
        ws_task_base.task_type = TASK_TYPE_BASE
        if ws_task_base.event_id is None:
            ws_task_base.event_id = event_id
        ws_task_base.status = TASK_STATUS_TODO
        ws_task_base.area = WS_AREA_PENDING
        ws_task_base.id = "*"
        ws_task_base.base_uuid = None
        ws_task_base.now_flag = None
        ret, ws_task_base, tags_str = add_task_and_tags(ws_task_base, 
                                                        ws_tags_list,
                                                        event_id)
        if ret == FAILURE:
            LOGGER.error("Failure recived while trying to add base task. "
                         "Stopping adding of derived tasks.")
            return FAILURE, None
        uuid_version_list.append((ws_task_base.uuid, ws_task_base.version))
    LOGGER.debug("Attempting to add derived tasks for base task {}"
                 .format(ws_task_base.uuid))
    base_uuid = ws_task_base.uuid
    base_ver = ws_task_base.version
    state = inspect(ws_task_base)
    if state.persistent or state.pending:
        SESSION.expunge(ws_task_base)
        make_transient(ws_task_base)
    #Get end date, else populate a date well into the future
    if ws_task_base.recur_end is not None:
        end_dt = (datetime.strptime(ws_task_base.recur_end, FMT_DATEONLY)
                  .date())
    else:
        end_dt = FUTDT
    if results is not None and (results[0])[0] is not None:
        """
        Tasks exist for this recurring set, so increment due date by 
        appropriate factor
        """
        LOGGER.debug("Task instances exists for this recurring task, finding "
                     "next due date")
        try:
            next_due = (calc_next_inst_date(ws_task_base.recur_mode, 
                                            ws_task_base.recur_when,
                                            datetime.strptime((results[0])[0], 
                                                                FMT_DATEONLY)
                                                    .date(), 
                                                    end_dt))[1]
        except (IndexError) as e:
            return SUCCESS, None
        create_first = False
    else:
        """
        No tasks exist for this recurring set, so due date should be base
        task's due date to create the first derived task
        Or we are creating a new recurring task
        Or due to modifying of recurrence properties we are recreating the 
        recurring task
        """
        LOGGER.debug("No existing task for this recurring task, so setting "
                     "next_due as the due date requested for the new task")
        next_due = (calc_next_inst_date(ws_task_base.recur_mode, 
                                       ws_task_base.recur_when,
                                       datetime.strptime(ws_task_base.due,
                                                         FMT_DATEONLY)
                                        .date(), end_dt))[0]
        create_first = True
    LOGGER.debug("Next due is {} and create_first is {}"
                 .format(next_due, create_first))
    """
    For derived tasks idea is to create tasks into the future until the 
    difference of the task's due date to today reaches a pre-defined 
    number or until the end data is reached.
    This pre-defined number is configured as a number of days as per the 
    mode, ex: for Daily it could be upto 2 days from today.
    Example 1: Daily recurring with due=15-Dec and end=25-Dec with today=
    15-Dec. It will create 2 tasks, one with due=15-Dec and another with
    due=16-Dec. Since the app is not a live system the task creation 
    beyond due=16-Dec will be tied into any command which will access the 
    database . So on 16-Dec if any such command is run it will create the task 
    with due=17-Dec. 
    The logic also works for back-dated due and end dates. 
    If the due date is in the future then the first task will be created 
    irrespective of how far ahead if the due date.
    """
    ws_task_drvd = ws_task_base
    """
    Need new values for below for the derived tasks. Event ID remains
    same as the base task
    Set the Base UUID as the base task's UUID for linkage 
    """
    ws_task_drvd.base_uuid = base_uuid
    # As this is a derived task
    ws_task_drvd.task_type = TASK_TYPE_DRVD
    """
    Determine the factor to apply to compute the hide date based on the base
    task's due and hide dates. This factor then gets propogated to all
    derived tasks
    """
    if ws_task_drvd.hide is not None:
        hide_due_diff = (datetime.strptime(ws_task_drvd.hide, FMT_DATEONLY)
                         - datetime.strptime(ws_task_drvd.due,
                                             FMT_DATEONLY)).days
    until_when = UNTIL_WHEN.get(ws_task_drvd.recur_mode)
    """
    Create task(s) until below conditions are satisfied. 
    1. This is the first task being created for the recurrence
    Or
    2. Until difference from today to due reaches a pre-defined number
        and
        Due date is less than the end date set for the task
    """
    LOGGER.debug("UNTIL_WHEN is {} and end is {}".format(until_when,
                                                            end_dt))
    while ((create_first or (next_due - curr_date).days < until_when)
                                and next_due <= end_dt):
        ws_task_drvd.due = next_due.strftime(FMT_DATEONLY)
        if ws_task_drvd.hide is not None:
            # **{timeunit: int(num)}
            ws_task_drvd.hide = ((next_due
                                    + relativedelta(
                                        **{"days": int(hide_due_diff)}))
                                    .strftime(FMT_DATEONLY))
        LOGGER.debug("Attempting to add a derived task now with due as {}"
                        " and hide as {}".format(ws_task_drvd.due,
                                                ws_task_drvd.hide))
        """
        For each derived task reset the below fields, the event ID 
        continues to remain the same as the base task
        """
        ws_task_drvd.uuid = None
        ws_task_drvd.version = None
        ws_task_drvd.id = None
        ws_task_drvd.created = None
        ws_rec_dt = WorkspaceRecurDates(uuid=base_uuid, version=base_ver,
                                        due=ws_task_drvd.due)
        ret, ws_task_drvd, r_tags_str = add_task_and_tags(ws_task_drvd,
                                                            ws_tags_list, 
                                                            event_id,
                                                            ws_rec_dt)
        if ret == FAILURE:
            LOGGER.error("Error will adding recurring tasks")
            return FAILURE, None, None
        uuid_version_list.append((ws_task_drvd.uuid, ws_task_drvd.version))
        create_first = False
        SESSION.expunge(ws_task_drvd)
        make_transient(ws_task_drvd)
        SESSION.expunge(ws_rec_dt)
        make_transient(ws_rec_dt)        
        try:
            next_due = (calc_next_inst_date(ws_task_base.recur_mode,
                                            ws_task_base.recur_when,
                                            next_due, end_dt))[1]
        except (IndexError) as e:
            break
    return SUCCESS, [(uuid_version_list, tags_str), ]


def calc_next_inst_date(recur_mode, recur_when, start_dt, end_dt, cnt=2):
    """
    Returns the next occurence date in a recurring rule.
    
    Uses the datetime.rrule library. Accepts the recur mode and recur when
    and translates this into a recurring rule which rrule can intepret and
    determine the first 2 dates in the recurrence.
    
    No validations are performed on the recurrence mode and when values.
    
    Params:
        recur_mode(str): A valid recurrence mode
        recur_when(str): A comma separted string of valid 'when' values
                         that correspond to the recur mode
        start_dt(date): The date from which the recurrence rule should be run
        
    Returns:
        (list of datetime): First 2 dates in the recurrence rule for the start
                            date
    """
    #Start with the BASIC modes (which do not need a 'when')
    if recur_mode == MODE_DAILY:
        next_due = (list(rrule(DAILY, count=cnt, dtstart=start_dt,
                               until=end_dt)))
    elif recur_mode == MODE_WEEKLY:
        next_due = (list(rrule(WEEKLY, count=cnt, dtstart=start_dt,
                               until=end_dt)))
    elif recur_mode == MODE_FRTNGHT:
        next_due = (list(rrule(WEEKLY, interval=2, count=cnt,
                               dtstart=start_dt, until=end_dt)))
    elif recur_mode == MODE_MONTHLY:
        next_due = (list(rrule(MONTHLY, count=cnt, dtstart=start_dt,
                               until=end_dt)))
    elif recur_mode == MODE_QRTR:
        next_due = (list(rrule(MONTHLY, interval=3, count=cnt,
                               dtstart=start_dt, until=end_dt)))
    elif recur_mode == MODE_SEMIANL:
        next_due = (list(rrule(MONTHLY, interval=6, count=cnt,
                               dtstart=start_dt, until=end_dt)))
    elif recur_mode == MODE_ANNUAL:
        next_due = (list(rrule(YEARLY, count=cnt, dtstart=start_dt,
                               until=end_dt)))
    else:
        #EXTENDED Modes
        #Parse the when list and check for modes which require a when
        when_list = [int(day) for day in recur_when.split(",")]
        when_list.sort()
        if recur_mode == MODE_WKDAY:
            #Adjust the when days by -1 to factor the 0 vs 1 index
            when_list = [day - 1 for day in when_list]
            next_due = (list(rrule(DAILY, count=cnt, byweekday=when_list,
                                   dtstart=start_dt, until=end_dt)))
        elif recur_mode == MODE_MTHDYS:
            next_due = (list(rrule(DAILY, count=cnt, bymonthday=when_list,
                                   dtstart=start_dt, until=end_dt)))
        elif recur_mode == MODE_MONTHS:
            next_due = (list(rrule(MONTHLY, count=cnt, bymonth=when_list,
                                   dtstart=start_dt, until=end_dt)))
    if next_due is not None:
        return [day.date() for day in next_due]


def parse_n_validate_recur(recur):
    when = []
    # Check if the 'mode' is something that requires 'when' - EXTENDED MODE
    # 2 charcater modes require 'when'
    if (recur[0:2]).ljust(2, " ") in VALID_MODES:
        mode = recur[0:2]
        when = (recur[2:]).rstrip(",").lstrip(",")
        if not when:
            CONSOLE.print("Insufficient input for recurrence. Check 'myt add "
                          "--help' for more info and examples.")
            return FAILURE, None, None
        # Convert to a list to validate
        when_list = when.split(",")
        if when_list:
            when_list = [int(i) for i in when_list]
        if mode == MODE_WKDAY:
            if not set(when_list).issubset(WHEN_WEEKDAYS):
                CONSOLE.print("Incorrect repeat information provided. Check "
                              "'myt add --help' for more info and examples.")
                return FAILURE, None, None
        elif mode == MODE_MTHDYS:
            if not set(when_list).issubset(WHEN_MONTHDAYS):
                CONSOLE.print("Incorrect repeat information provided. Check "
                              "'myt add --help' for more info and examples.")
                return FAILURE, None, None
        elif mode == MODE_MONTHS:
            if not set(when_list).issubset(WHEN_MONTHS):
                CONSOLE.print("Incorrect repeat information provided. Check "
                              "'myt add --help' for more info and examples.")
                return FAILURE, None, None
    elif recur[0:1] in VALID_MODES:
        #BASIC Mode
        mode = recur[0:1]
        when = None
    else:
        CONSOLE.print("Error in parsing recur option value. Check 'myt add "
                      "--help' for more info and examples.")
        return FAILURE, None, None
    return SUCCESS, mode, when


def add_task_and_tags(ws_task_src, ws_tags_list=None, event_id=None,
                      ws_rec_dt=None):
    LOGGER.debug("Incoming values for task:")
    LOGGER.debug("\n" + reflect_object_n_print(ws_task_src, to_print=False,
                                               print_all=True))
    LOGGER.debug("Incoming values for recur_dates:")
    LOGGER.debug("\n" + reflect_object_n_print(ws_rec_dt, to_print=False,
                                               print_all=True))
    ws_task = Workspace()
    if event_id is None:
        event_id = get_event_id()
    if ws_task_src.id is None:
        ws_task.id = derive_task_id()
    else:
        ws_task.id = ws_task_src.id
    if ws_task_src.due is not None:
        ws_task.due = convert_date(ws_task_src.due)
    else:
        ws_task.due = None
    if ws_task_src.hide is not None:
        if ws_task.due is not None:
            # Hide date relative to due date only if due date is available
            ws_task.hide = convert_date_rel(ws_task_src.hide, 
                                            parse(ws_task.due))
        else:
            ws_task.hide = convert_date_rel(ws_task_src.hide, None)
    else:
        ws_task.hide = None
    if ws_task_src.uuid is None:
        ws_task.uuid = str(uuid.uuid4())
    else:
        ws_task.uuid = ws_task_src.uuid
    if ws_task_src.event_id is None:
        ws_task.event_id = event_id
    else:
        ws_task.event_id = ws_task_src.event_id
    ws_task.priority = translate_priority(ws_task_src.priority)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws_task.created = now
    if not ws_task_src.inception:
        ws_task.inception = now
    else:
        ws_task.inception = ws_task_src.inception
    ws_task.version = get_task_new_version(str(ws_task.uuid))
    ws_task.description = ws_task_src.description
    ws_task.groups = ws_task_src.groups
    ws_task.now_flag = ws_task_src.now_flag
    if not ws_task_src.area:
        ws_task.area = WS_AREA_PENDING
    else:
        ws_task.area = ws_task_src.area
    if not ws_task_src.status:
        ws_task.status = TASK_STATUS_TODO
    else:
        ws_task.status = ws_task_src.status
    ws_task.recur_mode = ws_task_src.recur_mode
    ws_task.recur_when = ws_task_src.recur_when
    ws_task.recur_end = ws_task_src.recur_end
    if not ws_task_src.task_type:
        ws_task.task_type = TASK_TYPE_NRML
    else:
        ws_task.task_type = ws_task_src.task_type
    ws_task.base_uuid = ws_task_src.base_uuid
    try:
        LOGGER.debug("Adding values for task to database:")
        LOGGER.debug("\n" + reflect_object_n_print(ws_task, to_print=False,
                                                   print_all=True))
        # Insert the latest task version
        SESSION.add(ws_task)
        if ws_rec_dt is not None:
            LOGGER.debug("Adding values for recur_dates to database:")
            LOGGER.debug("\n" + reflect_object_n_print(ws_rec_dt, 
                                                       to_print=False,
                                                       print_all=True))
            SESSION.add(ws_rec_dt)
        tags_str = ""  # Only for display
        # Insert the latest tags
        if ws_tags_list is not None:
            for t in ws_tags_list:
                ws_tags = WorkspaceTags()
                ws_tags.uuid = ws_task.uuid
                ws_tags.version = ws_task.version
                ws_tags.tags = t.tags
                LOGGER.debug("Adding values for tags:")
                LOGGER.debug("\n" + reflect_object_n_print(ws_tags,
                                                           to_print=False,
                                                           print_all=True))
                SESSION.add(ws_tags)
                tags_str = tags_str + "," + t.tags
        # For all older entries remove the task_id
        (SESSION.query(Workspace).filter(Workspace.uuid == ws_task.uuid,
                                         Workspace.version <
                                         ws_task.version)
         .update({Workspace.id: "-"},
                 synchronize_session=False))
    except SQLAlchemyError as e:
        SESSION.rollback()
        print(str(e))
        return FAILURE, None, None
    return SUCCESS, ws_task, tags_str


def reset_now_flag():
    LOGGER.debug("Attempting to reset now flag if any...")
    try:
        (SESSION.query(Workspace).filter(Workspace.now_flag == True)
                                 .update({Workspace.now_flag: False},
                                         synchronize_session=False))
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return FAILURE
    return SUCCESS


def exit_app(stat=0):
    LOGGER.debug("Preparing to exit app...")
    ret = discard_db_resources()
    if ret != 0 or stat != 0:
        LOGGER.error("Errors encountered either in executing commands"
                     " or while exiting apps")
        sys.exit(1)
    else:
        LOGGER.debug("Exiting app.")
        sys.exit(0)


def discard_db_resources():
    global ENGINE
    LOGGER.debug("Atempting to remove sessions and db engines...")
    try:
        if ENGINE is not None:
            ENGINE.dispose()
    except Exception as e:
        LOGGER.error("Error encountered in removing sessions and db engines")
        LOGGER.error(str(e))
        return FAILURE
    else:
        LOGGER.debug("Successfully removed sessions and db engines")
        return SUCCESS
