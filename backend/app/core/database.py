import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from langchain_huggingface import HuggingFaceEmbeddings

QDRANT_PATH = "./local_qdrant_db"
COLLECTION_NAME = "creator_analytics"

# Global placeholders
_embeddings = None
_qdrant_client = None
_vector_store = None

def get_db():
    """Lazy initializer that validates and automatically repairs dimension mismatches."""
    global _embeddings, _qdrant_client, _vector_store
    
    if _qdrant_client is None:
        print("Connecting to Qdrant storage engine...")
        if os.getenv("QDRANT_HOST_URL"):
            _qdrant_client = QdrantClient(
                url=os.getenv("QDRANT_HOST_URL"),
                api_key=os.getenv("QDRANT_API_KEY"),
            )
        else:
            _qdrant_client = QdrantClient(path="./local_qdrant_db")
        
        print("Loading local embedding weights (BGE-Small)...")
        _embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
        
        # Guard: Validate existing collection dimensions to prevent parameter conflicts
        try:
            collection_info = _qdrant_client.get_collection(collection_name=COLLECTION_NAME)
            # Inspect actual configuration size
            current_size = collection_info.config.params.vectors.size
            
            if current_size != 384:
                print(f"Warning: Found mismatched collection dimension ({current_size}). Wiping and upgrading to 384...")
                _qdrant_client.delete_collection(collection_name=COLLECTION_NAME)
                raise ValueError("Rebuild required") # Forces transition into the except block
            else:
                print(f"Collection '{COLLECTION_NAME}' verified perfectly (Size: 384).")
                
        except Exception:
            print(f"Initializing a clean 384-dimension collection for '{COLLECTION_NAME}'...")
            _qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print("Collection created successfully.")
            
        _vector_store = QdrantVectorStore(
            client=_qdrant_client,
            collection_name=COLLECTION_NAME,
            embedding=_embeddings
        )
        
    return _qdrant_client, _vector_store