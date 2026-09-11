from appwrite.query import Query


def list_all_documents(db, *, database_id, collection_id):
    """Collect every page for existing list endpoints without changing their shape."""
    documents = []
    seen = set()
    offset = 0
    while True:
        result = db.list_documents(
            database_id=database_id,
            collection_id=collection_id,
            queries=[Query.limit(100), Query.offset(offset)],
        )
        page = result.get("documents", [])
        for document in page:
            document_id = document.get("$id")
            if document_id not in seen:
                documents.append(document)
                seen.add(document_id)
        if len(page) < 100:
            return {"documents": documents, "total": len(documents)}
        offset += len(page)
