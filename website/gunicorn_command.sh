#!/bin/bash
# Gunicorn command for deploying Flask application on Render
gunicorn --bind 0.0.0.0:8000 wsgi:app
