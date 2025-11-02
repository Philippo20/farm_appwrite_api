from fastapi import FastAPI, APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from main import client, bucket_id
from appwrite.services.storage import Storage
from appwrite.input_file import InputFile
from appwrite.id import ID
from io import BytesIO

st = Storage(client)

# create storage
# result = st.create_bucket(
#     bucket_id= ID.unique(),
#     name="Farm Estates Ltd Storage bucket"
# )

storage_router = APIRouter(tags=["Storage"])

@storage_router.post("/storage/buckets/{bucket_id}/files")
def create_file():
    with open("C:/Users/KKB_Official/Downloads/Microsoft_Cloud_Skill_Report.pdf", "rb") as f:
        content = f.read()

    result = st.create_file(
        bucket_id=bucket_id,
        file=InputFile.from_bytes(content, "file.pdf"),
        file_id=ID.unique(),
        permissions=[]
    )
   
    return result


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

@storage_router.get("/storage/buckets/{bucket_id}/files/{file_id}")
def list_files():
    result = st.list_files(
        bucket_id=bucket_id,
        queries=[]
    )
    return result

@storage_router.put("/storage/buckets/{bucket_id}/files/{file_id}")
def get_file(file_id:str):
    result = st.get_file(
        bucket_id=bucket_id,
        file_id=file_id
        # permissions=[]
    )
    return result

@storage_router.delete("/storage/buckets/{bucket_id}/files/{file_id}")
def delete_file(file_id:str):
    result = st.delete_file(
        bucket_id=bucket_id,
        file_id=file_id
    )
    return f" File '{file_id}' deleted successfully from bucket '{bucket_id}'."