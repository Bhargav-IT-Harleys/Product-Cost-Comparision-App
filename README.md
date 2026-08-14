# Product Cost Comparison App

A simple, fast Flask web application for managing and comparing product cost versions across locations.

## Features

- Upload Base Price Excel files
- Upload new Product Cost versions
- Compare versions product-wise and location-wise
- Search and filter comparison results
- Dashboard with summary statistics

## Tech Stack

- Python 3 + Flask
- SQLAlchemy + PostgreSQL
- Pandas + openpyxl for Excel processing
- Vanilla HTML/CSS/JavaScript

## Setup

### 1. Create PostgreSQL Database

```bash
createdb product_cost_db
```

Or via psql:

```sql
CREATE DATABASE product_cost_db;
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 5. Initialize Database

```bash
python database.py
```

### 6. Run Locally

```bash
python app.py
```

Open http://localhost:5000

### 7. Run with Gunicorn (Production)

```bash
gunicorn app:app
```

## Excel Format

Required columns:
- Product Name
- Product Category
- Unit
- HYD
- BLR
- MUM
- PUNE
- NCR

## Project Structure

```
product-cost-app/
├── app.py               # Flask application and routes
├── models.py            # SQLAlchemy models
├── database.py          # Database initialization
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── README.md           # This file
├── templates/          # Flask HTML templates
└── static/             # CSS and JavaScript
```
