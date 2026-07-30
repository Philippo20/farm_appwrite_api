from fastapi import FastAPI, Header
import os
from routes.r1_users import collection1_router
from routes.r2_farms import collection2_router
from routes.r3_plant_type import collection3_router
from routes.r4_inventory import collection4_router
from routes.r5_batches import collection5_router
from routes.r6_audits import collection6_router
from routes.r7_fulfillment import collection7_router
from routes.r8_sales import collection8_router
from routes.r9_package import collection9_router
from routes.r10_wallet import collection10_router
from routes.r11_sensors import collection11_router
from routes.r12_alerts import collection12_router
from routes.r13_thresholds import collection13_router
from routes.r14_logs import collection14_router
from routes.r15_grow_stages import collection15_router
from routes.r16_crops import collection16_router
from routes.r17_pricing import collection17_router
from routes.r18_system_config import collection18_router
from routes.r20_inventory_movements import collection20_router
from routes.r22_fund_requests import collection22_router
from routes.r23_farm_tasks import collection23_router
from routes.r24_farm_records import collection24_router
from routes.r25_notifications import collection25_router
from routes.r26_input_confirmations import collection26_router
from routes.r27_caretaker_settings import collection27_router
from storage import storage_router
from auth import auth_router
from backups import backups_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Farm Estates Ltd API",
    description="API built using appwrite's db",
    docs_url="/",
    openapi_url="/farmestatesltd",
)
# http
# http://localhost:8080
# "GET", "POST", "PUT", "DELETE", "PATCH"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "http://localhost:8080",
        "https://goldfish-app-pet66.ondigitalocean.app/"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Cookie"],
)

app.include_router(collection1_router)
app.include_router(collection2_router)
app.include_router(collection3_router)
app.include_router(collection20_router)
app.include_router(collection22_router)
app.include_router(collection23_router)
app.include_router(collection24_router)
app.include_router(collection25_router)
app.include_router(collection26_router)
app.include_router(collection27_router)
app.include_router(collection4_router)
app.include_router(collection5_router)
app.include_router(collection6_router)
app.include_router(collection7_router)
app.include_router(collection8_router)
app.include_router(collection9_router)
app.include_router(collection10_router)
app.include_router(collection11_router)
app.include_router(collection12_router)
app.include_router(collection13_router)
app.include_router(collection14_router)
app.include_router(collection15_router)
app.include_router(collection16_router)
app.include_router(collection17_router)
app.include_router(collection18_router)
app.include_router(storage_router)
app.include_router(auth_router)
app.include_router(backups_router)

@app.get("/debug/headers")
def debug_headers(authorization: str = Header(None)):
    return {"received": authorization}
