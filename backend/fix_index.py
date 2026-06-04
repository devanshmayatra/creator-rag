import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Load your environment variables (.env)
load_dotenv()

# Connect to your Qdrant Cloud Cluster
client = QdrantClient(
    url=os.getenv("QDRANT_HOST_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

COLLECTION_NAME = "creator_analytics"

print("Connecting to Qdrant Cloud to build the index...")

try:
    # Tell Qdrant to index the video_id field as a strict keyword
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="metadata.video_id",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    print("✅ Index created successfully! Your GET routes will now work.")
except Exception as e:
    print(f"Error: {e}")
    print("Note: If it says 'Index already exists', you are good to go!")