import sys
from io import StringIO
from operator import itemgetter
from datetime import datetime, timedelta
from copy import copy

from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, or_, case, func, tuple_, distinct, cast, Numeric
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.exc import SQLAlchemyError
from rich.table import Table as RichTable, box
from rich.panel import Panel
from rich.columns import Columns
import plotext as pltxt

import src.mytcli.constants as constants
from src.mytcli.constants import (LOGGER, CONSOLE, SUCCESS, FAILURE,
                               TASK_OVERDUE, TASK_TODAY, TASK_HIDDEN,
                               TASK_BIN, TASK_COMPLETE, TASK_STARTED,
                               TASK_NOW, TASK_ALL,
                               WS_AREA_PENDING, WS_AREA_COMPLETED, WS_AREA_BIN,
                               TASK_TYPE_BASE, TASK_TYPE_DRVD, TASK_TYPE_NRML,
                               TASK_STATUS_TODO, TASK_STATUS_STARTED,
                               TASK_STATUS_DONE, TASK_STATUS_DELETED,
                               PRIORITY_HIGH, PRIORITY_MEDIUM,
                               PRIORITY_LOW, PRIORITY_NORMAL,
                               FMT_DATEONLY, FMT_DATETIME, FMT_DAY_DATEW,
                               FMT_DATEW_TIME,
                               INDC_PR_HIGH, INDC_PR_MED, INDC_PR_NRML,
                               INDC_PR_LOW, INDC_NOW, INDC_NOTES, INDC_RECUR,
                               PRNT_CURR_VW_CNT, TASK_TOMMR, FUTDT)
from src.mytcli.models import Workspace, WorkspaceTags, WorkspaceRecurDates
import src.mytcli.db as db
from src.mytcli.queries import get_tasks, get_tags, get_task_uuid_n_ver
from src.mytcli.utils import (calc_task_scores, calc_next_inst_date,
                           convert_time_unit, get_and_print_task_count,
                           reflect_object_n_print)


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
    if not constants.TUI_MODE:
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
        task_list = (db.SESSION.query(case((cast(Workspace.due_diff_today,
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
        if not constants.TUI_MODE:
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
        task_list = (db.SESSION.query(id_xpr.label("id_or_uuid"),
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
        if not constants.TUI_MODE:
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
            res = (db.SESSION.query(func.max(WorkspaceRecurDates.due))
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
    if not constants.TUI_MODE:
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
        context_xpr = (case((Workspace.context == None, None),
                            else_=Workspace.context))
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
        tags_subqr = (db.SESSION.query(WorkspaceTags.uuid, WorkspaceTags.version,
                                    func.group_concat(WorkspaceTags.tags, " ")
                                    .label("tags"))
                      .group_by(WorkspaceTags.uuid,
                                WorkspaceTags.version)
                      .subquery())
        # Sub Query for Tags - END
        # Main query
        task_list = (db.SESSION.query(Workspace.uuid.label("uuid"),
                                   Workspace.id.label("id"),
                                   Workspace.description.label("description"),
                                   due_xpr.label("due"),
                                   recur_xpr.label("recur"),
                                   end_xpr.label("end"),
                                   groups_xpr.label("groups"),
                                   context_xpr.label("context"),
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
    table.add_column("context", justify="right")
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
                trow = [None] * 16
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
                task.groups, task.context, task.tags, task.status,
                task.priority_flg, task.now, hide, str(task.version),
                inception, created]
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
    if not constants.TUI_MODE:
        CONSOLE.print("Preparing view...", style="default")
    try:
        """
        bug-7: replaced the query to now include tasks with no tags.
        Order by is on tags without coalesce to ensure the no tag task count
        with NULL is shown on the first row.
        """
        tags_list = (db.SESSION.query(coalesce(WorkspaceTags.tags,"No Tag").label("tags"),
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
    if not constants.TUI_MODE:
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
        max_ver_sqr = (db.SESSION.query(Workspace.uuid,
                                func.max(Workspace.version)
                                        .label("maxver"))
                               .group_by(Workspace.uuid).subquery())
        task_status_cnt = (db.SESSION.query(Workspace.status,
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

        pending_task_cnt = (db.SESSION.query(
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

        if constants.TUI_MODE:
            old_stdout = sys.stdout
            sys.stdout = buf = StringIO()
            pltxt.show()
            sys.stdout = old_stdout
            CONSOLE.print(buf.getvalue())
        else:
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

        compl_trend = (db.SESSION.query(Workspace.ver_crt_diff_now,
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
        if constants.TUI_MODE:
            old_stdout = sys.stdout
            sys.stdout = buf = StringIO()
            pltxt.show()
            sys.stdout = old_stdout
            CONSOLE.print(buf.getvalue())
        else:
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

        new_trend = (db.SESSION.query(Workspace.ver_crt_diff_now,
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
        if constants.TUI_MODE:
            old_stdout = sys.stdout
            sys.stdout = buf = StringIO()
            pltxt.show()
            sys.stdout = old_stdout
            CONSOLE.print(buf.getvalue())
        else:
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
    if not constants.TUI_MODE:
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
        context_xpr = (case((Workspace.context == None, None),
                            else_=Workspace.context))
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
        tags_subqr = (db.SESSION.query(WorkspaceTags.uuid, WorkspaceTags.version,
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
        task_list = (db.SESSION.query(id_xpr.label("id_or_uuid"),
                                   Workspace.description.label("description"),
                                   addl_info_xpr.label("due_in"),
                                   due_xpr.label("due"),
                                   recur_xpr.label("recur"),
                                   end_xpr.label("end"),
                                   groups_xpr.label("groups"),
                                   context_xpr.label("context"),
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
    table.add_column("context", justify="right")
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
                task.recur, end, task.groups, task.context, task.tags,
                task.status, duration, hide,
                "".join([task.now,task.notes, task.priority_flg]),
                str(task.version), age, created, score]
        tdata.append(trow)
    #Now sort the list depending on which area we are displaying
    if task_list[0].area == WS_AREA_PENDING:
        #based on score, descending
        tdata = sorted(tdata, key=itemgetter(16), reverse=True)
    else:
        #hidden or bin task, so based on created date
        tdata = sorted(tdata, key=itemgetter(15), reverse=True)

    for trow in tdata:
        # Next Display the tasks with formatting based on various conditions
        if trow[9] == TASK_STATUS_DONE:
            table.add_row(*trow, style="done")
        elif trow[9] == TASK_STATUS_DELETED:
            table.add_row(*trow, style="binn")
        elif INDC_NOW in trow[12]:
            table.add_row(*trow, style="now")
        elif trow[9] == TASK_STATUS_STARTED:
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
        max_ver_sqr = (db.SESSION.query(Workspace.uuid,
                                func.max(Workspace.version)
                                .label("maxver"))
                               .filter(and_(Workspace.area.in_(
                                                            [WS_AREA_PENDING,
                                                            WS_AREA_COMPLETED]
                                                            )))
                               .group_by(Workspace.uuid).subquery())
        tags_list = (db.SESSION.query(distinct(WorkspaceTags.tags).label("tags"))
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
        max_ver_sqr = (db.SESSION.query(Workspace.uuid,
                                func.max(Workspace.version)
                                        .label("maxver"))
                               .group_by(Workspace.uuid).subquery())
        groups_list = (db.SESSION.query(distinct(Workspace.groups)
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
