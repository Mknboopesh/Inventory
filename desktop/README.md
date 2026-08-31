# Inventory Desktop App

This folder contains the Electron wrapper for the Inventory Management System.

## Development Run

From the project root:

```powershell
npm run desktop:install
npm run desktop
```

The desktop app starts:

- bundled MongoDB runtime from `mongodb-win32-x86_64-windows-7.0.14`
- FastAPI backend from `backend/main.py`
- React production build from `frontend/dist`

## Build Windows Desktop App

From the project root:

```powershell
npm run desktop:install
npm run desktop:build
```

The installer is created in:

```text
desktop-dist/
```

The generated installer has the `.exe` extension.
