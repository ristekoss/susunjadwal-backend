#!/bin/bash

# Start Gunicorn processes
echo Starting Gunicorn.
exec gunicorn app:app \
    --bind unix:sunjad.sock
    --workers 3
