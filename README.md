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

The public traceability site must send a `page_view` event when the experience opens. Prefer calling the API directly from the visitor's browser. DigitalOcean App Platform exposes the original browser address in `DO-Connecting-IP`, which this API uses by default, while the normal browser `User-Agent` supplies the device details. The browser must not obtain or submit its raw IP address.

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

If the public site must proxy traceability calls through its own server, configure the same long random `TRACEABILITY_PROXY_SECRET` on the public-site server and API. The proxy must copy its platform's authoritative original-client IP and the incoming browser metadata into these headers:

```http
X-Traceability-Proxy-Key: <server-only shared secret>
X-Visitor-IP: <original client IP from the public site's hosting platform>
X-Visitor-User-Agent: <incoming browser User-Agent>
X-Visitor-Platform: <incoming Sec-CH-UA-Platform, optional>
X-Visitor-Mobile: <incoming Sec-CH-UA-Mobile, optional>
```

Never expose `TRACEABILITY_PROXY_SECRET` in browser JavaScript. The API ignores these forwarding headers unless the shared secret matches. For a non-DigitalOcean API deployment, set `TRACEABILITY_CLIENT_IP_HEADER` to that platform's authoritative client-IP header; do not use `X-Forwarded-For` on DigitalOcean App Platform because it identifies the ingress server.

## Related repository

The Flutter client is maintained at [farm_flutter_ui](https://github.com/Philippo20/farm_flutter_ui).
