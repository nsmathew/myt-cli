from importlib import metadata
from operator import itemgetter
import re
import os
from os.path import getsize
import uuid
import sys
from pathlib import Path
import logging
import webbrowser
from copy import copy

import click
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from dateutil.rrule import *
from rich.console import Console
from rich.table import Column, Table as RichTable, box
from rich.style import Style
from rich.theme import Theme
from rich.prompt import Prompt
from rich.columns import Columns
from rich.panel import Panel
from sqlalchemy import (create_engine, Column, Integer, String, Index,
                        ForeignKeyConstraint, tuple_, and_, case, func,
                        BOOLEAN, distinct, inspect, or_)
from sqlalchemy.orm import sessionmaker, make_transient
#from sqlalchemy.orm import 
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.functions import coalesce
from sqlalchemy import cast, Numeric

import plotext as pltxt

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
# ORM Definition
#Base = declarative_base()
# Changelog URL
CHANGELOG = "https://github.com/nsmathew/myt-cli/blob/master/CHANGELOG.txt"

class Base(DeclarativeBase):
    pass

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
    status = Column(String, nullable=False)
    due = Column(String)
    hide = Column(String)
    area = Column(String, nullable=False)
    created = Column(String, nullable=False)
    groups = Column(String)
    event_id = Column(String, nullable=False)
    now_flag = Column(BOOLEAN)
    task_type = Column(String, nullable=False)
    base_uuid = Column(String)
    recur_mode = Column(String)
    recur_when = Column(String)
    recur_end = Column(String)
    inception = Column(String, nullable=False)
    duration = Column(Integer, default=0)
    dur_event = Column(String)
    notes = Column(String)

    # To get due date difference to today
    @hybrid_property
    def due_diff_today(self):
        curr_date = datetime.now().date()
        return (datetime.strptime(self.due, FMT_DATEONLY).date()
                    - curr_date).days

    @due_diff_today.expression
    def due_diff_today(cls):
        curr_date = datetime.now().date().strftime(FMT_DATEONLY)
        # julianday is an sqlite function
        date_diff = func.julianday(cls.due) - func.julianday(curr_date)
        """
        For some reason cast as Integer forces an addition in the sql
        when trying to concatenate with a string. Forcing as string causes
        the expression to be returned as a literal string rather than the
        result. Hence using substr and instr instead.
        """
        return func.substr(date_diff, 1, func.instr(date_diff, ".")-1)

    # To get time difference of inception to now in seconds
    @hybrid_property
    def incep_diff_now(self):
        curr_date = datetime.now()
        return round((curr_date -
                      datetime.strptime(self.inception, FMT_DATETIME)).seconds)

    @incep_diff_now.expression
    def incep_diff_now(cls):
        #curr_date = datetime.now().date().strftime(FMT_DATEONLY)
        curr_date = datetime.now()
        # julianday is an sqlite function
        date_diff = func.round(((func.julianday(curr_date)
                        - func.julianday(cls.inception)) * 24 * 60 * 60))
        return date_diff

    # To get time difference of version created to now in days
    @hybrid_property
    def ver_crt_diff_now(self):
        curr_date = datetime.now().date()
        return (datetime.strptime(self.created, FMT_DATETIME).date()
                    - curr_date).days        

    @ver_crt_diff_now.expression
    def ver_crt_diff_now(cls):
        curr_date = datetime.now().date().strftime(FMT_DATEONLY)
        # julianday is an sqlite function
        date_diff = func.julianday(func.substr(cls.created, 0, 11)) - func.julianday(curr_date)
        """
        For some reason cast as Integer forces an addition in the sql
        when trying to concatenate with a string. Forcing as string causes
        the expression to be returned as a literal string rather than the
        result. Hence using substr and instr instead.
        """
        return func.substr(date_diff, 1, func.instr(date_diff, ".")-1)    
    
    # To get time difference of duration event to now in seconds
    @hybrid_property
    def dur_ev_diff_now(self):
        curr_time = datetime.now()
        return round((datetime.strptime(self.dur_event, FMT_DATETIME)
                    - curr_time).seconds)

    @dur_ev_diff_now.expression
    def dur_ev_diff_now(cls):
        curr_time = datetime.now()
        # julianday is an sqlite function
        date_diff = func.round(((func.julianday(curr_time)
                        - func.julianday(cls.dur_event)) * 24 * 60 * 60))
        return date_diff

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

"""
Additional note on WorkspaceRecurDates. The rows for this table are created in
two scenarios:
1. At a derived task level - For each derived task a record is created in the
table using the base uuid and version with due = derived task's due.
This is what happens when
    - a new recurring task is added or
    - an indivdual recurring task instance is added or
    - when the entire recurring task gets modified due to changes in recurrence
      properties
2. When a new version of base task is created with no changes in due dates - In
this case the due dates of the base task from previous version are just copied
over as new records but with the new base taks version.
This is used when
    - the recurring task and its instances are modified with no changes in
      recurrence properties
    - when a base task is reverted from completed to pending area as part of
      the revert task option
"""
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
    """
    ORM for the table 'app_metadata' which holds application metadata.

        Primary Key: key
    """
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
    global CHANGELOG
    CONSOLE.print(metadata.version('myt-cli'))
    CONSOLE.print("Visit {} for the change log.".format(CHANGELOG))
    CONSOLE.print()
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
              help="Priority for Task - H, M, L or leave empty for Normal",
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
@click.option("--notes",
              "-no",
              type=str,
              help="Add some notes. You can also add URLs with a description "
              "for them using the format 'https://abc.com [ABC's website]'.",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def add(desc, priority, due, hide, group, tag, recur, end, notes, verbose, 
        full_db_path=None):
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
    DAILY - D, WEEKLY - W, MONTHLY - M and YEARLY - Y

    Ex: myt add -de "Pay the rent" -du 2020-11-01 -re M

    Here we add a task that will recur on the 1st of every month starting from
    1st Nov 2020.

    EXTENDED Mode:
    Every x DAYS - DEx, Every x WEEKS - WEx, Every x MONTHS - MEx,
    Every x YEARS - YEx
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
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    if desc is None:
        CONSOLE.print("No task information provided. Nothing to do...",
                      style="default")
        return SUCCESS
    else:
        event_id = get_event_id()
        ws_task = Workspace(description=desc, priority=priority,
                            due=due, hide=hide, groups=group, now_flag=False,
                            notes=notes)
        if tag is not None:
            """
            bug-17 to handle duplicate tags on input.
            Below logic removes a preceeding and succeeding ','
            Dict used to removes any duplicates. Examples:
            ab,nh : ab,nh
            ab,ab,nh : ab,nh
            ,-ab,nh,-ab, : -ab,nh
            """
            tags_list_text = ",".join(dict.fromkeys(filter(None,tag.split(","))))
            LOGGER.debug("After cleaning tags are: {}".format(tags_list_text))
            ws_tags_list = generate_tags(tags_list_text)
        else:
            ws_tags_list = None
        due = convert_date(due)
        end = convert_date(end)
        if due is not None:
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
            ws_task.event_id = event_id
            ret, return_list = prep_recurring_tasks(ws_task, ws_tags_list,
                                                    False)
            if ret == SUCCESS:
                SESSION.commit()
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
        else:
            ws_task.task_type = TASK_TYPE_NRML
            ws_task.event_id = event_id
            ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                       ws_tags_list,
                                                       None,
                                                       OPS_ADD)
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
              help="Priority for Task - H, M, L or leave empty for Normal",
              )
@click.option("--due",
              "-du",
              type=str,
              help="Due date for the task, use 'clr' to clear the due date",
              )
@click.option("--hide",
              "-hi",
              type=str,
              help=("Date until when task should be hidden from Task views, "
                    "use 'clr' to clear the current hide date"),
              )
@click.option("--group",
              "-gr",
              type=str,
              help=("Hierachical grouping for tasks using '.', use 'clr' to "
                    "clear groups."),
              )
