import re
import os
import sqlite3
import uuid
import sys
from urllib.request import pathname2url
from pathlib import Path
import logging

import click
from datetime import date
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from rich.console import Console
from rich.table import Column, Table as RichTable, box
from rich.style import Style
from rich.theme import Theme
from rich.prompt import Prompt
from sqlalchemy import create_engine, Column, Integer, String, Table, Index
from sqlalchemy import ForeignKeyConstraint, tuple_, and_, case, func
from sqlalchemy import distinct, cast, Date, inspect, or_
from sqlalchemy.orm import relationship, sessionmaker, make_transient
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.hybrid import hybrid_property

#Global - START
#SQL Connection Related
DEFAULT_FOLDER = os.path.join(str(Path.home()), "myt-cli")
DEFAULT_DB_NAME = "tasksdb.sqlite3"
ENGINE = None
SESSION = None
Session = None
#Return Statuses
SUCCESS = 0
FAILURE = 1
#Task Search Modifiers
TASK_OVERDUE = "OVERDUE"
TASK_TODAY = "TODAY"
TASK_HIDDEN = "HIDDEN"
TASK_BIN = "BIN"
TASK_DONE = "DONE"
TASK_STARTED = "STARTED"
#For Search, when no filters are provided or only area filters provided
TASK_ALL = "ALL"
#For Search, when no task property filters are provided
HL_FILTERS_ONLY = "HL_FILTERS_ONLY"
#To print the number of tasks shown in the filtered view
CURR_VIEW_CNT = "CURR_VIEW_CNT"
"""
Domain Values for the application
"""
#Task Status Domain
TASK_STATUS_TODO = "TO_DO"
TASK_STATUS_STARTED = "STARTED"
TASK_STATUS_DONE = "DONE"
#Task Area Domain
WS_AREA_PENDING = "pending"
WS_AREA_COMPLETED = "completed"
WS_AREA_BIN = "bin"
#Task Priority Domain
PRIORITY_HIGH = ["High", "H", "h"]
PRIORITY_MEDIUM = ["Medium", "M", "m"]
PRIORITY_LOW = ["Low", "L", "l"]
PRIORITY_NORMAL = ["Normal", "N", "n"]
#Logger Config
lFormat = ("**-**|%(levelname)s|%(filename)s|%(lineno)d|%(funcName)s "
           "- %(message)s")
logging.basicConfig(format=lFormat, level=logging.ERROR)
LOGGER = logging.getLogger()
#Rich Formatting Config
#Styles
myt_theme = Theme({
    "default" : "white",
    "today" : "dark_orange",
    "overdue" : "red",
    "started" : "green",
    "done" : "grey46",
    "binn" : "grey46",
    "info" : "yellow",
    "repr.none" : "italic magenta"
}, inherit=False)
CONSOLE = Console(theme=myt_theme)
#Printable attributes
PRINT_ATTR = ["description","priority","due","hide","groups","tags","status"]

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
    #To get due date difference to today
    @hybrid_property
    def due_diff_today(self):
        curr_date = datetime.now().date()
        return datetime.strptime(self.due,"%Y-%m-%d").date() - curr_date
    @due_diff_today.expression
    def due_diff_today(cls):
        curr_date = datetime.now().date().strftime("%Y-%m-%d")
        date_diff = func.julianday(cls.due) - func.julianday(curr_date)
        """
        For some reason cast as Integer forces an addition in the sql
        when trying to concatenate with a string. Forcing as string causes
        the expression to be returned as a literal string rather than the 
        calculation. Hence using substr and instr instead.
        """
        return func.substr(date_diff, 1, func.instr(date_diff,".")-1)

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
                    ["workspace.uuid", "workspace.version"]),{}
    )
Index("idx_ws_tg_uuid_ver", WorkspaceTags.uuid, WorkspaceTags.version)
#Global - END

#Start Commands Config
@click.group()
def myt():
    """
    myt - my tASK MANAGER
    
    An application to manage your tasks through the command line using
    simple options.
    """
    pass

#Add
@myt.command()
@click.argument("filters",nargs=-1)
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
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
              
