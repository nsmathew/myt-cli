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
from sqlalchemy import create_engine, Column, Integer, String, Table
from sqlalchemy import ForeignKeyConstraint, tuple_, and_, case, func
from sqlalchemy import distinct
from sqlalchemy.orm import relationship, sessionmaker, make_transient
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError

#Global
DEFAULT_FOLDER = os.path.join(str(Path.home()), "myt-cli")
DEFAULT_DB_NAME = "tasksdb.sqlite3"
CONN = None
ENGINE = None
SESSION = None
SUCCESS = 0
FAILURE = 1
TASK_TODO = "TO_DO"
TASK_STARTED = "STARTED"
TASK_DONE = "DONE"
TASK_OVERDUE = "OVERDUE"
TASK_TODAY = "TODAY"
TASK_HIDDEN = "HIDDEN"
TASK_BIN = "BIN"
WS_AREA_PENDING = "pending"
WS_AREA_COMPLETED = "completed"
WS_AREA_BIN = "bin"
HL_FILTERS_ONLY = "HL_FILTERS_ONLY"
lFormat = ("**-**|%(levelname)s|%(filename)s|%(lineno)d|%(funcName)s "
           "- %(message)s")
logging.basicConfig(format=lFormat, level=logging.ERROR)
LOGGER = logging.getLogger()

Base = declarative_base()
class Workspace(Base):
    __tablename__ = "workspace"
    uuid = Column(String, primary_key=True)
    version = Column(Integer, primary_key=True)
    id = Column(Integer)
    description = Column(String)
    status = Column(String)
    due = Column(String)
    hide = Column(String)
    done = Column(String)
    area = Column(String)
    created = Column(String)
    modified = Column(String)
    groups = Column(String)
    event_id = Column(String)

class WorkspaceTags(Base):
    __tablename__ = "workspace_tags"
    uuid = Column(String, primary_key=True)
    tags = Column(String, primary_key=True)
    version = Column(Integer, primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(["uuid", "version"],
                    ["workspace.uuid", "workspace.version"]),{}
    )

class TempUUIDVersion(Base):
    __tablename__ = "temp_uuid_version"
    rowid = Column(Integer, primary_key=True)
    temp_uuid = Column(String)
    temp_version = Column(Integer)

@click.group()
def myt():
    pass

@myt.command()
@click.argument("filters",nargs=-1)
@click.option("--desc", 
              "-de",
              type=str,
              help="Short description of task",
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
              help="Hierachical grouping for tasks using '.'.",
              )
@click.option("--tag",
              "-tg",
              type=str,
              help="Tags for the task.",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )
              
def add(filters, desc, due, hide, group, tag, verbose):
    if verbose:
        LOGGER.setLevel(level=logging.DEBUG)    
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if desc is None:
        click.echo("No task information provided. Nothing to do...")
        return SUCCESS
    else:
        ws_task = Workspace(description=desc, due=due, hide=hide, 
                            groups=group)
        ws_tags_list = generate_tags(tag)
        ret, uuid, version = add_task_and_tags(ws_task, ws_tags_list)
        get_and_print_task_count(to_print=True)
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
              help="Hierachical grouping for tasks using '.'.",
              )
@click.option("--tag",
              "-tg",
              type=str,
              help="Tags for the task.",
              )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )           
def modify(filters, desc, due, hide, group, tag, verbose):
    if verbose:
        set_versbose_logging()        
    potential_filters = parse_filters(filters)
    LOGGER.debug("Values for update: desc - {} due - {} hide - {} group - {}"
                 " tag - {}".format(desc, due, hide, group, tag))
    if (desc is None and due is None and hide is None and group is None 
            and tag is None):
        click.echo("No modification values provided. Nothing to do...")
        return
    if potential_filters.get("uuid"):
        click.echo("Cannot perform this operation using uuid filters")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get("all") == "yes":
        prompt = ("No filters given for modifying tasks,"
                  " are you sure? (yes/no)")
        if not yes_no(prompt):
            exit_app(0)
    ws_task = Workspace(description=desc, due=due, hide=hide, groups=group)
    ret = modify_task(potential_filters, ws_task, tag)
    get_and_print_task_count(to_print=True)
    exit_app(ret)

