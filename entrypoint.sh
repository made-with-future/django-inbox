#!/usr/bin/env bash
set -e

echo "Istalling Django>=$DJANGO_VERSION..."

pip3 install --upgrade pip &> /dev/null
pip3 install -r requirements.txt &> /dev/null
pip3 install "Django>=$DJANGO_VERSION" &> /dev/null
echo -n "Django Version: ";python3 -c "import django; print(django.get_version())"

exec "$@"
