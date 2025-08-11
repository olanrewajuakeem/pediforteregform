# Pediforte API

A RESTful API built with Flask for managing student registrations, rules agreements, admin authentication, and analytics for Pediforte.

## Features

- **Student Registration**: Create and manage student profiles with course and payment information.
- **Admin Authentication**: Secure login for administrators using HTTP Basic Auth.
- **Admin Operations**: CRUD operations for student records, with filtering by gender, preferred course, objectives, payment status, and terms agreed.
- **Student Rules Management**: Manage and track student agreements to rules.
- **Dashboard Analytics**: View statistics on student registrations, courses, and payments.
- **CSV/PDF Export**: Export student data as CSV or PDF reports with optional filters.
- **API Testing**: VIA Swagger UI.
- **CORS Support**: Configured for frontend integration (e.g., `http://localhost:4200`).

## Tech Stack

- **Python 3.8+** + **Flask**
- **Flask-RESTful**: For API resource management.
- **SQLAlchemy** + **Flask-Migrate**: For database migrations.
- **SQLite**: Lightweight database (configurable for other databases via `DATABASE_URL`).
- **Flasgger**: Swagger UI for API documentation (`/apidocs/`).
- **Flask-HTTPAuth**: For admin authentication.
- **ReportLab**: For generating PDF reports.
- **CORS**: Cross-Origin Resource Sharing for frontend integration.

## Prerequisites

- Python 3.8+
- pip
- Virtualenv
- SQLite (or another database if configured)

## Setup

1. **Clone the Repository**:
   ```bash
   git clone <repo-url>
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


