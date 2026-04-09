import re
import uuid
from datetime import datetime

import click
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, func, cast, Numeric, tuple_, inspect
from sqlalchemy.orm import make_transient
from sqlalchemy.exc import SQLAlchemyError
from rich.prompt import Prompt

import src.mytcli.constants as constants
from src.mytcli.constants import (LOGGER, CONSOLE, SUCCESS, FAILURE,
                               TASK_OVERDUE, TASK_TODAY, TASK_HIDDEN,
                               TASK_BIN, TASK_COMPLETE, TASK_STARTED,
                               TASK_NOW, TASK_ALL, HL_FILTERS_ONLY,
                               CLR_STR, FUTDT,
                               WS_AREA_PENDING, WS_AREA_COMPLETED, WS_AREA_BIN,
                               TASK_TYPE_BASE, TASK_TYPE_DRVD, TASK_TYPE_NRML,
                               TASK_STATUS_TODO, TASK_STATUS_STARTED,
                               TASK_STATUS_DONE, TASK_STATUS_DELETED,
                               FMT_DATEONLY, FMT_DATETIME,
                               OPS_ADD, OPS_MODIFY, OPS_START, OPS_STOP,
                               OPS_REVERT, OPS_RESET, OPS_DELETE, OPS_NOW,
                               OPS_UNLINK, OPS_DONE,
                               UNTIL_WHEN, PRIORITY_NORMAL)
