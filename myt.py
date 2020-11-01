import re
import os
import sqlite3
import uuid
import sys
from urllib.request import pathname2url

import click
from datetime import date
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from rich.console import Console
from rich.table import Column, Table, box
from rich.style import Style

#Global
DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "tasksdb.sqlite3")
CONN = None
TASK_TODO = "TO_DO"
TASK_INPROGRESS = "IN_PROGRESS"
TASK_DONE = "COMPLETE"
TASK_OVERDUE = "OVERDUE"
TASK_TODAY = "TODAY"
TASK_HIDDEN = "HIDDEN"

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

def get_filters():
        return input("Filters: ")

def yes_no(prompt):
    yes = set(["yes","y", "ye"])  
    choice = input(prompt).lower()
    if choice in yes:
        return True
    else:
        return False

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
def add(filters, desc, due, hide, group, tag):
    connect_to_tasksdb()
    if desc is None:
        click.echo("No task information provided. Nothing to do...")
    else:    
        add_task(desc, due, hide, group, tag, None, None, None)

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
def modify(filters, desc, due, hide, group, tag):
    potential_filters = parse_filters(filters)
    #display_opt_and_args(ops, desc, due, hide, group, tag, filters)
    connect_to_tasksdb()
    if potential_filters.get("all") == "yes":
        if not yes_no("No filters given for modify, are you sure? (yes/no)"):
            exit_app(0)
    modify_task(potential_filters, desc, due, hide, group, tag)

@myt.command()
@click.argument("filters",nargs=-1)
def start(filters):
    potential_filters = parse_filters(filters)
    connect_to_tasksdb()
    if potential_filters.get("all") == "yes":
        if not yes_no("No filters given for starting tasks,\
            are you sure? (yes/no)"):
            exit_app(0)
    mark_task_inprogress(potential_filters)
    return

@myt.command()
@click.argument("filters",nargs=-1)
def done(filters):
    potential_filters = parse_filters(filters)
    connect_to_tasksdb() 
    if potential_filters.get("all") == "yes":
        if not yes_no("No filters given for marking tasks as done,\
            are you sure? (yes/no)"):
            exit_app(0)
    mark_task_done(potential_filters)  
    return

@myt.command()
@click.argument("filters",nargs=-1)
def reset(filters):
    return

@myt.command()
@click.argument("filters",nargs=-1)
def pause(filters):
    potential_filters = parse_filters(filters)
    connect_to_tasksdb()
    if potential_filters.get("all") == "yes":
        if not yes_no("No filters given for starting tasks,\
            are you sure? (yes/no)"):
            exit_app(0)
    mark_task_paused(potential_filters)
    return

@myt.command()
@click.argument("filters",nargs=-1)
def view(filters):
    potential_filters = parse_filters(filters)
    connect_to_tasksdb()
    display_tasks(potential_filters) 
    return  

def mark_task_inprogress(potential_filters):
    uuid_version_results = get_task_uuid_and_version(potential_filters)
    """
    Flatten the tuple from (uuid,version),(uuid,version)
    to uuid,version,uuid,version...
    """
    task_uuid_and_version = [element for itm 
                            in uuid_version_results for element in itm]
    task_list = get_tasks(task_uuid_and_version)
    for task in task_list:
        #No changes to fields except the status, area and task Id
        desc = task[2]
        due = task[4]
        hide = task[5]
        group = task[6]
        task_uuid = task[8]
        task_id_u = task[0]
        area_u = task[9]
        status_u = TASK_INPROGRESS
        version = task[1]
        tags_list = get_tags(task_uuid, version)
        """
        Flatten the list of tuples to a list
        [(a,),(b,)] to [a,b]
        """
        tag_u = [element for itm in tags_list for element in itm]
        tag_u_str = ",".join(map(str, tag_u))
        task_uuid, version = add_task(desc,due,hide,group,tag_u_str,
                                      task_uuid,task_id_u,None,status_u,
                                      area_u)
    return
    
