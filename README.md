# Farm Estates API

FastAPI backend for the Farm Estates platform. It provides authentication, role-based access, farm operations, inventory, deliveries, sensors, telemetry, notifications, audit logs, backups, and analytics endpoints.

## Stack

- Python 3.11+
- FastAPI and Uvicorn
- Appwrite Cloud or self-hosted Appwrite
- Pydantic settings and HTTP integrations

## Local setup

```powershell
cd farm_appwrite_api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill in `.env` with the Appwrite endpoint, project ID, API key, database ID, and other service settings. Never commit `.env` or production credentials.

Start the development server:

```powershell
fastapi dev server.py
```

The API is available at `http://127.0.0.1:8000`. Health endpoints are available at `/health` and `/ready`; the OpenAPI document is available at `/openapi.json`.

For Android Emulator clients, use `http://10.0.2.2:8000` as the API host instead of `127.0.0.1`.

## Production

The repository includes a `Dockerfile` for deployment. Provide environment variables through the hosting provider or a protected secret store, then expose the API behind HTTPS and a reverse proxy.

## Related repository

The Flutter client is maintained at [farm_flutter_ui](https://github.com/Philippo20/farm_flutter_ui).