def add(filters, desc, priority, due, hide, group, tag, verbose):
    """
    Add a task, provide details using the various options available.
    Task gets added with a TO_DO status. If the task has a 'hide' date it
    will not be visible with the 'myt view' command until the 'hide' date.
    Use 'myt view HIDDEN' to view.
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
        ws_task = Workspace(description=desc, priority=priority, 
                            due=due, hide=hide, groups=group)
        ws_tags_list = generate_tags(tag)
        ret, uuid, version = add_task_and_tags(ws_task, ws_tags_list)
        get_and_print_task_count({WS_AREA_PENDING:"yes"},to_print=True)
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
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )           
def modify(filters, desc, priority, due, hide, group, tag, verbose):
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
                 " tag - {}".format(desc, due, hide, group, tag))
    if (desc is None and priority is None and due is None and hide is None 
            and group is None and tag is None):
        CONSOLE.print("No modification values provided. Nothing to do...",
                      style="default")
        return
    if potential_filters.get("uuid"):
        CONSOLE.print("Cannot perform this operation using uuid filters",
                    style="default")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for modifying tasks,"
                              " are you sure?"):
            exit_app(SUCCESS)
    ws_task = Workspace(description=desc, priority=priority, 
                        due=due, hide=hide, groups=group)
    ret = modify_task(potential_filters, ws_task, tag)
    get_and_print_task_count({WS_AREA_PENDING:"yes"},to_print=True)
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
    if potential_filters.get("uuid"):
        CONSOLE.print("Cannot perform this operation using uuid filters",
                       style="default")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for starting tasks,"
                              " are you sure?"):
            exit_app(SUCCESS)
    ret = start_task(potential_filters)
    get_and_print_task_count({WS_AREA_PENDING:"yes"},to_print=True)
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
    if potential_filters.get("uuid"):
        CONSOLE.print("Cannot perform this operation using uuid filters",
                       style="default")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for marking tasks as done,"
                              " are you sure?"):
            exit_app(SUCCESS)
    ret = complete_task(potential_filters)
    get_and_print_task_count({WS_AREA_PENDING:"yes"},to_print=True)
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
    get_and_print_task_count({WS_AREA_PENDING:"yes"},to_print=True)
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
    if potential_filters.get("uuid"):
        CONSOLE.print("Cannot perform this operation using uuid filters",
                       style="default")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get(TASK_ALL) == "yes":
        if not confirm_prompt("No filters given for stopping tasks, "
                              "are you sure?"):
            exit_app(SUCCESS)
    ret = stop_task(potential_filters)
    get_and_print_task_count({WS_AREA_PENDING:"yes"},to_print=True)
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
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable verbose Logging.",
              )
def view(filters, verbose, pager, top):
    if verbose:
        set_versbose_logging()        
    potential_filters = parse_filters(filters)
    if (potential_filters.get("uuid") 
            and not  potential_filters.get(TASK_DONE)
            and not potential_filters.get(TASK_BIN)):
        CONSOLE.print("Cannot perform this operation against pending tasks"
                   " using uuid filters", style="default")
        exit_app(SUCCESS)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)  
    ret = display_tasks(potential_filters, pager, top)
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
    ret = delete_tasks(potential_filters)
    get_and_print_task_count({WS_AREA_PENDING:"yes"},to_print=True)
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
    res = Prompt.ask(prompt_msg, choices=["yes","no"], default="no")
    if res == "no":
        return False
    else:
        return True

def reinitialize_db(verbose):
    full_db_path = os.path.join(DEFAULT_FOLDER,DEFAULT_DB_NAME)
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
    full_db_path = os.path.join(DEFAULT_FOLDER,DEFAULT_DB_NAME)
    ENGINE = create_engine("sqlite:///"+full_db_path, echo=verbose)
    
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
    LOGGER.debug("Now using tasks database at {}".format(full_db_path))
    
    LOGGER.debug("Creating session...")
    try:
        Session = sessionmaker(bind=ENGINE)
        SESSION = Session()
    except SQLAlchemyError as e:
        LOGGER.error("Error in creating session")
        LOGGER.error(str(e))
        return FAILURE
    return SUCCESS

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
        string(str):The string to perform this check on.

    Returns:
        bool:True if input is shortformat else False
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

        string(str):String to check for date

    Returns:
        bool:True if a valid date else False
    """
    try:
        parse(string, False)
        return True

    except ValueError:
        return False

def convert_to_date(refdate, num, timeunit = "days"):
    """
    Return a date post a relative adjustment to a reference date
    
    An adjustment of say +10 days or -2 Months is applied to a 
    reference date. The adjusted date is then returned

    Parameters:
        refdate(date):Date to apply relative adjustment 

        num(str):The adjustment value as +x or -x 

        timeunit(str):The unit for the adjustments, days, months, etc.
        The default is 'days'
                        

    Returns: 
        date:The adjusted date
    """
    conv_dt = refdate + relativedelta(**{timeunit: int(num)})
    return conv_dt

def convert_due(value):
    if value == "clr":
        return "clr"
    if value and is_date_short_format(value):
        if not value[1:]:  # No number specified after sign, append a 0
            value = value[0] + "0"
        return convert_to_date(date.today(), value).strftime("%Y-%m-%d")
    elif value and is_date(value):
        return parse(value).date().strftime("%Y-%m-%d")
    else:
        return None

def convert_hide(value, due):
    if value == "clr":
        return "clr"
    if value and is_date_short_format(value):
        if not value[1:]:  # No number specified after sign, append a 0
            value = value[0] + "0"
        if value[0:1] == "+":
            return convert_to_date(date.today(),value)
        elif due is not None and value[0:1] == "-":
            return convert_to_date(due, value).strftime("%Y-%m-%d")
    elif value and is_date(value):
        return parse(value).date().strftime("%Y-%m-%d")
    else:
        return None

def empty_bin():
    """
    Empty the bin area. All tasks are deleted permanently.
    Undo operation does not work here. No filters are accepted
    by this operation.
    """
    uuid_version_results = get_task_uuid_n_ver({TASK_BIN:"yes"},
                                                     WS_AREA_BIN)
    LOGGER.debug("Got list of UUID and Version for emptying:")
    LOGGER.debug(uuid_version_results)
    if uuid_version_results:
        if not confirm_prompt("Deleting all versions of {} task(s),"
                              " are your sure?"
                              .format(str(len(uuid_version_results)))):
            return SUCCESS
        uuid_list = []
        for uuid in uuid_version_results:
            uuid_list.append(uuid[0])
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

