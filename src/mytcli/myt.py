from importlib import metadata
import logging

import click
from dateutil.parser import parse

from src.mytcli.constants import (LOGGER, CONSOLE, SUCCESS, FAILURE,
                               TASK_COMPLETE, TASK_BIN, TASK_ALL,
                               HL_FILTERS_ONLY,
                               WS_AREA_PENDING,
                               TASK_TYPE_NRML, TASK_STATUS_TODO, CLR_STR,
                               OPS_ADD, PRNT_TASK_DTLS, CHANGELOG)
from src.mytcli.models import Workspace
import src.mytcli.db as db
from src.mytcli.db import (connect_to_tasksdb, exit_app, reinitialize_db,
                        set_versbose_logging)
from src.mytcli.queries import get_tasks
from src.mytcli.utils import (parse_filters, confirm_prompt, get_event_id,
                           convert_date, convert_date_rel, generate_tags,
                           get_and_print_task_count, parse_n_validate_recur)
from src.mytcli.operations import (prep_recurring_tasks, add_task_and_tags,
                                prep_modify, prep_delete, start_task,
                                stop_task, complete_task, revert_task,
                                reset_task, toggle_now, perform_undo,
                                process_url, empty_bin)
from src.mytcli.display import (display_default, display_full, display_history,
                             display_by_tags, display_by_groups,
                             display_dates, display_notes, display_7day,
                             display_stats, display_all_tags,
                             display_all_groups)


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
                    (parse(end) < parse(due))):
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
                db.SESSION.commit()
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
                db.SESSION.commit()
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
        db.SESSION.commit()
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
        db.SESSION.commit()
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
        db.SESSION.commit()
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
        db.SESSION.commit()
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
        db.SESSION.commit()
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
        db.SESSION.commit()
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
        db.SESSION.commit()
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
        db.SESSION.commit()
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
        db.SESSION.commit()
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