def mark_task_paused(potential_filters):
    uuid_version_results = get_task_uuid_and_version(potential_filters)
    """
    Flatten the tuple from (uuid,version),(uuid,version)
    to uuid,version,uuid,version...
    """
    task_uuid_and_version = [element for itm 
                            in uuid_version_results for element in itm]
    task_list = get_tasks(task_uuid_and_version)
    for task in task_list:
        #No changes to fields except the status, area and task Id
        desc = task[2]
        due = task[4]
        hide = task[5]
        group = task[6]
        task_uuid = task[8]
        task_id_u = task[0]
        area_u = task[9]
        status_u = TASK_TODO
        version = task[1]
        tags_list = get_tags(task_uuid, version)
        """
        Flatten the list of tuples to a list
        [(a,),(b,)] to [a,b]
        """
        tag_u = [element for itm in tags_list for element in itm]
        tag_u_str = ",".join(map(str, tag_u))
        add_task(desc,due,hide,group,tag_u_str,
                 task_uuid,task_id_u,None,status_u,area_u)
    return    

def mark_task_done(potential_filters):
    uuid_version_results = get_task_uuid_and_version(potential_filters)
    """
    Flatten the tuple from (uuid,version),(uuid,version)
    to uuid,version,uuid,version...
    """
    task_uuid_and_version = [element for itm 
                            in uuid_version_results for element in itm]
    task_list = get_tasks(task_uuid_and_version)
    for task in task_list:
        #No changes to fields except the status, area and task Id
        desc = task[2]
        due = task[4]
        hide = task[5]
        group = task[6]
        task_uuid = task[8]
        task_id_u = "-"
        area_u = "completed"
        status_u = TASK_DONE
        version = task[1]
        tags_list = get_tags(task_uuid, version)
        """
        Flatten the list of tuples to a list
        [(a,),(b,)] to [a,b]
        """
        tag_u = [element for itm in tags_list for element in itm]
        tag_u_str = ",".join(map(str, tag_u))
        add_task(desc,due,hide,group,tag_u_str,
                 task_uuid,task_id_u,None,status_u,area_u)
    return

def reset_task(potential_filters):
    uuid_version_results = get_task_uuid_and_version(potential_filters)
    """
    Flatten the tuple from (uuid,version),(uuid,version)
    to uuid,version,uuid,version...
    """
    task_uuid_and_version = [element for itm 
                            in uuid_version_results for element in itm]
    task_list = get_tasks(task_uuid_and_version)
    for task in task_list:
        #No changes to fields except the status, area and task Id
        desc = task[2]
        due = task[4]
        hide = task[5]
        group = task[6]
        task_uuid = task[8]
        task_id_u = "-"
        area_u = "completed"
        status_u = TASK_DONE
        version = task[1]
        tags_list = get_tags(task_uuid, version)
        """
        Flatten the list of tuples to a list
        [(a,),(b,)] to [a,b]
        """
        tag_u = [element for itm in tags_list for element in itm]
        tag_u_str = ",".join(map(str, tag_u))
        add_task(desc,due,hide,group,tag_u_str,
                 task_uuid,task_id_u,None,status_u,area_u)
    return

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
            if str(fl).startswith("id:"):
                potential_filters["id"] = (str(fl).split(":"))[1]
            if str(fl).startswith("gr:") or str(fl).startswith("group:"):
                potential_filters["group"] = (str(fl).split(":"))[1]
            if str(fl).startswith("tg:") or str(fl).startswith("tag:"):
                potential_filters["tag"] = (str(fl).split(":"))[1]
    else:
        potential_filters = {"all":"yes"}
    return potential_filters

def get_tasks(task_uuid_and_version):
    """
    Returns the task details for a list of task uuid and versions.

    Retrieves tasks details from the database for he provided
    list of task UUIDs and Versions. The index of the attributes
    are as below:
        0 - id
        1 - version
        2 - description
        3 - status
        4 - due
        5 - hide
        6 - groups
        7 - tags
        8 - uuid
        9 - area

    Parameters:
        task_uuid_and_version(list): List of uuid and versions
    
    Returns:
        list: List with details for each task
    """
    global CONN
    cur = CONN.cursor()
    sql_tasks = """
        select ws.id,\
        ws.version,\
        ws.description,\
        ws.status,\
        ws.due,\
        ws.hide,\
        ws.groups,\
        tg.tags,\
        ws.uuid,\
        ws.area
        from workspace ws left join 
        (select uuid ,version, group_concat(tags) as tags\
            from workspace_tags wt\
            group by uuid,version) tg\
        on ws.uuid=tg.uuid and tg.version = ws.version\
        where (ws.uuid, ws.version ) in (values %s)\
        order by modified desc\
        """ % ",".join(["(?,?)"]*int(len(task_uuid_and_version)/2))
    #print(sql_tasks)
    #return
    try:
        task_list = cur.execute(sql_tasks,task_uuid_and_version).fetchall()
    except sqlite3.ProgrammingError as e:
        click.echo(str(e))
        return None
    else:
        return task_list

