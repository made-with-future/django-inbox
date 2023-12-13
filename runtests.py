#!/usr/bin/env python
import os
import sys

from django.conf import settings
from django.test.utils import get_runner
import django


def runtests():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'

    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['tests'])
    sys.exit(bool(failures))

    # TODO Destroy DB
    # TODO Clear migrations folder in inbox


if __name__ == '__main__':
    runtests()