@click.option("--tag",
              "-tg",
              type=str,
              help=("Comma separated tags for the task. If tag has to be "
                    "removed then prefix a '-' before the tag"),
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
@click.option("--notes",
              "-no",
              type=str,
              help="Add some notes. You can also add URLs with a description "
              "for them using the format 'https://abc.com [ABC's website]'. "
              "Use 'clr' to clear notes.",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def modify(filters, desc, priority, due, hide, group, tag, recur, end, notes,
           verbose, full_db_path=None):
    """
    Modify task details. Specify 1 or more filters and provide the new values
    for attributes which need modification using the options available.
    
    NOTE: The tasks to be modified will be filtered based on provided filters 
    with hidden tasks included by default. If the 'hidden' filter is also 
    provided then the tasks will be filtered from only among hidden tasks.    

    --- FILTERS ---

    Filters can take various forms, refer below. Format is 'field:value'.

    id - Filter on tasks by id. This filters works by itself and cannot be
    combined as this is most specific. Works on tasks which are in status
    'TO_DO', 'STARTED'. Ex - id:4,10

    uuid - Filter on tasks by uuid. This works by itself and cannot be
    combined with other filters. Works on tasks with status 'DONE' or
    'DELETED'. Ex - uuid:31726cd2-2db3-4ae4-97ae-b2b7b29a7307

    desc - Filter on tasks by description. The filter searches within task
    descriptions. Can be combined with other filters. Ex - de:fitness or
    desc:fitness

    groups - Filter on tasks by the group name. Can be combined with other
    filters. Ex - gr:HOME.BILLS or group:HOME.BILLS

    tags - Filter tasks on tags, can be provided as comman separated. Can be
    combined with other filters. Ex - tg:bills,finance or tag:bills,finance

    priority - Filter tasks on the priority. Can be combined with other
    filters. Ex - pr:M or priority:Medium

    notes - Filter tasks on the notes. Can be combined with other filters.
    Ex - no:"avenue 6" or notes:"avenue 6"

    due, hide, end - Filter tasks on dates. It is possible to filter based on
    various conditions as explained below with examples using due/du

        Equal To - du:eq:+1 Tasks due tomorrow\n
        Less Than - du:lt:+0 Tasks with due dates earlier than today\n
        Less Than or Equal To - due:le:+0 Tasks due today or earlier\n
        Greater Than - du:gt:2020-12-10 Tasks with due date after 10th Dec '20
        \n
        Greater Than or Equal To - du:ge:+7 Tasks due in 7 days or beyond\n
        Between - du:bt:2020-12-01:2020-12-07 Tasks due in the first 7 days of
        Dec '20. Both dates are inclusive\n
        The same works for hide/hi and end/en as well. For hide when using the
        short form of the date as '-X' this is relative to today and noty due
        date. When providing an input value for hide with this format '-X' is
        relative to the due date.\n

    'started' - Filter all tasks that are in 'STARTED' status. Can be combined
    with other filters.

    'now' - Filter on the task marked as 'NOW'.

    The next section documents High Level Filters and should be used with
    caution as they could modify large number of tasks.

    'complete' - Filters all tasks that are in 'DONE' status. Mandatory filter
    when operating on tasks in the 'completed' are or tasks which are 'DONE'.

    'bin' - Filters all tasks that are in the DELETED status or in the bin and
    mandatory when operating on such tasks.

    'hidden' - Filters all tasks that are currently hidden from the normal
    view command but are still pending, 'TO_DO' or 'STARTED'. Mandatory filter
    when operating on tasks that are currently hidden.

    'today' - Filters all tasks that are due today. Works on pending tasks only

    'overdue' - Filters all tasks that are overdue. Works on pending tasks only

    --- CLEARING PROPERTIES ---

    The property values can be cleared or set to empty using the keyword 'clr'.
    This works on due, hide, priority, groups, tags, end and notes. For the
    respective option you can provide 'clr' as the value. Ex: -pr clr or -gr
    clr

    --- RECURRENCE ---

    If based on the filters any of the tasks are of recurring nature then a
    prompt will be displayed asking if the change needs to be applied to just
    this instance of the task or all recurring instances.

    Changes on individual instances are allowed only for description, groups,
    tags, priority, due and hide date. Changes on recurrence, that is the type
    of recurrence or the end date, are applicable only to all instances of the
    task.

    If the recurrence changes then a new tasks are created as per the new
    recurrence properties. Any pending instances of the old recurring task are
    deleted. Any 'DONE' instance are unlinked and will behance as normal tasks
    if reverted.

    --- EXAMPLES ---

    myt modify id:7,8 -de "Go to the gym" - Change the description for 2 tasks
    with ID as 7 and 8

    myt modify today -tg -relaxed,urgent - For all tasks that are due today,
    add a tag 'urgent' and remove a tag 'relaxed'

    myt modify overdue du:eq:-1 -pr HIGH - For all tasks that are overdue and
    were due as of yesterday set their priority to High

    myt modify hidden gr:HOME -hi clr - For all hidden tasks which have group
    as 'HOME' clear the hide date.

    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    LOGGER.debug("Values for update: desc - {} due - {} hide - {} group - {}"
                 " tag - {}"
                 .format(desc, due, hide, group, tag))
    # Perform validations
    if (potential_filters.get(TASK_COMPLETE) == "yes" or
            potential_filters.get(TASK_BIN) == "yes"):
        CONSOLE.print("Modify can be run only on 'pending' tasks.",
                      style="default")
        exit_app(SUCCESS)
    if (desc is None and priority is None and due is None and hide is None
            and group is None and tag is None and recur is None
            and notes is None and end is None):
        CONSOLE.print("No modification values provided. Nothing to do...",
                      style="default")
        exit_app(SUCCESS)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
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
        """
        bug-17 to handle duplicate tags on input.
        Below logic removes a preceeding and succeeding ','
        Dict used to removes any duplicates. Examples:
        ab,nh : ab,nh
        ab,ab,nh : ab,nh
        ,-ab,nh,-ab, : -ab,nh
        """
        tag = ",".join(dict.fromkeys(filter(None,tag.split(","))))
        LOGGER.debug("After cleaning tags are: {}".format(tag))
    else:
        tag = None
    if end is not None:
        end = convert_date(end)
    event_id = get_event_id()
    ws_task = Workspace(description=desc, priority=priority,
                        due=due, hide=hide, groups=group, recur_end=end,
                        notes=notes, recur_when=when, recur_mode=mode,
                        event_id=event_id)
    ret, task_tags_print = prep_modify(potential_filters,
                                       ws_task,
                                       tag)
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
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
@click.pass_context
def now(ctx, filters, verbose, full_db_path=None):
    """
    Toggles the 'now' status of the task

    For tasks you would like to give the highest priority to indicate
    you are working on now you can use the 'now' command. This will ensure
    the task is given a signifcantly higher score, therby pushing it to the
    top of the task's view.

    At any point only 1 task can be set as 'now'. 'now' tasks are shown in a
    different colour. The behaviour otherwise remains the same as any other
    task. If you are setting a task to 'now' and if it is not started you will
    be asked if you would like to start it.

    As this is a toggle type command you use the same command to set and remove
    the 'now' status for a task.
    
    NOTE: The tasks to be set as NOW will be filtered based on provided filters 
    with hidden tasks included by default. If the 'hidden' filter is also 
    provided then the tasks will be filtered from only among hidden tasks.    
    
    --- FILTERS ---

    Now tasks accept only the 'id:' filter and only 1 task id in the filter

    --- EXAMPLES ---

    Scenario - 2 tasks are available with ids 1 and 2, neither are set as 'now'

    myt now id:2 - This will set task 2 as 'now'

    myt now id:1 - This will set task 1 as 'now' while removing the 'now'
    status for task 2

    myt now id:1 - This will remove 'now' for task 1. At this point there will be
    no tasks set as 'now'
    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if (potential_filters.get(TASK_COMPLETE) == "yes" or
            potential_filters.get(TASK_BIN) == "yes"):
        CONSOLE.print("Now can be run only on 'pending' tasks.",
                      style="default")
        exit_app(SUCCESS)
    if potential_filters.get("id") is None:
        CONSOLE.print("NOW flag can be modified only with a task ID filter",
                      style="default")
        exit_app(SUCCESS)
    if len(potential_filters.get("id").split(",")) > 1:
        CONSOLE.print("NOW flag can be modified for only 1 task at a time",
                      style="default")
        exit_app(SUCCESS)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    event_id = get_event_id()
    ret, task_tags_print = toggle_now(potential_filters, event_id)
    if ret == SUCCESS:
        SESSION.commit()
        get_and_print_task_count({WS_AREA_PENDING: "yes",
                                 PRNT_TASK_DTLS: task_tags_print})
        """
        fet-16 When toggling now flag, ask user if they want to start
        the task as well if it is in TO DO status and it is being
        set to now.
        """
        if task_tags_print is not None:
            LOGGER.debug("Checking if we need to ask user to start task")
            for item in task_tags_print:
                #1st item is the task object
                ws_task = item[0]
                """
                There could be 2 tasks in the list when running now
                in a sceanrio where there is a task that is already 'now'
                Hence checking for the task id.
                """
                task_id = str(ws_task.id)
                if (task_id == potential_filters.get("id") and
                    ws_task.status == TASK_STATUS_TODO and
                    ws_task.now_flag == True):
                    if not confirm_prompt("Do you want to start task with "
                                          "id {}".format(ws_task.id)):
                        LOGGER.debug("User did not request to start task")
                        exit_app(SUCCESS)
                    else:
                        LOGGER.debug("User requested to start task")
                        ctx.invoke(start, 
                                   filters=("".join(["id:",task_id]),), 
                                   verbose=verbose,
                                   full_db_path=full_db_path)
                    break
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
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def start(filters, verbose, full_db_path=None):
    """
    Set a task as started or in progress

    Allows to track tasks that are in progress. When a task is started
    the task status changes to 'STARTED' and duration is kept track off
    against when the task was started.

    You can stop tasks at which point they go into 'TO_DO' status and
    the duration tracking is paued. They can be started again and the
    duration tracking will continue.

    The task remains in the 'pending' area. This command is only applicable
    for tasks in the 'pending' area.

    NOTE: The tasks to be started will be filtered based on provided filters 
    with hidden tasks included by default. If the 'hidden' filter is also 
    provided then the tasks will be filtered from only among hidden tasks.    
    
    --- FILTERS ---

    Please refer the help for the 'modify' command for information on
    available filters
    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    if (potential_filters.get(TASK_COMPLETE) == "yes" or
            potential_filters.get(TASK_BIN) == "yes"):
        CONSOLE.print("Start can be run only on 'pending' tasks.",
                      style="default")
        exit_app(SUCCESS)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for starting tasks,"
                              " are you sure?"):
            exit_app(SUCCESS)
    event_id = get_event_id()
    ret, task_tags_print = start_task(potential_filters, event_id)
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
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def done(filters, verbose, full_db_path=None):
    """
    Set a task as completed.

    To be used when a task is completed. This will set the task's status as
    'DONE' and move the task into the 'completed' area. Tasks in the
    'completed' area are not shown in the default 'view' command but
    can be viewed when using the 'complete' filter. Refer the help for the
    'view' command for more details.

    If the task was in 'STARTED' state the duractionm tracking is stopped
    and overall task duration is recorded. Tasks can be moved back to the
    'TO_DO' status by using the 'revert' command.

    The task remains in the 'pending' area. This command is only applicable
    for tasks in the 'pending' area.

    NOTE: The tasks to be completed will be filtered based on provided filters 
    with hidden tasks included by default. If the 'hidden' filter is also 
    provided then the tasks will be filtered from only among hidden tasks.    
    
    --- FILTERS ---

    Please refer the help for the 'modify' command for information on
    available filters
    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    if (potential_filters.get(TASK_COMPLETE) == "yes" or
            potential_filters.get(TASK_BIN) == "yes"):
        CONSOLE.print("Done can be run only on 'pending' tasks.",
                      style="default")
        exit_app(SUCCESS)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for marking tasks as done,"
                              " are you sure?"):
            exit_app(SUCCESS)
    event_id = get_event_id()
    ret, task_tags_print = complete_task(potential_filters, event_id)
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
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def revert(filters, verbose, full_db_path=None):
    """
    Reverts a completed task as pending

    This command is used to change a task's status from 'DONE' to
    'TO_DO'. This will move the task from the 'completed' area to the
    'pending' area. Once done operations applicable to a 'TO_DO' task
    can be performed on it. This can also be used on recurring tasks.

    The duration of the tasks is retained upon revert. If you 'start' the
    task then the duration tracking continues. Additionally the revert
    command only work in the 'completed' area hence you need to use the
    'complete' filter when running the command, refer the examples.
    
    NOTE: The tasks to be reverted will be filtered based on provided filters 
    with hidden tasks included by default. If the 'hidden' filter is also 
    provided then the tasks will be filtered from only among hidden tasks.    
    
    --- FILTERS ---

    Please refer the help for the 'modify' command for information on
    available filters

    --- EXAMPLES ---

    myt revert complete tg:bills - This will revert all completed tasks
    which have the tag 'bills'.

    myt revert complete uuid:7b97aa5f-4d09-43fb-810a-09023f7d2e88 - This will
    revert the task with the stated uuid. As tasks in the 'completed' area do
    not have a task ID you will need to use the uuid instead. This can be
    viewed using the 'myt view complete' command
    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_COMPLETE) != "yes":
        CONSOLE.print("Revert is applicable only to completed tasks. Use "
                      "'complete' filter in command")
        exit_app(SUCCESS)
    if potential_filters.get(TASK_BIN) == "yes":
        CONSOLE.print("Cannot apply operation to deleted tasks")
        exit_app(SUCCESS)
    if potential_filters.get(HL_FILTERS_ONLY) == "yes":
        if not confirm_prompt("No detailed filters given for reverting tasks "
                              "to TO_DO status, are you sure?"):
            exit_app(SUCCESS)
    event_id = get_event_id()
    ret, task_tags_print = revert_task(potential_filters, event_id)
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
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def reset(filters, verbose, full_db_path=None):
    """
    Reset a task's duration to 0 and the status to TO_DO status.
    This works on tasks in STARTED status.

    The task remains in the 'pending' area. This command is only applicable
    for tasks in the 'pending' area.    
    
    NOTE: The tasks to be reset will be filtered based on provided filters 
    with hidden tasks included by default. If the 'hidden' filter is also 
    provided then the tasks will be filtered from only among hidden tasks.    

    --- FILTERS ---

    Please refer the help for the 'modify' command for information on
    available filters

    --- EXAMPLES ---
    myt reset id:1 - Reset a task with ID = 1

    myt reset tg:planning - Reset all tasks in STARTED status with a tag as
    'planning'
    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    if (potential_filters.get(TASK_COMPLETE) == "yes" or
            potential_filters.get(TASK_BIN) == "yes"):
        CONSOLE.print("Reset can be run only on 'pending' tasks.",
                      style="default")
        exit_app(SUCCESS)
    if potential_filters.get(HL_FILTERS_ONLY) == "yes":
        if not confirm_prompt("No detailed filters given for reset of tasks "
                              ", are you sure?"):
            exit_app(SUCCESS)
    event_id = get_event_id()
    ret, task_tags_print = reset_task(potential_filters, event_id)
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
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def stop(filters, verbose, full_db_path=None):
    """
    Stop a started task and stop duration tracking.

    When you stop working on a task but it is yet to be completed you can
    you can use this command. It will set the task's status as 'TO_DO' and
    will stop tracking the task's duration.
    
    If you need to start the task again then just use the 'start' command.
    The task remains in the 'pending' area. This command is only applicable
    for tasks in the 'pending' area.
    
    NOTE: The tasks to be stopped will be filtered based on provided filters 
    with hidden tasks included by default. If the 'hidden' filter is also 
    provided then the tasks will be filtered from only among hidden tasks.    

    --- FILTERS ---

    Please refer the help for the 'modify' command for information on
    available filters

    --- EXAMPLES ---

    myt stop id:12 - Stops a task with task id as 12

    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    if (potential_filters.get(TASK_COMPLETE) == "yes" or
            potential_filters.get(TASK_BIN) == "yes"):
        CONSOLE.print("Stop can be run only on 'pending' tasks.",
                      style="default")
        exit_app(SUCCESS)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for stopping tasks, "
                              "are you sure?"):
            exit_app(SUCCESS)
    event_id = get_event_id()
    ret, task_tags_print = stop_task(potential_filters, event_id)
    if ret == SUCCESS:
        SESSION.commit()
        get_and_print_task_count({WS_AREA_PENDING: "yes",
                                    PRNT_TASK_DTLS: task_tags_print})
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
              type=int,
              help="Display only the top 'x' number of tasks",
              )
@click.option("--default",
              "viewmode",
              flag_value="default",
              default=True,
              help="Default view of tasks sorted by the task's score"
              )
@click.option("--full",
              "viewmode",
              flag_value="full",
              help="Display all attributes of the task stored in the backend"
              )
@click.option("--history",
              "viewmode",
              flag_value="history",
              help="Display all versions of the task"
              )
@click.option("--tags",
              "viewmode",
              flag_value="tags",
              help="Display tags and  number of tasks against each of them"
              )
@click.option("--groups",
              "viewmode",
              flag_value="groups",
              help="Display groups and number of tasks against each of them"
              )
@click.option("--dates",
              "viewmode",
              flag_value="dates",
              help="Display the future dates for recurring tasks",
              )
@click.option("--notes",
              "viewmode",
              flag_value="notes",
              help="Display the notes for tasks",
              )
@click.option("--7day",
              "viewmode",
              flag_value="7day",
              help="Display a 7 day upcoming view of tasks",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def view(filters, verbose, pager, top, viewmode, full_db_path=None):
    """
    Display tasks using various views and filters.

    The views by default apply on the 'pending' area and for tasks that are
    not hidden, ie any task that is in 'TO_DO' or 'STARTED' status and has no 
    hide date or the hide date > today. If you need tasks from other areas you 
    need to use the 'complete' or 'bin' filter.
    
    If additional filters like id, gr, tg etc are provided without 'bin' or 
    'complete', then the tasks will be filtered with hidden tasks also scoped 
    in unless the 'hidden' filter is also provided.

    All tasks in 'pending' area, hidden or not are shown with a numeric task
    id. Tasks in 'completed' or 'bin' area are always shown with their uuid or
    the unqiue identifier from the backend.

    --- FILTERS ---

    Please refer the help for the 'modify' command for information on
    available filters

    --- EXAMPLES ---

    myt view - The default view command on tasks in 'pending' area, without
    any filters and shows non hidden tasks

    myt view hidden gr:FINANCES - The default view command but on hidden tasks
    in 'pending' area and filtered by group as FINANCES

    myt view --top 10 - If you have a lot of tasks captured and would like to
    see the top 10 tasks only.
    """
    ret = SUCCESS
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    if viewmode == "default":
        ret = display_default(potential_filters, pager, top)
    elif viewmode == "full":
        ret = display_full(potential_filters, pager, top)
    elif viewmode == "history":
        ret = display_history(potential_filters, pager, top)
    elif viewmode == "tags":
        ret = display_by_tags(potential_filters, pager, top)
    elif viewmode == "groups":
        ret = display_by_groups(potential_filters, pager, top)
    elif viewmode == "dates":
        ret = display_dates(potential_filters, pager, top)
    elif viewmode == "notes":
        ret = display_notes(potential_filters, pager, top)
    elif viewmode == "7day":
        if top is not None:
            CONSOLE.print("Top option is not applicable, ignoring.")
        ret = display_7day(potential_filters, pager)        
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
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def delete(filters, verbose, full_db_path=None):
    """
    Delete a task

    You cna use this option to delete a task that is no longer required.
    Upon deletion the task moves into the 'bin' area and cannot be
    operated upon anymore.

    You can view tasks in the bin using 'myt view bin'. To empty the bin
    you can use 'myt admin --empty'. As of now there is no option to
    restore tasks from the bin.

    This command works for tasks in the 'pending' and 'completed' areas.
    While deleting tasks which are recurring you will be asked if you would
    like to delete just the one instance or all of them.
        
    NOTE: The tasks to be deleted will be filtered based on provided filters 
    with hidden tasks included by default. If the 'hidden' filter is also 
    provided then the tasks will be filtered from only among hidden tasks.    

    --- FILTERS ---

    Please refer the help for the 'modify' command for information on
    available filters

    --- EXAMPLES ---

    myt delete id:12 - Stops a task with task id as 12
    """
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if (potential_filters.get(TASK_BIN) == "yes"):
        CONSOLE.print("Delete cannot be run on deleted tasks.",
                      style="default")
        exit_app(SUCCESS)
    if potential_filters.get(HL_FILTERS_ONLY) == "yes":
        if not confirm_prompt("No detailed filters given for deleting tasks, "
                              "are you sure?"):
            exit_app(SUCCESS)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    event_id = get_event_id()
    ret, task_tags_print = prep_delete(potential_filters, event_id, False)
    if ret == SUCCESS:
        SESSION.commit()
        get_and_print_task_count({WS_AREA_PENDING: "yes",
                                  PRNT_TASK_DTLS: task_tags_print})
    exit_app(ret)


@myt.command()
@click.option("--empty",
              is_flag=True,
              help="Empty the bin area. Removed tasks cannot be retrieved.",
              )
@click.option("--reinit",
              is_flag=True,
              help=("Reinitialize the database. Recreates the database, hence "
                    "all data will be removed. USE WITH CAUTION!"),
              )
@click.option("--tags",
              is_flag=True,
              help=("View all tags available across pending and completed "
                    "tasks."),
              )
@click.option("--groups",
              is_flag=True,
              help=("View all groups available across pending and completed "
                    "tasks."),
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def admin(verbose, empty, reinit, tags, groups, full_db_path=None):
    """
    Allows to run admin related operations on the tasks database. This includes
    reinitialization of database and emptying the bin area. Refer to the
    options for more information.
    """
    ret = SUCCESS
    if verbose:
        set_versbose_logging()
    if reinit:
        if not confirm_prompt("This will delete the database including all "
                              "tasks and create an empty database. "
                              "Are you sure?"):
            exit_app(SUCCESS)
        ret = reinitialize_db(verbose, full_db_path)
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    if empty:
        ret = empty_bin()
    if tags:
        ret = display_all_tags()
    if groups:
        ret = display_all_groups()
    exit_app(ret)


@myt.command()
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def undo(verbose, full_db_path=None):
    """
    Performs an undo operation.

    The last operation requested by the user and any associated internal
    events are removed. The state of the tasks are restored to what the state
    was prior to the last operation.

    A point to note, the task IDs could be different from what was assigned
    to a task prior to running of the undo.
    """
    if verbose:
        set_versbose_logging()
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    ret = perform_undo()
    if ret == FAILURE:
        CONSOLE.print("Error while performing undo operation")
    else:
        SESSION.commit()
    exit_app(ret)


@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--urlno",
              "-ur",
              type=int,
              help="Which link to open based on order of links in the notes",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose logging.",
              )
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def urlopen(filters, urlno, verbose, full_db_path=None):
    """
    Parses task notes for URLs which can then be opened.

    The task notes are parsed to identify valid URLs. Notes can be added to
    tasks using '-no' option for the 'add' and 'modify' commands. URLS
    You can also add URLs with a description for them using the format
    'https://abc.com [ABC's website]'.

    All URLs in the notes are listed along with their description with a
    number against each URL. The user chooses one URL to be opened by
    indicating the number. If there is only 1 URL in the notes then it is
    opened by default when the command is run for a task ID/UUID.

    The user can use the --urlno or -ur option to provide a number as part of
    the command to open that particular URL without having to choose from the
    menu.
    
    The tasks to be stopped will be filtered based on provided filters with 
    hidden tasks included by default.        

    --- FILTERS ---

    This command works only with the ID or UUID filters and with just 1 task.
    If more than 1 task ID or UUID is provided the command just processes the
    first valid task for URLs.

    --- EXAMPLES ---

    myt urlopen id:3 - Displays all URLS from the notes for task 3 post which
    the user can choose which one they want to open. If there is only 1 URL
    then it will be opened without requiring a user prompt.

    myt urlopen uuid:65138024-31ec-4ddc-9706-26adc1bfac40 -ur 3 - This will
    open the 3rd URL mentioned in the notes without a user prompt. If there
    is no 3rd URL then it will display available URLs for the user to choose.
    """
    if verbose:
        set_versbose_logging()
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)
    potential_filters = parse_filters(filters)
    if not potential_filters.get("id") and not potential_filters.get("uuid"):
        CONSOLE.print("Provide an ID or UUID to open link")
        exit_app(SUCCESS)
    ret = process_url(potential_filters, urlno)
    exit_app(ret)

@myt.command()
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
@click.option("--full-db-path",
              "-db",
              type=str,
              help="Full path to tasks database file",
              )
def stats(verbose, full_db_path=None):
    """
    Displays stats on the state of pending and completed tasks. Includes how 
    many tasks are in the various state currently and how many are in the bin.
    Additionally also shows the trend for tasks completed and tasks created 
    over the last 7 days.
    """
    ret = SUCCESS
    if verbose:
        set_versbose_logging()
    if connect_to_tasksdb(verbose, full_db_path) == FAILURE:
        exit_app(FAILURE)        
    display_stats()
    exit_app(ret)

#App startup and exit functions
def check_valid_db(full_db_path):
    """
    Check the validity of the sqlite3 database file based on size of file and 
    content of first 16 bytes. Additional information available in the below 
    link, https://www.sqlite.org/fileformat.html.
    
    No check on if the file is a valid file in the filesystem is made since 
    this will already be done before this function is called.
    
    Parameters:
        full_db_path(str): The path to the database file. Default is None

    Returns:
        int: SUCCESS(0) or FAILURE(1)
    """
    # The file header is 100 bytes, so file with size < 100 is invalid
    if getsize(full_db_path) < 100:
        return FAILURE

    # The first 16 bytes should be "SQLite format 3\000"
    # This is as per https://www.sqlite.org/fileformat.html
    with open(full_db_path, 'rb') as fd:
        header = fd.read(100)

    if header[:16] ==  b'SQLite format 3\x00':
        return SUCCESS
    else:
        return FAILURE

def connect_to_tasksdb(verbose=False, full_db_path=None):
    """
    Connect to the tasks database and performs some startup functions

    Reads the global parameters on database location and creates a global
    Session object which is used by the functions to access the database. 
    If a database path is provided in the command argument it will attempt 
    to use it.In case the database does not exist the function will create 
    one, create the tables and then create a Session object.

    Post this it also check if any recurring instances of tasks have to be
    created and calls the create_recur_inst() to do so.

    Parameters:
        verbose(bool): Indicates if logging should be verbose(debug mode).
        Default is False.
                       
        full_db_path(str): The path to the database file. Default is None

    Returns:
        int: SUCCESS(0) or FAILURE(1)
    """
    global Session, SESSION, ENGINE
    if full_db_path is None: # If path not provided as cmd arg then default
        full_db_path = os.path.join(DEFAULT_FOLDER, DEFAULT_DB_NAME)
    
    # Validate the path
    if ".." in full_db_path or \
        not os.path.isdir(os.path.dirname(full_db_path)) or \
        not os.path.isabs(full_db_path):
        LOGGER.error("Tasks database path is invalid. " +\
                     "Please use absolute path only.")
        return FAILURE
    
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
        CONSOLE.print("Tasks database initialized...", style="info")
        db_init = True
    
    LOGGER.debug("Checking if tasks database at {} is valid"\
                .format(full_db_path))    
    if check_valid_db(full_db_path) == FAILURE:
        LOGGER.error("Tasks database at {} is not a valid sqlite3 database."\
                .format(full_db_path))        
        return FAILURE
    
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


def reinitialize_db(verbose, full_db_path=None):
    if full_db_path is None:
        full_db_path = os.path.join(DEFAULT_FOLDER, DEFAULT_DB_NAME)
    try:
        if os.path.exists(full_db_path):
            discard_db_resources()
            os.remove(full_db_path)
    except OSError as e:
        LOGGER.error("Unable to remove database.")
        LOGGER.error(str(e))
        return FAILURE
    CONSOLE.print("Database removed...", style="info")
    ret = connect_to_tasksdb(verbose=verbose)
    return ret


def set_versbose_logging():
    LOGGER.setLevel(level=logging.DEBUG)


#Helper functions
def open_url(url_):
    """
    Opens a url using the system's default web browser.

    Parameters:
        url_(string): The URL which needs to be openned

    Returns:
        int: 0 if successful, 1 if error encountered
    """
    CONSOLE.print("Opening URL: {}".format(url_))
    try:
        webbrowser.open(url_, new=0, autoraise=True)
    except webbrowser.Error as e:
        CONSOLE.print("Error while trying open URL")
        return FAILURE
    return SUCCESS


def confirm_prompt(prompt_msg):
    res = Prompt.ask(prompt_msg, choices=["yes", "no"], default="no")
    if res == "no":
        return False
    else:
        return True


def get_event_id():
    return datetime.now().strftime(FMT_EVENTID) + str(uuid.uuid4())


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


def convert_time_unit(in_time):
    """
    Converts a duration provided in minutes to time as below:
    [xD] [yh] zm or <1m
    If the duration is over a day the xD will be returned indicating x Day(s)
    If the duration is over an hour then yh will be returned indicating
    y hour(s)
    If the duration is over a minute then zm will be returned indicating z
    minutes
    If duration is less than a minutes then a fixed string of <1m will be
    returned.
    If duration is 0 then an empty string is returned.
    The functiona internally use datetime.timedelta.

    Parameters:
        in_time(int): The duration in minutes

    Returns:
        str: Duration converted in time units as described above.
    """
    if in_time == 0:
        return ""
    out_str = ""
    td = timedelta(seconds=in_time)
    #When the days is not 0 the it returns 'x days, h/hh:mm:ss' else
    #it returns 'h/hh:mm:ss'
    if td.days != 0:
        #If there is non zero days then include it
        out_str = "".join([str(td.days),"D"])
        temp = str(td).split(",")
        time_comp = temp[1].split(":")
    else:
        time_comp = str(td).split(":")
    hour_ = (time_comp[0].lstrip(" ")).lstrip("0")
    minute_ = (time_comp[1].lstrip(" ")).lstrip("0")
    if hour_:
        #If there is non zero hour component then include it along with minutes
        out_str = "".join([out_str,hour_,"h"])
        if minute_:
            out_str = "".join([out_str,minute_,"m"])
    else:
        #There is no hour, so only include minutes
        if minute_:
            out_str = "".join([out_str,minute_,"m"])
        else:
            #Less than a minute
            out_str = "<1m"
    return out_str


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
        ret, return_list = prep_recurring_tasks(task,
                                                ws_tags_list,
                                                True)
        if ret == FAILURE:
            return ret
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
            if str(fl).upper() == TASK_COMPLETE:
                potential_filters[TASK_COMPLETE] = "yes"
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
            if str(fl).startswith("no:") or str(fl).startswith("notes:"):
                potential_filters["notes"] = (str(fl).split(":"))[1]
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
            and "notes" not in potential_filters
            and "tag" not in potential_filters
            and "uuid" not in potential_filters
            and TASK_NOW not in potential_filters
            and TASK_STARTED not in potential_filters
            and "desc"  not in potential_filters
            and "due"  not in potential_filters
            and "hide"  not in potential_filters
            and "end"  not in potential_filters):
        potential_filters[HL_FILTERS_ONLY] = "yes"
    LOGGER.debug("Parsed Filters as below:")
    LOGGER.debug(potential_filters)
    return potential_filters


def parse_date_filters(comp_list):
    """
    Parses and validates the filters provided for date fields. Based on the
    operator the input is parsed, converted to a date from the short format
    where applicable. Where validation fails the operator is set to None to
    allow the calling functions to print back appropriate responses.
    Supported operations include below:
        lt - less than
        le - less than or equal to
        gt - greater than
        ge - greater than or equal to
        bt - between date1 and date2
        eq - equal to

    Paramerters:
        comp_list(list): List made up of operator, date1 and date2

    Returns:
        list: List made of up of operator, date1 and date2 post the validations
              and conversions to proper date
    """
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
            #the other operators require date1
            opr = None
    else:
        #Not a valid operator so set it as None
        opr = None
    return [opr, dt1, dt2]


def carryover_recur_dates(base_task):
    base_uuid = base_task.uuid
    base_version = base_task.version
    try:
        res = (SESSION.query(WorkspaceRecurDates)
                    .filter(and_(WorkspaceRecurDates.uuid == base_uuid,
                                WorkspaceRecurDates.version
                                    == base_version - 1))
                    .all())
        for rec_dt in res:
            SESSION.expunge(rec_dt)
            make_transient(rec_dt)
            rec_dt.uuid = base_uuid
            rec_dt.version = base_version
            SESSION.add(rec_dt)
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        CONSOLE.print("Error in adding recurring dates")
        return FAILURE
    return SUCCESS


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


def calc_task_scores(task_list):
    """
    Assigns a score for tasks based on the below task properties. Each property
    has a weight assigned to it. The final score for the task is then written
    back to the Workspace object.

    Initial Scoring:
        Now - Yes then 100 else 0. Weight of 15
        Priority - High, Medium, Normal, Low - 100, 95, 85, 70
        Status - STARTED 100, TO_DO, 75
        Groups - If any then 50 else 0
        Tags - If any then 50 else 0
        Notes - If any then 50 else 0
        Inception - Older tasks score higher
        Due - Tasks closer to due date score higher with bias towards tasks
        in the future compared to overdue tasks

    Weights assigned are as below totalling to 100:
        Now - 15
        Priority - 10
        Status - 14
        Groups - 1
        Tags - 1
        Notes - 1
        Inception - 8
        Due - 50

    Parameters:
        task_list(list): List of Workspace objects for which the tasks are
        scored

    Returns:
        list: List of Workspace objects recieved as input but with the task
        score written to the score property
    """
    sc_now = {1:100}
    sc_priority = {PRIORITY_HIGH[0]:100, PRIORITY_MEDIUM[0]:95,
                   PRIORITY_NORMAL[0]:85, PRIORITY_LOW[0]:70}
    sc_status = {TASK_STATUS_STARTED:100, TASK_STATUS_TODO:75}
    sc_groups = {"yes":10}
    sc_tags = {"yes":10}
    sc_notes = {"yes":10}
    sc_due = {"today":100, "past":99, "fut":99.5}
    weights = {"now":15, "due":50, "priority":15, "status":14, "inception":3,
               "groups":1,"tags":1,"notes":1}
    due_sum = 0
    incep_sum = 0
    for task in task_list:
        if task.due is not None:
            #For Due scoring
            due_sum = (due_sum + abs(task.due_diff_today))
        #For inception scoring
        incep_sum = (incep_sum + task.incep_diff_now)
    if due_sum == 0:
        due_sum = 1
    ret_score_list = {}
    for task in task_list:
        tags = get_tags(task.uuid, task.version, expunge=False)
        score = {}
        try:
            #Now
            score["now"] = ((sc_now.get(task.now_flag) or 0)
                                * weights.get("now"))
            #Priority
            score["pri"] = ((sc_priority.get(task.priority) or 0)
                                    * weights.get("priority"))
            #Status
            score["sts"] = ((sc_status.get(task.status) or 0)
                                    * weights.get("status"))
            #Groups
            if task.groups:
                score["grp"] =  (sc_groups.get("yes")) * weights.get("groups")
            #Tags
            if tags:
                score["tag"] =  (sc_tags.get("yes")) * weights.get("tags")
            #Notes
            if task.notes:
                score["notes"] =  (sc_notes.get("yes")) * weights.get("tags")
            #Inception
            score["incp"] = ((sc_due.get("today") * int(task.incep_diff_now)
                                /incep_sum) * weights.get("inception"))
            #Due
            if task.due is not None:
                if int(task.due_diff_today) == 0:
                    score["due"] =  (sc_due.get("today")) * weights.get("due")
                elif int(task.due_diff_today) < 0:
                    score["due"] =  ((sc_due.get("past")
                                        - abs(int(pow(task.due_diff_today, 2))
                                            /due_sum))
                                    * weights.get("due"))
                else:
                    score["due"] = ((sc_due.get("fut")
                                        - (int(pow(task.due_diff_today, 2))
                                            /due_sum))
                                    * weights.get("due"))
        except ZeroDivisionError as e:
            CONSOLE.print("Unable to calculate task scores...")
            return None
        LOGGER.debug("Score for task id {} as below".format(task.uuid))
        LOGGER.debug(score)
        ret_score_list[task.uuid] = round(sum(score.values())/100,2)
    return ret_score_list


def get_and_print_task_count(print_dict):
    """
    Displays the task attributes for an added or modified task. Additionally
    display the number of tasks being displayed as well as well the number
    of tasks in total in the area being displayed, pending, completed or bin.

    Parameters:
        print_dict(dict): Dictionary indicating which area and the task details
                          that need to be printed
    """
    # Print Task Details
    if print_dict.get(PRNT_TASK_DTLS):
        task_tags_list = print_dict.get(PRNT_TASK_DTLS)
        for item in task_tags_list:
            ws_task = item[0]
            tags_str = item[1]
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
                reflect_object_n_print(ws_task, to_print=True,
                                        print_all=False)
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
            CONSOLE.print("--")
            LOGGER.debug("Added/Updated Task UUID: {} and Area: {}"
                         .format(ws_task.uuid, ws_task.area))
    # Print No. of Tasks Displayed in the view
    if print_dict.get(PRNT_CURR_VW_CNT):
        CONSOLE.print(("Displayed Tasks: [magenta]{}[/magenta]"
                        .format(print_dict.get(PRNT_CURR_VW_CNT))),
                        style="info")

    # Print Pending, Complted and Bin Tasks
    curr_day = datetime.now()
    try:
        # Pending Tasks
        if print_dict.get(WS_AREA_PENDING) == "yes":
            # Get count of pending tasks split by HIDDEN and VISIBLE
            # Build case expression separately to simplify readability
            visib_xpr = (case((and_(Workspace.hide > curr_day.date(),
                                    Workspace.hide != None),
                               "HIDDEN"), else_="VISIBLE")
                         .label("VISIBILITY"))
            # Inner query to match max version for a UUID
            max_ver_sqr = (SESSION.query(Workspace.uuid,
                                         func.max(Workspace.version)
                                         .label("maxver"))
                           .group_by(Workspace.uuid).subquery())
            # Final Query
            results_pend = (SESSION.query(visib_xpr,
                                          func.count(distinct(Workspace.uuid))
                                          .label("CNT"))
                            .join(max_ver_sqr, Workspace.uuid ==
                                  max_ver_sqr.c.uuid)
                            .filter(and_(Workspace.area ==
                                         WS_AREA_PENDING,
                                         Workspace.version ==
                                         max_ver_sqr.c.maxver,
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
            if print_dict.get(WS_AREA_PENDING) == "yes":
                CONSOLE.print("Total Pending Tasks: "
                                "[magenta]{}[/magenta], "
                                "of which Hidden: "
                                "[magenta]{}[/magenta]"
                                .format(total, hid), style="info")
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
            CONSOLE.print("Total Completed tasks: [magenta]{}[/magenta]"
                            .format(compl), style="info")
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
            CONSOLE.print("Total tasks in Bin: [magenta]{}[/magenta]"
                            .format(binn), style="info")

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
        CONSOLE.print(out_str, end=None)
        return
    else:
        return out_str


def calc_duration(src_ops, ws_task_src, ws_task):
    if ws_task_src.task_type in [TASK_TYPE_NRML, TASK_TYPE_DRVD]:
        if src_ops == OPS_STOP:
            #Since the task is stopped calculate the duration
            duration = round(ws_task_src.duration
                                        + (datetime.strptime(ws_task.created,
                                                             FMT_DATETIME)
                                            - datetime
                                               .strptime(ws_task_src.dur_event,
                                                          FMT_DATETIME))
                                           .total_seconds())
        elif src_ops in ([OPS_START, OPS_MODIFY, OPS_DONE, OPS_DELETE,
                          OPS_REVERT, OPS_NOW]):
            #For Starting or modifying, completing, deleting, reverting the
            #task or setting now, carry forward last version's duration
            duration = ws_task_src.duration
        else:
            #For any other operation just set the duration to 0
            duration = 0
        if (src_ops in [OPS_MODIFY, OPS_NOW, OPS_UNLINK, OPS_DELETE, OPS_DONE,
                        OPS_REVERT]):
            """
            For these Ops ensure the last started/stopped version's duration
            event time is carried forward. This is to ensure duration can be
            calculated accurately. Revert should retain the last duration event
            time as well
            """
            dur_event = ws_task_src.dur_event
        else:
            """
            For start and stop the time will be creation time to calculate the
            duration. For reset we use the version's created time, same or Add
            """
            dur_event = ws_task.created
    else:
        #For base task there will be no duration and duration event time
        duration = 0
        dur_event = None
    return duration, dur_event


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
    next_due = None
    if recur_mode == MODE_DAILY:
        if recur_when is None:
            next_due = (list(rrule(DAILY, count=cnt, dtstart=start_dt,
                                   until=end_dt)))
        else:
            rec_intvl = int(recur_when[1:])
            next_due = (list(rrule(DAILY, interval=rec_intvl, count=cnt,
                                   dtstart=start_dt, until=end_dt)))
    elif recur_mode == MODE_WEEKLY:
        if recur_when is None:
            next_due = (list(rrule(WEEKLY, count=cnt, dtstart=start_dt,
                                   until=end_dt)))
        else:
            rec_intvl = int(recur_when[1:])
            next_due = (list(rrule(WEEKLY, interval=rec_intvl, count=cnt,
                                   dtstart=start_dt, until=end_dt)))
    elif recur_mode == MODE_MONTHLY:
        if recur_when is None:
            next_due = (list(rrule(MONTHLY, count=cnt, dtstart=start_dt,
                                   until=end_dt)))
        else:
            rec_intvl = int(recur_when[1:])
            next_due = (list(rrule(MONTHLY, interval=rec_intvl, count=cnt,
                                   dtstart=start_dt, until=end_dt)))
    elif recur_mode == MODE_YEARLY:
        if recur_when is None:
            next_due = (list(rrule(YEARLY, count=cnt, dtstart=start_dt,
                                   until=end_dt)))
        else:
            rec_intvl = int(recur_when[1:])
            next_due = (list(rrule(YEARLY, interval=rec_intvl, count=cnt,
                                   dtstart=start_dt, until=end_dt)))
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
    errmsg = ("Insufficient input for recurrence. Check 'myt add --help' for "
             "more info and examples.")
    when = []
    if (recur[0:2]).ljust(2, " ") in VALID_MODES:
        """
        Do the first 2 characters make up a valid mode. If they do then
        attempt to validate the string for EXTENDED mode - where the repeat
        information needs to be provided
        EXTENDED Mode
        """
        mode = recur[0:2]
        when = (recur[2:]).rstrip(",").lstrip(",")
        if not when:
            CONSOLE.print(errmsg)
            return FAILURE, None, None
        # Convert to a list to validate
        when_list = when.split(",")
        if when_list:
            #Cheack if each item in the repeat string is an integer
            try:
                when_list = [int(i) for i in when_list]
            except ValueError as e:
                CONSOLE.print(errmsg)
                return FAILURE, None, None
        #Validate if the repeat items are valid for the respective mode
        if mode == MODE_WKDAY:
            if not set(when_list).issubset(WHEN_WEEKDAYS):
                CONSOLE.print(errmsg)
                return FAILURE, None, None
        elif mode == MODE_MTHDYS:
            if not set(when_list).issubset(WHEN_MONTHDAYS):
                CONSOLE.print(errmsg)
                return FAILURE, None, None
        elif mode == MODE_MONTHS:
            if not set(when_list).issubset(WHEN_MONTHS):
                CONSOLE.print(errmsg)
                return FAILURE, None, None
    elif recur[0:1] in VALID_MODES:
        """
        If the first 2 characters do not make up a valid mode check if the
        first character by itself is a valid  mode.
        """
        mode = recur[0:1]
        if len(recur) == 1:
            #If only this 1 character provided then it is BASIC mode
            when = None
        elif recur[1:2] == "E":
            """
            If E is the second character then user is asking for 'every'
            X days or every X months etc. This is also an EXTENDED Mode
            """
            try:
                when = int(recur[2:])
                when = "E" + str(when)
            except ValueError as e:
                CONSOLE.print(errmsg)
                return FAILURE, None, None
        else:
            #Not Basic mode nor a valid extended mode
            CONSOLE.print(errmsg)
            return FAILURE, None, None

    else:
        #Not a valid mode
        CONSOLE.print(errmsg)
        return FAILURE, None, None
    return SUCCESS, mode, when


#Primary database retrieval function
def get_tasks(uuid_version=None, expunge=True):
    """
    Returns the task details for a list of task uuid and versions.

    Retrieves tasks details from the database for he provided
    list of task UUIDs and Versions.

    Parameters:
        task_uuid_and_version(list): List of tuples of uuid and versions
        expunge(boolean): Should the retrieved objects be expunged after
                          retrieval

    Returns:
        list: List with Workspace objects representing each task
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
    """
    Returns the tags in terms of WorkspaceTags objects using the provided
    task uuid and version

    Parameters:
        task_uuid(str): UUID of task for which the tags need to be returned
        task_version(int): Version of task
        expunge(boolean): Should the retrieved objects be expunged after
                          retrieval

    Returns:
        list: A list of WorkspaceTags objects
    """
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


