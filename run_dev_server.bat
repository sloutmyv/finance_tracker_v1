@echo off
echo Finance Tracker Development Server

REM Check if virtual environment exists, if not create it
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

REM Install or update required packages
echo Installing dependencies...
pip install -r requirements.txt

REM Run migrations
echo Running migrations...
python manage.py migrate

REM Check if test user exists, if not create it
echo Ensuring test user exists...
python manage.py create_test_user

REM Run development server
echo Starting development server...
python manage.py runserver

REM Deactivate virtual environment when script ends
deactivate