def get_tags(task_uuid, task_version):
    global CONN
    cur = CONN.cursor()
    sql_tags = """
               select tags from workspace_tags ws where ws.uuid=?\
               and ws.version=?
               """
    try:
        tags = cur.execute(sql_tags
            ,(task_uuid,task_version,)).fetchall()
    except sqlite3.ProgrammingError as e:
        click.echo(str(e))
        return None
    else:
        return tags

def modify_task(potential_filters, desc, due, hide, group, tag):
    global CONN
    cur = CONN.cursor()
    task_uuid_and_version = get_task_uuid_and_version(potential_filters)
    event_id = datetime.now().strftime("%Y%m-%d%H-%M%S-") +\
                str(uuid.uuid4())
    for task in task_uuid_and_version:
        #print(task)
        result = cur.execute("select\
            description, due, hide, groups, uuid,id, area,status\
            from workspace ws\
            where ws.uuid=?\
            and ws.version=?",(task[0],task[1],)).fetchall()
        #print(result)
        desc_u = result[0][0]
        due_u = result[0][1]
        hide_u = result[0][2]
        group_u = result[0][3]
        task_uuid = result[0][4]
        task_id = result[0][5]
        area = result[0][6]
        status = result[0][7]
        results = list(cur.execute("select\
            tags from workspace_tags ws\
            where ws.uuid=? and ws.version=?",(task[0],task[1],)).fetchall())
        """
        Flatten the list of tuples to a list
        [(a,),(b,)] to [a,b]
        """
        tag_u = [element for itm in results for element in itm]
        if desc == "clr":
            desc_u = None      
        elif desc is not None:
            desc_u = desc

        if due == "clr":
            due_u = None
        elif due is not None:
            due_u = due

        if hide == "clr":
            hide_u = None
        elif hide is not None:
            hide_u = hide

        if group == "clr":
            group_u = None
        elif group is not None:
            group_u = group

        tag_u_str = None
        if tag != "clr" and tag is not None:
            tag_list = tag.split(",")
            for t in tag_list:
                if t[0] == "-":
                    t = str(t[1:])
                    if t in tag_u:
                        #print("To Remove: %s" % t)
                        tag_u.remove(t)
                else:
                    if t[0] == "+":
                        t = str(t[1:])
                    if t not in tag_u:
                        #print("To Add %s" % t)
                        tag_u.append(t)
            tag_u_str = ",".join(map(str, tag_u)) 
        add_task(desc_u, due_u, hide_u, group_u, tag_u_str,
                 task_uuid, task_id, event_id,status, area)
    return

