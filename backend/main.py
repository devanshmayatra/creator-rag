from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.services.services import extract_video_info
from app.services.vector_store import process_and_store_video
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from app.graph.chatbot import graph_app
from app.core.database import get_db, COLLECTION_NAME
from qdrant_client import models

app = FastAPI(title="rag api", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLInput(BaseModel):
    url: str
    
class ChatInput(BaseModel):
    message: str
    video_ids: list[str]
    history: list[dict] = []
    
@app.get("/api/video/{video_id}")
async def get_video_data(video_id: str):
    """Fetches all metadata and perfectly reconstructs the transcript for a given video."""
    try:
        qdrant_client, _ = get_db()
        
        # Fetch all chunks for this video (limit to 1000 chunks, which is ~4 hours of speaking)
        results, _ = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.video_id",
                        match=models.MatchValue(value=video_id)
                    )
                ]
            ),
            limit=1000, 
            with_payload=True,
            with_vectors=False
        )
        
        if not results:
            raise HTTPException(status_code=404, detail="Video not found in database")
            
        video_metadata = results[0].payload.get("metadata", {})
        
        sorted_chunks = sorted(results, key=lambda x: x.payload.get("metadata", {}).get("chunk_index", 0))
        
        full_transcript = "\n\n".join([chunk.payload.get("page_content", "") for chunk in sorted_chunks])
        
        return {
            "status": "success",
            "data": {
                "metadata": video_metadata,
                "full_transcript": full_transcript,
                "total_chunks_stored": len(results)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/chat")
async def chat_endpoint(input_data: ChatInput):
    messages = []
    for turn in input_data.history:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
    
    messages.append(HumanMessage(content=input_data.message))
    
    inputs = {
        "messages": messages,
        "video_ids": input_data.video_ids
    }
    
    async def generate_stream():
        # Use v2 events to extract pure, raw LLM tokens and ignore graph state accumulation
        async for event in graph_app.astream_events(inputs, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk_content = event["data"]["chunk"].content
                if chunk_content:
                    yield chunk_content
    
    return StreamingResponse(generate_stream(), media_type="text/plain")

@app.post("/api/ingest")
async def ingest_video(data: URLInput):
    try:
        print(f"Starting extraction for URL: {data.url}")
        video_data = extract_video_info(data.url)
        
        print(f"Extraction completed. Storing data for: {video_data.video_id}")
        storage_result = process_and_store_video(video_data)
        
        return {
            "status": "success", 
            "message": storage_result,
            "metadata": {
                "video_id": video_data.video_id,
                "engagement_rate": video_data.engagement_rate,
                "creator": video_data.creator
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Engineers build systems, not scripts."}

if __name__ == "__main__":
    import uvicorn
    # uvicorn handles the web server
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)