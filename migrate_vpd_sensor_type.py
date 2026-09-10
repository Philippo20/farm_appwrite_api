"""Add VPD to existing sensor/alert enums. Run once before deploying VPD support."""
import os


def add_vpd(db, database_id, collection_id, key):
    attribute = db.get_attribute(database_id, collection_id, key)
    elements = list(attribute['elements'])
    if 'VPD' in elements:
        return False
    db.update_enum_attribute(
        database_id=database_id, collection_id=collection_id, key=key,
        elements=[*elements, 'VPD'], required=attribute['required'],
        default=attribute.get('default'),
    )
    return True


def main():
    from dotenv import load_dotenv
    from appwrite.client import Client
    from appwrite.services.databases import Databases
    load_dotenv()
    client = (Client().set_endpoint(os.environ['APPWRITE_ENDPOINT'])
              .set_project(os.environ['APPWRITE_PROJECT_ID'])
              .set_key(os.environ['APPWRITE_API_KEY']))
    db = Databases(client)
    for variable, key in [('APPWRITE_COLLECTION_ID11', 'sensortype'),
                          ('APPWRITE_COLLECTION_ID12', 'sensorType')]:
        changed = add_vpd(db, os.environ['APPWRITE_DB_ID'], os.environ[variable], key)
        print(key + (': VPD added' if changed else ': VPD already available'))


if __name__ == '__main__':
    main()
