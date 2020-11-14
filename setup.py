from setuptools import setup

setup(
    name='myt-cli',
    version='0.1',
    py_modules=['myt'],
    install_requires=[
        'Click','rich','python-dateutil','mock','sqlalchemy'
    ],
    entry_points='''
        [console_scripts]
    myt=myt:myt
    ''',
)
