from setuptools import setup

setup(
    name='myt-cli',
    version='0.1.1',
    description='myt - My Task Manager',
    py_modules=['myt'],
    install_requires=[
        'Click','rich','python-dateutil','mock','sqlalchemy',
        'importlib-metadata ~= 1.0 ; python_version < "3.8"'
    ],
    entry_points='''
        [console_scripts]
    myt=myt:myt
    ''',
)
