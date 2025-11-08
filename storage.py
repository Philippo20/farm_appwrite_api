from fastapi import FastAPI, APIRouter, HTTPException, status, File, UploadFile
from fastapi.responses import StreamingResponse
from main import client, bucket_id, project_id, appwrite_endpoint, db_id
from appwrite.services.storage import Storage
from appwrite.input_file import InputFile
from appwrite.id import ID
from io import BytesIO
from db import db
from typing import Annotated

st = Storage(client)

# create storage
# result = st.create_bucket(
#     bucket_id= ID.unique(),
#     name="Farm Estates Ltd Storage bucket"
# )

storage_router = APIRouter(tags=["Storage"])


@storage_router.get("/storage/buckets/{bucket_id}/files/{file_id}/download")
def get_file_for_download(file_id:str):
    # token = st.create_file_token(bucket_id=bucket_id, file_id=file_id)
    # print(token)
    try:
        # Get file bytes from Appwrite
        file_bytes = st.get_file_download(
            bucket_id=bucket_id,
            file_id=file_id)

        # Convert to stream response for FastAPI
        return StreamingResponse(
            BytesIO(file_bytes),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={file_id}.bin"
            }
        )
    except Exception as e:
        return {"error": str(e)}

@storage_router.get("/storage/buckets")
def list_files():
    result = st.list_files(
        bucket_id=bucket_id,
        queries=[]
    )
    return result

@storage_router.get("/storage/buckets/{bucket_id}/files/{file_id}")
def get_file(file_id:str):
    result = st.get_file(
        bucket_id=bucket_id,
        file_id=file_id,
        # permissions=[]
    )
    return result

@storage_router.put("/storage/buckets/{bucket_id}/files")
async def create_file(
    file_upload: Annotated[UploadFile, File(...)]

):
    file_bytes = await file_upload.read()
    
    try:
        # Upload file to Appwrite Storage
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=file_upload.filename)
            # file=crop_image.file  # use the file object directly
        )
        file_id = uploaded_file["$id"]

        # Generate file URLs
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"

        # Save URLs to Appwrite Database
        saved_doc = db.create_document(
            database_id=db_id,
            # collection_id=db_collection_id16,
            document_id=ID.unique(),
            data={
                "crop_image": file_upload.filename}
        )
        return {
            "message": "File created successfully",
            "file_id": file_id,
            "view_url": view_url,
            "download_url": download_url,
            "db_document_id": saved_doc["$id"]
        }
    except Exception as e:
        return {"error": str(e)}

@storage_router.delete("/storage/buckets/{bucket_id}/files/{file_id}")
def delete_file(file_id:str):
    result = st.delete_file(
        bucket_id=bucket_id,
        file_id=file_id
    )
    return f" File '{file_id}' deleted successfully from bucket '{bucket_id}'."