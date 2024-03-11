# myt-cli
My Tasks - A personal task manager

[![GitHub Release](https://img.shields.io/github/v/release/nsmathew/myt-cli)](https://github.com/nsmathew/myt-cli/releases/latest)
[![GitHub License](https://img.shields.io/github/license/nsmathew/myt-cli)](https://raw.githubusercontent.com/nsmathew/myt-cli/master/LICENSE)
![App Type](https://img.shields.io/badge/app_type-cli-blue)
[![PyPI - Status](https://img.shields.io/pypi/status/myt-cli)](https://pypi.org/project/myt-cli/)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fnsmathew%2Fmyt-cli%2Fmaster%2Fpyproject.toml)
![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/nsmathew/myt-cli)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

### What is it
A simple command line task manager written in python. It is inspired from taskwarrior but with no where near as much functionality. 

### What can it do
You can add tasks with descriptions, due dates and notes. You can groups tasks together and can add tags to them. Tasks can be modified. Tasks can also be set to indicate they are currently being worked on. There is functionality to set recurring tasks

### Screenshots
1. The default view - `myt view`
![TaskView](https://github.com/nsmathew/myt-cli/blob/master/images/TaskView.png?raw=true)
&nbsp;
2. Information displayed after adding a task - `myt add -de "Pay council tax" -du +2 -gr home.fin -tg bills,official`
![TaskView](https://github.com/nsmathew/myt-cli/blob/master/images/TaskAdd.png?raw=true)
&nbsp;
3. Basic statistics - `myt stats`
![TaskView](https://github.com/nsmathew/myt-cli/blob/master/images/TaskStats.png?raw=true)

### Examples
1. Add a simple task
`myt add -de "Buy gifts" -du 2021-06-25 -gr PERS.SHOPPING -tg birthday,occassions`
&nbsp;
1. Add a recurring task
`myt add -de "Pay the rent" -re M -du 2021-06-25 -hi -5 -gr PERS.FINANCES -tg bills`
This task is scheduled for the 25th of every month. Using the 'hide' option tt will be hidden until 5 days from the due date for every occurence in the tasks default view 
&nbsp;
1. Add a recurring task with an end date
`myt add -de "Project weekly catch ups" -re WD1,2,5 -du +0 -en +30 -gr WORK.PROJECTS`
This adds a recurring task for every Monday, Tuesday and Friday and ending in 30 days from today

Other functionality in the app can be explored using the app's help 

### Installation
Install using pip: `pip install myt-cli`

### Technology
* Python 3
* Sqlite3

### Links
- Github - https://github.com/nsmathew/myt-cli
- PyPi - https://pypi.org/project/myt-cli

### Contact
Nitin Mathew, nitn_mathew2000@hotmail.com
