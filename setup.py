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

tests_require = [
    'dj-database-url==0.2.1',
    'django-nose==1.1',
    'psycopg2==2.4.5',
    'nose-cov==1.6',
]

long_description = ''
try:
    long_description = open('README.md').read()
except IOError:
    pass

setup(
    name='krankshaft',
    version='0.1',
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
