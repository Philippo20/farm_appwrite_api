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

## Public traceability integration

The public traceability site must send a `page_view` event when the experience opens. The API derives the visitor's approximate IP location and device details from the request; the browser must not send or store a raw IP address.

```http
POST /public/traceability/events
Content-Type: application/json

{
  "event_type": "page_view",
  "public_token": "FS-EXAMPLE",
  "session_id": "anonymous-browser-session-id",
  "referrer": "https://example.com/"
}
```

After a product lookup, show a feedback section when `config.feedback_enabled` is true. Submit either product feedback or an issue report:

```http
POST /public/traceability/feedback
Content-Type: application/json

{
  "feedback_type": "feedback",
  "category": "product_quality",
  "rating": 5,
  "message": "The product was fresh and the batch details were clear.",
  "public_token": "FS-EXAMPLE",
  "batch_number": "BATCH-2026-001",
  "contact_name": "",
  "contact_email": "",
  "consent_to_contact": false,
  "session_id": "anonymous-browser-session-id"
}
```

For an issue, use `feedback_type: "issue"`; `rating` may be `0`. Supported categories are `product_quality`, `packaging`, `delivery`, `traceability`, and `other`. Contact email is required only when `consent_to_contact` is true. A successful submission returns HTTP `201` with `ok`, `feedback_id`, and a user-safe message. Display validation messages from the API's `detail` field inside the form.

Set `TRACEABILITY_GEOLOOKUP_URL=https://ipwho.is/{ip}` in production to enable city, region, country, coordinates, timezone, and ISP lookup. Exact IPs are not persisted: events retain a salted hash for unique-visitor counting and a masked value for support diagnostics.

## Related repository

The Flutter client is maintained at [farm_flutter_ui](https://github.com/Philippo20/farm_flutter_ui).
