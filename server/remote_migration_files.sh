#!/bin/bash

echo "🔍 Searching for Django migration files to delete..."

# Find and delete all migration Python files except __init__.py
find . -path "*/migrations/*.py" -not -name "__init__.py" -print -delete

# Find and delete all compiled migration Python files
find . -path "*/migrations/*.pyc" -print -delete

echo "✅ All migration files (except __init__.py) have been deleted."