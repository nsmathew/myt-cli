
import sys
import pytest
from click.testing import CliRunner
from datetime import date
from dateutil.relativedelta import relativedelta

from myt import add
from myt import modify


runner = CliRunner()
def test_add_1():
    result = runner.invoke(add, ['-de','Test task1','-gr','ABC.XYZ','-tg','qwerty,asdfgh,zxcvb'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task1" in result.output
    assert "Group:ABC.XYZ" in result.output
    assert "Tags:qwerty,asdfgh,zxcvb" in result.output

def test_add_2():
    result = runner.invoke(add, ['-de','Test task2','-du','2020-12-25'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task2" in result.output
    assert "Due:2020-12-25" in result.output

def test_add_3():
    result = runner.invoke(add, ['-de','Test task3','-du','2020-12-25','-hi','2020-12-21'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task3" in result.output
    assert "Due:2020-12-25" in result.output
    assert "Hide:2020-12-21" in result.output

def test_add_4():
    result = runner.invoke(add, ['-de','Test task4','-du','2020-12-25','-hi','-4'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Desc:Test task4" in result.output
    assert "Due:2020-12-25" in result.output
    assert "Hide:2020-12-21" in result.output

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


def test_modify_2(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','-2'])
    exp_dt = date.today() + relativedelta(days=-2)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Due:"+exp_dt.strftime("%Y-%m-%d") in result.output

def test_modify_3(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','-2'])
    exp_dt = date.today() + relativedelta(days=-4)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Hide:2020-12-23" in result.output

def test_modify_4(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','+4'])
    #-2 for change in due date in test_modify_2 and -2 for this test
    exp_dt = date.today() + relativedelta(days=+4)
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Hide:"+exp_dt.strftime("%Y-%m-%d") in result.output

def test_modify_5(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','2020-12-20'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Due:2020-12-20" in result.output

def test_modify_6(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','2020-12-15'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Hide:2020-12-15" in result.output

def test_modify_7(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-hi','clr'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Hide:None" in result.output

def test_modify_8(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-du','clr','-gr','GRPL1.GRPL2_1'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Due:None" in result.output
    assert "Group:GRPL1.GRPL2_1" in result.output

def test_modify_9(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-gr','clr','-tg', '-tag1,-tag6,tag8,tag9'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Group:None" in result.output
    assert "Tags:tag2,tag3,tag8,tag9" in result.output

def test_modify_10(create_task):
    result = runner.invoke(modify, ['id:'+str(create_task),'-tg','clr'])
    assert result.exit_code == 0
    assert "Added/Updated Task ID:" in result.output
    assert "Tags:None" in result.output