def display_tasks(potential_filters):
    global CONN
    uuid_version_results = get_task_uuid_and_version(potential_filters)
    """
    Flatten the tuple from (uuid,version),(uuid,version)
    to uuid,version,uuid,version...
    """
    if not uuid_version_results:
        click.echo("No tasks to display...")
        return
    task_uuid_and_version = [element for itm 
                             in uuid_version_results for element in itm]
    cur = CONN.cursor()
    console = Console()
    table = Table(box=box.HORIZONTALS, show_header=True, header_style="bold")
    table.add_column("id",width=4,justify="center")
    table.add_column("version",width=4,justify="center")
    table.add_column("description",justify="left")
    table.add_column("status",justify="center")
    table.add_column("due",justify="center")
    table.add_column("hidden",justify="center")
    table.add_column("groups",justify="center")
    table.add_column("tags",justify="center")
    table.add_column("addl_info",justify="center")
    
    #Styles for the tables rows
    todo = Style(color="white")
    todo_today = Style(color="dark_orange")
    todo_overdue = Style(color="red")
    inprogress = Style(color="black", bgcolor="grey93")
    inprogress_today = Style(color="dark_orange", bgcolor="grey93")
    inprogress_overdue = Style(color="red", bgcolor="grey93")
    done = Style(color="grey46")

    sql_view = """
        select ws.id,\
        ws.version,\
        ws.description,\
        ws.status,\
        case when ws.due is null then '-' else due end due,\
        case when ws.hide is null then '-' else hide end hide,\
        case when ws.groups is null then '-' else groups end groups,\
        case when tg.tags is null then '-' else tg.tags end tags,\
        case when ws.due<date('now') then 'OVERDUE' when ws.due=date('now')\
            then 'TODAY' else '-' end addl_info\
        from workspace ws left join
        (select uuid ,version,\
            group_concat(tags) as tags\
            from workspace_tags wt\
            group by uuid,version) tg 
        on ws.uuid=tg.uuid and\
        tg.version = ws.version where 
        (ws.uuid, ws.version ) in (values %s)"""\
        % ",".join(["(?,?)"]*int(len(task_uuid_and_version)/2))
        
    #print(sql_view)
    try:
        task_list = cur.execute(sql_view,task_uuid_and_version).fetchall()
        for task in task_list:
            if task[3] == TASK_TODO and task[8] == TASK_OVERDUE:
                table.add_row(str(task[0]),str(task[1]),str(task[2]),
                              str(task[3]),str(task[4]),str(task[5]),
                              str(task[6]),str(task[7]),str(task[8]),
                              style=todo_overdue)
            elif task[3] == TASK_TODO and task[8] == TASK_TODAY:
                table.add_row(str(task[0]),str(task[1]),str(task[2]),
                              str(task[3]),str(task[4]),str(task[5]),
                              str(task[6]),str(task[7]),str(task[8]),
                              style=todo_today)
            elif task[3] == TASK_TODO:
                table.add_row(str(task[0]),str(task[1]),str(task[2]),
                              str(task[3]),str(task[4]),str(task[5]),
                              str(task[6]),str(task[7]),str(task[8]),
                              style=todo)            
            elif task[3] == TASK_INPROGRESS and task[8] == TASK_OVERDUE:
                table.add_row(str(task[0]),str(task[1]),str(task[2]),
                              str(task[3]),str(task[4]),str(task[5]),
                              str(task[6]),str(task[7]),str(task[8]),
                              style=inprogress_overdue)
            elif task[3] == TASK_INPROGRESS and task[8] == TASK_TODAY:
                table.add_row(str(task[0]),str(task[1]),str(task[2]),
                              str(task[3]),str(task[4]),str(task[5]),
                              str(task[6]),str(task[7]),str(task[8]),
                              style=inprogress_today)
            elif task[3] == TASK_INPROGRESS:
                table.add_row(str(task[0]),str(task[1]),str(task[2]),
                              str(task[3]),str(task[4]),str(task[5]),
                              str(task[6]),str(task[7]),str(task[8]),
                              style=inprogress)
            elif task[3] == TASK_DONE:
                table.add_row(str(task[0]),str(task[1]),str(task[2]),
                              str(task[3]),str(task[4]),str(task[5]),
                              str(task[6]),str(task[7]),str(task[8]),
                              style=done)            
            else:
                table.add_row(str(task[0]),str(task[1]),str(task[2]),
                              str(task[3]),str(task[4]),str(task[5]),
                              str(task[6]),str(task[7]),str(task[8]),
                              style=todo)
            
    except sqlite3.ProgrammingError as e:
        click.echo(str(e))
        return
    console.print(table)
    get_and_printactive_task_count(print=True)
    
    return 

def get_and_printactive_task_count(print=True):
    global CONN
    cur = CONN.cursor()
    sql_cnt = """
        select\
        case when (hide>date('now') and hide is not null)\
            then 'HIDDEN'\
            else 'VISIBLE'\
            end VSIBILITY,\
        count( distinct uuid) CNT\
        from workspace ws\
        where ws.area='pending' and 
        ws.version = (select max(innrws.version)\
            from workspace \
            innrws where innrws.uuid = ws.uuid) 
        group by case when (hide>date('now') and  hide is not null)\
            then 'HIDDEN' else 'VISIBLE' end\
        order by VSIBILITY desc\
        """
    results = cur.execute(sql_cnt).fetchall()
    """
    VISIBILITY | CNT
    ----------   ---
    VISIBLE    |  3
    HIDDEN     |  2
    """
    if results:
        cnt = [x[1] for x in results]
        try:
            vis = cnt[0]
        except IndexError:
            vis = 0
        try:
            hid = cnt[1]
        except IndexError:
            hid = 0
        total = vis + hid
    if print:
        click.echo("Total Pending Tasks: %s, of which Hidden: %s"% (total,hid))
    return ([total,hid])

