import re
import uuid
import webbrowser
import logging
from datetime import date, datetime, timedelta
from copy import copy

from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from dateutil.rrule import *
from rich.prompt import Prompt
from sqlalchemy import and_, or_, case, func, distinct, cast, Numeric
from sqlalchemy.orm import make_transient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect

from src.mytcli.constants import (LOGGER, CONSOLE, SUCCESS, FAILURE,
                               TASK_OVERDUE, TASK_TODAY, TASK_HIDDEN,
                               TASK_BIN, TASK_COMPLETE, TASK_STARTED,
                               TASK_NOW, TASK_ALL, HL_FILTERS_ONLY,
                               CLR_STR, FUTDT,
                               WS_AREA_PENDING, WS_AREA_COMPLETED, WS_AREA_BIN,
                               TASK_TYPE_BASE, TASK_TYPE_DRVD, TASK_TYPE_NRML,
                               TASK_STATUS_TODO, TASK_STATUS_STARTED,
                               TASK_STATUS_DONE, TASK_STATUS_DELETED,
                               PRIORITY_HIGH, PRIORITY_MEDIUM,
                               PRIORITY_LOW, PRIORITY_NORMAL,
                               FMT_DATEONLY, FMT_DATETIME, FMT_EVENTID,
                               OPS_ADD, OPS_MODIFY, OPS_START, OPS_STOP,
                               OPS_REVERT, OPS_RESET, OPS_DELETE, OPS_NOW,
                               OPS_UNLINK, OPS_DONE,
                               MODE_DAILY, MODE_WEEKLY, MODE_MONTHLY,
                               MODE_YEARLY, MODE_WKDAY, MODE_MTHDYS,
                               MODE_MONTHS, VALID_MODES,
                               WHEN_WEEKDAYS, WHEN_MONTHDAYS, WHEN_MONTHS,
                               PRINT_ATTR, PRNT_TASK_DTLS, PRNT_CURR_VW_CNT)
from src.mytcli.models import Workspace, WorkspaceTags, WorkspaceRecurDates
import src.mytcli.db as db


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
        res = (db.SESSION.query(WorkspaceRecurDates)
                    .filter(and_(WorkspaceRecurDates.uuid == base_uuid,
                                WorkspaceRecurDates.version
                                    == base_version - 1))
                    .all())
        for rec_dt in res:
            db.SESSION.expunge(rec_dt)
            make_transient(rec_dt)
            rec_dt.uuid = base_uuid
            rec_dt.version = base_version
            db.SESSION.add(rec_dt)
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
    from src.mytcli.queries import get_tags
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
            max_ver_sqr = (db.SESSION.query(Workspace.uuid,
                                         func.max(Workspace.version)
                                         .label("maxver"))
                           .group_by(Workspace.uuid).subquery())
            # Final Query
            results_pend = (db.SESSION.query(visib_xpr,
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
            max_ver2_xpr = (db.SESSION.query(Workspace.uuid,
                                          func.max(Workspace.version)
                                          .label("maxver"))
                            .filter(Workspace.area != WS_AREA_COMPLETED)
                            .group_by(Workspace.uuid).subquery())
            # Final Query
            results_compl = (db.SESSION.query(func.count(distinct(Workspace.uuid))
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
            max_ver3_xpr = (db.SESSION.query(Workspace.uuid,
                                          func.max(Workspace.version)
                                          .label("maxver"))
                            .filter(Workspace.area != WS_AREA_BIN)
                            .group_by(Workspace.uuid).subquery())
            # Final Query
            results_bin = (db.SESSION.query(func.count(distinct(Workspace.uuid))
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
        results = (db.SESSION.query(Workspace.id)
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
        results = (db.SESSION.query(func.max(Workspace.version))
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
        (db.SESSION.query(Workspace).filter(Workspace.now_flag == True)
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
            next_due = (list(rrule(DAILY, count=cnt, dtstart=start_dt)))
        else:
            rec_intvl = int(recur_when[1:])
            next_due = (list(rrule(DAILY, interval=rec_intvl, count=cnt,
                                   dtstart=start_dt)))
    elif recur_mode == MODE_WEEKLY:
        if recur_when is None:
            next_due = (list(rrule(WEEKLY, count=cnt, dtstart=start_dt)))
        else:
            rec_intvl = int(recur_when[1:])
            next_due = (list(rrule(WEEKLY, interval=rec_intvl, count=cnt,
                                   dtstart=start_dt)))
    elif recur_mode == MODE_MONTHLY:
        if recur_when is None:
            next_due = (list(rrule(MONTHLY, count=cnt, dtstart=start_dt)))
        else:
            rec_intvl = int(recur_when[1:])
            next_due = (list(rrule(MONTHLY, interval=rec_intvl, count=cnt,
                                   dtstart=start_dt)))
    elif recur_mode == MODE_YEARLY:
        if recur_when is None:
            next_due = (list(rrule(YEARLY, count=cnt, dtstart=start_dt)))
        else:
            rec_intvl = int(recur_when[1:])
            next_due = (list(rrule(YEARLY, interval=rec_intvl, count=cnt,
                                   dtstart=start_dt)))
    else:
        #EXTENDED Modes
        #Parse the when list and check for modes which require a when
        when_list = [int(day) for day in recur_when.split(",")]
        when_list.sort()
        if recur_mode == MODE_WKDAY:
            #Adjust the when days by -1 to factor the 0 vs 1 index
            when_list = [day - 1 for day in when_list]
            next_due = (list(rrule(DAILY, count=cnt, byweekday=when_list,
                                   dtstart=start_dt)))
        elif recur_mode == MODE_MTHDYS:
            next_due = (list(rrule(DAILY, count=cnt, bymonthday=when_list,
                                   dtstart=start_dt)))
        elif recur_mode == MODE_MONTHS:
            next_due = (list(rrule(MONTHLY, count=cnt, bymonth=when_list,
                                   dtstart=start_dt)))
    if next_due is not None:
        if end_dt is not None:
            next_due = [d for d in next_due if d.date() <= end_dt]
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
