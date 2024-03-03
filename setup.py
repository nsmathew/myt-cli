from setuptools import setup

setup(
    name='myt-cli',
    version='0.1.5',
    description='myt - My Task Manager',
    author='Nitin Mathew',
    author_email='nitn_mathew2000@hotmail.com',
    py_modules=['myt'],
    install_requires=[
        'Click','rich','python-dateutil','mock','sqlalchemy'
    ],
    tests_require=['pytest'],
    entry_points='''
        [console_scripts]
    myt=myt:myt
    ''',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',  
        'Programming Language :: Python',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS',
        'Operating System :: POSIX :: Linux',
        'Topic :: Office/Business',
    ],
)
