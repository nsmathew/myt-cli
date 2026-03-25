from datetime import datetime

from sqlalchemy import (and_, or_, case, func, tuple_, distinct,
                        cast, Numeric)
from sqlalchemy.exc import SQLAlchemyError

from src.mytcli.constants import (LOGGER, CONSOLE, SUCCESS, FAILURE,
                               TASK_OVERDUE, TASK_TODAY, TASK_HIDDEN,
                               TASK_BIN, TASK_COMPLETE, TASK_STARTED,
                               TASK_NOW, TASK_ALL, HL_FILTERS_ONLY, FUTDT,
                               WS_AREA_PENDING, WS_AREA_COMPLETED, WS_AREA_BIN,
                               TASK_TYPE_BASE, TASK_TYPE_DRVD, TASK_TYPE_NRML,
                               TASK_STATUS_TODO, TASK_STATUS_STARTED,
                               TASK_STATUS_DONE, TASK_STATUS_DELETED,
                               FMT_DATEONLY, PRIORITY_HIGH, PRIORITY_MEDIUM,
                               PRIORITY_LOW, PRIORITY_NORMAL)
from src.mytcli.models import Workspace, WorkspaceTags, WorkspaceRecurDates
import src.mytcli.db as db


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
        ws_task_list = (db.SESSION.query(Workspace)
                        .filter(tuple_(Workspace.uuid, Workspace.version)
                                .in_(uuid_version))
                        .order_by(Workspace.task_type)
                        .all())
        if expunge:
            db.SESSION.expunge_all()
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
        ws_tags_list = (db.SESSION.query(WorkspaceTags)
                        .filter(and_(WorkspaceTags.uuid == task_uuid,
                                     WorkspaceTags.version == task_version))
                        .all())
        if expunge:
            db.SESSION.expunge_all()
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
    context = potential_filters.get("context")
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
    max_ver_sqr = (db.SESSION.query(Workspace.uuid,
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
        innrqr_all = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
        innrqr_idn = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
        innrqr_now = (db.SESSION.query(Workspace.uuid, Workspace.version)
                    .filter(and_(Workspace.area == WS_AREA_PENDING,
                                Workspace.now_flag == True,
                                Workspace.id != '-',
                                Workspace.task_type
                                .in_([TASK_TYPE_DRVD,
                                        TASK_TYPE_NRML]))))
        innrqr_list.append(innrqr_now)
    elif osrecur is not None:
        LOGGER.debug("Inside Outstanding Recurring Tasks filter")
        max_ver_sqr1 = (db.SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                        .label("maxver"))
                        .filter(Workspace.task_type == TASK_TYPE_BASE)
                        .group_by(Workspace.uuid).subquery())
        innrqr_osrecr = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
        innrqr_uuid = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
        max_ver_sqr1 = (db.SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                        .label("maxver"))
                        .filter(Workspace.task_type.in_([TASK_TYPE_DRVD]))
                        .group_by(Workspace.uuid).subquery())
        innrqr_buuid = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
        max_ver_sqr1 = (db.SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                        .label("maxver"))
                        .filter(Workspace.task_type == TASK_TYPE_BASE)
                        .group_by(Workspace.uuid).subquery())
        innrqr_buuido = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
        innrqr_eventid = (db.SESSION.query(Workspace.uuid, Workspace.version)
                            .filter(Workspace.event_id == eventid))
        innrqr_list.append(innrqr_eventid)
    elif missingid is not None:
        LOGGER.debug("Inside Missing ID filter with below params")
        LOGGER.debug(baseuuidonly)
        max_ver_sqr1 = (db.SESSION.query(Workspace.uuid,
                                        func.max(Workspace.version)
                                        .label("maxver"))
                        .group_by(Workspace.uuid).subquery())
        innrqr_missid = (db.SESSION.query(Workspace.uuid, Workspace.version)
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
            innrqr_groups = (db.SESSION.query(Workspace.uuid,
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
        if context is not None:
            LOGGER.debug("Inside context filter with below params")
            LOGGER.debug("%" + context + "%")
            innrqr_context = (db.SESSION.query(Workspace.uuid,
                                               Workspace.version)
                                .join(max_ver_sqr,
                                    and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                                .filter(and_(Workspace.context
                                                    .like("%"+context+"%"),
                                            Workspace.area == drvd_area)))
            innrqr_list.append(innrqr_context)
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
                innrqr_tags = (db.SESSION.query(WorkspaceTags.uuid,
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
                innrqr_tags = (db.SESSION.query(WorkspaceTags.uuid,
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
            innrqr_notes = (db.SESSION.query(Workspace.uuid,
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
            innrqr_desc = (db.SESSION.query(Workspace.uuid,
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
                innrqr_due = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due == due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "gt":
                innrqr_due = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due > due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "ge":
                innrqr_due = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due >= due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "lt":
                innrqr_due = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due < due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "le":
                innrqr_due = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.due <= due_list[1],
                                            Workspace.area == drvd_area)))
            elif due_list[0] == "bt":
                innrqr_due = (db.SESSION.query(Workspace.uuid,
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
                innrqr_due = (db.SESSION.query(Workspace.uuid,
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
                innrqr_hide = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide == hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "gt":
                innrqr_hide = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide > hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "ge":
                innrqr_hide = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide >= hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "lt":
                innrqr_hide = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide < hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "le":
                innrqr_hide = (db.SESSION.query(Workspace.uuid,
                                        Workspace.version)
                            .join(max_ver_sqr,
                                and_(Workspace.version ==
                                        max_ver_sqr.c.maxver,
                                        Workspace.uuid ==
                                        max_ver_sqr.c.uuid))
                            .filter(and_(Workspace.hide <= hide_list[1],
                                            Workspace.area == drvd_area)))
            elif hide_list[0] == "bt":
                innrqr_hide = (db.SESSION.query(Workspace.uuid,
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
                innrqr_hide = (db.SESSION.query(Workspace.uuid,
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
                innrqr_end = (db.SESSION.query(Workspace.uuid,
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
                innrqr_end = (db.SESSION.query(Workspace.uuid,
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
                innrqr_end = (db.SESSION.query(Workspace.uuid,
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
                innrqr_end = (db.SESSION.query(Workspace.uuid,
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
                innrqr_end = (db.SESSION.query(Workspace.uuid,
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
                innrqr_end = (db.SESSION.query(Workspace.uuid,
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
                innrqr_end = (db.SESSION.query(Workspace.uuid,
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
            innrqr_overdue = (db.SESSION.query(Workspace.uuid,
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
            innrqr_today = (db.SESSION.query(Workspace.uuid,
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
            innrqr_hidden = (db.SESSION.query(Workspace.uuid,
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
            innrqr_started = (db.SESSION.query(Workspace.uuid,
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
                innrqr_all = (db.SESSION.query(Workspace.uuid, Workspace.version)
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


def get_all_groups():
    """Returns list of distinct non-null group names from pending area."""
    try:
        max_ver_sqr = (db.SESSION.query(
            Workspace.uuid,
            func.max(Workspace.version).label("maxver"))
            .group_by(Workspace.uuid)
            .subquery())
        results = (db.SESSION.query(distinct(Workspace.groups))
                   .join(max_ver_sqr,
                         and_(Workspace.version == max_ver_sqr.c.maxver,
                              Workspace.uuid == max_ver_sqr.c.uuid))
                   .filter(and_(Workspace.area == WS_AREA_PENDING,
                                Workspace.groups.isnot(None)))
                   .all())
        return [r[0] for r in results if r[0]]
    except SQLAlchemyError:
        return []


def get_all_contexts():
    """Returns list of distinct non-null context names from pending area."""
    try:
        max_ver_sqr = (db.SESSION.query(
            Workspace.uuid,
            func.max(Workspace.version).label("maxver"))
            .group_by(Workspace.uuid)
            .subquery())
        results = (db.SESSION.query(distinct(Workspace.context))
                   .join(max_ver_sqr,
                         and_(Workspace.version == max_ver_sqr.c.maxver,
                              Workspace.uuid == max_ver_sqr.c.uuid))
                   .filter(and_(Workspace.area == WS_AREA_PENDING,
                                Workspace.context.isnot(None)))
                   .all())
        return [r[0] for r in results if r[0]]
    except SQLAlchemyError:
        return []


def get_all_tags():
    """Returns list of distinct tag names from pending area."""
    try:
        max_ver_sqr = (db.SESSION.query(
            Workspace.uuid,
            func.max(Workspace.version).label("maxver"))
            .group_by(Workspace.uuid)
            .subquery())
        results = (db.SESSION.query(distinct(WorkspaceTags.tags))
                   .join(Workspace, and_(
                       WorkspaceTags.uuid == Workspace.uuid,
                       WorkspaceTags.version == Workspace.version))
                   .join(max_ver_sqr,
                         and_(Workspace.version == max_ver_sqr.c.maxver,
                              Workspace.uuid == max_ver_sqr.c.uuid))
                   .filter(Workspace.area == WS_AREA_PENDING)
                   .all())
        return [r[0] for r in results if r[0]]
    except SQLAlchemyError:
        return []


def get_all_ids():
    """Returns list of current task IDs from pending area."""
    try:
        max_ver_sqr = (db.SESSION.query(
            Workspace.uuid,
            func.max(Workspace.version).label("maxver"))
            .group_by(Workspace.uuid)
            .subquery())
        results = (db.SESSION.query(Workspace.id)
                   .join(max_ver_sqr,
                         and_(Workspace.version == max_ver_sqr.c.maxver,
                              Workspace.uuid == max_ver_sqr.c.uuid))
                   .filter(and_(Workspace.area == WS_AREA_PENDING,
                                Workspace.id.isnot(None)))
                   .order_by(cast(Workspace.id, Numeric))
                   .all())
        return [str(r[0]) for r in results if r[0]]
    except SQLAlchemyError:
        return []
