"""Allow sensors without routine maintenance to omit a maintenance date."""
import os
import requests
from urllib.parse import quote
from db import db
from main import db_id, db_collection_id11

if __name__ == '__main__':
    attribute = db.get_attribute(database_id=db_id, collection_id=db_collection_id11, key='last_maintenance_date')
    if attribute.get('required'):
        # SDK 11 drops None parameters; preserve explicit JSON null for Appwrite.
        endpoint = os.environ['APPWRITE_ENDPOINT'].rstrip('/')
        path = f"/databases/{quote(db_id, safe='')}/collections/{quote(db_collection_id11, safe='')}/attributes/datetime/last_maintenance_date"
        response = requests.patch(endpoint + path,
            headers={'X-Appwrite-Project': os.environ['APPWRITE_PROJECT_ID'],
                     'X-Appwrite-Key': os.environ['APPWRITE_API_KEY']},
            json={'required': False, 'default': None}, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Maintenance migration failed ({response.status_code}): {response.json().get('message', 'Unknown error')}")
        print('Maintenance date is now optional; existing dates are preserved.')
    else:
        print('Maintenance date is already optional.')
