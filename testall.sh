#!/usr/bin/env bash
set -e

docker compose run inbox-django-2.2 python runtests.py
docker compose run inbox-django-3 python runtests.py
docker compose run inbox-django-4 python runtests.py
docker compose run inbox-django-5 python runtests.py