@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )                
def start(filters, verbose):
    if verbose:
        set_versbose_logging()        
    potential_filters = parse_filters(filters)
    if potential_filters.get("uuid"):
        click.echo("Cannot perform this operation using uuid filters")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get("all") == "yes":
        prompt = ("No filters given for starting tasks,"
                  " are you sure? (yes/no)")
        if not yes_no(prompt):
            exit_app(0)
    ret = start_task(potential_filters)
    get_and_print_task_count(to_print=True)
    exit_app(ret)

@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )
def done(filters, verbose):
    if verbose:
        set_versbose_logging()        
    potential_filters = parse_filters(filters)
    if potential_filters.get("uuid"):
        click.echo("Cannot perform this operation using uuid filters")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get("all") == "yes":
        prompt = ("No filters given for marking tasks as done,"
                  " are you sure? (yes/no)")
        if not yes_no(prompt):
            exit_app(0)
    ret = complete_task(potential_filters)
    get_and_print_task_count(to_print=True)
    exit_app(ret)

@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )
def revert(filters, verbose):
    if verbose:
        set_versbose_logging()        
    potential_filters = parse_filters(filters)
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get("all") == "yes":
        prompt = ("No filters given for reverting tasks,"
                  " are you sure? (yes/no)")
        if not yes_no(prompt):
            exit_app(0)
    if potential_filters.get(HL_FILTERS_ONLY) == "yes":
        prompt = ("No detailed filters given for deleting tasks,"
                " are you sure? (yes/no)")
        if not yes_no(prompt):
            exit_app(0)
    ret = revert_task(potential_filters)
    get_and_print_task_count(to_print=True)
    exit_app(ret)

@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )
def stop(filters, verbose):
    if verbose:
        set_versbose_logging()        
    potential_filters = parse_filters(filters)
    if potential_filters.get("uuid"):
        click.echo("Cannot perform this operation using uuid filters")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    if potential_filters.get("all") == "yes":
        prompt = ("No filters given for stopping tasks,"
                  " are you sure? (yes/no)")
        if not yes_no(prompt):
            exit_app(0)
    ret = stop_task(potential_filters)
    get_and_print_task_count(to_print=True)
    exit_app(ret)

@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )
def view(filters, verbose):
    if verbose:
        set_versbose_logging()        
    potential_filters = parse_filters(filters)
    if potential_filters.get("uuid"):
        click.echo("Cannot perform this operation using uuid filters")
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    ret = display_tasks(potential_filters)
    exit_app(ret)

@myt.command()
@click.argument("filters",
                nargs=-1,
                )
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )
def delete(filters, verbose):
    if verbose:
        set_versbose_logging()
    potential_filters = parse_filters(filters)
    if potential_filters.get(HL_FILTERS_ONLY) == "yes":
        prompt = ("No detailed filters given for deleting tasks,"
                   " are you sure? (yes/no)")
        if not yes_no(prompt):
            exit_app(0)    
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    ret = delete_tasks(potential_filters)
    get_and_print_task_count(True)
    exit_app(ret)

@myt.command()
@click.option("--verbose",
              "-v",
              is_flag=True,
              help="Enable Verbose Logging.",
              )
def empty(verbose):
    """
    Empty the bin area. All tasks are deleted permanently.
    Undo operation does not work here. No filters are accepted
    by this operation.
    """
    if verbose:
        set_versbose_logging()        
    if connect_to_tasksdb(verbose=verbose) == FAILURE:
        exit_app(FAILURE)
    ret = empty_bin()
    exit_app(ret)

