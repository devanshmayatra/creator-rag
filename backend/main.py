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
async def get_video_metadata(video_id: str):
    try:
        # 1. Get the unified cloud client
        qdrant_client, vector_store = get_db()
        
        # 2. Search Qdrant Cloud for this specific video's metadata
        records, next_page = qdrant_client.scroll(
            collection_name="creator_analytics",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.video_id", # Make sure this key matches how you saved it!
                        match=models.MatchValue(value=video_id)
                    )
                ]
            ),
            limit=1 # We only need 1 chunk to grab the metadata
        )
        
        if not records:
            raise HTTPException(status_code=404, detail="Video metadata not found in cloud")
            
        # 3. Return the payload securely
        return {"status": "success", "data": {"metadata": records[0].payload["metadata"]}}
        
    except Exception as e:
        print(f"Error fetching video {video_id}: {str(e)}")
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