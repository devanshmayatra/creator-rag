from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.core.models import VideoData
from app.core.database import get_db

def process_and_store_video(video_data: VideoData) -> str:
    """
    Chunks transcript and stores data efficiently using the dynamic getter pattern.
    """
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    
    qdrant_client, vector_store = get_db()
    
    print(f"Beginning ingestion process for video: {video_data.video_id}")
    
    transcript = video_data.transcript if video_data.transcript else "No spoken audio."
    
    chunks = text_splitter.split_text(transcript)
    
    print(f"Split {len(transcript)} chars into {len(chunks)} potential chunks.")

    if not chunks:
        return f"Warning: No valid transcript chunks generated for {video_data.video_id}. Ingestion skipped."

    documents = []
    for i, chunk in enumerate(chunks):
        doc = Document(
            page_content=chunk,
            metadata={
                "video_id": video_data.video_id,
                "platform": video_data.platform,
                "title": video_data.title,
                "creator": video_data.creator,
                "engagement_rate": video_data.engagement_rate,
                "views": video_data.views,
                "likes": video_data.likes,
                "comments": video_data.comments,
                "duration": video_data.duration,
                "chunk_index": i
            }
        )
        documents.append(doc)

    print(f"Submitting {len(documents)} documents to Qdrant...")
    vector_store.add_documents(documents)
    
    success_message = f"Successfully processed, embedded, and stored {len(documents)} chunks for video {video_data.video_id}"
    print(success_message)
    
    return success_message