"""Run once on deployment; creates only the email settings attribute."""
from appwrite.exception import AppwriteException
from db import db
from main import db_id, db_collection_id18

if __name__ == '__main__':
    try:
        db.create_string_attribute(database_id=db_id, collection_id=db_collection_id18,
                                   key='email_settings_json', size=12000, required=False)
        print('Email settings attribute created. Wait until Appwrite marks it available before saving settings.')
    except AppwriteException as error:
        if error.code != 409:
            raise
        print('Email settings attribute already exists.')
