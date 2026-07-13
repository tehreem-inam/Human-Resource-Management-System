# Human Resource Management System (HRMS)

A backend-based Human Resource Management System built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**. The project provides secure authentication, employee management, role-based access control, department management, and other HR-related functionalities through REST APIs.

## Tech Stack

* Python 3.12+
* FastAPI
* SQLAlchemy
* PostgreSQL
* Alembic
* JWT Authentication
* Pydantic
* Uvicorn

---

## Project Structure

```
backend/
│── app/
│── alembic/
│── requirements.txt
│── .env
│── main.py
```

---

## Prerequisites

Before running the project, make sure you have installed:

* Python 3.12 or later
* PostgreSQL
* Git

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/tehreem-inam/Human-Resource-Management-System.git
```

### 2. Navigate to Backend

```bash
cd Human-Resource-Management-System/backend
```

### 3. Create a Virtual Environment

Windows

```bash
python -m venv venv
```

Activate it

```bash
venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file inside the **backend** directory.

Example:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/hrms
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Replace the values with your own PostgreSQL credentials.

---

## Database Migration

Run the Alembic migrations:

```bash
alembic upgrade head
```

---

## Run the Application

```bash
uvicorn main:app --reload
```

or if your FastAPI app is located inside the app package:

```bash
uvicorn app.main:app --reload
```

---

## API Documentation

Once the server starts, open:

Swagger UI

```
http://127.0.0.1:8000/docs
```

ReDoc

```
http://127.0.0.1:8000/redoc
```

---

## Features

* User Authentication (JWT)
* Role-Based Access Control (RBAC)
* Employee Management
* Department Management
* Leave Management
* Attendance Management
* PostgreSQL Database Integration
* RESTful APIs
* Alembic Database Migrations

---

## Author

**Tehreem Inam**

GitHub: https://github.com/tehreem-inam
