# FinSight

FinSight is a financial data extraction and analysis pipeline that accepts bank statements (PDFs and Images), extracts transactions using OCR and Large Language Models, and generates structured spreadsheet outputs and financial insights.

## Project Structure

This repository follows a strict monorepo architecture:

```
FinSight/
│
├── frontend/
│   ├── package.json
│   └── src/
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── main.py
│   ├── backend_project/
│   ├── core/
│   ├── data/
│   └── mapping/
│
└── README.md
```

## Running the Application

### 1. Backend Service
The backend is responsible for document extraction, CoA categorization using the Groq LLM, and SQLite database storage. It has been wrapped in a standard Django architecture to allow future scalability into a robust REST API, whilst retaining its standard CLI pipeline execution.

Navigate to the backend:
```bash
cd backend
```
Install dependencies:
```bash
pip install -r requirements.txt
```

Run the FinSight Pipeline locally on a document/folder:
```bash
python main.py data/input/[YOUR_FILE_OR_FOLDER]
```

Run the Django Web Server (API layer):
```bash
python manage.py runserver
```
The server will be available at `http://127.0.0.1:8000/`.

### 2. Frontend Application
To start the placeholder frontend structure:
```bash
cd frontend
npm install
npm run dev
```
