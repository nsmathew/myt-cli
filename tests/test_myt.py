import datetime
import sys
import pytest
from click.testing import CliRunner
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import mock

from myt import add
from myt import modify
from myt import delete
from myt import start
from myt import stop
from myt import revert
from myt import reset
from myt import done
from myt import admin
from myt import view
from myt import now
from myt import urlopen

runner = CliRunner()
def test_add_1():
    result = runner.invoke(add, ['-de','Test task1','-gr','ABC.XYZ','-tg',
                           'qwerty,asdfgh,zxcvb'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task1" in result.output
    assert "groups : ABC.XYZ" in result.output
    assert "tags : qwerty,asdfgh,zxcvb" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_2():
    result = runner.invoke(add, ['-de','Test task2','-du','2020-12-25'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task2" in result.output
    assert "due : 2020-12-25" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_3():
    result = runner.invoke(add, ['-de','Test task3','-du','2020-12-25','-hi',
                           '2020-12-21'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task3" in result.output
    assert "due : 2020-12-25" in result.output
    assert "hide : 2020-12-21" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_4():
    result = runner.invoke(add, ['-de','Test task4','-du','2020-12-25','-hi',
                           '-4'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task4" in result.output
    assert "due : 2020-12-25" in result.output
    assert "hide : 2020-12-21" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_5_1():
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','h'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : H" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_5_2():
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','H'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : H" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_5_3():
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','m'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : M" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])
    
def test_add_5_4():
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','M'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : M" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_5_5():
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','l'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : L" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_5_6():
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25',
                           '-pr','l'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : L" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_5_7():
    result = runner.invoke(add, ['-de','Test task5'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : N" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_5_8():
    result = runner.invoke(add, ['-de','Test task5_8', '-tg', 
                                 ',abc,ghj,abc,'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "tags : abc,ghj" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_re_1():
    #With no due date
    result = runner.invoke(add, ['-de', 'Test task re 1', '-re', 'D'])
    assert result.exit_code == 0
    assert "Need a due date for recurring tasks" in result.output

def test_add_re_2():
    #Witjhout end date
    duedt = (date.today() + relativedelta(days=-1)).strftime("%Y-%m-%d")
    nextdt = (date.today()).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'D',
                                 '-tg', 're2,bnh', '-gr', 'ABC.ONH', '-du',
                                 duedt])
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
        runner.invoke(delete, ['tg:re2'])

def test_add_re_3():
    #With End date
    duedt = (date.today() + relativedelta(days=-1)).strftime("%Y-%m-%d")
    nextdt = (date.today()).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'D',
                                 '-tg', 're3,bnh', '-gr', 'ABC.ONH', '-du',
                                 duedt, '-en', enddt])
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
        runner.invoke(delete, ['tg:re3'])

def test_add_re_4():
    #Weekly
    duedt = (date.today()).strftime("%Y-%m-%d")
    nextdt = (date.today() + relativedelta(days=+7)).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'W','-du',
                                 duedt, '-en', enddt, '-tg', 're4'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type W-None") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : W" in result.output
    assert "recur_when : ..." in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re4'])

def test_add_re_5():
    #Monthly
    duedt = (date.today()).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(duedt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'M','-du',
                                 duedt, '-en', enddt, '-tg', 're5'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type M-None") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "recur_mode : M" in result.output
    assert "recur_when : ..." in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re5'])

def test_add_re_6():
    #Yearly
    duedt = (date.today()).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(duedt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'Y','-du',
                                 duedt, '-en', enddt, '-tg', 're6'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type Y-None") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "recur_mode : Y" in result.output
    assert "recur_when : ..." in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re6'])

def test_add_re_7():
    #Every 3 days
    duedt = (date.today() + relativedelta(days=-4)).strftime("%Y-%m-%d")
    nextdt = (datetime.strptime(duedt,"%Y-%m-%d") 
                + relativedelta(days=3)).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'DE3','-du',
                                 duedt, '-en', enddt, '-tg', 're7'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type D-E3") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : D" in result.output
    assert "recur_when : E3" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re7'])


def test_add_re_8():
    #Every 2 weeks
    duedt = (date.today() + relativedelta(days=-30)).strftime("%Y-%m-%d")
    nextdt = (datetime.strptime(duedt,"%Y-%m-%d") 
                + relativedelta(days=14)).strftime("%Y-%m-%d")
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'WE2','-du',
                                 duedt, '-en', enddt, '-tg', 're8'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type W-E2") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : W" in result.output
    assert "recur_when : E2" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re8'])

def test_add_re_9():
    #Every 2 months
    duedt = "2020-12-04"
    nextdt = "2021-02-04"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'ME2','-du',
                                 duedt, '-en', enddt, '-tg', 're9'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type M-E2") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : M" in result.output
    assert "recur_when : E2" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re9'])

def test_add_re_10():
    #Every 2 years
    duedt = "2019-12-03"
    nextdt = "2021-12-03"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'YE2','-du',
                                 duedt, '-en', enddt, '-tg', 're10'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type Y-E2") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : Y" in result.output
    assert "recur_when : E2" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re10'])

def test_add_re_11():
    #Every Monday and Wednesday
    duedt = "2021-01-04"
    nextdt = "2021-01-06"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'WD1,3','-du',
                                 duedt, '-en', enddt, '-tg', 're11'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type WD-1,3") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : WD" in result.output
    assert "recur_when : 1,3" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re11'])

def test_add_re_12():
    #Every 3rd and 5th of month
    duedt = "2021-01-03"
    nextdt = "2021-01-05"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'MD3,5','-du',
                                 duedt, '-en', enddt, '-tg', 're12'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type MD-3,5") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : MD" in result.output
    assert "recur_when : 3,5" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re12'])

def test_add_re_13():
    #Every October and December
    duedt = "2020-10-28"
    nextdt = "2020-12-28"
    enddt = (datetime.strptime(nextdt,"%Y-%m-%d") 
                + relativedelta(days=1)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task re 2', '-re', 'MO10,12',
                                 '-du', duedt, '-en', enddt, '-tg', 're13'])
    assert result.exit_code == 0
    assert ("Recurring task add/updated from " + duedt + " until " + enddt + 
            " for recurrence type MO-10,12") in result.output.replace("\n","")
    assert "Added/Updated Task ID:" in result.output
    assert "due : " + duedt in result.output
    assert "due : " + nextdt in result.output
    assert "recur_mode : MO" in result.output
    assert "recur_when : 10,12" in result.output
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:re13'])


@pytest.fixture
def create_task():
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25', '-gr',
                           'GRPL1.GRPL2', '-tg', 'tag1,tag2,tag3', '-pr','H'])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

def test_modify_1(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-de',
                           'Test task5.1'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "description : Test task5.1" in result.output
    assert "due : 2020-12-25" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])


def test_modify_2(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','-2'])
    exp_dt = date.today() + relativedelta(days=-2)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "due : "+exp_dt.strftime("%Y-%m-%d") in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_3(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','-2'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "hide : 2020-12-23" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_4(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','+4'])
    #-2 for change in due date in test_modify_2 and -2 for this test
    exp_dt = date.today() + relativedelta(days=+4)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "hide : "+exp_dt.strftime("%Y-%m-%d") in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_5(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','2020-12-20'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "due : 2020-12-20" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_6(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','2020-12-15'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "hide : 2020-12-15" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_7(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','clr'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "hide : ..." in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_8(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','clr','-gr',
                           'GRPL1.GRPL2_1'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "due : ..." in result.output
    assert "groups : GRPL1.GRPL2_1" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_9(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-gr','clr','-tg',
                           '-tag1,-tag6,tag8,tag9'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "groups : ..." in result.output
    assert "tags : tag2,tag3,tag8,tag9" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_10(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-tg','clr'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "tags : ..." in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_11_1(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-pr','L'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : L" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_11_2(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-pr','m'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : M" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_11_3(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-pr','clr'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : N" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_11_3(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-pr','xyz'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "priority : N" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_11_3(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),
                                    '-tg',',-tag1,-tag1,tag4,xyz,tag4,'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "tags : tag2,tag3,tag4,xyz" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_12_1():
    result = runner.invoke(modify, ['complete'])
    assert result.exit_code == 0
    assert "Modify can be run only on 'pending' tasks." in result.output

def test_modify_12_2():
    result = runner.invoke(modify, ['bin'])
    assert result.exit_code == 0
    assert "Modify can be run only on 'pending' tasks." in result.output

@pytest.fixture
def create_task2():
    result = runner.invoke(add, ['-de','Test task8','-du','2020-12-25', '-gr',
                           'GRPL1.GRPL2', '-tg', 'tag1,tag2,tag3'])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

def test_start_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : STARTED" in result.output
    runner.invoke(delete, ['id:'+str(create_task2)])

def test_start_2_1():
    result = runner.invoke(start, ['complete'])
    assert result.exit_code == 0
    assert "Start can be run only on 'pending' tasks." in result.output

def test_start_2_2():
    result = runner.invoke(start, ['bin'])
    assert result.exit_code == 0
    assert "Start can be run only on 'pending' tasks." in result.output 

def test_stop_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(stop, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(create_task2)])

def test_stop_2_1():
    result = runner.invoke(stop, ['complete'])
    assert result.exit_code == 0
    assert "Stop can be run only on 'pending' tasks." in result.output

def test_stop_2_2():
    result = runner.invoke(stop, ['bin'])
    assert result.exit_code == 0
    assert "Stop can be run only on 'pending' tasks." in result.output 

def test_reset_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(reset, ['id:'+str(create_task2)])
    temp = result.output.replace("\n"," ")
    new_id = temp.split(" ")[3]
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(new_id)])

def test_reset_2_1():
    result = runner.invoke(reset, ['complete'])
    assert result.exit_code == 0
    assert "Reset can be run only on 'pending' tasks." in result.output

def test_reset_2_2():
    result = runner.invoke(reset, ['bin'])
    assert result.exit_code == 0
    assert "Reset can be run only on 'pending' tasks." in result.output 

def test_revert_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(done, ['id:'+str(create_task2)])    
    temp = result.output.replace("\n"," ")
    uuid = temp.split(" ")[3]
    result = runner.invoke(revert, ['COMPLETE','uuid:'+str(uuid)])
    temp = result.output.replace("\n"," ")
    new_id = temp.split(" ")[3]
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(new_id)])

def test_revert_2_1():
    result = runner.invoke(revert, ['bin'])
    assert result.exit_code == 0
    assert ("Revert is applicable only to completed tasks. Use 'complete' "
           "filter in command") in result.output    

def test_done_1(create_task2):
    result = runner.invoke(done, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "Updated Task UUID:" in result.output
    assert "status : DONE" in result.output
    runner.invoke(delete, ['complete','tg:'+'tag1'])

def test_done_2_1():
    result = runner.invoke(done, ['complete'])
    assert result.exit_code == 0
    assert "Done can be run only on 'pending' tasks." in result.output

def test_done_2_2():
    result = runner.invoke(done, ['bin'])
    assert result.exit_code == 0
    assert "Done can be run only on 'pending' tasks." in result.output 

def test_delete_1(create_task2):
    runner.invoke(done, ['id:'+str(create_task2)])
    result = runner.invoke(delete, ['id:99999'])
    assert result.exit_code == 0
    assert "No applicable tasks to delete" in result.output
    runner.invoke(delete, ['complete','tg:'+'tag1'])

def test_delete_2(create_task2):
    runner.invoke(done, ['id:'+str(create_task2)])
    result = runner.invoke(delete, ['complete', 'tg:'+'tag1'])
    assert result.exit_code == 0
    assert "Updated Task UUID:" in result.output

def test_delete_3():
    result = runner.invoke(delete, ['bin'])
    assert result.exit_code == 0
    assert "Delete cannot be run on deleted tasks." in result.output 

def test_now_1(create_task2):
    #Now as True
    with mock.patch('builtins.input', return_value="no"):
        result = runner.invoke(now, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    runner.invoke(delete, ['tg:'+'tag1'])

def test_now_2(create_task2):
    #Now as False
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(now, ['id:'+str(create_task2)])
    result = runner.invoke(now, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "now_flag : ..." in result.output
    runner.invoke(delete, ['tg:'+'tag1'])

def test_now_3(create_task2):
    #Set another task as Now when a task is already set as Now
    with mock.patch('builtins.input', return_value="no"):
        runner.invoke(now, ['id:'+str(create_task2)])
    result = runner.invoke(add, ['-de','Test task8','-du','2020-12-25', '-gr',
                           'GRPL1.GRPL2', '-tg', 'tag1,tag2,tag3'])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="no"):
        result = runner.invoke(now, ['id:'+str(idn)])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    assert "now_flag : ..." in result.output
    runner.invoke(delete, ['tg:'+'tag1'])

def test_now_4(create_task2):
    #set as now and start task
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(now, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    assert "status : STARTED" in result.output
    runner.invoke(delete, ['id:'+str(create_task2)])

def test_now_5(create_task2):
    #set as now and do not start task
    with mock.patch('builtins.input', return_value="no"):
        result = runner.invoke(now, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(create_task2)])

def test_now_6(create_task2):
    #Set as now and for started task it should remain started
    runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(now, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "now_flag : True" in result.output
    assert "status : STARTED" in result.output
    runner.invoke(delete, ['id:'+str(create_task2)])

def test_now_7_1():
    result = runner.invoke(now, ['complete'])
    assert result.exit_code == 0
    assert "Now can be run only on 'pending' tasks." in result.output

def test_now_7_2():
    result = runner.invoke(now, ['bin'])
    assert result.exit_code == 0
    assert "Now can be run only on 'pending' tasks." in result.output 

@pytest.fixture
def create_task3():
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(delete)
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(delete, ['hidden'])        
    duedt = (date.today() + relativedelta(days=+5)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task9','-du',duedt, '-gr',
                                 'GRPL1AB.GRPL2CD', '-tg', 
                                 'view1,view2,view3,view4'])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

def test_view1(create_task3):
    duedt = date.today().strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view1', '-du', duedt])
    result = runner.invoke(view, ['TODAY'])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 0" in result.output
    runner.invoke(delete, ['tg:view1'])

def test_view2(create_task3):
    duedt = (date.today() + relativedelta(days=-4)).strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view2','-du', duedt])
    result = runner.invoke(view, ['overdue'])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 0" in result.output
    runner.invoke(delete, ['tg:view2'])

def test_view3(create_task3): 
    duedt = (date.today() + relativedelta(days=+10)).strftime("%Y-%m-%d")
    hidedt = (date.today() + relativedelta(days=+8)).strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view3','-du', 
                        duedt, '-hi', hidedt])
    result = runner.invoke(view, ['hidden'])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 1" in result.output
    runner.invoke(delete, ['tg:view3'])

def test_view4(create_task3):
    duedt = (date.today() + relativedelta(days=+10)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view4','-du', 
                        duedt])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(start, ['id:' + idn])
    result = runner.invoke(view, ['started'])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 0" in result.output
    runner.invoke(delete, ['tg:view4'])                     

def test_admin_empty_1():
    result = runner.invoke(add, ['-de', 'Test task 10.1'])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(delete, ['id:' + idn])
    result = runner.invoke(add, ['-de', 'Test task 10.2'])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(delete, ['id:' + idn])
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(admin, ['--empty'])
        assert "Bin emptied!" in result.output

def test_admin_reinit_1():
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(admin, ['--reinit'])
        assert "Database removed..." in result.output
        assert "Tasks database initialized..." in result.output

def test_admin_tags_1():
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit'])    
    result = runner.invoke(admin, ['--tags'])
    assert result.exit_code == 0
    assert "No tags added to tasks." in result.output

def test_admin_tags_2():
    runner.invoke(add, ['-de', 'Test task 11.1', '-tg', 'abc,xyz'])
    runner.invoke(add, ['-de', 'Test task 11.2', '-tg', 'tgh'])
    result = runner.invoke(admin, ['--tags'])
    assert "Total number of tags: 3" in result.output
    runner.invoke(delete, ['tg:abc,xyz,tgh'])

def test_admin_groups_1():
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit'])    
    result = runner.invoke(admin, ['--groups'])
    assert "No groups added to tasks." in result.output

def test_admin_groups_2():
    runner.invoke(add, ['-de', 'Test task 12.1', '-gr', 'PERS.AA1'])
    runner.invoke(add, ['-de', 'Test task 12.2', '-gr', 'PERS.AA1.AA2'])
    runner.invoke(add, ['-de', 'Test task 12.3', '-gr', 'OTH.AA3'])
    result = runner.invoke(admin, ['--groups'])
    assert "Total number of groups: 5" in result.output
    runner.invoke(delete, ['gr:OTH'])
    runner.invoke(delete, ['gr:PERS'])

def test_urlopen_1():
    result = runner.invoke(add, ['-de', 'Test task 13.1', '-du', '+0', '-no',
                            'Test https://abc.com [ABC] https://xy.com [ XY]', 
                            '-tg', 'tag13'])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    runner.invoke(modify, ['id:' + idn, '-no', 'http://bb.com bb'])
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn])
    assert result.exit_code == 0
    assert "1 - https://abc.com [ABC]" in result.output
    assert "2 - https://xy.com [ XY]" in result.output
    assert "3 - http://bb.com" in result.output
    runner.invoke(delete, ['id:' + idn])

def test_urlopen_2():
    result = runner.invoke(add, ['-de', 'Test task 13.2', '-du', '+0', '-no',
                            'Test https://abc.com [ABC] https://xy.com [ XY]', 
                            '-tg', 'tag13'])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-ur', str(4)])
    assert result.exit_code == 0
    assert "No URL found at the position provided" in result.output
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-ur', str(-2)])
    assert result.exit_code == 0
    assert "No URL found at the position provided" in result.output
    runner.invoke(delete, ['id:' + idn])

def test_urlopen_3():
    result = runner.invoke(add, ['-de', 'Test task 13.3', '-du', '+0', '-no',
                            'Test Notes', '-tg', 'tag13'])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn, '-ur', str(4)])
    assert result.exit_code == 0
    assert "No URLS found in notes for this task" in result.output
    runner.invoke(delete, ['id:' + idn])

def test_urlopen_4():
    result = runner.invoke(add, ['-de', 'Test task 13.3', '-du', '+0', '-no',
                            'Test Notes', '-tg', 'tag13'])
    temp = result.output.replace("\n"," ")
    idn = temp.split(" ")[3]
    with mock.patch('builtins.input', return_value="none"):
        result = runner.invoke(urlopen, ['id:' + idn])
    assert result.exit_code == 0
    assert "No URLS found in notes for this task" in result.output
    runner.invoke(delete, ['id:' + idn])
