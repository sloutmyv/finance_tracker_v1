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

## Features

### User Authentication
- Login/logout functionality
- Password change capability
- Protected routes requiring authentication

### Language Support
- Multi-language support (English and French)
- Language switching through user dropdown menu
- Translation of all UI elements

### Financial Environment
- Tax Household Management
  - Create and update a personal tax household
  - Add, edit, and remove household members
  - Each member has auto-generated trigram (first letter of first name + first two letters of last name)
- Bank Account Management
  - Link bank accounts to household members
  - Associate multiple members with each account
  - Track account creation and modification dates

### Transaction Categorization
- Transaction Category Management
  - Create, edit, and delete personalized transaction categories
  - Categories linked to your household for organization
  - Simple and intuitive interface for category management
- Cost Center Organization
  - Group categories into cost centers for higher-level organization
  - 18 color options for visual differentiation of cost centers
  - Assign multiple categories to cost centers with multi-select functionality
  - Visual indicators showing category counts per cost center
  - Distinctive colored borders (8px) for easy visual identification

## Project Structure

- `finance_tracker/`: Django project settings
- `core/`: Main application with views and authentication
  - `models.py`: Data models for Tax Household, Household Members, Bank Accounts, Transaction Categories, and Cost Centers
  - `forms.py`: Forms for managing financial data, categories, and cost centers
  - `views.py`: Views for authentication, financial management, and categorization
  - `urls.py`: URL routing configuration
- `templates/`: HTML templates with Bootstrap integration
  - `base.html`: Base template with responsive navbar
  - `home.html`: Public homepage with login redirect
  - `dashboard.html`: Personal user dashboard (protected)
  - `auth/`: Authentication templates
    - `login.html`: Login form
    - `password_change.html`: Change password form
    - `password_change_done.html`: Password change confirmation
  - `financial/`: Financial management templates
    - `settings.html`: Financial settings overview
    - `household_form.html`: Create/edit tax household
    - `household_members.html`: Manage multiple household members
    - `member_form.html`: Add/edit individual household members
    - `member_confirm_delete.html`: Confirm member deletion
    - `bank_account_list.html`: List bank accounts
    - `bank_account_form.html`: Add/edit bank accounts
    - `category_list.html`: Main categories management page (includes both transaction categories and cost centers)
    - `category_form.html`: Add/edit transaction categories
    - `category_confirm_delete.html`: Confirm category deletion
    - `cost_center_form.html`: Add/edit cost centers
    - `cost_center_confirm_delete.html`: Confirm cost center deletion
    - `cost_center_category_form.html`: Assign categories to cost centers

## Technologies
- Django 5.1.7
- Bootstrap 5.3.2 (via CDN)
- Select2 for enhanced multi-select functionality
- Django's built-in authentication system
- Python-dotenv for environment variable management
- Internationalization (i18n) support for English and French

## Recent Improvements
- **Enhanced Category Management**: Implemented a streamlined interface for managing transaction categories
- **Cost Center Framework**: Added a higher-level organizational structure with cost centers
- **Visual Differentiation**: Introduced a color system with 18 options for cost centers
- **UI Refinements**: Improved visual hierarchy with colored borders and category counts
- **Multi-Category Assignment**: Added the ability to assign multiple categories to cost centers at once
- **Complete Translations**: Full English and French support for all new features

## Development Roadmap
Future development plans include:
- **Transaction Management**: Implementing transaction recording and categorization
- **Reporting & Analytics**: Adding financial reporting and visualization capabilities
- **Data Import/Export**: Creating functionality to import transactions from banks
- **Mobile Optimization**: Further improving the responsive design for mobile users
- **Budget Planning**: Adding budget creation and tracking features