def connect_to_tasksdb(verbose=False):
    global SESSION, ENGINE
    full_db_path = os.path.join(DEFAULT_FOLDER,DEFAULT_DB_NAME)
    ENGINE = create_engine("sqlite:///"+full_db_path, echo=verbose)
    LOGGER.debug("Trying to use tasks database at {}".format(full_db_path))
    
    if not os.path.exists(full_db_path):
        click.echo("No tasks database exists, intializing at {}"
                    .format(full_db_path))
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
        click.echo("Tasks database initialized...")
    
    LOGGER.debug("Creating session...")
    try:
        Session = sessionmaker(bind=ENGINE)
        SESSION = Session()
    except SQLAlchemyError as e:
        LOGGER.error("Error in creating session")
        LOGGER.error(str(e))
        return FAILURE
    global CONN
    try:
        LOGGER.debug("Using database at {}".format(full_db_path))
        dburi = "file:{}?mode=rw".format(pathname2url(full_db_path))
        CONN = sqlite3.connect(dburi, uri=True)
    except sqlite3.OperationalError:
        click.echo("No database exists, intializing...")
        CONN = initialize_tasksdb(full_db_path)
    #CONN.set_trace_callback(print)
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

def yes_no(prompt):
    yes = set(["yes","y", "ye"])  
    choice = input(prompt).lower()
    if choice in yes:
        return True
    else:
        return False

def empty_bin():
    uuid_version_results = get_task_uuid_n_ver({TASK_BIN:"yes"},
                                                     WS_AREA_BIN)
    LOGGER.debug("Got list of UUID and Version for emptying:")
    LOGGER.debug(uuid_version_results)
    if uuid_version_results:
        prompt = ("Deleting all versions of {} task(s),"
                  " are your sure (yes/no)"
                  .format(str(len(uuid_version_results))))
        if not yes_no(prompt):
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
            LOGGER.debug(str(e))
            return FAILURE
        SESSION.commit()
        click.echo("Bin emptied!")
        return SUCCESS
    else:
        click.echo("Bin is already empty, nothing to do")
        return SUCCESS

def delete_tasks(potential_filters):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
    if not uuid_version_results:
        click.echo("No applicable tasks to delete")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                      .format(task.uuid, task.id))        
        make_transient(task)
        task._oid = None
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
    return SUCCESS

