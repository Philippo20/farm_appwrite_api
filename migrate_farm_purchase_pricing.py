"""Add optional farm purchase fields; historical receipts are never auto-priced."""
import os
import time
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException

if __name__ == "__main__":
    load_dotenv()
    db = Databases(Client().set_endpoint(os.environ["APPWRITE_ENDPOINT"])
        .set_project(os.environ["APPWRITE_PROJECT_ID"]).set_key(os.environ["APPWRITE_API_KEY"]))
    database = os.environ["APPWRITE_DB_ID"]
    fields = [(os.environ["APPWRITE_COLLECTION_ID17"], "owner_price_tier"),
              (os.environ["APPWRITE_COLLECTION_ID7"], "farm_purchase")]
    for collection, key in fields:
        try:
            if key == "owner_price_tier":
                db.create_enum_attribute(database, collection, key, ["Regular", "Bulk"], False, default="Regular")
            else:
                db.create_string_attribute(database, collection, key, 4096, False)
        except AppwriteException as error:
            if error.code != 409:
                raise
    for attempt in range(30):
        attributes = [db.get_attribute(database, collection, key) for collection, key in fields]
        if all(field["status"] == "available" for field in attributes):
            if any(field.get("required") for field in attributes):
                raise RuntimeError("Farm purchase fields must remain optional")
            tier, purchase = attributes
            if set(tier.get("elements", [])) != {"Regular", "Bulk"} or tier.get("default") != "Regular":
                raise RuntimeError("Existing owner_price_tier does not match the required schema")
            if purchase.get("type") != "string" or purchase.get("size", 0) < 4096:
                raise RuntimeError("Existing farm_purchase must be a string of at least 4096 characters")
            for field in attributes:
                print(field["key"] + ": available")
            break
        time.sleep(2)
    else:
        raise RuntimeError("Schema still building; rerun to verify before deployment.")