def get_task_uuid_n_ver(potential_filters):
    """
    Return task UUID and version by applying filters on tasks

    Using a list of filters identify the relevant task UUIDs and their
    latest versions. When all pending tasks are requested, i.e. no other 
    filters are provided, then hidden tasks are not extracted and the 'hidden' 
    filter is required to extract them. 
    When any other filter is provided the search by default will include 
    hidden tasks. This is done since the filters requested could apply to 
    hidden tasks and can cause unexpected behaviours if the hidden task are 
    filtered out by default. This has more significant impact on modify, 
    delete, start, stop and now actions.
    The purpose of hiding tasks is to avoid cluttering the default view 
    command (display_default) which gives an overview of all pending tasks.
    
    The filters come in the form of a dictionary and expected keys include:
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
        1. All tasks in pending area
            OR
        2. ID based filter for Pending area
            OR
        3. NOW task for Pending area
            OR
        4. Outstanding Recurring Tasks (Not User Callable)
            OR
        5. UUID based filter for selected area
            OR
        6. Derived Tasks for a base uuid for selected area (Not User Callable)
            OR
        7. Base Task only for a baseuuid for selected area (Not User Callable)
            OR
        8. By Event ID without area (Not User Callable)
            OR
        9. All tasks(base/derived/normal) which are in Pending area but
           without an ID (Not User Callable)
            OR
        10. Groups AND Tags AND Notes AND Description AND Due AND Hide AND End
            AND Overdue AND Today AND Hidden AND Started for selected area
                OR
           Defaults to Completed / Bin Tasks, depending on select area

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters

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
    done_task = potential_filters.get(TASK_COMPLETE)
    bin_task = potential_filters.get(TASK_BIN)
    started_task = potential_filters.get(TASK_STARTED)
    now_task = potential_filters.get(TASK_NOW)
    idn = potential_filters.get("id")
    uuidn = potential_filters.get("uuid")
    group = potential_filters.get("group")
    notes = potential_filters.get("notes")
    tag = potential_filters.get("tag")
    desc = potential_filters.get("desc")
    due_list = potential_filters.get("due")
    hide_list = potential_filters.get("hide")
    end_list = potential_filters.get("end")
    bybaseuuid = potential_filters.get("bybaseuuid")
    baseuuidonly = potential_filters.get("baseuuidonly")
    osrecur = potential_filters.get("osrecur")
    eventid = potential_filters.get("eventid")
    missingid = potential_filters.get("missingid")
    curr_date = datetime.now().date()
    """
    Inner query to match max version for a UUID. This is the default version
    and filters on NORMAL and DERIVED tasks. Within each filter if there is a
    need to deviate from this then they will use their own max_ver sub queries.

    """
    max_ver_sqr = (SESSION.query(Workspace.uuid,
                                 func.max(Workspace.version)
                                 .label("maxver"))
                   .filter(Workspace.task_type.in_([TASK_TYPE_DRVD,
                                                    TASK_TYPE_NRML]))
                   .group_by(Workspace.uuid).subquery())
    if done_task is not None:
        drvd_area = WS_AREA_COMPLETED
    elif bin_task is not None:
        drvd_area = WS_AREA_BIN
    else:
        drvd_area = WS_AREA_PENDING
    LOGGER.debug("Derived area is {}".format(drvd_area))
    if all_tasks:
        """
        When no filter is provided retrieve all tasks from pending area.
        Hidden tasks are not included here.
        """
        LOGGER.debug("Inside all_tasks filter")
        innrqr_all = (SESSION.query(Workspace.uuid, Workspace.version)
                    .join(max_ver_sqr, and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                    .filter(and_(Workspace.area == WS_AREA_PENDING,
                                or_(Workspace.hide <= curr_date,
                                    Workspace.hide == None))))
        innrqr_list.append(innrqr_all)
    elif idn is not None:
        """
        If id(s) is provided extract tasks only based on ID as it is most
        specific. Works only in pending area
        """
        id_list = idn.split(",")
        LOGGER.debug("Inside id filter with below params")
        LOGGER.debug(id_list)
        innrqr_idn = (SESSION.query(Workspace.uuid, Workspace.version)
                    .join(max_ver_sqr, and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                    .filter(and_(Workspace.area == WS_AREA_PENDING,
                                Workspace.id.in_(id_list))))
        innrqr_list.append(innrqr_idn)
    elif now_task is not None:
        """
        If now task filter then return the task marked as now_flag = True from
        pending area
        """
        LOGGER.debug("Inside now filter")
        innrqr_now = (SESSION.query(Workspace.uuid, Workspace.version)
                    .filter(and_(Workspace.area == WS_AREA_PENDING,
                                Workspace.now_flag == True,
                                Workspace.id != '-',
                                Workspace.task_type
                                .in_([TASK_TYPE_DRVD,
                                        TASK_TYPE_NRML]))))
        innrqr_list.append(innrqr_now)
    elif osrecur is not None:
        LOGGER.debug("Inside Outstanding Recurring Tasks filter")
        max_ver_sqr1 = (SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                        .label("maxver"))
                        .filter(Workspace.task_type == TASK_TYPE_BASE)
                        .group_by(Workspace.uuid).subquery())
        innrqr_osrecr = (SESSION.query(Workspace.uuid, Workspace.version)
                    .join(max_ver_sqr1,
                            and_(Workspace.version ==
                                max_ver_sqr1.c.maxver,
                                Workspace.uuid ==
                                max_ver_sqr1.c.uuid))
                    .filter(and_(Workspace.area == WS_AREA_PENDING,
                                Workspace.id == '*',
                                Workspace.task_type ==
                                TASK_TYPE_BASE,
                                or_(Workspace.recur_end == None,
                                    Workspace.recur_end >=
                                    curr_date))))
        innrqr_list.append(innrqr_osrecr)
    elif uuidn is not None:
        """
        If uuid(s) is provided extract tasks only based on UUID as
        it is most specific. Works only in completed or bin area.
        Preference given to UUID based filters.
        """
        uuid_list = uuidn.split(",")
        LOGGER.debug("Inside UUID filter with below params")
        LOGGER.debug(uuid_list)
        innrqr_uuid = (SESSION.query(Workspace.uuid, Workspace.version)
                        .join(max_ver_sqr, and_(Workspace.version ==
                                                max_ver_sqr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_sqr.c.uuid))
                        .filter(and_(Workspace.uuid.in_(uuid_list),
                                    Workspace.area == drvd_area)))
        innrqr_list.append(innrqr_uuid)
    elif bybaseuuid is not None:
        LOGGER.debug("Inside By Base UUID filter with below params")
        LOGGER.debug(bybaseuuid)
        max_ver_sqr1 = (SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                        .label("maxver"))
                        .filter(Workspace.task_type.in_([TASK_TYPE_DRVD]))
                        .group_by(Workspace.uuid).subquery())
        innrqr_buuid = (SESSION.query(Workspace.uuid, Workspace.version)
                        .join(max_ver_sqr1, and_(Workspace.version ==
                                                max_ver_sqr1.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_sqr1.c.uuid))
                        .filter(and_(Workspace.task_type ==
                                        TASK_TYPE_DRVD,
                                        Workspace.base_uuid == bybaseuuid,
                                        Workspace.area == drvd_area)))
        innrqr_list.append(innrqr_buuid)
    elif baseuuidonly is not None:
        LOGGER.debug("Inside Base UUID Only filter with below params")
        LOGGER.debug(baseuuidonly)
        max_ver_sqr1 = (SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                        .label("maxver"))
                        .filter(Workspace.task_type == TASK_TYPE_BASE)
                        .group_by(Workspace.uuid).subquery())
        innrqr_buuido = (SESSION.query(Workspace.uuid, Workspace.version)
                            .join(max_ver_sqr1, and_(Workspace.version ==
                                                    max_ver_sqr1.c.maxver,
                                                    Workspace.uuid ==
                                                    max_ver_sqr1.c.uuid))
                            .filter(and_(Workspace.task_type == TASK_TYPE_BASE,
                                        Workspace.uuid == baseuuidonly,
                                        Workspace.area == drvd_area)))
        innrqr_list.append(innrqr_buuido)
    elif eventid is not None:
        LOGGER.debug("Inside Event ID filter with below params")
        LOGGER.debug(eventid)
        innrqr_eventid = (SESSION.query(Workspace.uuid, Workspace.version)
                            .filter(Workspace.event_id == eventid))
        innrqr_list.append(innrqr_eventid)
    elif missingid is not None:
        LOGGER.debug("Inside Missing ID filter with below params")
        LOGGER.debug(baseuuidonly)
        max_ver_sqr1 = (SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                        .label("maxver"))
                        .group_by(Workspace.uuid).subquery())
        innrqr_missid = (SESSION.query(Workspace.uuid, Workspace.version)
                            .join(max_ver_sqr1, and_(Workspace.version ==
                                                    max_ver_sqr1.c.maxver,
                                                    Workspace.uuid ==
                                                    max_ver_sqr1.c.uuid))
                            .filter(and_(Workspace.id == '-',
                                        Workspace.area == WS_AREA_PENDING)))
        innrqr_list.append(innrqr_missid)
    else:
        if group is not None:
            """
            Query to get a list of uuid and version for matchiing groups
            from all 3 areas. Will be case insensitive
            """
            LOGGER.debug("Inside group filter with below params")
            LOGGER.debug("%" + group + "%")
            innrqr_groups = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                                .filter(and_(Workspace.groups
                                                    .like("%"+group+"%"),
                                            Workspace.area == drvd_area)))
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
                            .join(max_ver_sqr,
                                    and_(WorkspaceTags.version ==
                                        max_ver_sqr.c.maxver,
                                        WorkspaceTags.uuid ==
                                        max_ver_sqr.c.uuid))
                            .join(Workspace, and_(Workspace.uuid ==
                                                    WorkspaceTags.uuid,
                                                  Workspace.version ==
                                                    WorkspaceTags.version))
                            .filter(and_(WorkspaceTags.tags.in_(tag_list),
                                         Workspace.area == drvd_area)))
            else:
                #No tag provided, so any task that has a tag
                innrqr_tags = (SESSION.query(WorkspaceTags.uuid,
                                            WorkspaceTags.version)
                            .join(max_ver_sqr,
                                    and_(WorkspaceTags.version ==
                                        max_ver_sqr.c.maxver,
                                        WorkspaceTags.uuid ==
                                        max_ver_sqr.c.uuid))
                            .join(Workspace, and_(Workspace.uuid ==
                                                    WorkspaceTags.uuid,
                                                  Workspace.version ==
                                                    WorkspaceTags.version))
                            .filter(Workspace.area == drvd_area))
            innrqr_list.append(innrqr_tags)
        if notes is not None:
            """
            Query to get a list of uuid and version based on notes
            from all 3 areas. Will be case insensitive
            """
            LOGGER.debug("Inside notes filter with below params")
            LOGGER.debug("%" + notes + "%")
            innrqr_notes = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                                .filter(and_(Workspace.notes
                                                    .like("%"+notes+"%"),
                                            Workspace.area == drvd_area)))
            innrqr_list.append(innrqr_notes)
        if desc is not None:
            """
            Query to get a list of uuid and version for tasks which match
            the description as a substring. Will be case insensitive
            """
            LOGGER.debug("Inside description filter with below params")
            LOGGER.debug("%" + desc + "%")
            innrqr_desc = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                                .filter(and_(Workspace.description
                                                    .like("%"+desc+"%"),
                                            Workspace.area == drvd_area)))
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
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due == due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "gt":
                innrqr_due = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due > due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "ge":
                innrqr_due = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due >= due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "lt":
                innrqr_due = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due < due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "le":
                innrqr_due = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due <= due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "bt":
                innrqr_due = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                                        .join(max_ver_sqr,
                                        and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                                        .filter(and_(Workspace.due
                                                        >= due_list[1],
                                                    Workspace.due
                                                        <= due_list[2],
                                                    Workspace.area
                                                        == drvd_area)))
            else:
                #No valid due filter, so any task that has a due date
                innrqr_due = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                                .filter(and_(Workspace.due != None,
                                                Workspace.area == drvd_area)))
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
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide == hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "gt":
                innrqr_hide = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide > hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "ge":
                innrqr_hide = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide >= hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "lt":
                innrqr_hide = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide < hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "le":
                innrqr_hide = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide <= hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "bt":
                innrqr_hide = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                                        .join(max_ver_sqr,
                                        and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                                        .filter(and_(Workspace.hide
                                                        >= hide_list[1],
                                                    Workspace.hide
                                                        <= hide_list[2],
                                                    Workspace.area
                                                        == drvd_area)))
            else:
                #No valid hide filter, so any task that has a hide date
                innrqr_hide = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                                .filter(and_(Workspace.hide != None,
                                                Workspace.area == drvd_area)))
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
                                        .join(max_ver_sqr,
                                            and_(Workspace.version ==
                                                    max_ver_sqr.c.maxver,
                                                Workspace.uuid ==
                                                    max_ver_sqr.c.uuid))
                                        .filter(and_(Workspace.recur_end
                                                        == end_list[1],
                                                        Workspace.area
                                                        == drvd_area)))
            elif end_list[0] == "gt":
                innrqr_end = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                                    .join(max_ver_sqr,
                                        and_(Workspace.version ==
                                                max_ver_sqr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_sqr.c.uuid))
                                    .filter(and_(and_(Workspace.recur_end
                                                        > end_list[1],
                                                        Workspace.area
                                                        == drvd_area))))
            elif end_list[0] == "ge":
                innrqr_end = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                                    .join(max_ver_sqr,
                                        and_(Workspace.version ==
                                                max_ver_sqr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_sqr.c.uuid))
                                    .filter(and_(Workspace.recur_end
                                                    >= end_list[1],
                                                    Workspace.area
                                                    == drvd_area)))
            elif end_list[0] == "lt":
                innrqr_end = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                                    .join(max_ver_sqr,
                                        and_(Workspace.version ==
                                                max_ver_sqr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_sqr.c.uuid))
                                    .filter(and_(Workspace.recur_end
                                                    < end_list[1],
                                                    Workspace.area
                                                    == drvd_area)))
            elif end_list[0] == "le":
                innrqr_end = (SESSION.query(Workspace.uuid,
                                        Workspace.version)
                                    .join(max_ver_sqr,
                                        and_(Workspace.version ==
                                                max_ver_sqr.c.maxver,
                                                Workspace.uuid ==
                                                max_ver_sqr.c.uuid))
                                    .filter(and_(Workspace.recur_end
                                                    <= end_list[1],
                                                    Workspace.area
                                                    == drvd_area)))
            elif end_list[0] == "bt":
                innrqr_end = (SESSION.query(Workspace.uuid,
                                                    Workspace.version)
                                        .join(max_ver_sqr,
                                        and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                                        .filter(and_(Workspace.recur_end
                                                    >= end_list[1],
                                                Workspace.recur_end
                                                    <= end_list[2],
                                                Workspace.area
                                                    == drvd_area)))
            else:
                #No valid recur end filter, so any task that has a
                #recur end date
                innrqr_end = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                                .filter(and_(Workspace.recur_end != None,
                                                Workspace.area == drvd_area)))
            innrqr_list.append(innrqr_end)
        """
        Look for modifiers that work in the pending area
        """
        LOGGER.debug("Status for OVERDUE {}, TODAY {}, HIDDEN {}, STARTED{}"
                    .format(overdue_task, today_task, hidden_task,
                            started_task))
        if overdue_task is not None:
            LOGGER.debug("Inside overdue filter")
            innrqr_overdue = (SESSION.query(Workspace.uuid,
                                            Workspace.version)
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
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
                            .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
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
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
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
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                            max_ver_sqr.c.maxver,
                                            Workspace.uuid ==
                                            max_ver_sqr.c.uuid))
                                .filter(and_(Workspace.area ==
                                            WS_AREA_PENDING,
                                            Workspace.status ==
                                            TASK_STATUS_STARTED
                                            )))
            innrqr_list.append(innrqr_started)
        if not innrqr_list:
            #If no query has been created check if the HL area filters for
            #done or bin are provided
            if done_task is not None or bin_task is not None:
                """
                If no modifiers provided and if done or bin filters provided
                then create a default query for all tasks from completed  or
                bin area
                """
                LOGGER.debug("Inside default filter")
                innrqr_all = (SESSION.query(Workspace.uuid, Workspace.version)
                            .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(Workspace.area == drvd_area))
                innrqr_list.append(innrqr_all)
            else:
                #No valid filters, so return None
                return None
    try:
        firstqr = innrqr_list.pop(0)
        # Returns Tuple of rows, UUID,Version
        results = firstqr.intersect(*innrqr_list).all()
    except (SQLAlchemyError) as e:
        LOGGER.error(str(e))
        return None
    else:
        LOGGER.debug("List of resulting Task UUIDs and Versions:")
        LOGGER.debug("------------- {}".format(results))
        return results


#Core functions for the commands
def perform_undo():
    """
    Deletes all task data that have been created as part of the latest event.
    Using the latest event ID the corresponding task UUID and Version are
    identified. Then these are deleted from Workspace, WorkspaceTags and
    WorkspaceRecurDates.
    Post deletion the latest versions of tasks in the pending area are assigned
    appropriate IDs.

    Parameters:
        None

    Returns:
        int: 0 if successful else 1
    """
    #Get latest event ID
    res = SESSION.query(func.max(Workspace.event_id)).all()
    if res is not None:
        max_evt_id = (res[0])[0]
    else:
        return SUCCESS
    potential_filters = {}
    potential_filters["eventid"] = max_evt_id
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if uuid_version_results is None:
        CONSOLE.print("No more undo actions available")
        return SUCCESS
    #Attempt to delete the tasks using the UUID and version
    try:
        (SESSION.query(WorkspaceRecurDates)
            .filter(tuple_(WorkspaceRecurDates.uuid,
                           WorkspaceRecurDates.version)
                            .in_(uuid_version_results))
            .delete(synchronize_session=False))

        (SESSION.query(WorkspaceTags)
            .filter(tuple_(WorkspaceTags.uuid, WorkspaceTags.version)
                            .in_(uuid_version_results))
            .delete(synchronize_session=False))
        (SESSION.query(Workspace)
            .filter(tuple_(Workspace.uuid, Workspace.version)
                            .in_(uuid_version_results))
            .delete(synchronize_session=False))
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        LOGGER.error("Error while performing delete as part of undo")
        return FAILURE
    #Next for the max versions of task in pending area assign a task ID.
    potential_filters = {}
    potential_filters["missingid"] = "yes"
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if uuid_version_results is None:
        #Nothing to do
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        if task.task_type in [TASK_TYPE_DRVD, TASK_TYPE_NRML]:
            task.id = derive_task_id()
        else:
            #If Base  task then use '*' instead
            task.id = "*"
        SESSION.add(task)
    CONSOLE.print("NOTE: Tasks IDs might differ from the pre-undo state...")
    return SUCCESS


def process_url(potential_filters, urlno=None):
    """
    Processes the notes for a task to identify the URLs and then list them for
    the user to select one to be opened. The task is identified using the
    filters provided by users. Only the first task from the filtered tasks is
    processed as this command is meant to work for only 1 task at a time.
    If a urlno is provided then the function attempts to open that URL in that
    position in the notes. If there is no URL in that position then it defaults
    to the behavious mentioned above.
    If there is only 1 URL in the notes then that is opened without a user
    prompt.

    Parameters:
        potential_filters(dict): Dictionary with ID or UUID filters
        urlno(int, default=None): Position of a URL in the notes which should
                                  be opened without a user prompt

    Returns:
        (int): 0 is successful else returns 1
    """
    ret = SUCCESS
    #URL + description, ex: 'https://www.abc.com [ABC's website]'
    regex_1 = r"(http?://\S+\s+\[.*?\]|http?://\S+\
                |https?://\S+\s+\[.*?\]|https?://\S+)"
    #URL only
    regex_2 = r"(http?://\S+|https?://\S+)"
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks with this ID/UUID",
                        style="default")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    ws_task = task_list[0]
    LOGGER.debug("Working on Task UUID {} and Task ID {}"
                    .format(ws_task.uuid, ws_task.id))
    if ws_task.notes is None:
        CONSOLE.print("No notes for this task")
        return SUCCESS
    #Get all URLs along with their descriptions
    #ex: 'https://www.abc.com [ABC's website]'
    url_list = re.findall(regex_1, ws_task.notes)
    LOGGER.debug("Identified URLs:")
    LOGGER.debug(url_list)
    if url_list and url_list is not None:
        if urlno is not None:
            LOGGER.debug("User has provided a urlno - {}".format(urlno))           
            if int(urlno) < 1 or int(urlno) > len(url_list):
                CONSOLE.print("No URL found at the position provided {}. "
                "Attempting to identify URLs..."
                .format(urlno))
            else:
                LOGGER.debug("urlno is valid, attempting to open")
                #Attempt to open a URL at position given by user
                # Extract the URL description if available
                pattern = r'\[(.*?)\]'
                match = re.search(pattern, url_list[urlno-1])
                if match:
                    url_desc = " " + match.group(0) 
                else:
                    url_desc = ""                    
                try:
                    #Extract just the URL
                    #ex: 'https://www.abc.com'
                    url_ = re.findall(regex_2, url_list[urlno-1])
                    if confirm_prompt("Would you like to open " 
                                        + url_[0] + url_desc):
                        ret = open_url(url_[0])
                    return ret
                except IndexError as e:
                    #No URL exists in this position, print message and move
                    #to default behaviour
                    CONSOLE.print("No URL found at the position provided {}. "
                                "Attempting to identify URLs..."
                                .format(urlno))

        LOGGER.debug("URLs found")
        #More than 1 URLavailable so ask user to choose
        cnt = 1
        for cnt, u in enumerate(url_list, start=1):
            LOGGER.debug("Printing URL - {}".format(u))
            #For some reason the descriptions are not 
            #being printed when using console's print
            #so using click's echo instead 
            click.echo("{} - {}".format(str(cnt), u))
        choice_rng = [str(x) for x in list(range(1,cnt+1))]
        res = Prompt.ask("Choose the URL to be openned:",
                            choices=[*choice_rng,"none"],
                            default="none")
        if res == "none":
            ret = SUCCESS
        else:
            url_ = re.findall(regex_2, url_list[int(res)-1])
            ret = open_url(url_[0])
        return ret
    else:
        CONSOLE.print("No URLS found in notes for this task")
    return ret


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
            (SESSION.query(WorkspaceRecurDates)
             .filter(WorkspaceRecurDates.uuid.in_(uuid_list))
             .delete(synchronize_session=False))
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
        CONSOLE.print("Bin emptied!", style="info")
        return SUCCESS
    else:
        CONSOLE.print("Bin is already empty, nothing to do", style="default")
        return SUCCESS


def delete_tasks(ws_task):
    """
    Delete the task by creating a new version for the task with status as
    'DELETED', area as 'bin' and task ID as '-'.

    Parameters:
        ws_task(Workspace): The task which needs deletion
        event_id(text, default=None): The event ID which needs to be used for
        this deletion

    Returns:
        integer: 0 for successful execution, else 1 for any failures
        list: List of tuples of (Workspace - Deleted Tasks, String - Comma
        separated string of tasg for the task)
    """
    task_tags_print = []
    LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
    """
    A task in started state could be requested for deletion. In this case the
    task needs to be stopped first and then marked as complete. This allows
    the task druation to be recorded before completing.
    """
    if ws_task.status == TASK_STATUS_STARTED:
        uuidn = ws_task.uuid
        potential_filters = {}
        potential_filters["uuid"] = uuidn
        ret, innr_tsk_tgs_prnt = stop_task(potential_filters, ws_task.event_id)
        #The stopping of task is not communicated to the user unless there
        #is an issue
        if ret == FAILURE:
            CONSOLE.print("Error while trying to stop task...")
            return ret, None
        innr_task_list = get_tasks(get_task_uuid_n_ver(potential_filters))
        ws_task = innr_task_list[0]
        make_transient(ws_task)
        ws_task.uuid = uuidn
    #Proceed to complete the task
    ws_task.id = "-"
    ws_task.status = TASK_STATUS_DELETED
    ws_task.area = WS_AREA_BIN
    ws_task.now_flag = False
    LOGGER.debug("Deleting Task UUID {} and Task ID {}"
                    .format(ws_task.uuid, ws_task.id))
    ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
    ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                               ws_tags_list,
                                               None,
                                               OPS_DELETE)
    task_tags_print.append((ws_task, tags_str))
    if ret == FAILURE:
        LOGGER.error("Error encountered in adding task version, stopping")
        return ret, None
    return ret, task_tags_print


def prep_delete(potential_filters, event_id, delete_all=False):
    """
    Assess the tasks requested for deletion and makes appropriate decisions
    on how to deal with deletion of recurring tasks and normal tasks. If a
    task is a recurring instance then the user is asked if just that one
    instance needs to be deleted or all pending instances of the recurring
    task.

    If just one instance of task is to be deleted then move it to the
    bin. If this was the last pending instance in the recurrence then the base
    task is also move to the bin. If all tasks in the recurrence need to be
    moved to bin then the base task is also moved to the bin. In the above
    scenarios when the base task is moved to the bin any done tasks are
    unlinked, ie their linkage to thsi base task is removed and they are
    turned into normal tasks. This allows them to be reverted and operated on
    at a lter point.

    For normal tasks the task just gets moved to the bin.

    Parameters:
        potential_filters(dict): Filters which determine the tasks which
        require deletion
        event_id(text, default=None): An event id if it needs to be used for
        this operation
        delete_all(boolean, default=False): Used to force a deletion of all
        tasks requested as part of the filter rather than asking user input.
        Not invoked directly on user operation, instead used by other
        operations.

    Returns:
        integer: 0 for successful execution, else 1 for any failures
        list: List of tuples of (Workspace - Deleted Tasks, String - Comma
        separated string of tasg for the task)
    """
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    modified_base_uuids = set()
    task_tags_print = []
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to delete", style="default")
        return SUCCESS, None
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        if task.base_uuid in modified_base_uuids:
            LOGGER.debug("Already modifed base task, ignoring")
            ret = SUCCESS
            continue
        uuidn = task.uuid
        make_transient(task)
        ws_task = task
        ws_task.uuid = uuidn
        """
        Set the new event ID which will be used for deletions of derived and
        normal tasks. Also this is used in unlinking of done derived tasks
        as well as deletion of base tasks.
        For creating new recurring instances the event ID of the exitsing
        base task is used.
        """
        ws_task.event_id = event_id
        if (ws_task.task_type == TASK_TYPE_DRVD
                and ws_task.area == WS_AREA_PENDING):
            """
            if the task is not in pending area then treat them as normal
            tasks, hence the check for area
            """
            LOGGER.debug("Is a derived task")
            if not delete_all:
                res = Prompt.ask("{}, {} - This is a recurring task, do you "
                                "want to modify 'all' pending instances or "
                                "just 'this' instance"
                                    .format(ws_task.description, ws_task.due),
                                choices=["all", "this", "none"],
                                default="none")
            else:
                LOGGER.debug("Forced delete all")
                res = "all"
            if res == "none":
                ret = SUCCESS
                continue
            elif res == "all":
                """
                Delete all instances of the task in pending area and the base
                task. Unlink any done tasks
                """
                base_uuid = ws_task.base_uuid
                if ws_task.task_type == TASK_TYPE_DRVD:
                    modified_base_uuids.add(base_uuid)
                potential_filters = {}
                potential_filters["bybaseuuid"] = base_uuid
                uuid_version_results = get_task_uuid_n_ver(potential_filters)
                task_list = get_tasks(uuid_version_results)
                potential_filters = {}
                potential_filters["baseuuidonly"] = base_uuid
                uuid_version_results = get_task_uuid_n_ver(potential_filters)
                task_list2 = get_tasks(uuid_version_results)
                task_list.append(task_list2[0])
                #Delete all tasks now
                for innrtask in task_list:
                    uuidn = innrtask.uuid
                    make_transient(innrtask)
                    innrtask.uuid = uuidn
                    innrtask.event_id = event_id
                    ret, ret_task_tags_print = delete_tasks(innrtask)
                    if ret == FAILURE:
                        LOGGER.error("Error encountered while deleting tasks")
                        return ret, None
                    task_tags_print = (task_tags_print + (ret_task_tags_print
                                                            or []))
                #Next unlink all done tasks
                potential_filters = {}
                potential_filters["bybaseuuid"] = base_uuid
                potential_filters[TASK_COMPLETE] = "yes"
                ret, ret_task_tags_print = unlink_tasks(potential_filters,
                                                        event_id)
                task_tags_print = (task_tags_print + (ret_task_tags_print
                                                            or []))
                if ret == FAILURE:
                    LOGGER.error("Error while trying to unlink completed "
                                 "instances for this recurring task")
                    return ret, None
            elif res == "this":
                """
                Delete the requested instanc of task. After that is there are
                no more instances of this task in pending area then delete
                the base task as well and unlink all done tasks
                """
                #First delete this task
                LOGGER.debug("This task deletion selected. Attempting to "
                             "delete UUID {}".format(ws_task.uuid))
                base_uuid = ws_task.base_uuid
                ret, ret_task_tags_print = delete_tasks(ws_task)
                if ret == FAILURE:
                    LOGGER.error("Error encountered while deleting tasks")
                    return ret, None
                task_tags_print = (task_tags_print + (ret_task_tags_print
                                                       or []))
                """
                Next try to create another instance of the task. This is to
                ensure there is atleast 1 instance in the default view command
                to allow users to modify task if required.
                """
                LOGGER.debug("Attempting to add a recurring instance if "
                             "required")
                potential_filters = {}
                potential_filters["baseuuidonly"] = base_uuid
                uuid_version_results = get_task_uuid_n_ver(potential_filters)
                task_list = get_tasks(uuid_version_results)
                base_task = task_list[0]
                ws_tags_list = get_tags(base_task.uuid, base_task.version)
                make_transient(base_task)
                base_task.uuid = base_uuid
                #Creation of a new recurring instance should use the same
                #Event ID as the existing version of base task. So deletion's
                # event ID is not used to overwrite here
                ret, return_list = prep_recurring_tasks(base_task,
                                                        ws_tags_list,
                                                        True)
                if ret == FAILURE:
                    LOGGER.error("Error encountered in adding task version, "
                             "stopping")
                    return ret, None
                """
                Check if there are any more instances of the task left
                If there are then do nothing more
                If none then the base task should be mvoed to the bin
                And the all done instances need to be unlinked.
                """
                #Main Query
                LOGGER.debug("Checking if there are no more instances in "
                             "pending area.")
                max_ver_sqr = (SESSION.query(Workspace.uuid,
                                            func.max(Workspace.version)
                                                .label("maxver"))
                                    .filter(Workspace.task_type
                                                == TASK_TYPE_DRVD)
                                    .group_by(Workspace.uuid)
                                    .subquery())
                results = (SESSION.query(Workspace.uuid, Workspace.version)
                                .join(max_ver_sqr,
                                        and_(Workspace.uuid
                                                == max_ver_sqr.c.uuid,
                                            Workspace.version
                                                == max_ver_sqr.c.maxver))
                                .filter(and_(Workspace.task_type
                                                == TASK_TYPE_DRVD,
                                            Workspace.area == WS_AREA_PENDING,
                                            Workspace.base_uuid == base_uuid))
                                .all())
                if not results:
                    """
                    No tasks in pending area, proceed to delete base and
                    unlink done tasks
                    """
                    LOGGER.debug("No more instances in pending, proceeding "
                                 "to delete base task and unlink base tasks")
                    potential_filters = {}
                    potential_filters["baseuuidonly"] = base_uuid
                    uuid_version_results = get_task_uuid_n_ver(
                                                            potential_filters)
                    task_list = get_tasks(uuid_version_results)
                    base_task = task_list[0]
                    uuidn = base_task.uuid
                    make_transient(base_task)
                    base_task.uuid = uuidn
                    #USe the new event ID for the deletion and unlink
                    base_task.event_id = event_id
                    ret, ret_task_tags_print = delete_tasks(base_task)
                    if ret == FAILURE:
                        LOGGER.error("Error encountered while deleting tasks")
                        return ret, None
                    task_tags_print = (task_tags_print + (ret_task_tags_print
                                                        or []))
                    #Base task is deleted, next unlink the done instances
                    LOGGER.debug("Base task deleted {}, proceeding to unlink "
                                 "done tasks.")
                    potential_filters = {}
                    potential_filters["bybaseuuid"] = base_uuid
                    potential_filters[TASK_COMPLETE] = "yes"
                    ret, ret_task_tags_print = unlink_tasks(potential_filters,
                                                            event_id)
                    task_tags_print = (task_tags_print + (ret_task_tags_print
                                                                or []))
                    if ret == FAILURE:
                        LOGGER.error("Error while trying to unlink completed "
                                    "instances for this recurring task")
                        return ret, None
        else:
            ret, ret_task_tags_print = delete_tasks(ws_task)
            if ret == FAILURE:
                LOGGER.error("Error encountered while deleting tasks")
                return ret, None
            task_tags_print = (task_tags_print + (ret_task_tags_print
                                                    or []))
    return SUCCESS, task_tags_print


def unlink_tasks(potential_filters, event_id):
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
        #Overwrite with new event ID for the deletion or modification action
        ws_task.event_id = event_id
        ws_task.task_type = TASK_TYPE_NRML
        LOGGER.debug("Unlinking Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                   ws_tags_list,
                                                   None,
                                                   OPS_UNLINK)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None
    return SUCCESS, task_tags_print


def revert_task(potential_filters, event_id):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to revert", style="default")
        return SUCCESS, None
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        uuidn = task.uuid
        make_transient(task)
        ws_task = task
        ws_task.uuid = uuidn
        if ws_task.id == '-':
            ws_task.id = None
        base_uuid = ws_task.base_uuid
        ws_task.area = WS_AREA_PENDING
        ws_task.status = TASK_STATUS_TODO
        if ws_task.event_id is None:
            ws_task.event_id = event_id
        LOGGER.debug("Reverting Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        if ws_task.task_type == TASK_TYPE_DRVD:
            """
            Need additional check on if base task should also be moved back
            to pending area. This is required when all tasks for the recurring
            task are in done state and we are reverting one or more of the
            done instances. In this case the base task which at this point is
            in the done status(completed area) should also be reverted back
            to a TO_DO status and pending area.
            """
            LOGGER.debug("This is a derived task that is not in pending area")
            LOGGER.debug("Checking if base task {} is done".format(base_uuid))
            potential_filters = {}
            potential_filters["baseuuidonly"] = base_uuid
            potential_filters[TASK_COMPLETE] = "yes"
            uuid_version_results = get_task_uuid_n_ver(potential_filters)
            if uuid_version_results:
                task_list = get_tasks(uuid_version_results)
                base_task = task_list[0]
                if base_task.area == WS_AREA_COMPLETED:
                    LOGGER.debug("Base task {} is also done. So reverting base"
                                 " task first.".format(base_uuid))
                    make_transient(base_task)
                    base_task.uuid = base_uuid
                    base_task.id = '*'
                    base_task.area = WS_AREA_PENDING
                    base_task.status = TASK_STATUS_TODO
                    if base_task.event_id is None:
                        base_task.event_id = event_id
                    ws_tags_list = get_tags(base_task.uuid, base_task.version)
                    ret, base_task, tags_str = add_task_and_tags(base_task,
                                                                 ws_tags_list,
                                                                 None,
                                                                 OPS_REVERT)
                    if ret == FAILURE:
                        LOGGER.error("Error encountered while deleting tasks")
                        return ret, None
                    ret = carryover_recur_dates(base_task)
                    if ret == FAILURE:
                        LOGGER.error("Error encountered while deleting tasks")
                        return ret, None
                    task_tags_print.append((base_task, tags_str))
        """
        Next apply the revert action for the task
        """
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                   ws_tags_list,
                                                   None,
                                                   OPS_REVERT)

        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None
    return SUCCESS, task_tags_print


def reset_task(potential_filters, event_id):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to reset", style="default")
        return SUCCESS, None
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        uuidn = task.uuid
        make_transient(task)
        ws_task = task
        ws_task.uuid = uuidn
        base_uuid = ws_task.base_uuid
        ws_task.area = WS_AREA_PENDING
        ws_task.status = TASK_STATUS_TODO
        if ws_task.event_id is None:
            ws_task.event_id = event_id
        LOGGER.debug("Reset of Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        """
        Next apply the reset action for the task
        """
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                   ws_tags_list,
                                                   None,
                                                   OPS_RESET)

        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None
    return SUCCESS, task_tags_print


def start_task(potential_filters, event_id):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to start", style="default")
        return SUCCESS, None
    task_list = get_tasks(uuid_version_results)
    LOGGER.debug("Total Tasks to Start {}".format(len(task_list)))
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        if task.status == TASK_STATUS_STARTED:
            CONSOLE.print("{}, {} - This task is already in STARTED status..."
                        .format(task.description, task.due))
            continue
        make_transient(task)
        ws_task = task
        ws_task.status = TASK_STATUS_STARTED
        if ws_task.event_id is None:
            ws_task.event_id = event_id
        LOGGER.debug("Starting Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                   ws_tags_list,
                                                   None,
                                                   OPS_START)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None
    return SUCCESS, task_tags_print


def stop_task(potential_filters, event_id):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to stop", style="default")
        return SUCCESS, None
    task_list = get_tasks(uuid_version_results)
    LOGGER.debug("Total Tasks to Stop {}".format(len(task_list)))
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        if task.status == TASK_STATUS_TODO:
            CONSOLE.print("{}, {} - This task is not STARTED yet..."
                        .format(task.description, task.due))
            continue
        make_transient(task)
        ws_task = task
        ws_task.status = TASK_STATUS_TODO
        if ws_task.event_id is None:
            ws_task.event_id = event_id
        LOGGER.debug("Stopping Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                   ws_tags_list,
                                                   None,
                                                   OPS_STOP)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None
    return SUCCESS, task_tags_print


def complete_task(potential_filters, event_id):
    task_tags_print = []
    base_uuids = set()
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to complete", style="default")
        return SUCCESS, None
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        uuidn = task.uuid
        make_transient(task)
        ws_task = task
        ws_task.uuid = uuidn
        """
        A task in started state could be requested for move to completed
        status. In this case the task needs to be stopped first and then
        marked as complete. This allows the task druation to be recorded
        before completing.
        """
        if ws_task.status == TASK_STATUS_STARTED:
            potential_filters = {}
            potential_filters["uuid"] = uuidn
            ret, innr_tsk_tgs_prnt = stop_task(potential_filters, event_id)
            #The stopping of task is not communicated to the user unless there
            #is an issue
            if ret == FAILURE:
                CONSOLE.print("Error while trying to stop task...")
                return ret, None
            innr_task_list = get_tasks(get_task_uuid_n_ver(potential_filters))
            ws_task = innr_task_list[0]
            make_transient(ws_task)
            ws_task.uuid = uuidn
        #Proceed to complete the task
        ws_task.id = "-"
        ws_task.area = WS_AREA_COMPLETED
        ws_task.status = TASK_STATUS_DONE
        #Set the new event ID for the task completion
        ws_task.event_id = event_id
        ws_task.now_flag = None
        LOGGER.debug("Completing Task UUID {} and Task ID {}"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                   ws_tags_list,
                                                   None,
                                                   OPS_DONE)
        task_tags_print.append((ws_task, tags_str))
        if ws_task.task_type == TASK_TYPE_DRVD:
            base_uuids.add(ws_task.base_uuid)
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None

    if base_uuids:
        """
        First, if for any of the recurring tasks all tasks in the pending
        area are completed and the recur end date has not reached then we
        create atleast 1 instance of the next derived task. This will then
        give a task entry for the user to use to modify any properties. Else
        they do not have any way to access this recurring task.
        If the task is well into the future they can apply a hide date to
        prevent it from coming up in the default vuew command.
        This task creation output is silent and not printed.
        """
        for base_uuid in base_uuids:
            LOGGER.debug("Now trying to create derived tasks "
                         "for to UUID {}".format(base_uuid))
            potential_filters = {}
            potential_filters["baseuuidonly"] = base_uuid
            uuid_version_results = get_task_uuid_n_ver(potential_filters)
            tasks_list = get_tasks(uuid_version_results)
            for task in tasks_list:
                LOGGER.debug("Trying to add recurring tasks as a post process "
                             "after applying the 'done' operations. Working on"
                             " UUID {} and version {}"
                             .format(task.uuid, task.version))
                ws_tags_list = get_tags(task.uuid, task.version)
                uuidn = task.uuid
                make_transient(task)
                task.uuid = uuidn
                #Recurring instance to be added with original event ID
                #So do not overwrite with new event ID
                ret, return_list = prep_recurring_tasks(task,
                                                        ws_tags_list,
                                                        True)
                if ret == FAILURE:
                    LOGGER.error("Error encountered in adding task version, "
                             "stopping")
                    return ret, None
            """
            If any of the tasks are derived then we need to check if the base
            task should also be moved to 'completed' area. For this we check as
            below:
            1. Base task has a recur_end date
            2. recur_end date = max of the due date in workspace_recur_dates
                table. That is all derived tasks have been created for this
                base task.
            3. No derived task exists in the 'pending' area for this base task.
                That is all derived tasks have either been completed or have
                been deleted.
            Task creation output is not printed and is silent.
            """
            LOGGER.debug("Checking if there are no more instances in "
                            "pending area.")
            max_ver_sqr = (SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                            .label("maxver"))
                                .filter(Workspace.task_type == TASK_TYPE_DRVD)
                                .group_by(Workspace.uuid)
                                .subquery())
            results = (SESSION.query(Workspace.uuid, Workspace.version)
                            .join(max_ver_sqr,
                                    and_(Workspace.uuid == max_ver_sqr.c.uuid,
                                        Workspace.version
                                            == max_ver_sqr.c.maxver)
                                        )
                            .filter(and_(Workspace.task_type == TASK_TYPE_DRVD,
                                        Workspace.area == WS_AREA_PENDING,
                                        Workspace.base_uuid == base_uuid))
                            .all())
            if not results:
                #Now get the actual base tasks for these UUIDs which need to be
                #completed.
                LOGGER.debug("No more instances in pending, proceeding "
                                 "to mark base task as done")
                potential_filters = {}
                potential_filters["baseuuidonly"] = base_uuid
                uuid_version_results = get_task_uuid_n_ver(potential_filters)
                task_list = get_tasks(uuid_version_results)
                base_task = task_list[0]
                ws_tags_list = get_tags(base_task.uuid, base_task.version)
                uuidn = base_task.uuid
                make_transient(base_task)
                base_task.uuid = uuidn
                base_task.id = "-"
                base_task.area = WS_AREA_COMPLETED
                base_task.status = TASK_STATUS_DONE
                #Since we are completing this base task, use the new event ID
                #used for completing the derived task
                base_task.event_id = event_id
                base_task.now_flag = None
                LOGGER.debug("Completing Base Task UUID {} and Task ID {}"
                                .format(base_task.uuid, base_task.id))
                ret, base_task, tags_str = add_task_and_tags(base_task,
                                                             ws_tags_list,
                                                             None,
                                                             OPS_DONE)
                if ret == FAILURE:
                    LOGGER.error("Error encountered in adding task version, "
                                    "stopping")
                    return ret, None
                ret = carryover_recur_dates(base_task)
                if ret == FAILURE:
                    LOGGER.error("Error encountered while deleting tasks")
                    return ret, None
                task_tags_print.append((base_task, tags_str))
    return SUCCESS, task_tags_print


def toggle_now(potential_filters, event_id):
    task_tags_print = []
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No applicable task to set as NOW", style="default")
        return SUCCESS, None
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                     .format(task.uuid, task.id))
        make_transient(task)
        ws_task = task
        if ws_task.now_flag == True:
            ws_task.now_flag = None
        else:
            ws_task.now_flag = True
        if ws_task.event_id is None:
            ws_task.event_id = event_id
        LOGGER.debug("Setting Task UUID {} and Task ID {} as NOW"
                     .format(ws_task.uuid, ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, ws_task, tags_str = add_task_and_tags(ws_task,
                                                   ws_tags_list,
                                                   None,
                                                   OPS_NOW)
        task_tags_print.append((ws_task, tags_str))
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret, None
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
                ws_task_innr.now_flag = False
                LOGGER.debug("Resetting NOW: Task UUID {} and Task ID {}"
                             .format(ws_task_innr.uuid, ws_task_innr.id))
                ws_tags_innr_list = get_tags(ws_task_innr.uuid,
                                             ws_task_innr.version)
                ret, ws_task, tags_str = add_task_and_tags(ws_task_innr,
                                                           ws_tags_innr_list,
                                                           None,
                                                           OPS_NOW)
                task_tags_print.append((ws_task, tags_str))
                if ret == FAILURE:
                    # Rollback already performed from nested
                    LOGGER.error("Error encountered in reset of NOW")
                    return FAILURE, None
    return SUCCESS, task_tags_print


def prep_modify(potential_filters, ws_task_src, tag):
    ret = SUCCESS
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
            res = Prompt.ask("{}, {} - This is a recurring task, do you want"
                                " to modify 'all' pending instances or "
                                "just 'this' instance"
                                    .format(ws_task.description, ws_task.due),
                                choices=["all", "this", "none"],
                                default="none")
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
                                                   rec_chg))
                    potential_filters = {}
                    potential_filters["id"] = str(ws_task.id)
                    # Delete base and derived tasks and unlink done tasks
                    ret, r_tsk_tg_prnt1 = prep_delete(potential_filters,
                                                      ws_task_src.event_id,
                                                      True)
                    if ret == FAILURE:
                        LOGGER.error("Failure recived while trying to delete "
                                     "old pending occurences of this task. "
                                     "Stopping adding of base and derived "
                                     "tasks.")
                        return FAILURE, None
                    # Next call modify to merge user changes and
                    # recreate the recurring task
                    LOGGER.debug("Sending this task for RECREATION to "
                                 "modify_task - UUID: {}"
                                 .format(ws_task.uuid))
                    ret, r_tsk_tg_prnt3 = modify_task(ws_task_src,
                                                      ws_task,
                                                      tag,
                                                      multi_change,
                                                      rec_chg,
                                                      due_chg,
                                                      hide_chg)
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
                    LOGGER.debug("Sending this BASE task for modification to "
                                 "modify_task - UUID: {}"
                                 .format(ws_task_innr.uuid))
                    ret, r_tsk_tg_prnt4 = modify_task(ws_task_src,
                                                      ws_task_innr,
                                                      tag,
                                                      multi_change,
                                                      rec_chg,
                                                      due_chg,
                                                      hide_chg)
                    if ret == FAILURE:
                        LOGGER.error("Failure recived while trying to modify "
                                     "base task. Stopping adding of derived "
                                     "tasks.")
                        return FAILURE, None
                    """
                    Now that base task's new version is added, carry over the
                    WorkspaceRecurDates from previous version as no change is
                    requested on the due dates.
                    """
                    base_task = (r_tsk_tg_prnt4[0])[0]
                    LOGGER.debug("Creating Recur Dates now for this base task"
                                 " by carrying over the dates from previous "
                                 "version")
                    ret = carryover_recur_dates(base_task)
                    if ret == FAILURE:
                        LOGGER.error("Failure returned while trying to modify "
                                     "task.")
                        return ret, None
                    """
                    Next step is to modify each pending instance of this
                    recurring task
                    """
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
                        LOGGER.debug("Working on DERIVED task {}"
                                     .format(uuidn))
                        LOGGER.debug("Sending the DERIVED task for "
                                     "modification to modify_task - UUID: {}"
                                     .format(ws_task_innr.uuid))
                        ret, r_tsk_tg_prnt5_1 = modify_task(ws_task_src,
                                                            ws_task_innr,
                                                            tag,
                                                            multi_change,
                                                            rec_chg,
                                                            due_chg,
                                                            hide_chg)
                        if ret == FAILURE:
                            LOGGER.error("Failure returned while trying to "
                                         "modify task.")
                            return ret, None
                        r_tsk_tg_prnt5 = (r_tsk_tg_prnt5
                                          + (r_tsk_tg_prnt5_1 or []))
                # Collect all task's for printing
                r_tsk_tg_prnt = ((r_tsk_tg_prnt1 or [])
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
                LOGGER.debug("Sending 'this' DERIVED task for "
                             "modification to modify_task - UUID: {}"
                             .format(ws_task.uuid))
                ret, r_tsk_tg_prnt = modify_task(ws_task_src,
                                                 ws_task,
                                                 tag,
                                                 multi_change,
                                                 rec_chg,
                                                 due_chg,
                                                 hide_chg)
        else:
            """
            This is modification for a non recurring task
            """
            LOGGER.debug("Modification requested a NORMAL task")
            multi_change = False
            LOGGER.debug("Sending the NORMAL task for "
                         "modification to modify_task - UUID: {}"
                         .format(ws_task.uuid))
            ret, r_tsk_tg_prnt = modify_task(ws_task_src,
                                             ws_task,
                                             tag,
                                             multi_change,
                                             rec_chg,
                                             due_chg,
                                             hide_chg)
        if ret == FAILURE:
            LOGGER.error("Failure returned while trying to modify task.")
            return ret, None
        if r_tsk_tg_prnt is not None:
            task_tags_print = task_tags_print + r_tsk_tg_prnt
    return ret, task_tags_print


def modify_task(ws_task_src, ws_task, tag, multi_change, rec_chg, due_chg,
                hide_chg):
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
    Event ID to be used should be populated in ws_task_src object
    """
    task_tags_print = []
    # Start merge related activties
    uuidn = ws_task.uuid
    make_transient(ws_task)
    ws_task.uuid = uuidn
    LOGGER.debug("Modification for Task UUID {} and Task ID {}"
                 .format(ws_task.uuid, ws_task.id))

    if ws_task_src.description is not None:
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

    if ws_task_src.notes == CLR_STR:
        ws_task.notes = None
    elif ws_task_src.notes is not None:
        #For notes default modify action is to append
        ws_task.notes = "".join([(ws_task.notes or ""), " ",
                                 ws_task_src.notes])
        #Remove the prefix whitespace if notes added to task without notes
        ws_task.notes = ws_task.notes.lstrip(" ")

    if ws_task_src.recur_end == CLR_STR:
        ws_task.recur_end = None
    elif ws_task_src.recur_end is not None:
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
                                                   None,
                                                   OPS_MODIFY)
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
                                                    False)
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
                                                       OPS_MODIFY)
            task_tags_print.append((ws_task, tags_str))

    if ret == FAILURE:
        LOGGER.error("Error encountered in adding task version, stopping")
        return ret
    return SUCCESS, task_tags_print