from src.mytcli.models import Workspace, WorkspaceTags, WorkspaceRecurDates
import src.mytcli.db as db
from src.mytcli.queries import get_tasks, get_tags, get_task_uuid_n_ver
from src.mytcli.utils import (open_url, confirm_prompt, get_event_id,
                           convert_date, convert_date_rel, convert_time_unit,
                           translate_priority, carryover_recur_dates,
                           generate_tags, derive_task_id, get_task_new_version,
                           reflect_object_n_print, calc_duration,
                           reset_now_flag, calc_next_inst_date,
                           parse_n_validate_recur, is_date_short_format)


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
    res = db.SESSION.query(func.max(Workspace.event_id)).all()
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
        (db.SESSION.query(WorkspaceRecurDates)
            .filter(tuple_(WorkspaceRecurDates.uuid,
                           WorkspaceRecurDates.version)
                            .in_(uuid_version_results))
            .delete(synchronize_session=False))

        (db.SESSION.query(WorkspaceTags)
            .filter(tuple_(WorkspaceTags.uuid, WorkspaceTags.version)
                            .in_(uuid_version_results))
            .delete(synchronize_session=False))
        (db.SESSION.query(Workspace)
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
        db.SESSION.add(task)
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
        if constants.TUI_MODE:
            if constants.TUI_PROMPT_CALLBACK:
                res = constants.TUI_PROMPT_CALLBACK(
                    "Choose the URL to open:",
                    [*choice_rng, "none"], "none"
                )
            else:
                CONSOLE.print("Multiple URLs found. Re-run with -ur <number> to open one.")
                res = "none"
            if res == "none":
                ret = SUCCESS
            else:
                url_ = re.findall(regex_2, url_list[int(res)-1])
                ret = open_url(url_[0])
        else:
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
            (db.SESSION.query(WorkspaceRecurDates)
             .filter(WorkspaceRecurDates.uuid.in_(uuid_list))
             .delete(synchronize_session=False))
            (db.SESSION.query(WorkspaceTags)
             .filter(WorkspaceTags.uuid.in_(uuid_list))
             .delete(synchronize_session=False))
            (db.SESSION.query(Workspace)
             .filter(Workspace.uuid.in_(uuid_list))
             .delete(synchronize_session=False))
        except SQLAlchemyError as e:
            LOGGER.error(str(e))
            return FAILURE
        db.SESSION.commit()
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
                prompt_msg = ("{}, {} - This is a recurring task, do you "
                              "want to modify 'all' pending instances or "
                              "just 'this' instance"
                              .format(ws_task.description, ws_task.due))
                if constants.TUI_MODE:
                    if constants.TUI_PROMPT_CALLBACK:
                        res = constants.TUI_PROMPT_CALLBACK(
                            prompt_msg, ["all", "this", "none"], "none"
                        )
                    else:
                        CONSOLE.print("{} → Defaulting to 'this' in TUI mode."
                                      .format(prompt_msg))
                        res = "this"
                else:
                    res = Prompt.ask(prompt_msg,
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
                max_ver_sqr = (db.SESSION.query(Workspace.uuid,
                                            func.max(Workspace.version)
                                                .label("maxver"))
                                    .filter(Workspace.task_type
                                                == TASK_TYPE_DRVD)
                                    .group_by(Workspace.uuid)
                                    .subquery())
                results = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
            max_ver_sqr = (db.SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                            .label("maxver"))
                                .filter(Workspace.task_type == TASK_TYPE_DRVD)
                                .group_by(Workspace.uuid)
                                .subquery())
            results = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
        uuid_ver = (db.SESSION.query(Workspace.uuid,
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
            prompt_msg = ("{}, {} - This is a recurring task, do you want"
                          " to modify 'all' pending instances or "
                          "just 'this' instance"
                          .format(ws_task.description, ws_task.due))
            if constants.TUI_MODE:
                if constants.TUI_PROMPT_CALLBACK:
                    res = constants.TUI_PROMPT_CALLBACK(
                        prompt_msg, ["all", "this", "none"], "none"
                    )
                else:
                    CONSOLE.print("{} → Defaulting to 'this' in TUI mode."
                                  .format(prompt_msg))
                    res = "this"
            else:
                res = Prompt.ask(prompt_msg,
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
                    no due date is provided then the original base task's
                    due date is used, keeping the recreation independent of
                    which derived instance the user happened to filter on.
                    """
                    LOGGER.debug("Change requested in due:{} or hide:{} or "
                                 "recur:{}".format(due_chg, hide_chg,
                                                   rec_chg))
                    # Validate: clearing due ('clr') on 'all' recurring
                    # instances leaves the base task without a due date,
                    # which prep_recurring_tasks cannot use to generate
                    # instances. Keep the message short so it fits in
                    # the TUI's single-line status toolbar.
                    if due_chg and ws_task_src.due == CLR_STR:
                        CONSOLE.print(
                            "Cannot clear due for 'all' recurring - "
                            "pick a new date or delete instead.",
                            style="default")
                        return SUCCESS, None
                    # Validate: for recurring tasks, modifying hide for 'all'
                    # only makes sense as a due-relative offset (-N) or clr,
                    # because each instance has its own due date and so the
                    # hide is semantically an offset, not an absolute date.
                    # Kept short for the TUI toolbar.
                    if hide_chg and ws_task_src.hide != CLR_STR:
                        if not (is_date_short_format(ws_task_src.hide)
                                and ws_task_src.hide.startswith("-")):
                            CONSOLE.print(
                                "Hide for 'all' recurring needs a "
                                "due-relative offset (e.g. -3) or 'clr'.",
                                style="default")
                            return SUCCESS, None
                    # Fetch the base task BEFORE deleting so we can seed the
                    # recreation from the base's stored due/hide rather than
                    # from whatever derived instance the user filtered by.
                    base_filter = {"baseuuidonly": base_uuid}
                    base_uv = get_task_uuid_n_ver(base_filter)
                    base_tasks = get_tasks(base_uv) if base_uv else []
                    if not base_tasks:
                        LOGGER.error("Could not retrieve base task for "
                                     "recurring recreation")
                        return FAILURE, None
                    ws_task_seed = base_tasks[0]
                    make_transient(ws_task_seed)
                    ws_task_seed.uuid = base_uuid
                    # Base task has id '*'; restore the filtered task's id so
                    # the recreated first instance can reuse it naturally.
                    ws_task_seed.id = ws_task.id
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
                    LOGGER.debug("Sending base task for RECREATION to "
                                 "modify_task - UUID: {}"
                                 .format(ws_task_seed.uuid))
                    ret, r_tsk_tg_prnt3 = modify_task(ws_task_src,
                                                      ws_task_seed,
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
                # When due is being changed on a single recurring instance
                # and the instance has a hide date that the user did not
                # touch, offer to shift the hide by the same delta. Default
                # is 'no' to keep the absolute-hide semantics consistent
                # with non-recurring tasks; the prompt just spares users
                # from having to recompute the new hide themselves.
                if (due_chg and not hide_chg
                        and ws_task_src.due != CLR_STR
                        and ws_task.hide is not None
                        and ws_task.due is not None):
                    shift_msg = ("Shift hide date by the same delta as the "
                                 "due change for this instance?")
                    if constants.TUI_MODE:
                        if constants.TUI_PROMPT_CALLBACK:
                            shift_res = constants.TUI_PROMPT_CALLBACK(
                                shift_msg, ["yes", "no"], "no"
                            )
                        else:
                            shift_res = "no"
                    else:
                        shift_res = Prompt.ask(shift_msg,
                                               choices=["yes", "no"],
                                               default="no")
                    if shift_res == "yes":
                        old_due_d = datetime.strptime(ws_task.due,
                                                      FMT_DATEONLY).date()
                        new_due_d = datetime.strptime(ws_task_src.due,
                                                      FMT_DATEONLY).date()
                        delta_days = (new_due_d - old_due_d).days
                        old_hide_d = datetime.strptime(ws_task.hide,
                                                       FMT_DATEONLY).date()
                        new_hide_d = (old_hide_d
                                      + relativedelta(days=delta_days))
                        ws_task_src.hide = new_hide_d.strftime(FMT_DATEONLY)
                        hide_chg = True
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
        # When recreating a recurring series with a due change but no
        # explicit hide change, preserve the original hide/due offset.
        # The base task stores hide as an absolute date, so naively
        # swapping due alone would leave prep_recurring_tasks computing
        # a meaningless (old_hide − new_due) offset for the rebuilt
        # series. Shift hide here so the offset stays intact.
        if (multi_change and due_chg and not hide_chg
                and ws_task.hide is not None
                and ws_task.due is not None):
            old_offset = (datetime.strptime(ws_task.hide, FMT_DATEONLY)
                          - datetime.strptime(ws_task.due,
                                              FMT_DATEONLY)).days
            new_due_date = datetime.strptime(ws_task_src.due,
                                             FMT_DATEONLY).date()
            ws_task.hide = ((new_due_date
                             + relativedelta(days=old_offset))
                            .strftime(FMT_DATEONLY))
        ws_task.due = ws_task_src.due

    if ws_task_src.hide == CLR_STR:
        ws_task.hide = None
    elif ws_task_src.hide is not None:
        # Resolve relative hide dates using the effective due date:
        # prefer the newly-set due (ws_task.due already updated above),
        # fall back to the task's existing due date.
        eff_due = parse(ws_task.due) if ws_task.due else None
        converted = convert_date_rel(ws_task_src.hide, eff_due)
        if converted is not None:
            ws_task.hide = converted

    if ws_task_src.groups == CLR_STR:
        ws_task.groups = None
    elif ws_task_src.groups is not None:
        ws_task.groups = ws_task_src.groups

    if ws_task_src.context == CLR_STR:
        ws_task.context = None
    elif ws_task_src.context is not None:
        ws_task.context = ws_task_src.context

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
        max_ver_sqr = (db.SESSION.query(Workspace.uuid,
                                     func.max(Workspace.version)
                                     .label("maxver"))
                       .filter(Workspace.task_type == TASK_TYPE_BASE)
                       .group_by(Workspace.uuid).subquery())
        results = (db.SESSION.query(func.max(WorkspaceRecurDates.due))
                   .join(max_ver_sqr, and_(WorkspaceRecurDates.version ==
                                           max_ver_sqr.c.maxver,
                                           WorkspaceRecurDates.uuid ==
                                           max_ver_sqr.c.uuid))
                   .filter(WorkspaceRecurDates.uuid ==
                           ws_task_base.uuid)
                   .all())

        max_ver_d_sqr = (db.SESSION.query(Workspace.uuid,
                                     func.max(Workspace.version)
                                        .label("maxver"))
                              .filter(Workspace.task_type == TASK_TYPE_DRVD)
                              .group_by(Workspace.uuid)
                              .subquery())
        #Check if there are any derived tasks in 'pending' area
        #If none then create atleast one.
        task_exists = (db.SESSION.query(Workspace.uuid)
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
        db.SESSION.expunge(ws_task_base)
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
        db.SESSION.expunge(ws_task_drvd)
        make_transient(ws_task_drvd)
        db.SESSION.expunge(ws_rec_dt)
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
    ws_task.context = ws_task_src.context
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
        db.SESSION.add(ws_task)
        if ws_rec_dt is not None:
            LOGGER.debug("Adding values for recur_dates to database:")
            LOGGER.debug("\n" + reflect_object_n_print(ws_rec_dt,
                                                       to_print=False,
                                                       print_all=True))
            db.SESSION.add(ws_rec_dt)
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
                db.SESSION.add(ws_tags)
                tags_str = tags_str + "," + t.tags
        # For all older entries remove the task_id
        (db.SESSION.query(Workspace).filter(Workspace.uuid == ws_task.uuid,
                                         Workspace.version <
                                         ws_task.version)
         .update({Workspace.id: "-"},
                 synchronize_session=False))
    except SQLAlchemyError as e:
        db.SESSION.rollback()
        LOGGER.error(str(e))
        return FAILURE, None, None
    return SUCCESS, ws_task, tags_str
