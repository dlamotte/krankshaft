#!/usr/bin/env python

from setuptools import setup, find_packages

# see: http://bugs.python.org/issue15881
try:
    import multiprocessing
except ImportError:
    pass

install_requires = [
    'mimeparse==0.1.3',
]

try:
    tests_requires = open('requirements.txt').read().splitlines()
except IOError:
    tests_requires = []

long_description = ''
try:
    long_description = open('README.rst').read()
except IOError:
    pass

setup(
    name='krankshaft',
    version='0.2.3',
    author='Dan LaMotte',
    author_email='lamotte85@gmail.com',
    url='https://github.com/dlamotte/krankshaft',
    description='A Web API Framework (with Django, ...)',
    long_description=long_description,
    packages=find_packages('.'),
    zip_safe=False,
    install_requires=install_requires,
    license='MIT',
    tests_require=tests_requires,
    test_suite='runtests.runtests',
    include_package_data=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Utilities'
    ],
)
