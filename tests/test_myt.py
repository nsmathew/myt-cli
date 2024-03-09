import datetime
import tempfile
import pytest
from click.testing import CliRunner
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import mock
import logging

from src.mytcli.myt import add
from src.mytcli.myt import modify
from src.mytcli.myt import delete
from src.mytcli.myt import start
from src.mytcli.myt import stop
from src.mytcli.myt import revert
from src.mytcli.myt import reset
from src.mytcli.myt import done
from src.mytcli.myt import admin
from src.mytcli.myt import view
from src.mytcli.myt import now
from src.mytcli.myt import urlopen
from src.mytcli.myt import stats

runner = CliRunner()
# Use db in a temp location
@pytest.fixture(scope='session')
def set_full_db_path():
    return tempfile.mkdtemp() + "/tasksdb.sqlite3"

       
# Reinit the db when running the full suite of tests
def test_reinit(set_full_db_path):
    print(set_full_db_path)
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(admin, ['--reinit', '-db', set_full_db_path])
        assert "Database removed..." in result.output
        assert "Tasks database initialized..." in result.output

def test_add_1(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task1','-gr','ABC.XYZ','-tg',
                           'qwerty,asdfgh,zxcvb', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task1" in result.output
    assert "groups : ABC.XYZ" in result.output
    assert "tags : qwerty,asdfgh,zxcvb" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_2(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task2','-du','2020-12-25', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task2" in result.output
    assert "due : 2020-12-25" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_3(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task3','-du','2020-12-25','-hi',
                           '2020-12-21', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task3" in result.output
    assert "due : 2020-12-25" in result.output
    assert "hide : 2020-12-21" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_4(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task4','-du','2020-12-25','-hi',
                           '-4', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task4" in result.output
    assert "due : 2020-12-25" in result.output
    assert "hide : 2020-12-21" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_5_1(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','h', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : H" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_5_2(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','H', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : H" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_5_3(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','m', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : M" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])
    
def test_add_5_4(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','M', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : M" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_5_5(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','l', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : L" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_5_6(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','l', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : L" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_5_7(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : N" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_5_8(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5_8', '-tg', 
                                 ',abc,ghj,abc,', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "tags : abc,ghj" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_add_re_1(set_full_db_path):
    #With no due date
    result = runner.invoke(add, ['-de', 'Test task re 1', '-re', 'D', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Need a due date for recurring tasks" in result.output

def test_add_re_2(set_full_db_path):
    #Witjhout end date
    duedt = (date.today() + relativedelta(days=-1)).strftime("%Y-%m-%d")
    nextdt = (date.today()).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'D',
                                 '-tg', 're2,bnh', '-gr', 'ABC.ONH', '-du',
                                 duedt, '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + 
            " until None for recurrence type D-None") in result.output
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "tags : re2,bnh" in result.output
    assert "task_type : DERIVED" in result.output
    assert "groups : ABC.ONH" in result.output
    assert "recur_mode : D" in result.output
    assert "recur_when : ..." in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re2', '-db', set_full_db_path])

def test_add_re_3(set_full_db_path):
    #With End date
    duedt = (date.today() + relativedelta(days=-1)).strftime("%Y-%m-%d")
    nextdt = (date.today()).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'D',
                                 '-tg', 're3,bnh', '-gr', 'ABC.ONH', '-du',
                                 duedt, '-en', enddt, '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type D-None") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "tags : re3,bnh" in result.output
    assert "task_type : DERIVED" in result.output
    assert "groups : ABC.ONH" in result.output
    assert "recur_mode : D" in result.output
    assert "recur_when : ..." in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re3', '-db', set_full_db_path])

def test_add_re_4(set_full_db_path):
    #Weekly
    duedt = (date.today()).strftime("%Y-%m-%d")
    nextdt = (date.today() + relativedelta(days=+7)).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'W','-du',
                                 duedt, '-en', enddt, '-tg', 're4', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type W-None") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : W" in result.output
    assert "recur_when : ..." in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re4', '-db', set_full_db_path])

def test_add_re_5(set_full_db_path):
    #Monthly
    duedt = (date.today()).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(duedt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'M','-du',
                                 duedt, '-en', enddt, '-tg', 're5', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type M-None") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "recur_mode : M" in result.output
    assert "recur_when : ..." in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re5', '-db', set_full_db_path])

def test_add_re_6(set_full_db_path):
    #Yearly
    duedt = (date.today()).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(duedt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'Y','-du',
                                 duedt, '-en', enddt, '-tg', 're6', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type Y-None") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "recur_mode : Y" in result.output
    assert "recur_when : ..." in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re6', '-db', set_full_db_path])

def test_add_re_7(set_full_db_path):
    #Every 3 days
    duedt = (date.today() + relativedelta(days=-4)).strftime("%Y-%m-%d")
    nextdt = (datetime.strptime(duedt,"%Y-%m-%d") 
                + relativedelta(days=3)).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'DE3','-du',
                                 duedt, '-en', enddt, '-tg', 're7', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type D-E3") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : D" in result.output
    assert "recur_when : E3" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re7', '-db', set_full_db_path])


def test_add_re_8(set_full_db_path):
    #Every 2 weeks
    duedt = (date.today() + relativedelta(days=-30)).strftime("%Y-%m-%d")
    nextdt = (datetime.strptime(duedt,"%Y-%m-%d") 
                + relativedelta(days=14)).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'WE2','-du',
                                 duedt, '-en', enddt, '-tg', 're8', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type W-E2") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : W" in result.output
    assert "recur_when : E2" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re8', '-db', set_full_db_path])

def test_add_re_9(set_full_db_path):
    #Every 2 months
    duedt = "2020-12-04"
    nextdt = "2021-02-04"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'ME2','-du',
                                 duedt, '-en', enddt, '-tg', 're9', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type M-E2") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : M" in result.output
    assert "recur_when : E2" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re9', '-db', set_full_db_path])

def test_add_re_10(set_full_db_path):
    #Every 2 years
    duedt = "2019-12-03"
    nextdt = "2021-12-03"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'YE2','-du',
                                 duedt, '-en', enddt, '-tg', 're10', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type Y-E2") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : Y" in result.output
    assert "recur_when : E2" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re10', '-db', set_full_db_path])

def test_add_re_11(set_full_db_path):
    #Every Monday and Wednesday
    duedt = "2021-01-04"
    nextdt = "2021-01-06"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'WD1,3','-du',
                                 duedt, '-en', enddt, '-tg', 're11', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type WD-1,3") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : WD" in result.output
    assert "recur_when : 1,3" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re11', '-db', set_full_db_path])

def test_add_re_12(set_full_db_path):
    #Every 3rd and 5th of month
    duedt = "2021-01-03"
    nextdt = "2021-01-05"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'MD3,5','-du',
                                 duedt, '-en', enddt, '-tg', 're12', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type MD-3,5") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : MD" in result.output
    assert "recur_when : 3,5" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re12', '-db', set_full_db_path])

def test_add_re_13(set_full_db_path):
    #Every October and December
    duedt = "2020-10-28"
    nextdt = "2020-12-28"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'MO10,12',
                                 '-du', duedt, '-en', enddt, '-tg', 're13', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type MO-10,12") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : MO" in result.output
    assert "recur_when : 10,12" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re13', '-db', set_full_db_path])


@pytest.fixture
def create_task(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25', '-gr',
                           'GRPL1.GRPL2', '-tg', 'tag1,tag2,tag3', '-pr','H', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

def test_modify_1(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-de',
                           'Test task5.1', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task5.1" in result.output
    assert "due : 2020-12-25" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])


def test_modify_2(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','-2', '-db', set_full_db_path])
    exp_dt = date.today() + relativedelta(days=-2)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "due : "+exp_dt.strftime("%Y-%m-%d") in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_3(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','-2', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "hide : 2020-12-23" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_4(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','+4', '-db', set_full_db_path])
    #-2 for change in due date in test_modify_2 and -2 for this test
    exp_dt = date.today() + relativedelta(days=+4)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "hide : "+exp_dt.strftime("%Y-%m-%d") in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_5(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','2020-12-20', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "due : 2020-12-20" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_6(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','2020-12-15', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "hide : 2020-12-15" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_7(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','clr', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "hide : ..." in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_8(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','clr','-gr',
                           'GRPL1.GRPL2_1', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "due : ..." in result.output
    assert "groups : GRPL1.GRPL2_1" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_9(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-gr','clr','-tg',
                           '-tag1,-tag6,tag8,tag9', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "groups : ..." in result.output
    assert "tags : tag2,tag3,tag8,tag9" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_10(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-tg','clr', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "tags : ..." in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_11_1(create_task,set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-pr','L', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : L" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_11_2(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-pr','m', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : M" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_11_3(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-pr','clr', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : N" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_11_3(create_taskm, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),'-pr','xyz', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : N" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_11_3(create_task, set_full_db_path):
    result = runner.invoke(modify, ['id:'+str(create_task),
                                    '-tg',',-tag1,-tag1,tag4,xyz,tag4,', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "tags : tag2,tag3,tag4,xyz" in result.output
    runner.invoke(delete, ['id:'+str(create_task), '-db', set_full_db_path])

def test_modify_12_1(set_full_db_path):
    result = runner.invoke(modify, ['complete', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Modify can be run only on 'pending' tasks." in result.output

def test_modify_12_2(set_full_db_path):
    result = runner.invoke(modify, ['bin', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Modify can be run only on 'pending' tasks." in result.output

@pytest.fixture
def create_task2(set_full_db_path):
    result = runner.invoke(add, ['-de','Test task8','-du','2020-12-25', '-gr',
                           'GRPL1.GRPL2', '-tg', 'tag1,tag2,tag3', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

def test_start_1(create_task2, set_full_db_path):
    result = runner.invoke(start, ['id:'+str(create_task2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : STARTED" in result.output
    runner.invoke(delete, ['id:'+str(create_task2), '-db', set_full_db_path])

def test_start_2_1(set_full_db_path):
    result = runner.invoke(start, ['complete', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Start can be run only on 'pending' tasks." in result.output

def test_start_2_2(set_full_db_path):
    result = runner.invoke(start, ['bin', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Start can be run only on 'pending' tasks." in result.output 

def test_stop_1(create_task2, set_full_db_path):
    result = runner.invoke(start, ['id:'+str(create_task2), '-db', set_full_db_path])
    result = runner.invoke(stop, ['id:'+str(create_task2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(create_task2), '-db', set_full_db_path])

def test_stop_2_1(set_full_db_path):
    result = runner.invoke(stop, ['complete', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Stop can be run only on 'pending' tasks." in result.output

def test_stop_2_2(set_full_db_path):
    result = runner.invoke(stop, ['bin', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Stop can be run only on 'pending' tasks." in result.output 

def test_reset_1(create_task2, set_full_db_path):
    result = runner.invoke(start, ['id:'+str(create_task2), '-db', set_full_db_path])
    result = runner.invoke(reset, ['id:'+str(create_task2), '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    new_id = temp.split(" ")[3]
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(new_id), '-db', set_full_db_path])

def test_reset_2_1(set_full_db_path):
    result = runner.invoke(reset, ['complete', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Reset can be run only on 'pending' tasks." in result.output

def test_reset_2_2(set_full_db_path):
    result = runner.invoke(reset, ['bin', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Reset can be run only on 'pending' tasks." in result.output 

def test_revert_1(create_task2, set_full_db_path):
    result = runner.invoke(start, ['id:'+str(create_task2), '-db', set_full_db_path])
    result = runner.invoke(done, ['id:'+str(create_task2), '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    uuid = temp.split(" ")[3]
    result = runner.invoke(revert, ['COMPLETE','uuid:'+str(uuid), '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    new_id = temp.split(" ")[3]
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(new_id), '-db', set_full_db_path])

def test_revert_2_1(set_full_db_path):
    result = runner.invoke(revert, ['bin', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert ("Revert is applicable only to completed tasks. Use 'complete' "
           "filter in command") in result.output    

def test_done_1(create_task2, set_full_db_path):
    result = runner.invoke(done, ['id:'+str(create_task2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Updated Task UUID:" in result.output
    assert "status : DONE" in result.output
    runner.invoke(delete, ['complete','tg:'+'tag1', '-db', set_full_db_path])

def test_done_2_1(set_full_db_path):
    result = runner.invoke(done, ['complete', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Done can be run only on 'pending' tasks." in result.output

def test_done_2_2(set_full_db_path):
    result = runner.invoke(done, ['bin', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Done can be run only on 'pending' tasks." in result.output 

def test_delete_1(create_task2, set_full_db_path):
    runner.invoke(done, ['id:'+str(create_task2), '-db', set_full_db_path])
    result = runner.invoke(delete, ['id:99999', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "No applicable tasks to delete" in result.output
    runner.invoke(delete, ['complete','tg:'+'tag1', '-db', set_full_db_path])

def test_delete_2(create_task2, set_full_db_path):
    runner.invoke(done, ['id:'+str(create_task2), '-db', set_full_db_path])
    result = runner.invoke(delete, ['complete', 'tg:'+'tag1', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Updated Task UUID:" in result.output

def test_delete_3(set_full_db_path):
    result = runner.invoke(delete, ['bin', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Delete cannot be run on deleted tasks." in result.output 

def test_now_1(create_task2, set_full_db_path):
    #Now as True
    with mock.patch('builtins.input', return_value="no"):
        result = runner.invoke(now, ['id:'+str(create_task2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    runner.invoke(delete, ['tg:'+'tag1', '-db', set_full_db_path])

def test_now_2(create_task2, set_full_db_path):
    #Now as False
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(now, ['id:'+str(create_task2), '-db', set_full_db_path])
    result = runner.invoke(now, ['id:'+str(create_task2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "now_flag : ..." in result.output
    runner.invoke(delete, ['tg:'+'tag1', '-db', set_full_db_path])

def test_now_3(create_task2, set_full_db_path):
    #Set another task as Now when a task is already set as Now
    with mock.patch('builtins.input', return_value="no"):
        runner.invoke(now, ['id:'+str(create_task2), '-db', set_full_db_path])
    result = runner.invoke(add, ['-de','Test task8','-du','2020-12-25', '-gr',
                           'GRPL1.GRPL2', '-tg', 'tag1,tag2,tag3', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="no"):
        result = runner.invoke(now, ['id:'+str(idn), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    assert "now_flag : ..." in result.output
    runner.invoke(delete, ['tg:'+'tag1', '-db', set_full_db_path])

def test_now_4(create_task2, set_full_db_path):
    #set as now and start task
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(now, ['id:'+str(create_task2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    assert "status : STARTED" in result.output
    runner.invoke(delete, ['id:'+str(create_task2), '-db', set_full_db_path])

def test_now_5(create_task2, set_full_db_path):
    #set as now and do not start task
    with mock.patch('builtins.input', return_value="no"):
        result = runner.invoke(now, ['id:'+str(create_task2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(create_task2), '-db', set_full_db_path])

def test_now_6(create_task2, set_full_db_path):
    #Set as now and for started task it should remain started
    runner.invoke(start, ['id:'+str(create_task2), '-db', set_full_db_path])
    result = runner.invoke(now, ['id:'+str(create_task2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    assert "status : STARTED" in result.output
    runner.invoke(delete, ['id:'+str(create_task2), '-db', set_full_db_path])

def test_now_7_1(set_full_db_path):
    result = runner.invoke(now, ['complete', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Now can be run only on 'pending' tasks." in result.output

def test_now_7_2(set_full_db_path):
    result = runner.invoke(now, ['bin', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Now can be run only on 'pending' tasks." in result.output 

@pytest.fixture
def create_task3(set_full_db_path):
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(delete,  ['-db', set_full_db_path])
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(delete, ['hidden', '-db', set_full_db_path])        
    duedt = (date.today() + relativedelta(days=+5)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task9','-du',duedt, '-gr',
                                 'GRPL1AB.GRPL2CD', '-tg', 
                                 'view1,view2,view3,view4', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

def test_view1(create_task3, set_full_db_path):
    duedt = date.today().strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view1', '-du', duedt, '-db', set_full_db_path])
    result = runner.invoke(view, ['TODAY', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 0" in result.output
    runner.invoke(delete, ['tg:view1', '-db', set_full_db_path])

def test_view2(create_task3, set_full_db_path):
    duedt = (date.today() + relativedelta(days=-4)).strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view2','-du', duedt, '-db', set_full_db_path])
    result = runner.invoke(view, ['overdue', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 0" in result.output
    runner.invoke(delete, ['tg:view2', '-db', set_full_db_path])

def test_view3(create_task3, set_full_db_path): 
    duedt = (date.today() + relativedelta(days=+10)).strftime("%Y-%m-%d")
    hidedt = (date.today() + relativedelta(days=+8)).strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view3','-du', 
                        duedt, '-hi', hidedt, '-db', set_full_db_path])
    result = runner.invoke(view, ['hidden', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 1" in result.output
    runner.invoke(delete, ['tg:view3', '-db', set_full_db_path])

def test_view4(create_task3, set_full_db_path):
    duedt = (date.today() + relativedelta(days=+10)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view4','-du', 
                        duedt, '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(start, ['id:' + idn, '-db', set_full_db_path])
    result = runner.invoke(view, ['started', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 0" in result.output
    runner.invoke(delete, ['tg:view4', '-db', set_full_db_path])                     

def test_admin_empty_1(set_full_db_path):
    result = runner.invoke(add, ['-de', 'Test task 10.1', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(delete, ['id:' + idn, '-db', set_full_db_path])
    result = runner.invoke(add, ['-de', 'Test task 10.2', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(delete, ['id:' + idn, '-db', set_full_db_path])
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(admin, ['--empty', '-db', set_full_db_path])
        assert "Bin emptied!" in result.output

def test_admin_reinit_1(set_full_db_path):
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(admin, ['--reinit', '-db', set_full_db_path])
        assert "Database removed..." in result.output
        assert "Tasks database initialized..." in result.output

def test_admin_tags_1(set_full_db_path):
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit', '-db', set_full_db_path])    
    result = runner.invoke(admin, ['--tags', '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "No tags added to tasks." in result.output

def test_admin_tags_2(set_full_db_path):
    runner.invoke(add, ['-de', 'Test task 11.1', '-tg', 'abc,xyz', '-db', set_full_db_path])
    runner.invoke(add, ['-de', 'Test task 11.2', '-tg', 'tgh', '-db', set_full_db_path])
    result = runner.invoke(admin, ['--tags', '-db', set_full_db_path])
    assert "Total number of tags: 3" in result.output
    runner.invoke(delete, ['tg:abc,xyz,tgh', '-db', set_full_db_path])

def test_admin_groups_1(set_full_db_path):
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit', '-db', set_full_db_path])
    result = runner.invoke(add, ['-de', 'Test task 9.1', '-gr', 'PERS.ABC', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(delete, ['id:' + idn, '-db', set_full_db_path])
    result = runner.invoke(admin, ['--groups', '-db', set_full_db_path])
    assert "No groups added to tasks." in result.output

def test_admin_groups_2(set_full_db_path):
    runner.invoke(add, ['-de', 'Test task 12.1', '-gr', 'PERS.AA1', '-db', set_full_db_path])
    runner.invoke(add, ['-de', 'Test task 12.2', '-gr', 'PERS.AA1.AA2', '-db', set_full_db_path])
    runner.invoke(add, ['-de', 'Test task 12.3', '-gr', 'OTH.AA3', '-db', set_full_db_path])
    result = runner.invoke(admin, ['--groups', '-db', set_full_db_path])
    assert "Total number of groups: 5" in result.output
    runner.invoke(delete, ['gr:OTH', '-db', set_full_db_path])
    runner.invoke(delete, ['gr:PERS', '-db', set_full_db_path])

def test_urlopen_1(set_full_db_path):
    result = runner.invoke(add, ['-de', 'Test task 13.1', '-du', '+0', '-no',
                            'Test https://abc.com [ABC] https://xy.com [ XY]', 
                            '-tg', 'tag13', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(modify, ['id:' + idn, '-no', 'http://bb.com bb', '-db', set_full_db_path])
    runner.invoke(modify, ['id:' + idn, '-no', 'http://cc.com [cc]', '-db', set_full_db_path])
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "1 - https://abc.com [ABC]" in result.output
    assert "2 - https://xy.com [ XY]" in result.output
    assert "3 - http://bb.com" in result.output
    assert "4 - http://cc.com [cc]" in result.output
    runner.invoke(delete, ['id:' + idn, '-db', set_full_db_path])

def test_urlopen_2(set_full_db_path):
    result = runner.invoke(add, ['-de', 'Test task 13.2', '-du', '+0', '-no',
                            'Test https://abc.com [ABC] https://xy.com [ XY]', 
                            '-tg', 'tag13', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-ur', str(4), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "No URL found at the position provided" in result.output
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-ur', str(-2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "No URL found at the position provided" in result.output
    runner.invoke(delete, ['id:' + idn, '-db', set_full_db_path])

def test_urlopen_3(set_full_db_path):
    result = runner.invoke(add, ['-de', 'Test task 13.3', '-du', '+0', '-no',
                            'Test Notes', '-tg', 'tag13', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-ur', str(4), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "No URLS found in notes for this task" in result.output
    runner.invoke(delete, ['id:' + idn, '-db', set_full_db_path])

def test_urlopen_4(set_full_db_path):
    result = runner.invoke(add, ['-de', 'Test task 13.3', '-du', '+0', '-no',
                            'Test Notes', '-tg', 'tag13', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "No URLS found in notes for this task" in result.output
    runner.invoke(delete, ['id:' + idn, '-db', set_full_db_path])

# Test if the prompt is shown when a url num is provided
def test_urlopen_5(set_full_db_path):
    result = runner.invoke(add, ['-de', 'Test task 13.1', '-du', '+0', '-no',
                            'Test https://abc.com [ABC] https://xy.com [ XY]', 
                            '-tg', 'tag13', '-db', set_full_db_path])
    result = runner.invoke(add, ['-de', 'Test task 13.2', '-du', '+0', '-no',
                            'Test https://abc.com [ABC] https://xy.com [ XY]', 
                            '-tg', 'tag13', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="no"):
        result = runner.invoke(urlopen, ['id:' + idn, '-ur', str(2), '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "Would you like to open https://xy.com [ XY]" in result.output
    runner.invoke(delete, ['tg:tag13', '-db', set_full_db_path])

# Test if the prompt is shown when there is only 1 URL
def test_urlopen_6(set_full_db_path):
    result = runner.invoke(add, ['-de', 'Test task 13.1', '-du', '+0', '-no',
                            'Test https://abc.com [ABC]', 
                            '-tg', 'tag13', '-db', set_full_db_path])
    result = runner.invoke(add, ['-de', 'Test task 13.2', '-du', '+0', '-no',
                            'Test https://abc.com [ABC]', 
                            '-tg', 'tag13', '-db', set_full_db_path])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-db', set_full_db_path])
    assert result.exit_code == 0
    assert "1 - https://abc.com [ABC]" in result.output
    assert "Choose the URL to be openned" in result.output
    runner.invoke(delete, ['tg:tag13', '-db', set_full_db_path])    
        
# Tests stats view 2
def test_stats(set_full_db_path, caplog):
    caplog.set_level(logging.DEBUG)
    # Reinit the db to get accurate results
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit', '-db', set_full_db_path])    
    # TODO Tasks
    duedt = (date.today()).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task','-du', duedt,  '-gr', 'STATS', '-db',set_full_db_path])
    result = runner.invoke(add, ['-de','Test task','-du', duedt, '-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])
    
    duedt = (date.today() + relativedelta(days=-4)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task','-du', duedt,  '-gr', 'STATS', '-db', set_full_db_path])
    result = runner.invoke(add, ['-de','Test task','-du', duedt, '-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])
    
    duedt = (date.today() + relativedelta(days=+4)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task','-du', duedt,  '-gr', 'STATS', '-db', set_full_db_path])
    result = runner.invoke(add, ['-de','Test task','-du', duedt, '-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])    
    
    result = runner.invoke(add, ['-de','Test task',  '-gr', 'STATS', '-db', set_full_db_path])
    result = runner.invoke(add, ['-de','Test task','-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])   
    
    # Started tasks 
    duedt = (date.today()).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task','-du', duedt,  '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])    
    
    result = runner.invoke(add, ['-de','Test task','-du', duedt, '-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])    
    
    
    duedt = (date.today() + relativedelta(days=-4)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task','-du', duedt,  '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])        
    
    result = runner.invoke(add, ['-de','Test task','-du', duedt, '-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])        
    
    
    duedt = (date.today() + relativedelta(days=+4)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task','-du', duedt,  '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])        
    
    result = runner.invoke(add, ['-de','Test task','-du', duedt, '-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])    
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])    
    
    result = runner.invoke(add, ['-de','Test task',  '-gr', 'STATS', '-db', set_full_db_path])   
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])         
    
    result = runner.invoke(add, ['-de','Test task','-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])      
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])     
    
    result = runner.invoke(stats, ['--verbose', '-db', set_full_db_path])   
    assert result.exit_code == 0
    assert "[4, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 16, 4, 4, 4, 4]" in caplog.text

    runner.invoke(delete, ['gr:STATS', '-db', set_full_db_path])
    
# Tests stats view 1
def test_stats2(set_full_db_path, caplog):
    caplog.set_level(logging.DEBUG)
    # Reinit the db to get accurate results
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit', '-db', set_full_db_path])       
    # TODO Tasks
    duedt = (date.today()).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task1','-du', duedt,  '-gr', 'STATS', '-db',set_full_db_path])
    result = runner.invoke(add, ['-de','Test task2','-du', duedt, '-hi', +10,  '-gr', 'STATS', '-db', set_full_db_path])
    # STARTED Task
    result = runner.invoke(add, ['-de','Test task3','-du', duedt, '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(start, ['id:'+str(id), '-db', set_full_db_path])     
    # DONE Task
    result = runner.invoke(add, ['-de','Test task4','-du', duedt, '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(done, ['id:'+str(id), '-db', set_full_db_path])     
    # DELETED Task
    result = runner.invoke(add, ['-de','Test task5','-du', duedt, '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(delete, ['id:'+str(id), '-db', set_full_db_path])         
    
    result = runner.invoke(stats, ['--verbose', '-db', set_full_db_path])   
    assert result.exit_code == 0
    assert "[('TO_DO', 'pending', 2), ('STARTED', 'pending', 1), ('DONE', 'completed', 1), ('DELETED', 'bin', 1)]" in caplog.text

    runner.invoke(delete, ['gr:STATS', '-db', set_full_db_path])
    
# Tests stats view 3
def test_stats3(set_full_db_path, caplog):
    caplog.set_level(logging.DEBUG)
    # Reinit the db to get accurate results
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit', '-db', set_full_db_path])       
    # DONE Tasks
    duedt = (date.today()).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task4','-du', duedt, '-gr', 'STATS', '-db', set_full_db_path])
    result = runner.invoke(add, ['-de','Test task4','-du', duedt, '-gr', 'STATS', '-db', set_full_db_path])
    id = result.output.replace("\n"," ").split(" ")[3]    
    result = runner.invoke(done, ['id:'+str(id), '-db', set_full_db_path])     
    
    result = runner.invoke(stats, ['--verbose', '-db', set_full_db_path])   
    assert result.exit_code == 0
    assert "Retrieved stats for view 3 is {-7: 0, -6: 0, -5: 0, -4: 0, -3: 0, -2: 0, -1: 0, 0: 1}" in caplog.text
    runner.invoke(delete, ['gr:STATS', '-db', set_full_db_path])
    
    
# Tests stats view 4
def test_stats4(set_full_db_path, caplog):
    caplog.set_level(logging.DEBUG)
    # Reinit the db to get accurate results
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit', '-db', set_full_db_path])       
    # New TO_DO Tasks
    duedt = (date.today()).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task1','-du', duedt,  '-gr', 'STATS', '-db',set_full_db_path])
    result = runner.invoke(add, ['-de','Test task2','-du', duedt,  '-gr', 'STATS', '-db',set_full_db_path])
    
    result = runner.invoke(stats, ['--verbose', '-db', set_full_db_path])   
    assert result.exit_code == 0
    assert "Retrieved stats for view 4 is {-7: 0, -6: 0, -5: 0, -4: 0, -3: 0, -2: 0, -1: 0, 0: 2}" in caplog.text    
    
    runner.invoke(delete, ['gr:STATS', '-db', set_full_db_path])
    