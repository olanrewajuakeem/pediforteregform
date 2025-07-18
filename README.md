# Pediforte API

This is a RESTful API built with Flask for managing student registration, rules agreements, admin authentication, and reporting analytics for Pediforte.

## Features

- Student registration
- Admin login/register/logout
- Student rules management and agreement tracking
- Passport upload
- Dashboard analytics
- CSV data export
- API tested using 

##  Stack

- Python + Flask
- Flask-RESTful
- SQLAlchemy + Flask-Migrate
- SQLite 
- CORS support for frontend

## Setup

```bash
git clone repo

cd folder name
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## DB setup 
flask db upgrade

## Running the app
flask run

