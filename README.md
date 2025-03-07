# Finance Tracker

A Django project with Bootstrap integration and user authentication.

## Quick Start

The easiest way to run the application is to use the provided script:

```bash
./run_dev_server.sh
```

This script will:
1. Create a virtual environment if it doesn't exist
2. Install all dependencies
3. Run migrations
4. Create a test user if it doesn't exist
5. Start the development server

## Manual Setup Instructions

### 1. Clone the repository
```bash
git clone <repository-url>
cd finance_tracker_v1
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
The project uses python-dotenv to manage environment variables. A .env file has been created with default development settings.

### 5. Run migrations
```bash
python manage.py migrate
```

### 6. Create a test user
```bash
python manage.py create_test_user
```
This creates a user with:
- Username: testuser
- Password: password123

### 7. Run the development server
```bash
python manage.py runserver
```

### 8. Access the application
Open your browser and navigate to http://127.0.0.1:8000/

## User Authentication Flow

1. When a user visits the site, they are presented with a login page
2. After successful login, they are redirected to their personal dashboard with a welcome message
3. The navigation menu displays options to access the dashboard, change password, or log out
4. When logging out, the user is redirected to the login page with a logout confirmation message
5. Protected routes require login (redirects to login page if not authenticated)

## Project Structure

- `finance_tracker/`: Django project settings
- `core/`: Main application with views and authentication
- `templates/`: HTML templates with Bootstrap integration
  - `base.html`: Base template with responsive navbar
  - `home.html`: Public homepage with login redirect
  - `dashboard.html`: Personal user dashboard (protected)
  - `auth/`: Authentication templates
    - `login.html`: Login form
    - `password_change.html`: Change password form
    - `password_change_done.html`: Password change confirmation

## Technologies
- Django 5.1.7
- Bootstrap 5.3.2 (via CDN)
- Django's built-in authentication system