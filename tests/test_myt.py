import click
from click.testing import CliRunner
from myt import add_task

runner = CliRunner()

def test_add_task():
    response = runner.invoke(add_task, ['Test task1', '+10', '-2', 'TESTS.T1','test1,test2',None,None])
    assert response.exit_code == 0
    assert 0 in response.output
