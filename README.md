# Pediforte API

A RESTful API built with Flask for managing student registrations, rules agreements, admin authentication, passport uploads, and analytics for Pediforte.

## Features

- **Student Registration**: Create and manage student profiles with course and payment information.
- **Admin Authentication**: Secure login, registration, and logout for administrators.
- **Student Rules Management**: Manage and track student agreements to rules.
- **Passport Upload**: Upload student passport photos (`.png`, `.jpg`, `.jpeg`, `.gif`, `.pdf`, <5MB).
- **Dashboard Analytics**: View statistics on student registrations, courses, and payments.
- **CSV Export**: Export student data as CSV for reporting.
- **API Testing**: Automated tests via `test_api.py`.
- **CORS Support**: Configured for frontend integration (e.g., `http://localhost:4200`).

## Tech Stack

- **Python 3.8+** + **Flask**
- **Flask-RESTful**: For API resource management.
- **SQLAlchemy** + **Flask-Migrate**: For database migrations.
- **SQLite**: Lightweight database (configurable for other databases via `DATABASE_URL`).
- **Flasgger**: Swagger UI for API documentation (`/apidocs/`).
- **CORS**: Cross-Origin Resource Sharing for frontend integration.

## Prerequisites

- Python 3.8+
- pip
- Virtualenv
- SQLite (or another database if configured)

## Setup

1. **Clone the Repository**:
   ```bash
   git clone repo
   cd pediforte

python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt

2. **Initialize the Database**:
flask db init  
flask db migrate
flask db upgrade

3. **Run the Application**:
flask run
Access the API at http://localhost:5000.
View API docs at http://localhost:5000/apidocs/.

4. **Frontend Integration**:
The API supports CORS for frontends running at:http://localhost:4200
http://127.0.0.1:5000
http://localhost:5000