def derive_task_id():
    """Get next available task ID from  active area in the workspace"""

    global CONN
    cur = CONN.cursor()
    results = cur.execute("""select id from workspace where \
        area='pending'""").fetchall()
    id_list =[]
    for row in results:
        id_list.append(row[0])
    id_list.insert(0, 0)
    id_list.sort()
    available_list = sorted(set(range(id_list[0], id_list[-1]))-set(id_list))
    if not available_list:  # If no tasks exist/no available intermediate seq
        return id_list[-1] + 1
    return available_list[0]


def get_task_uuid_and_version(potential_filters):
    """
    Return task UUID and version by applying filters on tasks

    Using a list of filters identify the relevant task UUIDs and their
    latest versions. The filters come in the form of a dictionary and
    expected keys include:
        - For All Pending Items
        - Overdue Tasks
        - Tasks due today
        - Hidden Tasks
        - Completed Tasks
        - Task id based filters
        - Task group based filters
        - Task tags based filters
    No validations are performed on the filters. Using the priority set 
    in function the filters are applied onto the tasks table.
    As multiple filters can be provided, priority is followed as below:
        1. All Pending Tasks
        2. IDs
        3. Groups, Tags, Overdue, Today (these can be combined)
        4. Hidden
        5. Completed

    Parameters:
        potential_filters(dict): Dictionary with the various types of
                                 filters
    
    Returns:
        list: List of tuples of (task UUID,Version)

    """
    global CONN
    cur = CONN.cursor()
    params = ()
    sql_list = []

    all_tasks = potential_filters.get("all")
    overdue_task = potential_filters.get(TASK_OVERDUE)
    today_task = potential_filters.get(TASK_TODAY)
    hidden_task = potential_filters.get(TASK_HIDDEN)
    done_task = potential_filters.get(TASK_DONE)
    idn = potential_filters.get("id")
    group = potential_filters.get("group")
    tag = potential_filters.get("tag")

    if all_tasks:
        """
        When no filter is provided retrieve all tasks from pending area
        """
        sql = "select uuid,version from workspace ws where ws.area='pending'\
            and (ws.hide <= date('now') or ws.hide is null) and \
            ws.version = (select max(innrws.version) from workspace innrws\
            where ws.uuid=innrws.uuid)"
        params = {}
    elif idn is not None:
        """
        If id(s) is provided extract tasks only based on ID as it is most 
        specific
        """
        id_list = idn.split(",")
        sql = "select uuid,version from workspace ws where ws.area='pending'\
            and ws.version = (select max(innrws.version) from workspace \
            innrws where ws.uuid=innrws.uuid)\
            and ws.id in (%s)" % ",".join("?"*len(id_list))
        params = tuple(id_list)
    else:
        """
        If it is not ID then try to get task list from combination of filters
        provided by user
        """
        if group is not None:
            #print("for group")
            sql_grp = "select uuid,version from workspace ws\
                       where ws.groups like ?\
                       and ws.area='pending'"
            params = (group+"%",)
            sql_list.append(sql_grp)
        if tag is not None:
            #print("for tag")
            tag_list = tag.split(",")
            sql_tag = "select uuid,version from workspace_tags tg\
                       where tg.tags \
                       in (%s) and tg.uuid in\
                       (select innrws.uuid from workspace\
                       innrws where innrws.area='pending')"\
                % ",".join("?"*len(tag_list))
            params = params + tuple(tag_list)
            sql_list.append(sql_tag)
        if overdue_task is not None:
            #print("for overdue")
            sql_overdue = "select uuid,version from workspace ws where \
                           ws.due<date('now') and area='pending'\
                           and (ws.hide <= date('now') or ws.hide is null)"
            sql_list.append(sql_overdue)
        if today_task is not None:
            #print("for today")
            sql_today = "select uuid,version from workspace ws where \
                         ws.due=date('now') and area='pending'\
                         and (ws.hide <= date('now') or ws.hide is null)"
            sql_list.append(sql_today)
        elif hidden_task is not None:
            #print("for hidden")
            sql_hidden = "select uuid,version from workspace ws where \
                          ws.area='pending' and\
                          (ws.hide>date('now') and  ws.hide is not null)"
            sql_list.append(sql_hidden)
        elif done_task is not None:
            #print("for done")
            sql_done = "select uuid,version from workspace ws where \
                        ws.area='completed'"
            sql_list.append(sql_done)
                  
        if not sql_list:
            #No valid filters provided
            return None
        sql = " union ".join(sql_list)
        sql = "select uuid, version from (%s) unionws\
               where unionws.version =\
               (select max(verws.version) from workspace verws where\
               unionws.uuid=verws.uuid)" % sql

    #print(sql)
    try:
        #Tuple of rows, UUID,Version
        results = cur.execute(sql, params).fetchall() 
    except sqlite3.ProgrammingError as e:
        click.echo(str(e))
    return results

