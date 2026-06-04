import os
from typing import Annotated, List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from app.core.database import get_db, COLLECTION_NAME
from qdrant_client import models 

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    video_ids: List[str]

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINI_API_KEY"), streaming=True)

async def rag_node(state: AgentState):
    """Gathers metadata and transcript chunks using strictly typed filter models."""
    user_query = state["messages"][-1].content
    video_ids = state.get("video_ids", [])
    
    qdrant_client, vector_store = get_db()

    metadata_context = ""
    seen_videos = set()
    
    for vid in video_ids:
        results = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.video_id",
                        match=models.MatchValue(value=vid)
                    )
                ]
            ),
            limit=1
        )[0]
        
        if results:
            meta = results[0].payload.get("metadata", {})
            if meta and meta.get("video_id") not in seen_videos:
                seen_videos.add(meta.get("video_id"))
                metadata_context += (
                    f"- Video ID: {meta.get('video_id', 'Unknown')}\n"
                    f"  Creator: {meta.get('creator', 'Unknown')} ({meta.get('followers', 'N/A')} followers)\n"
                    f"  Platform: {meta.get('platform', 'Unknown')}\n"
                    f"  Views: {meta.get('views', 0)} | Likes: {meta.get('likes', 0)} | Comments: {meta.get('comments', 0)}\n"
                    f"  Engagement Rate: {meta.get('engagement_rate', 0)}%\n\n"
                )

    # Pass 2: LangChain Semantic Search
    # CRITICAL FIX: We pass the native Qdrant models.Filter object directly 
    # to LangChain, bypassing the kwargs dict crash completely.
    qdrant_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.video_id",
                match=models.MatchAny(any=video_ids)
            )
        ]
    )
    
    semantic_results = vector_store.similarity_search(
        query=user_query, 
        k=5, 
        filter=qdrant_filter
    )

    transcript_context = ""
    for doc in semantic_results:
        meta = doc.metadata
        transcript_context += f"[Source: Video {meta.get('video_id')}, Chunk {meta.get('chunk_index')}]: \"{doc.page_content}\"\n\n"

    system_prompt = (
        "You are an elite Social Media Growth Engineer auditing content performance.\n"
        "Analyze the provided videos using the exact numeric metadata and transcript snippets provided.\n\n"
        "CRITICAL RULES:\n"
        "1. BE CONVERSATIONAL & NATURAL: Do NOT output raw chunk numbers (e.g., [Chunk 5]) or raw Video IDs (e.g., JFS8y42jQbU) in your response. Refer to them naturally as 'The 2025 review' or 'Video A/B' based on context.\n"
        "2. BE CONCISE & DIRECT: Answer ONLY the specific question asked. Do not restate previous summaries or carry over context from previous answers unless explicitly asked to compare them.\n"
        "3. NO HALLUCINATION: Rely strictly on the data provided below.\n\n"
        f"=== NUMERIC METADATA ===\n{metadata_context}\n"
        f"=== TRANSCRIPT SNIPPETS ===\n{transcript_context}"
    )

    messages_payload = [SystemMessage(content=system_prompt)] + state["messages"][-3:]
    
    response = await llm.ainvoke(messages_payload)
    return {"messages": [response]}

workflow = StateGraph(AgentState)
workflow.add_node("agent_brain", rag_node)
workflow.add_edge(START, "agent_brain")
workflow.add_edge("agent_brain", END)

graph_app = workflow.compile()