def display_full(potential_filters, pager=False, top=None):
    """
    Displays all attributes held in the backend for the task. This can be
    used as input into other programs if required. Uses a simple structure of
    'AttributeName : Attribute Value'

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters to determine tasks for display
        pager(boolean): Default=False. Determines if a pager should be used
                        to display the task information
        top(integer): Limit the number of tasks which should be displayed

    Returns:
        integer: Status of Success=0 or Failure=1
    """
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
            tags_str = ",".join([tag.tags for tag in tags_list])
        else:
            tags_str = "..."
        # Gather all output into a string
        # This is done to allow to print all at once via a pager
        out_str = out_str + "\n" + reflect_object_n_print(task,
                                                          to_print=False,
                                                          print_all=True)
        with CONSOLE.capture() as capture:
            CONSOLE.print("tags : [magenta]{}[/magenta]"
                          .format(tags_str), style="info")
        out_str = out_str + capture.get() + "\n" + "--"
    if pager:
        with CONSOLE.pager(styles=True):
            CONSOLE.print(out_str)
    else:
        CONSOLE.print(out_str)
    return SUCCESS

def display_7day(potential_filters, pager):
    """
    Display tasks due for today and the next 6 days in kanban style. Tasks 
    without a due date are also shown in a separate swimlane. This works for 
    only pending tasks. 'view' command options like 'pager' and 'top' are not 
    relevant here.
    
    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters to determine tasks for display
        pager(boolean): Default=False. Determines if a pager should be used
                        to display the task information                                 
    Returns:
        integer: Status of Success=0 or Failure=1    
    """
    
    # View is relevant only for tasks in pending area
    if potential_filters.get(TASK_BIN) is not None \
            or potential_filters.get(TASK_COMPLETE) is not None:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    try:
        drvd_due = case((cast(Workspace.due_diff_today, 
                                             Numeric(10, 0))<0, 
                                datetime.now().date().strftime('%Y-%m-%d')),
                             (Workspace.due == None, "No Due Date"), 
                             else_=Workspace.due).label("drvd_due")
        drvd_groups = case((Workspace.groups == None, "No Group"), 
                           else_=Workspace.groups)
        is_recur = case((Workspace.task_type == TASK_TYPE_DRVD, "1"), 
                           else_=0)        
        task_list = (SESSION.query(case((cast(Workspace.due_diff_today, 
                                             Numeric(10, 0))<0, 1), 
                                        else_=0).label("is_overdue"),
                                   drvd_due.label("drvd_due"),
                                   Workspace.id.label("id"),
                                   is_recur.label("is_recur"),
                                   drvd_groups.label("drvd_groups"),
                                   Workspace.description.label("description"),
                                   Workspace.status.label("status"))
                     .filter(and_(tuple_(Workspace.uuid, Workspace.version)
                             .in_(uuid_version_results),
                             or_(Workspace.due == None, 
                                 cast(Workspace.due_diff_today, 
                                             Numeric(10, 0)) <= 7),
                             Workspace.area == WS_AREA_PENDING))
                     .order_by(drvd_due.asc(), drvd_groups.asc())
                     .all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return FAILURE
    if task_list:
        CONSOLE.print("Preparing view...", style="default")
    else:
        CONSOLE.print("No tasks to display")
        return SUCCESS                
    
    date_tasks_dict = {}    
    # Populate the dictionary with dates from today until +6 days
    start_date = datetime.today()
    for i in range(7):
        date = start_date + timedelta(days=i)
        date_tasks_dict[date.strftime('%Y-%m-%d')] = None
    date_tasks_dict["No Due Date"] = None
    prev_due = None
    prev_group = None
    group_tasks_dict = {}
    group_tasks = []
    reset = True
    
    # Populate a heirarchy of Dict->Dict->List to populate the tables
    # {Due Date 1: {
    #   Group 1: 
    #       [task1, task2, ...], 
    #   Group 2: 
    #       [task1, task2, ...],
    #   ...
    #   },
    #  Due Date 2: {
    #   Group 1: 
    #       [task1, task2, ...], 
    #   Group 2: 
    #       [task1, task2, ...]
    #   ...
    #   },
    #   ...
    # }
    for cnt, task in enumerate(task_list, start=1):
        # To kickoff the process we need to initialise the 'prev' variables
        # with values of the first task
        if reset:
            prev_due = task.drvd_due
            prev_group = task.drvd_groups
        if prev_due == task.drvd_due and prev_group == task.drvd_groups:
            group_tasks.append((task.id, 
                                task.description,
                                task.is_recur, 
                                task.status, 
                                task.is_overdue))
            reset = False
        elif prev_group != task.drvd_groups and prev_due == task.drvd_due:
            group_tasks_dict[prev_group] = copy(group_tasks)
            group_tasks.clear()
            group_tasks.append((task.id, 
                                task.description,  
                                task.is_recur, 
                                task.status, 
                                task.is_overdue))
        elif prev_due != task.drvd_due:
            group_tasks_dict[prev_group] = copy(group_tasks)
            group_tasks.clear()
            date_tasks_dict[prev_due] = copy(group_tasks_dict)
            group_tasks_dict.clear()
            group_tasks.append((task.id, 
                                task.description, 
                                task.is_recur, 
                                task.status, 
                                task.is_overdue))
            
        if cnt == len(task_list):
            group_tasks_dict[task.drvd_groups] = copy(group_tasks)
            date_tasks_dict[task.drvd_due] = copy(group_tasks_dict)
            group_tasks.clear()
            group_tasks_dict.clear()
            
        prev_due = task.drvd_due
        prev_group = task.drvd_groups
    
    # The data will be displayed kanban style with each due date representing 
    # a swimlane. Individual rich Tables are used for each swim lane and are
    # brought together using a rich Panel
    tables = []
    for due_date, g_tasks in date_tasks_dict.items():
        table = RichTable(box=box.SIMPLE_HEAD, show_header=True,
                      header_style="header", expand=False,
                      min_width=20)

        table.add_column(datetime.strptime(due_date, "%Y-%m-%d")\
                            .strftime("%Y-%m-%d %a") \
                                if due_date != "No Due Date" \
                                    else due_date, no_wrap=False, width=25)
        if g_tasks is None:
            table.add_row("-")
        else:
            for grp, tasks in g_tasks.items():
                task_cnt = len(tasks)
                table.add_row(grp + "  (" + str(task_cnt) + ")", 
                              style="subheader")
                for task in tasks:
                    # Intepret the is_recur flag which is used for the display
                    recur_flag = str(" " + INDC_RECUR \
                                        if  int(task[-3]) == 1 else "")
                    # Set colours based on tasks status and if they are overdue
                    if task[-1] == 1: 
                        table.add_row(": ".join(str(item) \
                            for item in task[:2]) + recur_flag, 
                                      style="overdue")
                    elif task[-2] == TASK_STARTED:
                        table.add_row(": ".join(str(item) \
                            for item in task[:2]) + recur_flag, 
                                      style="started")
                    else:
                        table.add_row(": ".join(str(item) \
                            for item in task[:2]) + recur_flag, 
                                      style="")
                table.add_row("")
        tables.append(table)
    
    # Use a panel to display the tables 
    # Panel will shown a border for better visualisation
    panel = Panel.fit(
            Columns(tables),
            title="",
            border_style="none",
            title_align="left",
            padding=(1, 2)
        )
    
    # Display a legend row at the bottom
    grid = RichTable.grid(padding=3)
    grid.add_column(style="overdue", justify="center")
    grid.add_column(style="started", justify="center")
    grid.add_column(style="default", justify="center")
    grid.add_row("OVERDUE", "STARTED", INDC_RECUR + " RECURRING")
    if pager:
        with CONSOLE.pager(styles=True):
            CONSOLE.print(panel)
            CONSOLE.print(grid, justify="right")
    else:
        CONSOLE.print(panel)
        CONSOLE.print(grid, justify="right")
    
    # Print the standard task counts
    print_dict = {}
    print_dict[PRNT_CURR_VW_CNT] = len(task_list)
    print_dict[WS_AREA_PENDING] = "yes"
    if potential_filters.get(TASK_COMPLETE) == "yes":
        print_dict[WS_AREA_COMPLETED] = "yes"
    elif potential_filters.get(TASK_BIN) == "yes":
        print_dict[WS_AREA_BIN] = "yes"
    get_and_print_task_count(print_dict)    
    
    return SUCCESS

def display_notes(potential_filters, pager=False, top=None):
    """
    Diplays the notes for the filtered tasks

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters to determine tasks for display
        pager(boolean): Default=False. Determines if a pager should be used
                        to display the task information
        top(integer): Limit the number of tasks which should be displayed

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    curr_day = datetime.now().date()
    tommr = curr_day + relativedelta(days=1)
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    try:
        id_xpr = (case((Workspace.area == WS_AREA_PENDING, Workspace.id),
                        (Workspace.area.in_([WS_AREA_COMPLETED, WS_AREA_BIN]),
                            Workspace.uuid)))
        now_flag_xpr = (case((Workspace.now_flag == True, INDC_NOW),
                             else_=""))
        # Additional information
        addl_info_xpr = (case((Workspace.area == WS_AREA_COMPLETED,
                                'IS DONE'),
                               (Workspace.area == WS_AREA_BIN,
                                'IS DELETED'),
                               (Workspace.due < curr_day, TASK_OVERDUE),
                               (Workspace.due == curr_day, TASK_TODAY),
                               (Workspace.due == tommr, TASK_TOMMR),
                               (Workspace.due != None,
                                Workspace.due_diff_today + " DAYS"),
                              else_=""))
        # Main query
        task_list = (SESSION.query(id_xpr.label("id_or_uuid"),
                                   addl_info_xpr.label("due_in"),
                                   Workspace.description.label("description"),
                                   now_flag_xpr.label("now"),
                                   Workspace.notes.label("notes"),
                                   Workspace.uuid.label("uuid"),
                                   Workspace.area.label("area"),
                                   Workspace.status.label("status"))
                     .filter(tuple_(Workspace.uuid, Workspace.version)
                             .in_(uuid_version_results))
                     .order_by(Workspace.created.desc())
                     .all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return FAILURE
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=False)
    # Column and Header Names
    # Only uuid has fxied column width to ensure uuid does not get cropped
    if (task_list[0]).area == WS_AREA_PENDING:
        table.add_column("id", justify="right")
    else:
        table.add_column("uuid", justify="right", width=36)
    table.add_column("description", justify="left")
    table.add_column("due in", justify="left")
    table.add_column("notes", justify="left")
    if top is None:
        top = len(task_list)
    else:
        top = int(top)
    for cnt, task in enumerate(task_list, start=1):
        if cnt > top:
            break
        trow = [str(task.id_or_uuid), task.description, task.due_in,
                task.notes]
        if task.status == TASK_STATUS_DONE:
            table.add_row(*trow, style="done")
        elif task.status == TASK_STATUS_DELETED:
            table.add_row(*trow, style="binn")
        elif task.now == INDC_NOW:
            table.add_row(*trow, style="now")
        elif task.status == TASK_STATUS_STARTED:
            table.add_row(*trow, style="started")
        elif task.due_in == TASK_OVERDUE:
            table.add_row(*trow, style="overdue")
        elif task.due_in == TASK_TODAY:
            table.add_row(*trow, style="today")
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
    grid.add_row("OVERDUE", "TODAY", "STARTED", "NOW", "DONE", "BIN")
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
    if potential_filters.get(TASK_COMPLETE) == "yes":
        print_dict[WS_AREA_COMPLETED] = "yes"
    elif potential_filters.get(TASK_BIN) == "yes":
        print_dict[WS_AREA_BIN] = "yes"
    get_and_print_task_count(print_dict)
    return SUCCESS


def display_dates(potential_filters, pager=False, top=None):
    """
    Displays a projection of upto 10 due dates for recurring tasks.

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters to determine tasks for display
        pager(boolean): Default=False. Determines if a pager should be used
                        to display the task information
        top(integer): Limit the number of tasks which should be displayed

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    """
    Where the tasks have been created use them to display the due dates. For
    the remaining, upto 10 dates use projected dates based on the base task.
    This is to ensure any modifications done on individual tasks are reflected
    in the output.
    """
    curr_date = datetime.now().date()
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    #Work on only derived tasks
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
    #List to hold base uuids to avoid processing the same recurring tasks again
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
            #Empty row to separate recurring tasks
            table.add_row(None, None)
        #For this derived tasks retreive all the derived task instances
        potential_filters = {}
        potential_filters["bybaseuuid"] = task.base_uuid
        uuid_version_results = get_task_uuid_n_ver(potential_filters)
        task_list = get_tasks(uuid_version_results)
        innrcnt = 0
        """
        For each derived task instance if it is today or beyond add it for
        display
        """
        for task in task_list:
            if (datetime.strptime(task.due, FMT_DATEONLY).date()
                    < datetime.now().date()):
                #Show only tasks from today and beyond
                continue
            due = datetime(int(task.due[0:4]), int(task.due[5:7]),
                           int(task.due[8:])).strftime(FMT_DAY_DATEW)
            table.add_row(task.description, due,style="default")
            innrcnt = innrcnt + 1
            if innrcnt > 10:
                #Only upto 10 dates to display
                break
        if innrcnt > 10:
            #Only upto 10 dates to display
            continue
        """
        Next using the base task create the prpject due dates but limit to
        overall 10 dates for display including above existing instances
        """
        potential_filters = {}
        potential_filters["baseuuidonly"] = task.base_uuid
        uuid_version_results = get_task_uuid_n_ver(potential_filters)
        task_list = get_tasks(uuid_version_results)
        base_task = task_list[0]
        #Get end date for the base task
        if base_task.recur_end is not None:
            end_dt = (datetime.strptime(base_task.recur_end, FMT_DATEONLY)
                    .date())
        else:
            end_dt = FUTDT
        """
        Get the last due date for tasks that have been created. This becomes
        the start date for the projection. Relying on this over the due date
        for the last derived instance as that could have been modified by user
        """
        try:
            res = (SESSION.query(func.max(WorkspaceRecurDates.due))
                         .filter(and_(WorkspaceRecurDates.uuid
                                            == base_task.uuid,
                                      WorkspaceRecurDates.version
                                            == base_task.version))
                         .all())
        except SQLAlchemyError as e:
            LOGGER.error(str(e))
            CONSOLE.print("Error in retrieving information to display dates.")
            return FAILURE
        start_dt = datetime.strptime((res[0])[0],FMT_DATEONLY).date()
        """
        Get the projection, getting 11 projections as the function will
        return the first projected date same as the start date which we have
        already covered in earlier section.
        We then remove that entry from the list and rest are added for display
        """
        due_list =  calc_next_inst_date(base_task.recur_mode,
                                        base_task.recur_when,
                                        start_dt,
                                        end_dt,
                                        11 - innrcnt)
        if due_list is not None:
            due_list = [day  for day in due_list if day >= curr_date and
                                                    day != start_dt]
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


def display_history(potential_filters, pager=False, top=None):
    """
    Display all versions of a task.

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                    filters to determine tasks for display
        pager(boolean): Default=False. Determines if a pager should be used
                        to display the task information
        top(integer): Limit the number of tags which should be displayed

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    uuid_list = map(lambda x: x[0], uuid_version_results)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    CONSOLE.print("Preparing view...", style="default")
    curr_day = datetime.now().date()
    tommr = curr_day + relativedelta(days=1)
    try:
        due_xpr = (case((Workspace.due == None, None),
                        else_=Workspace.due))
        hide_xpr = (case((Workspace.hide == None, None),
                         else_=Workspace.hide))
        groups_xpr = (case((Workspace.groups == None, None),
                           else_=Workspace.groups))
        now_flag_xpr = (case((Workspace.now_flag == True, INDC_NOW),
                             else_=""))
        recur_xpr = (case((Workspace.recur_mode != None, Workspace.recur_mode
                            + " " + func.ifnull(Workspace.recur_when, "")),
                          else_=None))
        end_xpr = (case((Workspace.recur_end == None, None),
                        else_=Workspace.recur_end))
        pri_xpr = (case((Workspace.priority == PRIORITY_HIGH[0],
                          INDC_PR_HIGH),
                         (Workspace.priority == PRIORITY_MEDIUM[0],
                          INDC_PR_MED),
                         (Workspace.priority == PRIORITY_LOW[0],
                          INDC_PR_LOW),
                        else_=INDC_PR_NRML))

        # Sub Query for Tags - START
        tags_subqr = (SESSION.query(WorkspaceTags.uuid, WorkspaceTags.version,
                                    func.group_concat(WorkspaceTags.tags, " ")
                                    .label("tags"))
                      .group_by(WorkspaceTags.uuid,
                                WorkspaceTags.version)
                      .subquery())
        # Sub Query for Tags - END
        # Main query
        task_list = (SESSION.query(Workspace.uuid.label("uuid"),
                                   Workspace.id.label("id"),
                                   Workspace.description.label("description"),
                                   due_xpr.label("due"),
                                   recur_xpr.label("recur"),
                                   end_xpr.label("end"),
                                   groups_xpr.label("groups"),
                                   case((tags_subqr.c.tags == None, None),
                                        else_=tags_subqr.c.tags).label("tags"),
                                   Workspace.status.label("status"),
                                   pri_xpr.label("priority_flg"),
                                   now_flag_xpr.label("now"),
                                   hide_xpr.label("hide"),
                                   Workspace.version.label("version"),
                                   Workspace.inception.label("inception"),
                                   Workspace.created.label("created"),
                                   Workspace.event_id.label("eventid"),
                                   Workspace.area.label("area"))
                     .outerjoin(tags_subqr,
                                and_(Workspace.uuid ==
                                     tags_subqr.c.uuid,
                                     Workspace.version ==
                                     tags_subqr.c.version))
                     .filter(Workspace.uuid
                             .in_(uuid_list))
                     .order_by(Workspace.uuid, Workspace.version.desc())
                     .all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return FAILURE

    LOGGER.debug("Task Details for display:\n{}".format(task_list))
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=True)
    # Column and Header Names
    # Only uuid has fxied column width to ensure uuid does not get cropped
    table.add_column("uuid", justify="right", width=36)
    table.add_column("id", justify="right")
    table.add_column("description", justify="left")
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
    table.add_column("inception_date", justify="left")
    table.add_column("modifed_date", justify="left")
    if top is None:
        top = len(task_list)
    last_uuid = None
    cnt = 0
    for task in task_list:
        if last_uuid != task.uuid:
            """
            As this can have various UUIDs and the top is applied at a UUID
            level, so doing the top check in a different manner to other
            view functions
            """
            last_uuid = task.uuid
            cnt = cnt + 1
            if cnt > top:
                break
            if cnt > 1:
                #Empty row to separate recurring tasks
                trow = [None] * 15
                table.add_row(*trow)
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
        # 0:4 - YYYY, 5:7 - MM, 8:10 - DD, 11:13 - HH, 14:16 - MM
        created = (datetime(int(task.created[0:4]),
                           int(task.created[5:7]),
                           int(task.created[8:10]),
                           int(task.created[11:13]),
                           int(task.created[14:16]))
                    .strftime(FMT_DATEW_TIME))

        inception = (datetime(int(task.inception[0:4]),
                             int(task.inception[5:7]),
                             int(task.inception[8:10]),
                             int(task.inception[11:13]),
                             int(task.inception[14:16]))
                        .strftime(FMT_DATEW_TIME))
        # Create a list to print
        trow = [task.uuid, str(task.id), task.description, due, task.recur,end,
                task.groups, task.tags, task.status, task.priority_flg,
                task.now, hide, str(task.version), inception, created]
        table.add_row(*trow, style="default")

    # Print a legend on the indicators used for priority and now
    grid = RichTable.grid(padding=3)
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_row(INDC_PR_HIGH + " High Priority",
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
    if potential_filters.get(TASK_COMPLETE) == "yes":
        print_dict[WS_AREA_COMPLETED] = "yes"
    elif potential_filters.get(TASK_BIN) == "yes":
        print_dict[WS_AREA_BIN] = "yes"
    get_and_print_task_count(print_dict)
    return SUCCESS


def display_by_tags(potential_filters, pager=False, top=None):
    """
    Displays a the count of tasks against each tag with breakdown by status.

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters to determine tasks for display
        pager(boolean): Default=False. Determines if a pager should be used
                        to display the task information
        top(integer): Limit the number of tags which should be displayed

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    CONSOLE.print("Preparing view...", style="default")
    try:
        """
        bug-7: replaced the query to now include tasks with no tags.
        Order by is on tags without coalesce to ensure the no tag task count
        with NULL is shown on the first row.
        """
        tags_list = (SESSION.query(coalesce(WorkspaceTags.tags,"No Tag").label("tags"),
                                Workspace.area.label("area"),
                                Workspace.status.label("status"),
                                func.count(Workspace.uuid).label("count"))
                            .outerjoin(WorkspaceTags, and_(Workspace.uuid
                                                    == WorkspaceTags.uuid,
                                                Workspace.version
                                                    == WorkspaceTags.version))
                            .filter(tuple_(Workspace.uuid,
                                           Workspace.version)
                                           .in_(uuid_version_results))
                            .group_by(WorkspaceTags.tags, Workspace.area,
                                    Workspace.status)
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
    table.add_column("no. of tasks", justify="right")
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
        if tag.area == WS_AREA_COMPLETED:
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


def display_by_groups(potential_filters, pager=False, top=None):
    """
    Displays a the count tasks by the groups broken down by hierarchy and
    task status.

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters to determine tasks for display
        pager(boolean): Default=False. Determines if a pager should be used
                        to display the task information
        top(integer): Limit the number of groups which should be displayed

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    """
    The groups are not natievly split by hierarchy and stored in the Workspace
    table. This view breaks it down by hierarchy and display the count. This
    is acheived in the python code without relying on SQL.
    """
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    CONSOLE.print("Preparing view...", style="default")
    task_list = get_tasks(uuid_version_results)
    area = task_list[0].area
    task_cnt = {}
    last_parent = None
    for task in task_list:
        if task.groups is not None:
            grp_list = task.groups.split(".")
            grp = ""
            for item in grp_list:
                grp = grp + "." + item
                status_cnt = task_cnt.get(grp.lstrip("."))
                if status_cnt is None:
                    status_cnt = {}
                status_cnt[task.status] = ((status_cnt.get(task.status) or 0)
                                            + 1)
                task_cnt[grp.lstrip(".")] = status_cnt
        else:
            """
            Added for Bug-7. Shows additional rows for tasks which do not
            have a group
            """
            status_cnt = task_cnt.get("No Group")
            if status_cnt is None:
                status_cnt = {}
            status_cnt[task.status] = ((status_cnt.get(task.status) or 0)
                                        + 1)
            task_cnt["No Group"] = status_cnt
    LOGGER.debug("Total grps to print {}".format(len(task_cnt)))
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=False)
    table.add_column("group", justify="left")
    table.add_column("area", justify="left")
    table.add_column("status", justify="left")
    table.add_column("no. of tasks", justify="right")
    if top is None:
        top = len(task_cnt)
    else:
        top = int(top)
    prev_grp = None
    #For each group in the hierarchy create a row for each task status
    for cnt, grp in enumerate(sorted(task_cnt, reverse=True), start=1):
        if cnt > top:
            break
        status_cnt = task_cnt.get(grp)
        #1 row for each task status under that group hierarchy
        for status in sorted(status_cnt):
            trow = []
            if grp == prev_grp:
                trow.append(None)
            else:
                trow.append(grp)
                prev_grp = grp
            trow.append(area)
            trow.append(status)
            trow.append(str(status_cnt.get(status)))
            if area == WS_AREA_COMPLETED:
                table.add_row(*trow, style="done")
            elif area == WS_AREA_BIN:
                table.add_row(*trow, style="binn")
            else:
                table.add_row(*trow, style="default")
        #Add a separator after each hierarchy
        if "." not in grp and cnt != len(task_cnt):
            table.add_row("--", "--","--","--")
    grid = RichTable.grid(padding=3)
    grid.add_column(justify="right")
    grid.add_row("NOTE: Tasks rolled up through GROUP hierarchy")
    if pager:
        with CONSOLE.pager(styles=True):
            CONSOLE.print(table, soft_wrap=True)
            CONSOLE.print(grid, justify="right")
    else:
        CONSOLE.print(table, soft_wrap=True)
        CONSOLE.print(grid, justify="left")
    return SUCCESS

def display_stats():
    """
    Displays stats on the state of pending and completed tasks. Includes how 
    many tasks are in the various state currently and how many are in the bin.
    Additionally also shows the trend for tasks completed and tasks created 
    over the last 7 days.
    
    Parameters:
        None

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    CONSOLE.print("----------------------------------------------")
    CONSOLE.print("1. Preparing stats view for all tasks by task status...", 
                  style="default")
    CONSOLE.print("----------------------------------------------")
   
    try:
        max_ver_sqr = (SESSION.query(Workspace.uuid,
                                func.max(Workspace.version)
                                        .label("maxver"))
                               .group_by(Workspace.uuid).subquery())
        task_status_cnt = (SESSION.query(Workspace.status,
                                    Workspace.area,
                                    func.count(Workspace.uuid).label("count"))
                              .join(max_ver_sqr, and_(max_ver_sqr.c.uuid
                                                        == Workspace.uuid,
                                                        max_ver_sqr.c.maxver
                                                        == Workspace.version))
                              .filter(and_(Workspace.task_type.in_(
                                                            [TASK_TYPE_DRVD,
                                                             TASK_TYPE_NRML]
                                                            )))
                              .group_by(Workspace.status,
                                         Workspace.area)
                              .order_by(Workspace.status.desc()).all())
    except SQLAlchemyError as e:
        CONSOLE.print("Error while trying to get stats for task status")
        LOGGER.error(str(e))
        return FAILURE
    LOGGER.debug("Status records to print {}".format(len(task_status_cnt)))
    LOGGER.debug("Status record values are ")
    LOGGER.debug(task_status_cnt)
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=False)
    table.add_column("status", justify="left")
    table.add_column("no. of tasks", justify="left")
    if len(task_status_cnt) > 0: # Prepare table only if data exists
        # Counts as str since that is what rich table requires
        status_cnt_dict = {'TO_DO': ['0', 'pending'], 
                           'STARTED': ['0', 'pending'], 
                           'DONE': ['0', 'completed'], 
                           'DELETED': ['0', 'bin']}
        for cnt, rec in enumerate(task_status_cnt, start=1):
            status_cnt_dict[rec.status] = [str(rec.count), rec.area]
        for k in status_cnt_dict:
            v = status_cnt_dict.get(k) # [count, area]
            trow = []
            trow.append(k) # status
            trow.append(v[0]) # count
            if v[1] == WS_AREA_COMPLETED: # display style based on area
                table.add_row(*trow, style="done")
            elif v[1] == WS_AREA_BIN:
                table.add_row(*trow, style="binn")
            else:
                table.add_row(*trow, style="default")
        CONSOLE.print(table, soft_wrap=True)
    else:
        CONSOLE.print("No matching tasks in database.")
    CONSOLE.print()
    CONSOLE.print()
    
    CONSOLE.print("----------------------------------------------")
    CONSOLE.print("2. Preparing stats view for pending tasks by due date...", 
                  style="default")
    CONSOLE.print("----------------------------------------------")
    
    try:
        today_cnt_xpr = func.sum(case((cast(Workspace.due_diff_today, 
                                            Numeric(10, 0)) == 0, 1), 
                                      else_=0))
        overdue_cnt_xpr = func.sum(case((cast(Workspace.due_diff_today, 
                                              Numeric(10, 0)) < 0, 1), 
                                        else_=0))
        future_cnt_xpr = func.sum(case((cast(Workspace.due_diff_today, 
                                             Numeric(10, 0)) > 0, 1), 
                                       else_=0))
        nodue_cnt_xpr = func.sum(case((Workspace.due == None, 1), 
                                      else_=0))
        today_todo_cnt_xpr = func.sum(case((
                            and_(cast(Workspace.due_diff_today, 
                                        Numeric(10, 0)) == 0, 
                                    Workspace.hide == None, 
                                    Workspace.status==TASK_STATUS_TODO), 1), 
                                        else_=0))
        overdue_todo_cnt_xpr = func.sum(case((
                            and_(cast(Workspace.due_diff_today, 
                                        Numeric(10, 0)) < 0, 
                                    Workspace.hide == None, 
                                    Workspace.status==TASK_STATUS_TODO), 1), 
                                        else_=0))
        future_todo_cnt_xpr = func.sum(case((
                            and_(cast(Workspace.due_diff_today, 
                                        Numeric(10, 0)) > 0, 
                                    Workspace.hide == None, 
                                    Workspace.status==TASK_STATUS_TODO), 1), 
                                        else_=0))
        nodue_todo_cnt_xpr = func.sum(case((
                            and_(Workspace.due == None, 
                                    Workspace.hide == None, 
                                    Workspace.status==TASK_STATUS_TODO), 1), 
                                        else_=0))
        today_started_cnt_xpr = func.sum(case((
                        and_(cast(Workspace.due_diff_today, 
                                    Numeric(10, 0)) == 0,
                                Workspace.hide == None, 
                                Workspace.status == TASK_STATUS_STARTED), 1), 
                                      else_=0))
        overdue_started_cnt_xpr = func.sum(case((
                        and_(cast(Workspace.due_diff_today, 
                                    Numeric(10, 0)) < 0, 
                                Workspace.hide == None, 
                                Workspace.status == TASK_STATUS_STARTED), 1), 
                                        else_=0))
        future_started_cnt_xpr = func.sum(case((
                        and_(cast(Workspace.due_diff_today, 
                                    Numeric(10, 0)) > 0, 
                                Workspace.hide == None, 
                                Workspace.status == TASK_STATUS_STARTED), 1), 
                                       else_=0))
        nodue_started_cnt_xpr = func.sum(case((
                        and_(Workspace.due == None, 
                                Workspace.hide == None, 
                                Workspace.status == TASK_STATUS_STARTED), 1), 
                                      else_=0))     
        today_hid_todo_cnt_xpr = func.sum(case((
                            and_(cast(Workspace.due_diff_today, 
                                        Numeric(10, 0)) == 0, 
                                    Workspace.hide != None, 
                                    Workspace.status==TASK_STATUS_TODO), 1), 
                                        else_=0))
        overdue_hid_todo_cnt_xpr = func.sum(case((
                            and_(cast(Workspace.due_diff_today, 
                                        Numeric(10, 0)) < 0, 
                                    Workspace.hide != None, 
                                    Workspace.status==TASK_STATUS_TODO), 1), 
                                        else_=0))
        future_hid_todo_cnt_xpr = func.sum(case((
                            and_(cast(Workspace.due_diff_today, 
                                        Numeric(10, 0)) > 0, 
                                    Workspace.hide != None, 
                                    Workspace.status==TASK_STATUS_TODO), 1), 
                                        else_=0))
        nodue_hid_todo_cnt_xpr = func.sum(case((
                            and_(Workspace.due == None, 
                                    Workspace.hide != None, 
                                    Workspace.status==TASK_STATUS_TODO), 1), 
                                        else_=0))        
        today_hid_str_cnt_xpr = func.sum(case((
                        and_(cast(Workspace.due_diff_today, 
                                    Numeric(10, 0)) == 0, 
                                Workspace.hide != None, 
                                Workspace.status==TASK_STATUS_STARTED), 1), 
                                        else_=0))
        overdue_hid_str_cnt_xpr = func.sum(case((
                        and_(cast(Workspace.due_diff_today, 
                                    Numeric(10, 0)) < 0, 
                                Workspace.hide != None, 
                                Workspace.status==TASK_STATUS_STARTED), 1), 
                                        else_=0))
        future_hid_str_cnt_xpr = func.sum(case((
                        and_(cast(Workspace.due_diff_today, 
                                    Numeric(10, 0)) > 0, 
                                Workspace.hide != None, 
                                Workspace.status==TASK_STATUS_STARTED), 1), 
                                        else_=0))
        nodue_hid_str_cnt_xpr = func.sum(case((
                        and_(Workspace.due == None, 
                                Workspace.hide != None, 
                                Workspace.status==TASK_STATUS_STARTED), 1), 
                                        else_=0))      
        total_tasks_xpr = func.count(Workspace.uuid)
        total_todo_xpr = func.sum(case((and_(
                                    Workspace.status == TASK_STATUS_TODO, 
                                    Workspace.hide == None), 1), else_=0))
        total_started_xpr = func.sum(case((and_(
                                    Workspace.status == TASK_STATUS_STARTED, 
                                    Workspace.hide == None), 1), else_=0))
        total_hidden_todo_xpr = func.sum(case((and_(
                                    Workspace.status == TASK_STATUS_TODO, 
                                    Workspace.hide != None), 1), else_=0))              
        total_hidden_str_xpr = func.sum(case((and_(
                                    Workspace.status == TASK_STATUS_TODO, 
                                    Workspace.hide != None), 1), else_=0))
        
        pending_task_cnt = (SESSION.query(
                        today_cnt_xpr.label("today_total_cnt"),
                        overdue_cnt_xpr.label("overdue_total_cnt"),            
                        future_cnt_xpr.label("future_total_cnt"),
                        nodue_cnt_xpr.label("nodue_total_cnt"),
                        today_todo_cnt_xpr.label("today_todo_cnt"),
                        overdue_todo_cnt_xpr.label("overdue_todo_cnt"),
                        future_todo_cnt_xpr.label("future_todo_cnt"),
                        nodue_todo_cnt_xpr.label("nodue_todo_cnt"),
                        today_started_cnt_xpr.label("today_str_cnt"),
                        overdue_started_cnt_xpr.label("overdue_str_cnt"),
                        future_started_cnt_xpr.label("future_str_cnt"),
                        nodue_started_cnt_xpr.label("nodue_str_cnt"),                            
                        today_hid_todo_cnt_xpr.label("today_hid_todo_cnt"),
                        overdue_hid_todo_cnt_xpr.label("overdue_hid_todo_cnt"),
                        future_hid_todo_cnt_xpr.label("future_hid_todo_cnt"),
                        nodue_hid_todo_cnt_xpr.label("nodue_hid_todo_cnt"),
                        today_hid_str_cnt_xpr.label("today_hid_str_cnt"),
                        overdue_hid_str_cnt_xpr.label("overdue_hid_str_cnt"),
                        future_hid_str_cnt_xpr.label("future_hid_str_cnt"),
                        nodue_hid_str_cnt_xpr.label("nodue_hid_str_cnt"),
                        total_tasks_xpr.label("total_tasks_cnt"),
                        total_todo_xpr.label("total_todo_cnt"),
                        total_started_xpr.label("total_started_cnt"),
                        total_hidden_todo_xpr.label("total_hidden_todo_cnt"),
                        total_hidden_str_xpr.label("total_hidden_str_cnt"))                            
                        .join(max_ver_sqr, and_(max_ver_sqr.c.uuid
                                                == Workspace.uuid,
                                                max_ver_sqr.c.maxver
                                                == Workspace.version,
                                                Workspace.task_type.in_(
                                                    [TASK_TYPE_DRVD,
                                                        TASK_TYPE_NRML]
                                                    )))
                        .filter(and_(Workspace.area == WS_AREA_PENDING))
                        .first())
    except SQLAlchemyError as e:
        CONSOLE.print("Error while trying to get stats for task status")
        LOGGER.error(str(e))
        return FAILURE
    if pending_task_cnt.total_tasks_cnt > 0:
        row_dict = {}
        if pending_task_cnt:
            row_dict = pending_task_cnt._mapping
        LOGGER.debug("Retrieved stats is ")
        LOGGER.debug(list(row_dict.values()))

        # Calculate the various additional stats for the breakdown. The 
        # breakdown is based on showing pending tasks in TODO and STARTED 
        # statuses including how many are hidden.
        
        # Print a simple graph of the breakdown data
        todo_counts = [row_dict['today_todo_cnt'], 
                       row_dict['overdue_todo_cnt'], 
                       row_dict['future_todo_cnt'], 
                       row_dict['nodue_todo_cnt']]
        started_counts =[row_dict['today_str_cnt'], 
                         row_dict['overdue_str_cnt'], 
                         row_dict['future_str_cnt'], 
                         row_dict['nodue_str_cnt']] 
        hidden_todo_counts = [row_dict['today_hid_todo_cnt'], 
                            row_dict['overdue_hid_todo_cnt'],
                            row_dict['future_hid_todo_cnt'], 
                            row_dict['nodue_hid_todo_cnt']]
        hidden_started_counts = [row_dict['today_hid_str_cnt'], 
                                row_dict['overdue_hid_str_cnt'], 
                                row_dict['future_hid_str_cnt'], 
                                row_dict['nodue_hid_str_cnt']]
        
        # Colours are from
        # https://github.com/piccolomo/plotext/blob/master/readme/aspect.md#colors
        pltxt.simple_stacked_bar(['today', 'overdue', 'future', 'no due date'], 
                                [todo_counts, started_counts, 
                                 hidden_todo_counts, 
                                 hidden_started_counts], 
                                width = 50,
                                labels=['todo', 'started', 'hidden todo', 
                                        'hidden started'],
                                colors=[32, 47, 104, 226])

        pltxt.show()
        pltxt.clf()
        CONSOLE.print()
        
        # Print a table with same data but the overall tasks counts that are  
        # due today, in the future, overdue and that have no due dates.

        table = RichTable(box=box.HORIZONTALS, show_header=True,
                        header_style="header", expand=False)
        table.add_column("due", justify="left")
        table.add_column("total", justify="left")
        table.add_column("todo", justify="left")
        table.add_column("started", justify="left")
        table.add_column("hidden todo", justify="left")
        table.add_column("hidden started", justify="left")
        trow = ['today', str(row_dict['today_total_cnt']), 
                str(row_dict['today_todo_cnt']), 
                str(row_dict['today_str_cnt']), 
                str(row_dict['today_hid_todo_cnt']),
                str(row_dict['today_hid_str_cnt'])]
        table.add_row(*trow, style="default")
        trow = ['overdue', str(row_dict['overdue_total_cnt']),
                str(row_dict['overdue_todo_cnt']), 
                str(row_dict['overdue_str_cnt']), 
                str(row_dict['overdue_hid_todo_cnt']), 
                str(row_dict['overdue_hid_str_cnt'])]
        table.add_row(*trow, style="default")
        trow = ['future', str(row_dict['future_total_cnt']), 
                str(row_dict['future_todo_cnt']), 
                str(row_dict['future_str_cnt']), 
                str(row_dict['future_hid_todo_cnt']), 
                str(row_dict['future_hid_str_cnt'])]
        table.add_row(*trow, style="default")
        trow = ['no due date', str(row_dict['nodue_total_cnt']),
                str(row_dict['nodue_todo_cnt']), 
                str(row_dict['nodue_str_cnt']), 
                str(row_dict['nodue_hid_todo_cnt']), 
                str(row_dict['nodue_hid_str_cnt'])]
        table.add_row(*trow, style="default")
        table.add_section()
        trow = ['total', str(row_dict['total_tasks_cnt']), 
                str(row_dict['total_todo_cnt']), 
                str(row_dict['total_started_cnt']), 
                str(row_dict['total_hidden_todo_cnt']), 
                str(row_dict['total_hidden_str_cnt'])]
        table.add_row(*trow, style="default")
        CONSOLE.print(table, soft_wrap=True)
    else:
        CONSOLE.print("No matching tasks in database.")
    CONSOLE.print()
    CONSOLE.print()
    
    CONSOLE.print("----------------------------------------------")
    CONSOLE.print("3. Preparing completion trend...", 
                  style="default")
    CONSOLE.print("----------------------------------------------")
    back_lmt_day = int(datetime.now().date().strftime('%Y%m%d')) - 8
    
    try:
        
        compl_trend = (SESSION.query(Workspace.ver_crt_diff_now,
                                    func.count(Workspace.uuid).label('count'))
                            .join(max_ver_sqr, and_(max_ver_sqr.c.uuid
                                                == Workspace.uuid,
                                                max_ver_sqr.c.maxver
                                                == Workspace.version,
                                                Workspace.task_type.in_(
                                                    [TASK_TYPE_DRVD,
                                                        TASK_TYPE_NRML]
                                                    )))
                            .filter(and_(Workspace.area == WS_AREA_COMPLETED,
                                         cast(func.replace(Workspace.created, 
                                                           '-', 
                                                           ''), 
                                              Numeric(10, 0)) > back_lmt_day))
                            .group_by(Workspace.ver_crt_diff_now)
                            .all())
    except SQLAlchemyError as e:
        CONSOLE.print("Error while trying to get completed trend data")
        LOGGER.error(str(e))
        return FAILURE
    if len(compl_trend) > 0:
        trend_results = {i: 0 for i in range(-7, 1, 1)}
        for cnt, rec in enumerate(compl_trend, start=1):
            trend_results[int(rec.ver_crt_diff_now)] = rec.count
        LOGGER.debug("Retrieved stats for view 3 is " + str(trend_results))
        
        # Display a bar grpah showing the trend for task completion over the 
        # last 1 week and today
        pltxt.simple_bar(["Day " + str(k) for k in trend_results.keys()], 
                                trend_results.values(), 
                                width = 50)
        pltxt.show()
        pltxt.clf()
    else:
        CONSOLE.print("No matching tasks in database.")
    CONSOLE.print()      
    CONSOLE.print()
    
    CONSOLE.print("----------------------------------------------")
    CONSOLE.print("4. Preparing new tasks trend...", 
                  style="default")
    CONSOLE.print("----------------------------------------------")
    back_lmt_day = int(datetime.now().date().strftime('%Y%m%d')) - 8
    
    try:
        
        new_trend = (SESSION.query(Workspace.ver_crt_diff_now,
                                    func.count(Workspace.uuid).label('count'))
                            .filter(and_(Workspace.area != WS_AREA_BIN,
                                         cast(func.replace(Workspace.created, 
                                                           '-', 
                                                           ''), 
                                              Numeric(10, 0)) > back_lmt_day, 
                                        Workspace.task_type.in_(
                                                [TASK_TYPE_DRVD,
                                                TASK_TYPE_NRML]),
                                        Workspace.version == 1
                                        ))
                            .group_by(Workspace.ver_crt_diff_now)
                            .all())
    except SQLAlchemyError as e:
        CONSOLE.print("Error while trying to get completed trend data")
        LOGGER.error(str(e))
        return FAILURE
    if len(new_trend) > 0:
        trend_results = {i: 0 for i in range(-7, 1, 1)}
        for cnt, rec in enumerate(new_trend, start=1):
            trend_results[int(rec.ver_crt_diff_now)] = rec.count
        LOGGER.debug("Retrieved stats for view 4 is " + str(trend_results))
        # Display a bar grpah showing the trend for task completion over the 
        # last 1 week and today
        pltxt.simple_bar(["Day " + str(k) for k in trend_results.keys()], 
                                trend_results.values(), 
                                width = 50, color=226)
        pltxt.show()
        pltxt.clf()
    else:
        CONSOLE.print("No matching tasks in database.")
    CONSOLE.print()      
    return SUCCESS

def display_default(potential_filters, pager=False, top=None):
    """
    Displays a tasks with relevant information. Tasks are sorted by their
    score in this view. Hidden tasks are not shown in the default view unless 
    specified as a filter.

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters to determine tasks for display
        pager(boolean): Default=False. Determines if a pager should be used
                        to display the task information
        top(integer): Limit the number of tasks which should be displayed

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    uuid_version_results = get_task_uuid_n_ver(potential_filters)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        get_and_print_task_count({WS_AREA_PENDING: "yes"})
        return SUCCESS
    CONSOLE.print("Preparing view...", style="default")
    curr_day = datetime.now().date()
    tommr = curr_day + relativedelta(days=1)
    try:
        id_xpr = (case((Workspace.area == WS_AREA_PENDING, Workspace.id),
                        (Workspace.area.in_([WS_AREA_COMPLETED, WS_AREA_BIN]),
                            Workspace.uuid)))
        due_xpr = (case((Workspace.due == None, None),
                        else_=Workspace.due))
        hide_xpr = (case((Workspace.hide == None, None),
                         else_=Workspace.hide))
        groups_xpr = (case((Workspace.groups == None, None),
                           else_=Workspace.groups))
        now_flag_xpr = (case((Workspace.now_flag == True, INDC_NOW),
                             else_=""))
        notes_flag_xpr = (case((Workspace.notes != None, INDC_NOTES),
                             else_=""))
        recur_xpr = (case((Workspace.recur_mode != None, Workspace.recur_mode
                            + " " + func.ifnull(Workspace.recur_when, "")),
                          else_=None))
        end_xpr = (case((Workspace.recur_end == None, None),
                        else_=Workspace.recur_end))
        pri_xpr = (case((Workspace.priority == PRIORITY_HIGH[0],
                          INDC_PR_HIGH),
                         (Workspace.priority == PRIORITY_MEDIUM[0],
                          INDC_PR_MED),
                         (Workspace.priority == PRIORITY_LOW[0],
                          INDC_PR_LOW),
                        else_=INDC_PR_NRML))
        dur_xpr = (case ((Workspace.status == TASK_STATUS_STARTED,
                            Workspace.duration + Workspace.dur_ev_diff_now),
                        else_=Workspace.duration))

        # Sub Query for Tags - START
        tags_subqr = (SESSION.query(WorkspaceTags.uuid, WorkspaceTags.version,
                                    func.group_concat(WorkspaceTags.tags, " ")
                                    .label("tags"))
                      .group_by(WorkspaceTags.uuid,
                                WorkspaceTags.version)
                      .subquery())
        # Sub Query for Tags - END
        # Additional information
        addl_info_xpr = (case((Workspace.area == WS_AREA_COMPLETED,
                                'IS DONE'),
                               (Workspace.area == WS_AREA_BIN,
                                'IS DELETED'),
                               (Workspace.due < curr_day, TASK_OVERDUE),
                               (Workspace.due == curr_day, TASK_TODAY),
                               (Workspace.due == tommr, TASK_TOMMR),
                               (Workspace.due != None,
                                Workspace.due_diff_today + " DAYS"),
                              else_=""))
        # Main query
        task_list = (SESSION.query(id_xpr.label("id_or_uuid"),
                                   Workspace.description.label("description"),
                                   addl_info_xpr.label("due_in"),
                                   due_xpr.label("due"),
                                   recur_xpr.label("recur"),
                                   end_xpr.label("end"),
                                   groups_xpr.label("groups"),
                                   case((tags_subqr.c.tags == None, None),
                                        else_=tags_subqr.c.tags).label("tags"),
                                   Workspace.status.label("status"),
                                   pri_xpr.label("priority_flg"),
                                   now_flag_xpr.label("now"),
                                   notes_flag_xpr.label("notes"),
                                   hide_xpr.label("hide"),
                                   Workspace.version.label("version"),
                                   Workspace.area.label("area"),
                                   Workspace.created.label("created"),
                                   dur_xpr.label("duration"),
                                   Workspace.incep_diff_now.label("age"),
                                   Workspace.uuid.label("uuid"))
                     .outerjoin(tags_subqr,
                                and_(Workspace.uuid ==
                                     tags_subqr.c.uuid,
                                     Workspace.version ==
                                     tags_subqr.c.version))
                     .filter(tuple_(Workspace.uuid, Workspace.version)
                             .in_(uuid_version_results))
                     .order_by(Workspace.created.desc())
                     .all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return FAILURE
    #Calculate the task score if we are displaying pending tasks
    if task_list[0].area == WS_AREA_PENDING:
        LOGGER.debug("Attempting to get scores for tasks for Pending area")
        #score_list = None
        score_list = calc_task_scores(get_tasks(uuid_version_results,
                                                expunge=False))
    else:
        LOGGER.debug("Not Pending area, so no scores to be calculated")
        score_list = None
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
    table.add_column("duration", justify="left")
    table.add_column("hide until", justify="left")
    table.add_column("flags", justify="right")
    table.add_column("version", justify="right")
    table.add_column("age", justify="right")
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
    tdata = []
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
        # 0:4 - YYYY, 5:7 - MM, 8:10 - DD, 11:13 - HH, 14:16 - MM
        created = datetime(int(task.created[0:4]), int(task.created[5:7]),
                           int(task.created[8:10]), int(task.created[11:13]),
                           int(task.created[14:16])).strftime(FMT_DATEW_TIME)
        age = convert_time_unit(task.age)
        duration = convert_time_unit(task.duration)
        if score_list is not None:
            score = str(score_list.get(task.uuid))
        else:
            #Not a view on pending tasks, so do not look for a score
            score = ""

        # Create a list to print. Any change in order ensure the if/else
        #in below loop is also modified
        trow = [str(task.id_or_uuid), task.description, task.due_in, due,
                task.recur, end, task.groups, task.tags, task.status,
                duration, hide,
                "".join([task.now,task.notes, task.priority_flg]),
                str(task.version), age, created, score]
                #str(score_dict.get(task.uuid))]
        tdata.append(trow)
    #Now sort the list depending on which area we are displaying
    if task_list[0].area == WS_AREA_PENDING:
        #based on score, descending
        tdata = sorted(tdata, key=itemgetter(15), reverse=True)
    else:
        #hidden or bin task, so based on created date
        tdata = sorted(tdata, key=itemgetter(14), reverse=True)

    for trow in tdata:
        # Next Display the tasks with formatting based on various conditions
        if trow[8] == TASK_STATUS_DONE:
            table.add_row(*trow, style="done")
        elif trow[8] == TASK_STATUS_DELETED:
            table.add_row(*trow, style="binn")
        elif INDC_NOW in trow[11]:
            table.add_row(*trow, style="now")
        elif trow[8] == TASK_STATUS_STARTED:
            table.add_row(*trow, style="started")
        elif trow[2] == TASK_OVERDUE:
            table.add_row(*trow, style="overdue")
        elif trow[2] == TASK_TODAY:
            table.add_row(*trow, style="today")
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
    grid.add_column(justify="center")
    grid.add_row("OVERDUE", "TODAY", "STARTED", "NOW", "DONE", "BIN",
                 INDC_PR_HIGH + " High Priority",
                 INDC_PR_MED + " Medium Priority",
                 INDC_PR_LOW + " Low Priority",
                 INDC_NOW + " Now Task",
                 INDC_NOTES + " Notes Exist")

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
    if potential_filters.get(TASK_COMPLETE) == "yes":
        print_dict[WS_AREA_COMPLETED] = "yes"
    elif potential_filters.get(TASK_BIN) == "yes":
        print_dict[WS_AREA_BIN] = "yes"
    get_and_print_task_count(print_dict)
    return SUCCESS


def prep_recurring_tasks(ws_task_src, ws_tags_list, add_recur_inst):
    uuid_version_list = []
    create_one = False
    tags_str = ""
    curr_date = datetime.now().date()
    """
    The base task is there to hold a verion of the task using which the
    actual recurring tasks can be derived. This task is not visible to the
    users but get modified with any change that applies to the complete set of
    recurring tasks
    """
    ws_task_base = ws_task_src
    results = None
    if ws_task_base.event_id is None:
        ws_task_base.event_id = get_event_id()
    if add_recur_inst:
        # Get last done or pending task whichever is the latest. Create
        # the next occurence from the next due date
        max_ver_sqr = (SESSION.query(Workspace.uuid,
                                     func.max(Workspace.version)
                                     .label("maxver"))
                       .filter(Workspace.task_type == TASK_TYPE_BASE)
                       .group_by(Workspace.uuid).subquery())
        results = (SESSION.query(func.max(WorkspaceRecurDates.due))
                   .join(max_ver_sqr, and_(WorkspaceRecurDates.version ==
                                           max_ver_sqr.c.maxver,
                                           WorkspaceRecurDates.uuid ==
                                           max_ver_sqr.c.uuid))
                   .filter(WorkspaceRecurDates.uuid ==
                           ws_task_base.uuid)
                   .all())

        max_ver_d_sqr = (SESSION.query(Workspace.uuid,
                                     func.max(Workspace.version)
                                        .label("maxver"))
                              .filter(Workspace.task_type == TASK_TYPE_DRVD)
                              .group_by(Workspace.uuid)
                              .subquery())
        #Check if there are any derived tasks in 'pending' area
        #If none then create atleast one.
        task_exists = (SESSION.query(Workspace.uuid)
                                  .join(max_ver_d_sqr,
                                        and_(Workspace.uuid == max_ver_d_sqr
                                                                .c.uuid,
                                             Workspace.version == max_ver_d_sqr
                                                                .c.maxver))
                                  .filter(and_(Workspace.task_type
                                                == TASK_TYPE_DRVD,
                                               Workspace.area
                                                == WS_AREA_PENDING,
                                               Workspace.base_uuid
                                                == ws_task_base.uuid))
                                  .all())
        if not task_exists:
            create_one = True
    else:
        # Create a new base task - from add or
        # version for the base task - from modify
        ws_task_base.uuid = None
        ws_task_base.task_type = TASK_TYPE_BASE
        ws_task_base.status = TASK_STATUS_TODO
        ws_task_base.area = WS_AREA_PENDING
        ws_task_base.id = "*"
        ws_task_base.base_uuid = None
        ws_task_base.now_flag = None
        ret, ws_task_base, tags_str = add_task_and_tags(ws_task_base,
                                                        ws_tags_list,
                                                        None,
                                                        OPS_ADD)
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
        create_one = True
    LOGGER.debug("Next due is {} and create_one is {}"
                 .format(next_due, create_one))
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
    database for the first run during a new day.
    So on 16-Dec if any such command is run it will create the task
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
    hide_due_diff = 0
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
    while ((create_one or (next_due - curr_date).days < until_when)
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
        if add_recur_inst:
            #If we are adding a recurring instance then do not take the
            #inception from base task, instead it should be current time
            ws_task_drvd.inception = None
        ws_rec_dt = WorkspaceRecurDates(uuid=base_uuid, version=base_ver,
                                        due=ws_task_drvd.due)
        ret, ws_task_drvd, r_tags_str = add_task_and_tags(ws_task_drvd,
                                                            ws_tags_list,
                                                            ws_rec_dt,
                                                            OPS_ADD)
        if ret == FAILURE:
            LOGGER.error("Error will adding recurring tasks")
            return FAILURE, None, None
        uuid_version_list.append((ws_task_drvd.uuid, ws_task_drvd.version))
        create_one = False
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


def add_task_and_tags(ws_task_src, ws_tags_list=None, ws_rec_dt=None,
                      src_ops=None):
    """
    Add a task version into the database. This function adds a Workspace
    object and optionally WorkspaceTags and WorkspaceRecurDates objects.

    """
    LOGGER.debug("Incoming values for task:")
    LOGGER.debug("\n" + reflect_object_n_print(ws_task_src, to_print=False,
                                               print_all=True))
    LOGGER.debug("Incoming values for recur_dates:")
    LOGGER.debug("\n" + reflect_object_n_print(ws_rec_dt, to_print=False,
                                               print_all=True))
    ws_task = Workspace()
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
        ws_task.event_id = get_event_id()
    else:
        ws_task.event_id = ws_task_src.event_id
    ws_task.priority = translate_priority(ws_task_src.priority)
    now = datetime.now().strftime(FMT_DATETIME)
    ws_task.created = now
    if not ws_task_src.inception:
        ws_task.inception = now
    else:
        ws_task.inception = ws_task_src.inception
    ws_task.version = get_task_new_version(str(ws_task.uuid))
    ws_task.description = ws_task_src.description
    ws_task.groups = ws_task_src.groups
    ws_task.notes = ws_task_src.notes
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

    ws_task.duration, ws_task.dur_event = calc_duration(src_ops, ws_task_src,
                                                        ws_task)

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
        LOGGER.error(str(e))
        return FAILURE, None, None
    return SUCCESS, ws_task, tags_str


def display_all_tags():
    """
    Displays a list of the tags used in pending and completed tasks.
    Does not show any tags from the deleted tasks

    Parameters:
        None

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    try:
        max_ver_sqr = (SESSION.query(Workspace.uuid,
                                func.max(Workspace.version)
                                .label("maxver"))
                               .filter(and_(Workspace.area.in_(
                                                            [WS_AREA_PENDING,
                                                            WS_AREA_COMPLETED]
                                                            )))
                               .group_by(Workspace.uuid).subquery())
        tags_list = (SESSION.query(distinct(WorkspaceTags.tags).label("tags"))
                            .filter(and_(WorkspaceTags.uuid
                                                    == max_ver_sqr.c.uuid,
                                                WorkspaceTags.version
                                                    == max_ver_sqr.c.maxver))
                            .order_by(WorkspaceTags.tags).all())
    except SQLAlchemyError as e:
        CONSOLE.print("Error while trying to display all tags")
        LOGGER.error(str(e))
        return FAILURE
    if not tags_list:
        LOGGER.debug("No tags found")
        CONSOLE.print("No tags added to tasks.")
        return SUCCESS
    LOGGER.debug("Total tags to print {}".format(len(tags_list)))
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=False)
    table.add_column("tag", justify="left")
    for tag in tags_list:
        trow = []
        LOGGER.debug("Tag: " + tag.tags)
        trow.append(tag.tags)
        table.add_row(*trow, style="default")
    CONSOLE.print("Total number of tags: {}".format(len(tags_list)))
    CONSOLE.print(table, soft_wrap=True)
    return SUCCESS