def get_task_new_version(task_uuid):
    global CONN
    cur = CONN.cursor()
    #print("INFO: Trying to get version for (%s)" % task_uuid)
    try:
        results = cur.execute("select max(version) from workspace ws\
                               where ws.area = 'pending'\
                               and uuid = ?",(task_uuid,)).fetchall()
    except sqlite3.ProgrammingError as e:
        click.echo(str(e))
    if (results[0])[0] is not None:  #Tasks exists so increment version
        return (results[0][0]) + 1
    else:   # New task so return 1
        #print("default")
        return "1"
    
def add_task(desc, due, hide, group, tag,
             task_uuid, task_id,event_id,status=TASK_TODO,area="pending"):
    global CONN
    cur = CONN.cursor()
    if task_id is None:
        task_id = derive_task_id()
    #print("Due %s : " % due)
    if due is not None:
        due_dt = convert_due(due)
    else:
        due_dt = None
    if hide is not None:
        if due is not None: 
        #Hide date relative to due date only if due date is available
            hide_dt = convert_hide(hide,parse(due_dt))
        else:
            hide_dt = convert_hide(hide,None)
    else:
        hide_dt = None
    try:
        if task_uuid is None:
            task_uuid = uuid.uuid4()
        if event_id is None:
            event_id = datetime.now().strftime("%Y%m-%d%H-%M%S-") +\
                str(uuid.uuid4())
        now = datetime.now()
        task_ver = get_task_new_version(str(task_uuid))
        cur.execute("""insert into workspace\
                (uuid, version, id, description, status, groups, area,\
                due,hide, modified, event_id) values\
                (?,?,?,?,?,?,?,?,?,?,?)""", (str(task_uuid), task_ver,\
                task_id, desc, status, group, area, due_dt,\
                hide_dt, now, event_id))
        if tag is not None:
            tag_list = tag.split(",")
            for t in tag_list:
                cur.execute("""insert into workspace_tags\
                    (uuid, version, tags) values(?, ?, ?)""",
                            (str(task_uuid), task_ver, t))
                # datetime("now"),datetime("now")))
        cur.execute("""insert into event_stack (event_id) values (?)"""\
            ,(event_id,))
    except sqlite3.ProgrammingError as e:
        print(str(e))
        return None, None
    CONN.commit()
    click.echo("Added Task ID: %s" % task_id)
    get_and_printactive_task_count(print=True)
    return task_uuid, task_ver


def display_opt_and_args(ops, desc, due, hide, group, tag, filters):
    click.echo("Select Operation is %s" % ops)
    click.echo("Description: %s" % desc)
    click.echo("Due: %s" % due)
    click.echo("Hide: %s" % hide)
    click.echo("Group: %s" % group)
    click.echo("Tags: %s" % tag)
    #click.echo("Filters: %s" % filters)



def connect_to_tasksdb(dbpath=DEFAULT_PATH):
    global CONN
    try:
        dburi = "file:{}?mode=rw".format(pathname2url(dbpath))
        CONN = sqlite3.connect(dburi, uri=True)
    except sqlite3.OperationalError:
        click.echo("INFO: No database exists, intializing...")
        CONN = initialize_tasksdb(dbpath)
    #CONN.set_trace_callback(print)
    return CONN


def exit_app(stat=0):
    sys.exit(stat)


def initialize_tasksdb(dbpath):
    global CONN
    try:
        dburi = "file:{}?mode=rwc".format(pathname2url(dbpath))
        CONN = sqlite3.connect(dburi, uri=True)
        sql_list = retrieve_sql()
        cur = CONN.cursor()
        for sql in sql_list:
            cur.execute(sql)
        cur.close()
    except sqlite3.OperationalError as e:
        click.echo("ERROR: Database creation could be partial.")
        click.echo(str(e))
        exit_app(1)
    click.echo("INFO: Database initialized...")
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
    bin_sql = """
              create table bin (
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
              primary key(uuid, version)
              )"""
    bin_tags_sql = """
                   create table bin_tags ( 
                       uuid text,
                       tags text,
                       version integer,
                       primary key(uuid, tags, version)
                   )"""
    return [workspace_sql, workspace_tags_sql, bin_sql, bin_tags_sql]
