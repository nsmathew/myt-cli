import os
import sys
import logging
from pathlib import Path
from os.path import getsize
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from src.mytcli.constants import (SUCCESS, FAILURE, DEFAULT_FOLDER, DEFAULT_DB_NAME,
                               DB_SCHEMA_VER, FMT_DATEONLY, LOGGER, CONSOLE)
from src.mytcli.models import Base, AppMetadata

# Global state
ENGINE = None
SESSION = None
Session = None


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
                # Lazy import to avoid circular dependency
                from src.mytcli.operations import create_recur_inst
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