def revert_task(potential_filters):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
    if not uuid_version_results:
        click.echo("No applicable tasks to revert")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                    .format(task.uuid, task.id))
        make_transient(task)
        task._oid = None
        ws_task = Workspace()
        ws_task = task
        ws_task.id = None
        ws_task.area = WS_AREA_PENDING
        ws_task.status = TASK_TODO
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
        click.echo("No applicable tasks to start")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    LOGGER.debug("Total Tasks to Start {}".format(len(task_list)))
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                      .format(task.uuid, task.id))
        make_transient(task)
        task._oid = None
        ws_task = Workspace()
        ws_task = task
        ws_task.status = TASK_STARTED
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
        click.echo("No applicable tasks to stop")
        return SUCCESS
    task_list = get_tasks(uuid_version_results)
    LOGGER.debug("Total Tasks to Stop {}".format(len(task_list)))
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                      .format(task.uuid, task.id))
        make_transient(task)
        task._oid = None
        ws_task = Workspace()
        ws_task = task
        ws_task.status = TASK_TODO
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
        click.echo("No applicable tasks to complete")
        return
    task_list = get_tasks(uuid_version_results)
    for task in task_list:
        LOGGER.debug("Working on Task UUID {} and Task ID {}"
                      .format(task.uuid, task.id))        
        make_transient(task)
        task._oid = None
        ws_task = Workspace()
        ws_task = task
        ws_task.id = "-"
        ws_task.area = WS_AREA_COMPLETED
        ws_task.status = TASK_DONE
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
            if str(fl) == TASK_OVERDUE:
                potential_filters[TASK_OVERDUE] = "yes"
            if str(fl) == TASK_TODAY:
                potential_filters[TASK_TODAY] ="yes"
            if str(fl) == TASK_HIDDEN:
                potential_filters[TASK_HIDDEN] = "yes"
            if str(fl) == TASK_DONE:
                potential_filters[TASK_DONE] = "yes"
            if str(fl) == TASK_BIN:
                potential_filters[TASK_BIN] = "yes"    
            if str(fl).startswith("id:"):
                potential_filters["id"] = (str(fl).split(":"))[1]
            if str(fl).startswith("gr:") or str(fl).startswith("group:"):
                potential_filters["group"] = (str(fl).split(":"))[1]
            if str(fl).startswith("tg:") or str(fl).startswith("tag:"):
                potential_filters["tag"] = (str(fl).split(":"))[1]
            if str(fl).startswith("uuid:"):
                potential_filters["uuid"] = (str(fl).split(":"))[1]
    else:
        potential_filters = {"all":"yes"}
    #If only High LEvel Filters provided then set a key to use to warn users
    if ("id" not in potential_filters and "group" not in potential_filters
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
    except SQLAlchemyError as e:
        LOGGER.error(str(e))
        return None
    else:
        return ws_tags_list

def modify_task(potential_filters, ws_task_src, tag):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)    
    if not uuid_version_results:
        click.echo("No applicable tasks to modify")
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
        make_transient(task)
        task._oid = None
        ws_task = Workspace()
        ws_task = task        
        LOGGER.debug("Modification for Task UUID {} and Task ID {}"\
                      .format(ws_task.uuid,ws_task.id))
        if ws_task_src.description == "clr":
            ws_task.description = None      
        elif ws_task_src.description is not None:
            ws_task.description = ws_task_src.description

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
    return SUCCESS

