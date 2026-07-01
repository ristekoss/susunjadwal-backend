#!/usr/bin/env sh

set -eu

exec gunicorn --bind :"$PORT" app:app
