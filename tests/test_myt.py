import sys
import pytest
from click.testing import CliRunner
from datetime import date
from dateutil.relativedelta import relativedelta
import mock

from myt import add
from myt import modify
from myt import delete
from myt import start
from myt import stop
from myt import revert
from myt import done
from myt import admin
from myt import view

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
    exp_dt = date.today() + relativedelta(days=-4)
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
    assert "hide : None" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_8(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','clr','-gr',
                           'GRPL1.GRPL2_1'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "due : None" in result.output
    assert "groups : GRPL1.GRPL2_1" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_9(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-gr','clr','-tg',
                           '-tag1,-tag6,tag8,tag9'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "groups : None" in result.output
    assert "tags : tag2,tag3,tag8,tag9" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_10(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-tg','clr'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "tags : None" in result.output
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

def test_stop_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(stop, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(create_task2)])

def test_revert_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(revert, ['id:'+str(create_task2)])    
    temp = result.output.replace("\n"," ")
    new_id = temp.split(" ")[3]
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(new_id)])

def test_revert_2(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(done, ['id:'+str(create_task2)])    
    temp = result.output.replace("\n"," ")
    uuid = temp.split(" ")[3]
    result = runner.invoke(revert, ['DONE','uuid:'+str(uuid)])
    temp = result.output.replace("\n"," ")
    new_id = temp.split(" ")[3]
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "status : TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(new_id)])

def test_done_1(create_task2):
    result = runner.invoke(done, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "Updated Task UUID:" in result.output
    assert "status : DONE" in result.output
    runner.invoke(delete, ['DONE','tg:'+'tag1'])

def test_delete_1(create_task2):
    runner.invoke(done, ['id:'+str(create_task2)])
    result = runner.invoke(delete, ['id:99999'])
    assert result.exit_code == 0
    assert "No applicable tasks to delete" in result.output
    runner.invoke(delete, ['DONE','tg:'+'tag1'])

def test_delete_2(create_task2):
    runner.invoke(done, ['id:'+str(create_task2)])
    result = runner.invoke(delete, ['DONE', 'tg:'+'tag1'])
    assert result.exit_code == 0
    assert "Updated Task UUID:" in result.output

@pytest.fixture
def create_task3():
    duedt = (date.today() + relativedelta(days=+5)).strftime("%Y-%m-%d")
    result = runner.invoke(add, ['-de','Test task9','-du',duedt, '-gr',
                                 'GRPL1AB.GRPL2CD', '-tg', 
                                 'view1,view2,view3,view4'])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

@pytest.fixture
def delete_all():
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(delete)
        result = runner.invoke(delete, ['hidden'])

def test_view1(delete_all, create_task3):
    duedt = date.today().strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view1', '-du', duedt])
    result = runner.invoke(view, ['TODAY'])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 0" in result.output
    runner.invoke(delete, ['tg:view1'])

def test_view2(delete_all, create_task3):
    duedt = (date.today() + relativedelta(days=-4)).strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view2','-du', duedt])
    result = runner.invoke(view, ['overdue'])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 0" in result.output
    runner.invoke(delete, ['tg:view2'])

def test_view3(delete_all, create_task3):
    duedt = (date.today() + relativedelta(days=+10)).strftime("%Y-%m-%d")
    hidedt = (date.today() + relativedelta(days=+8)).strftime("%Y-%m-%d")
    runner.invoke(add, ['-de', 'Test task 9.1', '-tg','view3','-du', 
                        duedt, '-hi', hidedt])
    result = runner.invoke(view, ['hidden'])
    assert result.exit_code == 0
    assert "Displayed Tasks: 1" in result.output
    assert "Total Pending Tasks: 2, of which Hidden: 1" in result.output
    runner.invoke(delete, ['tg:view3'])

def test_view4(delete_all, create_task3):
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



