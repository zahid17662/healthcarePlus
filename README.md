# MediBook Healthcare Appointment System

Full-stack hospital appointment booking application.

## Quick Start

### 1. Run the Frontend

From the project root:

```bash
npm run dev
```

Or from the `frontend` folder:

```bash
cd frontend
npm run dev
```

The application will be available at [http://localhost:5173](http://localhost:5173) (or `http://localhost:5174` if 5173 is occupied).

### 2. Run the Backend (Optional)

The frontend includes a built-in mock API by default when `VITE_API_URL` is empty in `frontend/.env`.

To run the real FastAPI backend with PostgreSQL:

```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Backend interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).
