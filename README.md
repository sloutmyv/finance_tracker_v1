# Finance Tracker

A minimal Django project with Bootstrap integration.

## Setup Instructions

### 1. Clone the repository
```bash
git clone <repository-url>
cd finance_tracker_v1
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install django
```

### 4. Run migrations
```bash
python manage.py migrate
```

### 5. Run the development server
```bash
python manage.py runserver
```

### 6. Access the application
Open your browser and navigate to http://127.0.0.1:8000/

## Project Structure

- `finance_tracker/`: Django project settings
- `core/`: Main application
- `templates/`: HTML templates (with Bootstrap integration)
  - `base.html`: Base template with Bootstrap
  - `home.html`: Homepage that displays "Hello World"

## Technologies
- Django 5.1.7
- Bootstrap 5.3.2 (via CDN)