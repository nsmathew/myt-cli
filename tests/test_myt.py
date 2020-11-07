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
from myt import empty

runner = CliRunner()
def test_add_1():
    result = runner.invoke(add, ['-de','Test task1','-gr','ABC.XYZ','-tg','qwerty,asdfgh,zxcvb'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task1" in result.output
    assert "Group:ABC.XYZ" in result.output
    assert "Tags:qwerty,asdfgh,zxcvb" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])


def test_add_2():
    result = runner.invoke(add, ['-de','Test task2','-du','2020-12-25'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task2" in result.output
    assert "Due:2020-12-25" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_3():
    result = runner.invoke(add, ['-de','Test task3','-du','2020-12-25','-hi','2020-12-21'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task3" in result.output
    assert "Due:2020-12-25" in result.output
    assert "Hide:2020-12-21" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

def test_add_4():
    result = runner.invoke(add, ['-de','Test task4','-du','2020-12-25','-hi','-4'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task4" in result.output
    assert "Due:2020-12-25" in result.output
    assert "Hide:2020-12-21" in result.output
    temp = result.output.replace("\n"," ")
    create_task = temp.split(" ")[3]
    create_task = runner.invoke(delete, ['id:'+str(create_task)])

@pytest.fixture
def create_task():
    result = runner.invoke(add, ['-de','Test task5','-du','2020-12-25', '-gr', 'GRPL1.GRPL2', '-tg', 'tag1,tag2,tag3'])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

def test_modify_1(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-de','Test task5.1'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task5.1" in result.output
    assert "Due:2020-12-25" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])


def test_modify_2(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','-2'])
    exp_dt = date.today() + relativedelta(days=-2)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Due:"+exp_dt.strftime("%Y-%m-%d") in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_3(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','-2'])
    exp_dt = date.today() + relativedelta(days=-4)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Hide:2020-12-23" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_4(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','+4'])
    #-2 for change in due date in test_modify_2 and -2 for this test
    exp_dt = date.today() + relativedelta(days=+4)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Hide:"+exp_dt.strftime("%Y-%m-%d") in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_5(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','2020-12-20'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Due:2020-12-20" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_6(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','2020-12-15'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Hide:2020-12-15" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_7(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','clr'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Hide:None" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_8(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','clr','-gr','GRPL1.GRPL2_1'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Due:None" in result.output
    assert "Group:GRPL1.GRPL2_1" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_9(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-gr','clr','-tg', '-tag1,-tag6,tag8,tag9'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Group:None" in result.output
    assert "Tags:tag2,tag3,tag8,tag9" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])

def test_modify_10(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-tg','clr'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Tags:None" in result.output
    runner.invoke(delete, ['id:'+str(create_task)])


@pytest.fixture
def create_task2():
    result = runner.invoke(add, ['-de','Test task8','-du','2020-12-25', '-gr', 'GRPL1.GRPL2', '-tg', 'tag1,tag2,tag3'])
    temp = result.output.replace("\n"," ")
    return temp.split(" ")[3]

def test_start_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Sts:STARTED" in result.output
    runner.invoke(delete, ['id:'+str(create_task2)])

def test_stop_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(stop, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Sts:TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(create_task2)])

def test_revert_1(create_task2):
    result = runner.invoke(start, ['id:'+str(create_task2)])
    result = runner.invoke(revert, ['id:'+str(create_task2)])    
    temp = result.output.replace("\n"," ")
    new_id = temp.split(" ")[3]
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Sts:TO_DO" in result.output
    runner.invoke(delete, ['id:'+str(new_id)])

def test_done_1(create_task2):
    result = runner.invoke(done, ['id:'+str(create_task2)])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Sts:DONE" in result.output
    runner.invoke(delete, ['DONE','tg:'+'tag1'])

def test_delete_1(create_task2):
    runner.invoke(done, ['id:'+str(create_task2)])
    result = runner.invoke(delete, ['id:999'])
    assert result.exit_code == 0
    assert "No applicable tasks to delete" in result.output
    runner.invoke(delete, ['DONE','tg:'+'tag1'])

def test_delete_2(create_task2):
    runner.invoke(done, ['id:'+str(create_task2)])
    result = runner.invoke(delete, ['DONE', 'tg:'+'tag1'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID: -" in result.output

def test_empty_1():
    with mock.patch('builtins.input', return_value="yes"):
        result = runner.invoke(empty)
        assert "Bin emptied!" in result.output