def delete_tasks(potential_filters):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
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
        ws_task = Workspace()
        ws_task = task
        ws_task.id = "-"
        ws_task.area = WS_AREA_BIN
        ws_task.event_id = None
        LOGGER.debug("Deleting Task UUID {} and Task ID {}"
                      .format(ws_task.uuid,ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, uuid, version = add_task_and_tags(ws_task, ws_tags_list)
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
        task = []
        CONSOLE.print("{} task(s) deleted".format(str(len(task_list))),
                       style="info")
    return SUCCESS

def revert_task(potential_filters):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to revert", style="default")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                    .format(task.uuid, task.id))
        make_transient(task)
        ws_task = Workspace()
        ws_task = task
        ws_task.id = None
        ws_task.area = WS_AREA_PENDING
        ws_task.status = TASK_STATUS_TODO
        ws_task.event_id = None
        LOGGER.debug("Reverting Task UUID {} and Task ID {}"\
                      .format(ws_task.uuid,ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, uuid, version = add_task_and_tags(ws_task, ws_tags_list)
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
        task = None
    return SUCCESS

def start_task(potential_filters,):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to start", style="default")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    LOGGER.debug("Total Tasks to Start {}".format(len(task_list)))
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                      .format(task.uuid, task.id))
        make_transient(task)
        ws_task = Workspace()
        ws_task = task
        ws_task.status = TASK_STATUS_STARTED
        ws_task.event_id = None
        LOGGER.debug("Starting Task UUID {} and Task ID {}"\
                      .format(ws_task.uuid,ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, uuid, version = add_task_and_tags(ws_task, ws_tags_list)
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
        task = None
    return SUCCESS
    
def stop_task(potential_filters):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to stop", style="default")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    LOGGER.debug("Total Tasks to Stop {}".format(len(task_list)))
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                      .format(task.uuid, task.id))
        make_transient(task)
        ws_task = Workspace()
        ws_task = task
        ws_task.status = TASK_STATUS_TODO
        ws_task.event_id = None
        LOGGER.debug("Stopping Task UUID {} and Task ID {}"\
                      .format(ws_task.uuid,ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, uuid, version = add_task_and_tags(ws_task, ws_tags_list)
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
        task = None
    return SUCCESS    

def complete_task(potential_filters):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to complete", style="default")
        return
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                      .format(task.uuid, task.id))        
        make_transient(task)
        ws_task = Workspace()
        ws_task = task
        ws_task.id = "-"
        ws_task.area = WS_AREA_COMPLETED
        ws_task.status = TASK_STATUS_DONE
        ws_task.event_id = None
        LOGGER.debug("Completing Task UUID {} and Task ID {}"\
                      .format(ws_task.uuid,ws_task.id))
        ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
        ret, uuid, version = add_task_and_tags(ws_task, ws_tags_list)
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
        task = None
    return SUCCESS
    
def parse_filters(filters):
    potential_filters={}
    if filters:
        for fl in filters:
            if str(fl).upper() == TASK_OVERDUE:
                potential_filters[TASK_OVERDUE] = "yes"
            if str(fl).upper() == TASK_TODAY:
                potential_filters[TASK_TODAY] ="yes"
            if str(fl).upper() == TASK_HIDDEN:
                potential_filters[TASK_HIDDEN] = "yes"
            if str(fl).upper() == TASK_DONE:
                potential_filters[TASK_DONE] = "yes"
            if str(fl).upper() == TASK_BIN:
                potential_filters[TASK_BIN] = "yes"    
            if str(fl).startswith("id:"):
                potential_filters["id"] = (str(fl).split(":"))[1]
            if str(fl).startswith("pr:") or str(fl).startswith("priority:"):
                potential_filters["priority"] = (str(fl).split(":"))[1]                
            if str(fl).startswith("gr:") or str(fl).startswith("group:"):
                potential_filters["group"] = (str(fl).split(":"))[1]
            if str(fl).startswith("tg:") or str(fl).startswith("tag:"):
                potential_filters["tag"] = (str(fl).split(":"))[1]
            if str(fl).startswith("uuid:"):
                potential_filters["uuid"] = (str(fl).split(":"))[1]
    if not potential_filters:
        potential_filters = {TASK_ALL:"yes"}
    #If only High Level Filters provided then set a key to use to warn users
    if ("id" not in potential_filters and "priority" not in potential_filters 
            and "group" not in potential_filters
            and "tag" not in potential_filters
            and "uuid" not in potential_filters):
        potential_filters[HL_FILTERS_ONLY] = "yes"
    return potential_filters

def get_tasks(uuid_version=None):
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
                        .filter(tuple_(Workspace.uuid,Workspace.version).
                        in_(uuid_version)).all())
        SESSION.expunge_all()
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return None
    else:
        return ws_task_list

def get_tags(task_uuid, task_version):
    try:
        ws_tags_list = (SESSION.query(WorkspaceTags)
                    .filter(and_(WorkspaceTags.uuid == task_uuid,
                    WorkspaceTags.version == task_version)).all())
        SESSION.expunge_all()
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return None
    else:
        return ws_tags_list

def modify_task(potential_filters, ws_task_src, tag):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)    
    if not uuid_version_results:
        CONSOLE.print("No applicable tasks to modify", style=-"default")
        return
    event_id = datetime.now().strftime("%Y%m-%d%H-%M%S-") +\
                str(uuid.uuid4())
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        #print(task)
        """
        Populate values for the modify action
        Retreive data from database
        If user requested update or clearing then overwrite
        If user has not requested update for field then retain original value
        """ 
        SESSION.expunge
        make_transient(task)
        ws_task = Workspace()
        ws_task = task        
        LOGGER.debug("Modification for Task UUID {} and Task ID {}"\
                      .format(ws_task.uuid,ws_task.id))
        if ws_task_src.description == "clr":
            ws_task.description = None      
        elif ws_task_src.description is not None:
            ws_task.description = ws_task_src.description

        if ws_task_src.priority == "clr":
            ws_task.priority = PRIORITY_NORMAL
        elif ws_task_src.priority is not None:
            ws_task.priority = ws_task_src.priority

        if ws_task_src.due == "clr":
            ws_task.due = None
        elif ws_task_src.due is not None:
            ws_task.due = ws_task_src.due

        if ws_task_src.hide == "clr":
            ws_task.hide = None
        elif ws_task_src.hide is not None:
            ws_task.hide = ws_task_src.hide

        if ws_task_src.groups == "clr":
            ws_task.groups = None
        elif ws_task_src.groups is not None:
            ws_task.groups = ws_task_src.groups

        tag_u_str = None
        #If operation is not to clear tags then retrieve current tags
        tag_u = []
        ws_tags_list = []        
        if tag != "clr":
            LOGGER.debug("For Task ID {} and UUID {} and version {}"
                         "attempting to retreive tags"
                         .format(ws_task.id, ws_task.uuid, ws_task.version))
            ws_tags_list = get_tags(ws_task.uuid, ws_task.version)
            for temptag in ws_tags_list:
                tag_u.append(temptag.tags)
            LOGGER.debug("Retrieved Tags: {}".format(tag_u))
        #Apply the user requested update
        if tag != "clr" and tag is not None:
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
        #add_task(desc_u, due_u, hide_u, group_u, tag_u_str,
        #         task_uuid, task_id, event_id,status, area)
        ret, tuuid, tversion = add_task_and_tags(ws_task, ws_tags_list)
        if ret == FAILURE:
            LOGGER.error("Error encountered in adding task version, stopping")
            return ret
        task = None
    return SUCCESS

def display_tasks(potential_filters, pager=False, top=None):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
    if not uuid_version_results:
        CONSOLE.print("No tasks to display...", style="default")
        return SUCCESS
    CONSOLE.print("Preparing view...", style="default")   
    curr_day = datetime.now() 
    try:
        id_xpr = (case([(Workspace.area == WS_AREA_PENDING,Workspace.id),
                        (Workspace.area.in_([WS_AREA_COMPLETED,WS_AREA_BIN]),
                            Workspace.uuid),]))             
        due_xpr = (case([(Workspace.due == None,"-"),],else_ = Workspace.due))
        hide_xpr = (case([(Workspace.hide == None,"-")],else_ =Workspace.hide))
        groups_xpr = (case([(Workspace.groups == None,"-")],
                                else_ = Workspace.groups))
        #Sub Query for Tags - START
        tags_subqr = (SESSION.query(WorkspaceTags.uuid,WorkspaceTags.version,
                                func.group_concat(WorkspaceTags.tags)
                                .label("tags"))
                            .group_by(WorkspaceTags.uuid,WorkspaceTags.version)
                            .subquery())
        #Sub Query for Tags - END
        #Additional information
        addl_info_xpr = (case([(Workspace.area == WS_AREA_COMPLETED,'-'),
                               (Workspace.area == WS_AREA_BIN, '-'),
                               (Workspace.due < curr_day.date(), TASK_OVERDUE),
                               (Workspace.due == curr_day.date(),TASK_TODAY),
                               (Workspace.due != None, 
                                    Workspace.due_diff_today + " DAY(S)"),],
                               else_ = "-"))
        #Main query
        task_list = (SESSION.query(id_xpr.label("id_or_uuid"), 
                                Workspace.version.label("version"),
                                Workspace.description.label("description"),
                                Workspace.priority.label("priority"),
                                Workspace.status.label("status"),
                                due_xpr.label("due"),
                                hide_xpr.label("hide"),
                                groups_xpr.label("groups"),
                                case([(tags_subqr.c.tags == None, "-"),],
                                    else_ = tags_subqr.c.tags).label("tags"),
                                addl_info_xpr.label("due_in"),
                                Workspace.area.label("area"),
                                Workspace.created.label("created"))
                            .outerjoin(tags_subqr, 
                                        and_(Workspace.uuid == 
                                                tags_subqr.c.uuid,
                                             Workspace.version == 
                                                tags_subqr.c.version))
                            .filter(tuple_(Workspace.uuid,Workspace.version)
                                    .in_(uuid_version_results))
                            .all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return FAILURE
    
    LOGGER.debug("Task Details for display:\n{}".format(task_list))
    
    table = RichTable(box=box.HORIZONTALS, show_header=True, 
                      header_style="bold")
    #Column and Header Names
    if (task_list[0]).area == WS_AREA_PENDING:
        table.add_column("id",justify="center")
    else:
        table.add_column("uuid",justify="center")
    table.add_column("description",justify="left")
    table.add_column("priority",justify="center")
    table.add_column("due in",justify="center")
    table.add_column("due on",justify="center")
    table.add_column("groups",justify="center")
    table.add_column("tags",justify="center")
    table.add_column("status",justify="center")
    table.add_column("hide until",justify="center")
    table.add_column("version"  ,justify="center")
    if(task_list[0].area == WS_AREA_COMPLETED):
        table.add_column("done_date",justify="center")
    elif(task_list[0].area == WS_AREA_BIN):
        table.add_column("deleted_date",justify="center")
    else:
        table.add_column("modifed_date",justify="center")
    if top is None:
        top = len(task_list)
    else:
        top = int(top)
    for cnt, task in enumerate(task_list, start=1):
        if cnt > top:
            break
        if task.status == TASK_STATUS_DONE:
            table.add_row(
                        str(task.id_or_uuid),
                        str(task.description),str(task.priority),
                        str(task.due_in),str(task.due),str(task.groups),
                        str(task.tags),str(task.status),
                        str(task.hide),str(task.version),str(task.created),
                        style="done")
        elif task.area == WS_AREA_BIN:
            table.add_row(
                        str(task.id_or_uuid),
                        str(task.description),str(task.priority),
                        str(task.due_in),str(task.due),str(task.groups),
                        str(task.tags),str(task.status),
                        str(task.hide),str(task.version),str(task.created),
                        style="binn")           
        elif task.due_in == TASK_OVERDUE:
            table.add_row(
                        str(task.id_or_uuid),
                        str(task.description),str(task.priority),
                        str(task.due_in),str(task.due),str(task.groups),
                        str(task.tags),str(task.status),
                        str(task.hide),str(task.version),str(task.created),
                        style="overdue")
        elif task.due_in == TASK_TODAY:
            table.add_row(
                        str(task.id_or_uuid),
                        str(task.description),str(task.priority),
                        str(task.due_in),str(task.due),str(task.groups),
                        str(task.tags),str(task.status),
                        str(task.hide),str(task.version),str(task.created),
                        style="today")
        elif task.status == TASK_STATUS_STARTED:
            table.add_row(
                        str(task.id_or_uuid),
                        str(task.description),str(task.priority),
                        str(task.due_in),str(task.due),str(task.groups),
                        str(task.tags),str(task.status),
                        str(task.hide),str(task.version),str(task.created),
                        style="started")                     
        else:
            table.add_row(
                        str(task.id_or_uuid),
                        str(task.description),str(task.priority),
                        str(task.due_in),str(task.due),str(task.groups),
                        str(task.tags),str(task.status),
                        str(task.hide),str(task.version),str(task.created),
                        style="default")
    if pager:
        with CONSOLE.pager(styles=True):
            CONSOLE.print(table)
    else:
        CONSOLE.print(table)

    print_dict = {}
    print_dict[CURR_VIEW_CNT] = len(task_list)
    print_dict[WS_AREA_PENDING] = "yes"
    if potential_filters.get(TASK_DONE) == "yes":
        print_dict[WS_AREA_COMPLETED] = "yes"
    elif potential_filters.get(TASK_BIN) == "yes":
        print_dict[WS_AREA_BIN] = "yes"
    get_and_print_task_count(print_dict, to_print=True)
    return SUCCESS

def get_and_print_task_count(print_dict, to_print=True):
    curr_day = datetime.now()
    try:
        #Get count of pending tasks split by HIDDEN and VISIBLE
        #Build case expression separately to simplify readability
        visib_xpr = case([(and_(Workspace.hide>curr_day.date(), 
                                Workspace.hide!=None), 
                         "HIDDEN"),], else_ = "VISIBLE").label("VISIBILITY")
        #Inner query to match max version for a UUID
        max_ver_xpr = (SESSION.query(Workspace.uuid,
                                     func.max(Workspace.version)
                                         .label("maxver"))
                              .group_by(Workspace.uuid).subquery())
        #Final Query
        results_pend = (SESSION.query(visib_xpr,
                                      func.count(distinct(Workspace.uuid))
                                          .label("CNT"))
                                .join(max_ver_xpr, Workspace.uuid == 
                                                    max_ver_xpr.c.uuid)
                                .filter(and_(Workspace.area == WS_AREA_PENDING,
                                             Workspace.version == 
                                                max_ver_xpr.c.maxver))
                                .group_by(visib_xpr)
                                .all())

        #Get count of completed tasks
        #Inner query to match max version for a UUID
        max_ver2_xpr = (SESSION.query(Workspace.uuid,
                                      func.max(Workspace.version)
                                          .label("maxver"))
                               .filter(Workspace.area != WS_AREA_COMPLETED)
                               .group_by(Workspace.uuid).subquery())       
        #Final Query
        results_compl = (SESSION.query(func.count(distinct(Workspace.uuid))
                                           .label("CNT"))
                                .join(max_ver2_xpr, Workspace.uuid == 
                                                    max_ver2_xpr.c.uuid)
                                .filter(and_(Workspace.area == 
                                                WS_AREA_COMPLETED,
                                             Workspace.version > 
                                                max_ver2_xpr.c.maxver))
                                .all())
 
        #Get count of tasks in bin
        #Inner query to match max version for a UUID
        max_ver3_xpr = (SESSION.query(Workspace.uuid,
                                      func.max(Workspace.version)
                                          .label("maxver"))
                               .filter(Workspace.area != WS_AREA_BIN)
                               .group_by(Workspace.uuid).subquery())       
        #Final Query
        results_bin = (SESSION.query(func.count(distinct(Workspace.uuid))
                                         .label("CNT"))
                     .join(max_ver3_xpr, Workspace.uuid == 
                                                    max_ver3_xpr.c.uuid)
                     .filter(and_(Workspace.area == WS_AREA_BIN,
                             Workspace.version > max_ver3_xpr.c.maxver))
                     .all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
    
    LOGGER.debug("Pending: {}".format(results_pend))
    LOGGER.debug("Completed: {}".format(results_compl))
    LOGGER.debug("Bin: {}".format(results_bin))

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
    if results_compl:
        compl = (results_compl[0])[0]
    if results_bin:
        binn = (results_bin[0])[0]
    if to_print:
        if print_dict.get(CURR_VIEW_CNT):
            CONSOLE.print(("Displayed Tasks: [magenta]{}[/magenta]"
                           .format(print_dict.get(CURR_VIEW_CNT))),
                           style="info")
        if print_dict.get(WS_AREA_COMPLETED) == "yes":
            CONSOLE.print("Total Completed tasks: "
                          "[magenta]{}[/magenta]"
                           .format(compl), style="info")
        if print_dict.get(WS_AREA_BIN) == "yes":
            CONSOLE.print("Total tasks in Bin: [magenta]{}[/magenta]"
                           .format(binn),style="info")
        if print_dict.get(WS_AREA_PENDING) == "yes":
           CONSOLE.print("Total Pending Tasks: "
                         "[magenta]{}[/magenta], "
                         "of which Hidden: "
                         "[magenta]{}[/magenta]"
                       .format(total,hid), style="info")
    return ([total,hid,])

def derive_task_id():
    """Get next available task ID from  active area in the workspace"""
    try:
        results = (SESSION.query(Workspace.id)
                          .filter(and_(Workspace.area == WS_AREA_PENDING,
                                       Workspace.id != '-')).all())
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return None

    LOGGER.debug("Returned list of task IDs {}".format(results))
    id_list =[]
    for row in results:
        id_list.append(row[0])
    id_list.insert(0, 0)
    id_list.sort()
    available_list = sorted(set(range(id_list[0], id_list[-1]))-set(id_list))   
    if not available_list:  #If no tasks exist/no available intermediate seq
        return id_list[-1] + 1
    return available_list[0]

def get_task_uuid_n_ver(potential_filters, area=WS_AREA_PENDING):
    """
    Return task UUID and version by applying filters on tasks

    Using a list of filters identify the relevant task UUIDs and their
    latest versions. The filters come in the form of a dictionary and
    expected keys include:
        - For all pending - Default when non filter provided
        - Overdue Tasks - Works only on pending
        - Tasks due today - Works only on pending
        - Hidden Tasks - Works only on pending
        - Completed Tasks - Works only on completed
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
        3. UUIDs for Completed or Bin tasks only
        4. Groups, Tags
            a. Overdue, Today, Hidden
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
              is an exception

    """
    LOGGER.debug("Incoming Filters: ")
    LOGGER.debug(potential_filters)
    subquery_list = []
    subqr = None
    all_tasks = potential_filters.get(TASK_ALL)
    overdue_task = potential_filters.get(TASK_OVERDUE)
    today_task = potential_filters.get(TASK_TODAY)
    hidden_task = potential_filters.get(TASK_HIDDEN)
    done_task = potential_filters.get(TASK_DONE)
    bin_task = potential_filters.get(TASK_BIN)
    idn = potential_filters.get("id")
    uuidn = potential_filters.get("uuid")
    group = potential_filters.get("group")
    tag = potential_filters.get("tag")
    curr_date = datetime.now().date()
    #Inner query to match max version for a UUID
    max_ver_xpr = (SESSION.query(Workspace.uuid,
                                    func.max(Workspace.version)
                                        .label("maxver"))
                          .group_by(Workspace.uuid).subquery())
    if all_tasks:
        """
        When no filter is provided retrieve all tasks from pending area
        """
        LOGGER.debug("Inside all_tasks filter with below params")
        LOGGER.debug(area)
        try:
            results  = (SESSION.query(Workspace.uuid, Workspace.version)
                               .join(max_ver_xpr, and_(Workspace.version == 
                                                    max_ver_xpr.c.maxver,
                                                  Workspace.uuid == 
                                                    max_ver_xpr.c.uuid))
                               .filter(and_(Workspace.area == area, 
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
            results  = (SESSION.query(Workspace.uuid, Workspace.version)
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
            subqr_uuid = (SESSION.query(Workspace.uuid, Workspace.version)
                            .join(max_ver_xpr, and_(Workspace.version == 
                                                    max_ver_xpr.c.maxver,
                                                  Workspace.uuid == 
                                                    max_ver_xpr.c.uuid))
                            .filter(and_(Workspace.area.in_([WS_AREA_COMPLETED, 
                                                            WS_AREA_BIN]), 
                                         Workspace.uuid.
                                                in_(uuid_list))))
            subquery_list.append(subqr_uuid)
        else:
            if group is not None:
                """
                Query to get a list of uuid and version for matchiing groups
                from all 3 areas
                """
                LOGGER.debug("Inside group filter with below params")
                LOGGER.debug(group+"%")
                subqr_groups = (SESSION.query(Workspace.uuid, 
                                              Workspace.version)
                                       .join(max_ver_xpr, 
                                             and_(Workspace.version == 
                                                    max_ver_xpr.c.maxver,
                                                  Workspace.uuid == 
                                                    max_ver_xpr.c.uuid))
                                    .filter(Workspace.groups.like(group+"%")))
                subquery_list.append(subqr_groups)
            if tag is not None:
                """
                Query to get a list of uuid and version for matchiing tags
                from all 3 areas
                """            
                #print("for tag")
                tag_list = tag.split(",")
                LOGGER.debug("Inside tag filter with below params")
                LOGGER.debug(tag_list)
                subqr_tags = (SESSION.query(WorkspaceTags.uuid, 
                                           WorkspaceTags.version)
                                    .join(max_ver_xpr, 
                                          and_(WorkspaceTags.version == 
                                                    max_ver_xpr.c.maxver,
                                               WorkspaceTags.uuid == 
                                                    max_ver_xpr.c.uuid))
                                    .filter(WorkspaceTags.tags.
                                                    in_(tag_list)))
                subquery_list.append(subqr_tags)
        """
        Look for modifiers that work in the pending area
        """
        LOGGER.debug("Status for OVERDUE {}, TODAY {}, HIDDEN {}"
                     .format(overdue_task, today_task, hidden_task))
        if (overdue_task is not None or today_task is not None or
                hidden_task is not None):
            if overdue_task is not None:
                LOGGER.debug("Inside overdue filter")
                subqr_overdue = (SESSION.query(Workspace.uuid, 
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
                subquery_list.append(subqr_overdue)
            if today_task is not None:
                LOGGER.debug("Inside today filter")
                subqr_today = (SESSION.query(Workspace.uuid, 
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
                subquery_list.append(subqr_today)
            if hidden_task is not None:
                LOGGER.debug("Inside hidden filter")
                subqr_hidden = (SESSION.query(Workspace.uuid, 
                                                Workspace.version)
                                        .join(max_ver_xpr, 
                                              and_(Workspace.version == 
                                                    max_ver_xpr.c.maxver,
                                                   Workspace.uuid == 
                                                    max_ver_xpr.c.uuid))
                                        .filter(and_(Workspace.area == 
                                                        WS_AREA_PENDING, 
                                                     Workspace.due == 
                                                        curr_date, 
                                                     and_(Workspace.hide > 
                                                            curr_date,
                                                         Workspace.hide != 
                                                            None))))
                subquery_list.append(subqr_hidden)
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
            subqr_done = (SESSION.query(Workspace.uuid, Workspace.version)
                                    .join(max_ver_xpr2, 
                                          and_(Workspace.uuid == 
                                                    max_ver_xpr2.c.uuid,
                                               Workspace.version >
                                                    max_ver_xpr2.c.maxver))
                                    .filter(Workspace.area == 
                                                WS_AREA_COMPLETED))
            subquery_list.append(subqr_done)
        elif bin_task is not None:
            # Get all tasks in the bin
            LOGGER.debug("Inside bin filter")
            max_ver_xpr3 = (SESSION.query(Workspace.uuid,
                                            func.max(Workspace.version)
                                            .label("maxver"))
                                    .filter(Workspace.area != WS_AREA_BIN)
                                    .group_by(Workspace.uuid).subquery())
            subqr_bin = (SESSION.query(Workspace.uuid, Workspace.version)
                                    .join(max_ver_xpr3, 
                                          and_(Workspace.uuid == 
                                                    max_ver_xpr3.c.uuid,
                                               Workspace.version >
                                                    max_ver_xpr3.c.maxver))
                                .filter(Workspace.area == 
                                                WS_AREA_BIN))
            subquery_list.append(subqr_bin)
        # If no modifiers provided then default to tasks in pending area
        else:
            LOGGER.debug("Inside default filter")
            max_ver_xpr4 = (SESSION.query(Workspace.uuid,
                                            func.max(Workspace.version)
                                            .label("maxver"),Workspace.area)
                                    .filter(and_(Workspace.id != '-',
                                                 Workspace.area == 
                                                    WS_AREA_PENDING))
                                    .group_by(Workspace.uuid).subquery())
            subqr_all = (SESSION.query(Workspace.uuid, Workspace.version)
                                .join(max_ver_xpr4, 
                                      and_(Workspace.version == 
                                                max_ver_xpr4.c.maxver,
                                           Workspace.uuid == 
                                                max_ver_xpr4.c.uuid))
                                .filter(and_(Workspace.area == 
                                                WS_AREA_PENDING,
                                             Workspace.id != '-')))
            subquery_list.append(subqr_all)
        if subquery_list is None:
            return None
    try:
        #Tuple of rows, UUID,Version 
        results = subquery_list[0].intersect(*subquery_list).all()
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
    if (results[0])[0] is not None:  #Tasks exists so increment version
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

def reflect_object_n_print(src_object,to_print=False):
    inst = inspect(src_object)
    attr_names = [c_attr.key for c_attr in inst.mapper.column_attrs]
    if to_print:
        for attr in attr_names:
            if attr in PRINT_ATTR:
                with CONSOLE.capture() as capture:
                    CONSOLE.print("{} : [magenta]{}[/magenta]"
                                .format(attr,getattr(src_object,attr)),
                                style="info")
                click.echo(capture.get(), nl=False)
        return
    else:
        ret_str=""
        for attr in attr_names:
            ret_str = ret_str + ("{0} : {1}\n"
                                 .format(attr,getattr(src_object,attr)))
        return ret_str

def add_task_and_tags(ws_task_src, ws_tags_list=None):
    LOGGER.debug("Incoming values for task:\n{}"
                  .format(reflect_object_n_print(ws_task_src,to_print=False)))
    ws_task = Workspace()
    if ws_task_src.id is None:
        ws_task.id = derive_task_id()
    else:
        ws_task.id = ws_task_src.id
    if ws_task_src.due is not None:
        ws_task.due = convert_due(ws_task_src.due)
    else:
        ws_task.due = None
    if ws_task_src.hide is not None:
        if ws_task.due is not None: 
        #Hide date relative to due date only if due date is available
            ws_task.hide = convert_hide(ws_task_src.hide,parse(ws_task.due))
        else:
            ws_task.hide = convert_hide(ws_task_src.hide,None)
    else:
        ws_task.hide = None
    if ws_task_src.uuid is None:
        ws_task.uuid = str(uuid.uuid4())
    else:
        ws_task.uuid = ws_task_src.uuid
    if ws_task_src.event_id is None:
        ws_task.event_id = datetime.now().strftime("%Y%m-%d%H-%M%S-") +\
            str(uuid.uuid4())
    else:
        ws_task.event_id = ws_task_src.event_id
    ws_task.priority = translate_priority(ws_task_src.priority)
    now = datetime.now().strftime("%Y-%m-%d")
    ws_task.created = now
    ws_task.version = get_task_new_version(str(ws_task.uuid))
    ws_task.description = ws_task_src.description
    ws_task.groups = ws_task_src.groups
    if not ws_task_src.area:
        ws_task.area = WS_AREA_PENDING
    else:
        ws_task.area = ws_task_src.area
    if not ws_task_src.status:
        ws_task.status = TASK_STATUS_TODO
    else:
        ws_task.status = ws_task_src.status
    try:
        LOGGER.debug("Adding values for task:\n{}"
                      .format(reflect_object_n_print(ws_task,to_print=False)))        
        # Insert the latest task version
        SESSION.add(ws_task)
        tags_str = "" #Only for display
        # Insert the latest tags
        if ws_tags_list is not None:
            for t in ws_tags_list:
                ws_tags = WorkspaceTags()
                ws_tags.uuid = ws_task.uuid
                ws_tags.version = ws_task.version
                ws_tags.tags = t.tags
                LOGGER.debug("Adding values for tags:")
                LOGGER.debug(reflect_object_n_print(ws_tags,to_print=False))
                SESSION.add(ws_tags)
                tags_str =tags_str + "," +t.tags
        # For all older entries remove the task_id
        (SESSION.query(Workspace).filter(Workspace.uuid == ws_task.uuid, 
                                         Workspace.version < ws_task.version).
                                         update({Workspace.id:"-"},
                                         synchronize_session = False))
    except SQLAlchemyError as e:
        print(str(e))
        return FAILURE, None, None

    SESSION.commit()
    if ws_task.id == '-':
        """
        Using a context manager to capture output from print and pass
        it onto click's echo for the pytests to receive the input.
        This is done only where the output is required for pytest.
        CONSOLE.print gives a simpler management of coloured printing
        compared to click's echo.
        Suppress the newline for echo to ensure double line breaks
        are not printed, 1 from print and another from echo.
        """         
        with CONSOLE.capture() as capture:
            CONSOLE.print("Updated Task UUID: [magenta]{}[/magenta]"
                            .format(ws_task.uuid),
                            style="info")
        click.echo(capture.get(), nl=False)
    else:
        with CONSOLE.capture() as capture:
            CONSOLE.print("Added/Updated Task ID: [magenta]{}[/magenta]"
                            .format(ws_task.id),
                            style="info")
        click.echo(capture.get(), nl=False)
    if not tags_str:
        tags_str = "-None"
    reflect_object_n_print(ws_task, to_print=True)
    with CONSOLE.capture() as capture:
        CONSOLE.print("tags : [magenta]{}[/magenta]"
                       .format(tags_str[1:]),style="info")
    click.echo(capture.get(), nl=False)
    LOGGER.debug("Added/Updated Task UUID: {} and Area: {}"
                 .format(ws_task.uuid,ws_task.area))
    return SUCCESS, ws_task.uuid, ws_task.version

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