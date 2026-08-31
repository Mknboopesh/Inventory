# Inventory Management System

Full-stack inventory management app built with:

- Frontend: React + Vite
- Backend: Python FastAPI
- Database: MongoDB

The app supports owner/company registration, manager and employee approval, GRN entry, production workflow, generated invoice/report HTML files, working-material tracking, and salary calculation.

## Project Structure

```text
frontend/              React app
backend/main.py        FastAPI app
backend/requirements.txt
generated-documents/   Generated invoice/report files
data/database.json     Old JSON data used for first MongoDB migration
data/mongo-db/         Local MongoDB data directory
```

## Run Locally

Start MongoDB:

```powershell
.\mongodb-win32-x86_64-windows-7.0.14\bin\mongod.exe --dbpath .\data\mongo-db --bind_ip 127.0.0.1
```

Start the backend:

```powershell
npm run backend
```

Build the frontend and serve it from FastAPI:

```powershell
npm run build
```

Open:

```text
http://localhost:8000
```

For frontend development only:

```powershell
npm run frontend
```

Then open:

```text
http://localhost:5173
```

## Run With Docker

Start the full application with MongoDB:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8000
```

Stop the containers:

```powershell
docker compose down
```

MongoDB data is stored in the Docker volume `inventory_mongo-data`. Generated invoice/report files are stored on your machine in:

```text
generated-documents/
```

To remove the Docker database volume and start fresh:

```powershell
docker compose down -v
```

## Run As Desktop Application

Fast Windows launcher, no extra download:

```powershell
.\InventoryDesktop.cmd
```

This starts MongoDB and the Python backend, then opens the app in a desktop-style browser window.

Install the desktop wrapper dependencies:

```powershell
npm run desktop:install
```

If `npm` is not recognized on this machine, use the bundled Node/npm:

```powershell
.\venv\node-v20.11.1-win-x64\npm.cmd run desktop:install
```

Run as a desktop app:

```powershell
npm run desktop
```

Build a Windows `.exe` installer:

```powershell
npm run desktop:build
```

The installer is created in:

```text
desktop-dist/
```

The generated Windows installer has the `.exe` extension.

## Environment

```text
MONGO_URI=mongodb://localhost:27017
MONGO_DB=inventory_management
DOCUMENTS_DIR=generated-documents
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

On first backend startup, if MongoDB is empty, the backend imports existing records from `data/database.json`.

## Connect MongoDB Atlas

Create a `.env` file in the project root:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set your Atlas connection string:

```text
MONGO_URI=mongodb+srv://<username>:<password>@<cluster-name>.mongodb.net/?retryWrites=true&w=majority
MONGO_DB=inventory_management
```

In MongoDB Atlas:

- Create a database user.
- Add your current IP address in **Network Access**.
- Use the Atlas **Drivers** connection string as `MONGO_URI`.

Then run:

```powershell
.\InventoryDesktop.cmd
```

When `MONGO_URI` points to Atlas, the desktop launcher skips local MongoDB and connects directly to Atlas.

For Docker with Atlas:

```powershell
docker compose -f docker-compose.yml -f docker-compose.atlas.yml up --build app
```

## API

Main endpoints:

```text
GET  /health
POST /api/auth/owner-register
POST /api/auth/staff-register
POST /api/auth/login
GET  /api/dashboard
GET  /api/users
POST /api/inventory/arrival
PATCH /api/inventory/{id}/process
PATCH /api/inventory/{id}/machining
PATCH /api/inventory/{id}/inspection
POST /api/inventory/{id}/documents/generate
POST /api/salary
```
