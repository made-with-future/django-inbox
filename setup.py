#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev

import io
import os
import sys
from shutil import rmtree

from setuptools import Command, find_packages, setup

NAME = 'django-inbox'
DESCRIPTION = 'A Django app to support user inbox messages.'
URL = 'https://www.madewithfuture.com/'
EMAIL = 'jt@madewithfuture.com'
AUTHOR = 'Josh Turmel'
REQUIRES_PYTHON = '>=3.7'
VERSION = '0.8.12'

REQUIRED = [
    'django>=2.2,<=5.0',
    'django-annoying',
    'django_enumfield>=2.0.0',
    'djangorestframework',
    'jsonschema',
    'drf-extensions',
    'toolz',
    'psycopg2-binary'
]

EXTRAS = {
    'app_push_firebase': ['pyfcm<=2.0.0'],
    'admin_commands': ['beautifultable']
}

TESTS_REQUIRE = [
    'coverage',
    'Faker',
    'django-annoying',
    'responses',
    'djangorestframework-simplejwt',
    'hashids==1.2.0',
    'freezegun',
    'twine',
    'beautifultable',
    'pyfcm==1.4.7'
]

# The rest you shouldn't have to touch too much :)
# ------------------------------------------------
# Except, perhaps the License and Trove Classifiers!
# If you do change the License, remember to change the Trove Classifier for that!

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = DESCRIPTION

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    project_slug = NAME.lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = VERSION


class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('python setup.py sdist bdist_wheel')

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload -r pypicloud dist/*')

        self.status('Pushing git tags…')
        os.system('git tag releases/v{0}'.format(about['__version__']))
        os.system('git push --tags')

        sys.exit()

setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
    # If your package is a single module, use this instead of 'packages':
    # py_modules=['mypackage'],

    # entry_points={
    #     'console_scripts': ['mycli=mymodule:cli'],
    # },
    test_suite="runtests.runtests",
    install_requires=REQUIRED,
    tests_require=TESTS_REQUIRE,
    extras_require=EXTRAS,
    include_package_data=True,
    license='MIT',
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
    },
)
