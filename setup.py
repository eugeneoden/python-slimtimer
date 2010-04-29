from setuptools import setup

PACKAGE = 'python-slimtimer'
VERSION = '0.1.0'

setup(
    name=PACKAGE,
    version=VERSION,

    packages=['slimtimer'],
    install_requires = ['elementtree>=1.2.6-20050316'],
    description='SlimTimer interface for Python',
    keywords='slimtimer slim timer',
    license = 'BSD',
    url = 'http://github.com/eugeneoden/python-slimtimer',
    author='Eugene Oden',
    author_email='eugeneoden@gmail.com',
    long_description="""
    Provides an interface for SlimTimer.com, a time-tracking website.
    """,
    zip_safe=True
)