def display_tasks(potential_filters):
    uuid_version_results = get_task_uuid_n_ver(potential_filters,
                                               WS_AREA_PENDING)
    if not uuid_version_results:
        click.echo("No tasks to display...")
        return SUCCESS
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
        addl_info_xpr = (case([(Workspace.area == WS_AREA_COMPLETED,TASK_DONE),
                               (Workspace.area == WS_AREA_BIN, TASK_BIN),
                               (Workspace.due < curr_day.date(), TASK_OVERDUE),
                               (Workspace.due == curr_day.date(),TASK_TODAY),],
                               else_ = "-").label("addl_info"))

        #Main query
        task_list = (SESSION.query(id_xpr.label("id_or_uuid"), 
                                Workspace.version.label("version"),
                                Workspace.description.label("description"),
                                Workspace.status.label("status"),
                                due_xpr.label("due"),
                                hide_xpr.label("hide"),
                                groups_xpr.label("groups"),
                                case([(tags_subqr.c.tags == None, "-"),],
                                    else_ = tags_subqr.c.tags).label("tags"),
                                addl_info_xpr.label("addl_info"),
                                Workspace.area.label("area"))
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
    
    #Styles and config for the 'rich' tables rows
    default = Style(color="white")
    today = Style(color="dark_orange")
    overdue = Style(color="red")
    started = Style(color="green")
    done = Style(color="grey46")
    binn = Style(color="grey46")
    console = Console()
    table = RichTable(box=box.HORIZONTALS, show_header=True, 
                      header_style="bold")
    #Column and Header Names
    if (task_list[0]).area == WS_AREA_PENDING:
        table.add_column("id",justify="center")
    else:
        table.add_column("uuid",justify="center")
    table.add_column("description",justify="left")
    table.add_column("due on",justify="center")
    table.add_column("groups",justify="center")
    table.add_column("tags",justify="center")
    table.add_column("status",justify="center")
    table.add_column("addl_info",justify="center")
    table.add_column("hide until",justify="center")
    table.add_column("version"  ,justify="center")
    
    for task in task_list:
        if task.status == TASK_DONE:
            table.add_row(
                          str(task.id_or_uuid),
                          str(task.description),str(task.due),
                          str(task.groups),str(task.tags),
                          str(task.status),str(task.addl_info),
                          str(task.hide),str(task.version),
                          style=done)
        elif task.addl_info == TASK_BIN:
            table.add_row(
                          str(task.id_or_uuid),
                          str(task.description),str(task.due),
                          str(task.groups),str(task.tags),
                          str(task.status),str(task.addl_info),
                          str(task.hide),str(task.version),
                          style=binn)           
        elif task.addl_info == TASK_OVERDUE:
            table.add_row(
                          str(task.id_or_uuid),
                          str(task.description),str(task.due),
                          str(task.groups),str(task.tags),
                          str(task.status),str(task.addl_info),
                          str(task.hide),str(task.version),
                          style=overdue)
        elif task.addl_info == TASK_TODAY:
            table.add_row(
                          str(task.id_or_uuid),
                          str(task.description),str(task.due),
                          str(task.groups),str(task.tags),
                          str(task.status),str(task.addl_info),
                          str(task.hide),str(task.version),
                          style=today)
        elif task.status == TASK_STARTED:
            table.add_row(
                          str(task.id_or_uuid),
                          str(task.description),str(task.due),
                          str(task.groups),str(task.tags),
                          str(task.status),str(task.addl_info),
                          str(task.hide),str(task.version),
                          style=started)                     
        else:
            table.add_row(
                          str(task.id_or_uuid),
                          str(task.description),str(task.due),
                          str(task.groups),str(task.tags),
                          str(task.status),str(task.addl_info),
                          str(task.hide),str(task.version),
                          style=default)
    console.print(table)
    get_and_print_task_count(to_print=True)
    if potential_filters.get(TASK_DONE) == "yes":
        get_and_print_task_count(True, WS_AREA_COMPLETED)
    elif potential_filters.get(TASK_BIN) == "yes":
        get_and_print_task_count(True, WS_AREA_BIN)
    return SUCCESS

def get_and_print_task_count(to_print=True, area=WS_AREA_PENDING):
    curr_day = datetime.now()
    try:
        #Get count of pending tasks split by HIDDEN and VISIBLE
        #Build case expression separately to simplify readability
        visib_xpr = case([(and_(Workspace.hide>curr_day.date(), Workspace.hide!=None), 
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
                     .join(max_ver_xpr, Workspace.uuid == max_ver_xpr.c.uuid)
                     .filter(and_(Workspace.area == WS_AREA_PENDING,
                             Workspace.version == max_ver_xpr.c.maxver))
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
                     .join(max_ver2_xpr, 
                           Workspace.uuid == max_ver2_xpr.c.uuid)
                     .filter(and_(Workspace.area == WS_AREA_COMPLETED,
                             Workspace.version > max_ver2_xpr.c.maxver))
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
                     .join(max_ver3_xpr, 
                           Workspace.uuid == max_ver3_xpr.c.uuid)
                     .filter(and_(Workspace.area == WS_AREA_BIN,
                             Workspace.version > max_ver3_xpr.c.maxver))
                     .all())
    except SQLAlchemyError as e:
        LOGGER.debug(str(e))
    
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
        if area == WS_AREA_COMPLETED:
            click.echo("Total Completed tasks: {}".format(compl))
        if area == WS_AREA_BIN:
            click.echo("Total tasks in Bin: {}".format(binn))
        if area == WS_AREA_PENDING:
            click.echo("Total Pending Tasks: {}, of which Hidden: {}"
                       .format(total,hid))
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
    cur = CONN.cursor()
    params = ()
    sql_list = []
    all_tasks = potential_filters.get("all")
    overdue_task = potential_filters.get(TASK_OVERDUE)
    today_task = potential_filters.get(TASK_TODAY)
    hidden_task = potential_filters.get(TASK_HIDDEN)
    done_task = potential_filters.get(TASK_DONE)
    bin_task = potential_filters.get(TASK_BIN)
    idn = potential_filters.get("id")
    uuidn = potential_filters.get("uuid")
    group = potential_filters.get("group")
    tag = potential_filters.get("tag")
    if all_tasks:
        """
        When no filter is provided retrieve all tasks from pending area
        """
        sql = "insert into temp_uuid_version (temp_uuid, temp_version)\
               select uuid,version from workspace ws where ws.area=?\
               and (ws.hide <= date('now') or ws.hide is null) and \
               ws.version = (select max(innrws.version) from workspace\
               innrws where ws.uuid=innrws.uuid)"
        params = (area,)
        LOGGER.debug("Inside all_tasks filter with below params and SQL")
        LOGGER.debug(params)
        LOGGER.debug("SQL: \n{}".format(sql))
    elif idn is not None:
        """
        If id(s) is provided extract tasks only based on ID as it is most 
        specific. Works only in pending area
        """
        id_list = idn.split(",")
        sql = "insert into temp_uuid_version (temp_uuid, temp_version)\
               select uuid,version from workspace ws where ws.area='pending'\
               and ws.version = (select max(innrws.version) from\
               workspace innrws where ws.uuid=innrws.uuid)\
               and ws.id in (%s)" % ",".join("?"*len(id_list))
        params = tuple(id_list)
        LOGGER.debug("Inside id filter with below params and SQL")
        LOGGER.debug(params)
        LOGGER.debug("SQL: \n{}".format(sql))
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
            sql_uuid = "select uuid,version from workspace ws where \
                        ws.version = (select max(innrws.version) from \
                        workspace innrws where ws.uuid=innrws.uuid)\
                        and ws.uuid in (%s)" % ",".join("?"*len(uuid_list))
            params = tuple(uuid_list)
            sql_list.append(sql_uuid)
            LOGGER.debug("Inside UUID filter with below params and SQL")
            LOGGER.debug(params)
            LOGGER.debug("SQL: \n{}".format(sql_uuid))
        else:
            if group is not None:
                """
                Query to get a list of uuid and version for matchiing groups
                from all 3 areas
                """
                #print("for group")
                sql_grp = "select uuid,version from workspace ws\
                        where ws.groups like ? and ws.version=\
                        (select max(innrws.version) from workspace innrws\
                        where innrws.uuid=ws.uuid)"
                params = params + (group+"%",)
                sql_list.append(sql_grp)
                LOGGER.debug("Inside group filter with below params and SQL")
                LOGGER.debug(params)
                LOGGER.debug("SQL: \n{}".format(sql_grp))
            if tag is not None:
                """
                Query to get a list of uuid and version for matchiing tags
                from all 3 areas
                """            
                #print("for tag")
                tag_list = tag.split(",")
                sql_tag = "select distinct uuid,version from workspace_tags tg\
                        where tg.tags \
                        in (%s) and tg.version =\
                        (select max(innrws.version) from workspace\
                        innrws where innrws.uuid=tg.uuid)"\
                    % ",".join("?"*len(tag_list))
                params = params + tuple(tag_list)
                sql_list.append(sql_tag)
                LOGGER.debug("Inside tag filter with below params and SQL")
                LOGGER.debug(params)
                LOGGER.debug("SQL: \n{}".format(sql_tag))
            LOGGER.debug("sql_list after group, tag:")
            LOGGER.debug(sql_list)

        """
        Look for modifiers that work in the pending area
        """
        LOGGER.debug("Status for OVERDUE {}, TODAY {}, HIDDEN {}"
                     .format(overdue_task, today_task, hidden_task))
        if (overdue_task is not None or today_task is not None or
                hidden_task is not None):
            if overdue_task is not None:
                #print("for overdue")
                sql_overdue = "select uuid,version from workspace ws where\
                               ws.due<date('now') and area='pending'\
                               and (ws.hide <= date('now') or\
                               ws.hide is null) and ws.version=\
                               (select max(innrws.version) from\
                               workspace innrws where innrws.uuid=ws.uuid)"
                sql_list.append(sql_overdue)
                LOGGER.debug("Inside overdue filter with below SQL")
                LOGGER.debug("SQL: \n{}".format(sql_overdue))
            if today_task is not None:
                #print("for today")
                sql_today = "select uuid,version from workspace ws where \
                            ws.due=date('now') and area='pending'\
                            and (ws.hide <= date('now') or ws.hide is null)\
                            and ws.version=(select max(innrws.version) from\
                            workspace innrws where innrws.uuid=ws.uuid)"                                
                sql_list.append(sql_today)
                LOGGER.debug("Inside today filter with below SQL")
                LOGGER.debug("SQL: \n{}".format(sql_today))
            if hidden_task is not None:
                #print("for hidden")
                sql_hidden = "select uuid,version from workspace ws where \
                              ws.area='pending' and\
                              (ws.hide>date('now') and  ws.hide is not null)\
                              and ws.version=(select max(innrws.version)\
                              from workspace innrws\
                              where innrws.uuid=ws.uuid)"                                
                sql_list.append(sql_hidden)
                LOGGER.debug("Inside hidden filter with below SQL")
                LOGGER.debug("SQL: \n{}".format(sql_hidden))
            LOGGER.debug("sql_list after overdue, today, hidden:")
            LOGGER.debug(sql_list)
        elif done_task is not None:
            """
            If none of the pending area modifiers are given look for other 
            modifiers. Preference is given to DONE over BIN and they are 
            mutually exclusive
            """
            # Get all completed tasks
            #print("for done")
            sql_done = "select distinct uuid,version from workspace ws where\
                        ws.area='completed' and ws.version >\
                       (select max(innrws.version) from workspace\
                       innrws where innrws.area <>'completed' and\
                       innrws.uuid=ws.uuid)"
            sql_list.append(sql_done)
            LOGGER.debug("Inside done filter with below SQL")
            LOGGER.debug("SQL: \n{}".format(sql_done))
        elif bin_task is not None:
            # Get all tasks in the bin
            #print("for bin")
            sql_bin = "select distinct uuid,version from workspace ws\
                        where ws.area='bin' and ws.version >\
                        (select max(innrws.version) from workspace\
                        innrws where innrws.area <>'bin' and\
                        innrws.uuid=ws.uuid)"
            sql_list.append(sql_bin)
            LOGGER.debug("Inside bin filter with below SQL")
            LOGGER.debug("SQL: \n{}".format(sql_bin))
        # If no modifiers provided then default to tasks in pending area
        else:
            sql_all = "select distinct uuid,version from workspace ws\
                        where ws.area='pending' and ws.id<>'-'\
                        and ws.version =\
                        (select max(innrws.version) from workspace\
                        innrws where innrws.area =ws.area and\
                        innrws.uuid=ws.uuid and ws.id<>'-')"
            sql_list.append(sql_all)
            LOGGER.debug("Inside default filter with below SQL")
            LOGGER.debug("SQL: \n{}".format(sql_all))
        LOGGER.debug("final sql_list:")
        LOGGER.debug(sql_list)
        if sql_list is None:
            return None
        sql = " intersect ".join(sql_list)
        sql = ("insert into temp_uuid_version (temp_uuid, temp_version) "
               "select uuid, version "
               "from (%s) unionws where unionws.version = "
               "(select max(verws.version) from workspace verws where "
               "unionws.uuid=verws.uuid)") % sql
    LOGGER.debug("Final SQL for getting task UUID/Version:\n{}"
                     .format(sql))
    sql_retreive = ("select temp_uuid, temp_version from "
                    "temp_uuid_version")
    try:
        LOGGER.debug(("Deleting from temp_uuid_version and inserting"
                      "the filter results of task UUIDs and versions"))
        cur.execute("delete from temp_uuid_version")
        cur.execute(sql, params)
        #Tuple of rows, UUID,Version        
        results = cur.execute(sql_retreive).fetchall() 
    except sqlite3.ProgrammingError as e:
        click.echo(str(e))
        return None
    else:
        CONN.commit()
        LOGGER.debug("List of resulting Task UUIDs and Versions:")
        LOGGER.debug(results)
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

def add_task_and_tags(ws_task_src, ws_tags_list=None):
    #LOGGER.debug("Incoming values Desc-{} Due-{} Hide-{} Group-{} Tag-{} "
    #             "Task_UUID-{} Task_ID-{} Event ID-{} status-{} area-{}"
    #             .format(desc, due, hide, group, tag,task_uuid, task_id,
    #             event_id,status,area))
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
    now = datetime.now().strftime("%Y-%m-%d")
    ws_task.created = now
    ws_task.modified = now
    ws_task.version = get_task_new_version(str(ws_task.uuid))
    ws_task.description = ws_task_src.description
    ws_task.groups = ws_task_src.groups
    if not ws_task_src.area:
        ws_task.area = WS_AREA_PENDING
    else:
        ws_task.area = ws_task_src.area
    if not ws_task_src.status:
        ws_task.status = TASK_TODO
    else:
        ws_task.status = ws_task_src.status   
    try:
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
        click.echo("Updated Task UUID: {}".format(ws_task.uuid))
    else:        
        click.echo("Added/Updated Task ID: {}".format(ws_task.id))
    if not tags_str:
        tags_str = "--"
    click.echo("ID:{} Ver:{} Sts:{} Desc:{} Due:{} Hide:{} Group:{} Tags:{}"
                .format(ws_task.id, ws_task.version, ws_task.status, 
                        ws_task.description, ws_task.due, ws_task.hide, 
                        ws_task.groups, tags_str[1:]))
    LOGGER.debug("Added/Updated Task UUID: {} and Area: {}"
                 .format(ws_task.uuid,ws_task.area))
    return SUCCESS, ws_task.uuid, ws_task.version

def exit_app(stat=0):
    global CONN, SESSION, ENGINE
    try:
        CONN.close()
        SESSION.remove()
        ENGINE.dispose()
    except:
        sys.exit(stat)
    else:
        sys.exit(stat)

def initialize_tasksdb(dbpath):
    global CONN
    try:
        LOGGER.debug("Attempting to intialize db")
        dburi = "file:{}?mode=rwc".format(pathname2url(dbpath))
        CONN = sqlite3.connect(dburi, uri=True)
        sql_list = retrieve_sql()
        LOGGER.debug("Executing following SQLs:\n" + sql_list)
        cur = CONN.cursor()
        for sql in sql_list:
            cur.execute(sql)
        cur.close()
    except sqlite3.OperationalError as e:
        click.echo("Error! Database creation could be partial.")
        click.echo(str(e))
        exit_app(1)
    click.echo("Database initialized...")
    return CONN

def retrieve_sql():
    workspace_sql = """
                    create table workspace (
                        uuid text ,
                        id integer,
                        description text,
                        status text,
                        due text,
                        hide text,
                        done text,
                        area text,
                        modified text,
                        groups text,
                        version integer,
                        event_id text,
                        primary key(uuid, version)
                    )"""
    workspace_tags_sql = """
                         create table workspace_tags ( 
                             uuid text,
                             tags text,
                             version integer,
                             primary key(uuid, tags, version)
                         )
                         """
    ws_uuid_ver__area_idx_sql = """
                                CREATE UNIQUE INDEX "ws_uuid_ver__area_idx" 
                                ON "workspace" (
                                "uuid"	ASC,
                                "version"	DESC,
                                "area"	DESC
                                )
                                """
    temp_uuid_version_sql = """
                        CREATE TABLE "temp_uuid_version" (
                        "temp_uuid"	TEXT,
                        "temp_version"	INTEGER
                        )
                        """
    return [workspace_sql, workspace_tags_sql, ws_uuid_ver__area_idx_sql,
            temp_uuid_table]
