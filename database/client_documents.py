"""RDS catalog queries for client-scoped documents stored in organization S3."""


def list_documents(connection, organization_id, client_id):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT document.id, document.title, document.document_type,
                document.source_filename, document.version_number, document.created_at,
                document.workflow_status, content.content_type, content.byte_size,
                (SELECT count(*) FROM app.client_document_pages page
                 WHERE page.document_id=document.id) AS page_count,
                document.thumbnail_artifact_id IS NOT NULL AS has_thumbnail
            FROM app.client_documents document
            JOIN app.clinical_artifacts content ON content.id=document.content_artifact_id
            WHERE document.organization_id=%s AND document.client_id=%s
              AND document.status='active' AND document.deleted_at IS NULL
              AND content.lifecycle_state='active' AND content.deleted_at IS NULL
            ORDER BY document.created_at DESC, document.title""", (organization_id, client_id))
        return cursor.fetchall()


def get_document_artifact(connection, organization_id, client_id, document_id, asset):
    artifact_column = "thumbnail_artifact_id" if asset == "thumbnail" else "content_artifact_id"
    with connection.cursor() as cursor:
        cursor.execute(f"""SELECT artifact.storage_bucket, artifact.object_key,
                artifact.object_version_id, artifact.content_type, artifact.byte_size,
                document.source_filename, storage.region
            FROM app.client_documents document
            JOIN app.clinical_artifacts artifact ON artifact.id=document.{artifact_column}
            JOIN app.organization_storage storage ON storage.organization_id=document.organization_id
            WHERE document.id=%s AND document.organization_id=%s AND document.client_id=%s
              AND document.status='active' AND document.deleted_at IS NULL
              AND artifact.lifecycle_state='active' AND artifact.deleted_at IS NULL""",
            (document_id, organization_id, client_id))
        return cursor.fetchone()


def get_document_page_artifact(connection, organization_id, client_id, document_id, page_number):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT artifact.storage_bucket, artifact.object_key,
                artifact.object_version_id, artifact.content_type, artifact.byte_size,
                document.source_filename, storage.region
            FROM app.client_documents document
            JOIN app.client_document_pages page ON page.document_id=document.id
            JOIN app.clinical_artifacts artifact ON artifact.id=page.artifact_id
            JOIN app.organization_storage storage ON storage.organization_id=document.organization_id
            WHERE document.id=%s AND document.organization_id=%s AND document.client_id=%s
              AND page.page_number=%s AND document.status='active' AND document.deleted_at IS NULL
              AND artifact.lifecycle_state='active' AND artifact.deleted_at IS NULL""",
            (document_id, organization_id, client_id, page_number))
        return cursor.fetchone()
