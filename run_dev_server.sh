#!/bin/bash

# Check if virtual environment exists, if not create it
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install or update required packages
echo "Installing dependencies..."
pip install -r requirements.txt

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Check if test user exists, if not create it
echo "Ensuring test user exists..."
python manage.py create_test_user

# Run development server
echo "Starting development server..."
python manage.py runserver

# Deactivate virtual environment when script ends
deactivate