from datetime import datetime

from sqlalchemy import (Column, Integer, String, Index,
                        ForeignKeyConstraint, BOOLEAN, func)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.hybrid import hybrid_property

from src.mytcli.constants import FMT_DATEONLY, FMT_DATETIME


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