def display_all_groups():
    """
    Displays a list of the groups used in pending and completed tasks.
    Shows groups broken down by hierarchy
    Does not show any groups from the deleted tasks

    Parameters:
        None

    Returns:
        integer: Status of Success=0 or Failure=1
    """
    try:
        max_ver_sqr = (SESSION.query(Workspace.uuid,
                                func.max(Workspace.version)
                                        .label("maxver"))
                               .group_by(Workspace.uuid).subquery())
        groups_list = (SESSION.query(distinct(Workspace.groups)
                                        .label("groups"))
                              .join(max_ver_sqr, and_(max_ver_sqr.c.uuid
                                                            == Workspace.uuid,
                                                            max_ver_sqr.c.maxver
                                                            == Workspace.version))
                              .filter(and_(Workspace.area.in_(
                                                            [WS_AREA_PENDING,
                                                            WS_AREA_COMPLETED]
                                                            )))
                              .order_by(Workspace.groups).all())
    except SQLAlchemyError as e:
        CONSOLE.print("Error while trying to display all groups")
        LOGGER.error(str(e))
        return FAILURE
    if not groups_list:
        LOGGER.debug("No groups found")
        CONSOLE.print("No groups added to tasks.")
        return SUCCESS
    LOGGER.debug("Total groups to print before breaking "
                 " into hierarchy {}".format(len(groups_list)))
    table = RichTable(box=box.HORIZONTALS, show_header=True,
                      header_style="header", expand=False)
    table.add_column("groups", justify="left")
    all_groups = set()
    for group in groups_list:
        if group is not None and group[0] is not None:
            grp_split = str(group[0]).split(".")
            grp = ""
            for item in grp_split:
                grp = grp + "." + item
                grp = grp.lstrip(".")
                if grp.lstrip(".") not in all_groups:
                    LOGGER.debug("Group: " + grp)
                    trow = []
                    trow.append(grp)
                    table.add_row(*trow, style="default")
                    all_groups.add(grp)
    CONSOLE.print("Total number of groups: {}".format(len(all_groups)))
    LOGGER.debug("Total grps to print {}".format(len(all_groups)))
    CONSOLE.print(table, soft_wrap=True)
    return SUCCESS