"""
Flask-Slither
-------------

Slither is a thin library that sits between a mongodb and RESTful
API endpoints.
"""
from setuptools import setup


setup(
    name='Flask-Slither',
    version='1.1.7',
    url='http://github.com/gevious/flask_slither',
    license='MIT',
    author='Nico Gevers',
    author_email='me@gevious.com',
    description='A small library between MongoDB and JSON API endpoints',
    long_description=__doc__,
    packages=['flask_slither'],
    test_suite='nose.collector',
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask==1.0',
        'pymongo==2.6',
        'inflect==0.2.5'
    ],
    tests_require=[
        'Flask==1.0',
        'inflect==0.2.5',
        'pymongo==2.6',
        'nose==1.3.3'
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
