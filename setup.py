"""
Flask-Slither
-------------

Slither is a thin library that sits between a mongodb and RESTful
API endpoints.
"""
from setuptools import setup


setup(
    name='Flask-Slither',
    version='1.0',
    url='http://github.com/gevious/flask_slither',
    license='MIT',
    author='Nico Gevers',
    author_email='ingevious@gmail.com',
    description='A small library between MongoDB and JSON API endpoints',
    long_description=__doc__,
    py_modules=['flask_slither'],
    # if you would be using a package instead use packages instead
    # of py_modules:
    # packages=['flask_sqlite3'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask',
        'pymongo',
        'mongokit',
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
