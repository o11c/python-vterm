#!/usr/bin/env python

from setuptools import setup

setup(
    name='vterm',
    version='0.1',
    description='Wrapper for LeoNerd\'s libvterm',
    author='Ben Longbons',
    author_email='b.r.longbons@gmail.com',
    url='https://github.com/o11c/python-vterm',
    packages=['vterm', 'vterm.backports'],
    setup_requires=['cffi'],
    install_requires=['cffi'],
    cffi_modules=['vterm/_c_build.py:ffibuilder']
)
