#!/usr/bin/env sh

gunicorn --bind :"$PORT" app:app