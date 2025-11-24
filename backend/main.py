"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import secrets
import os
from collections import defaultdict
from time import time

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from .config import SECRET_AUTH_TOKEN
from .models import get_available_models, format_models_for_ui

app = FastAPI(title="LLM Council API")

# Configure CORS - supports both development and production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limiting for authentication - simple in-memory implementation
# For production, consider Redis-based rate limiting
_auth_attempts = defaultdict(list)
_MAX_AUTH_ATTEMPTS = 5
_AUTH_WINDOW_SECONDS = 300  # 5 minutes


def check_rate_limit(identifier: str) -> bool:
    """Check if the identifier has exceeded rate limit."""
    now = time()
    # Clean old attempts
    _auth_attempts[identifier] = [t for t in _auth_attempts[identifier] if now - t < _AUTH_WINDOW_SECONDS]
    
    # Check limit
    if len(_auth_attempts[identifier]) >= _MAX_AUTH_ATTEMPTS:
        return False
    
    # Record attempt
    _auth_attempts[identifier].append(now)
    return True


# Authentication dependency with timing-attack protection
async def verify_token(request: Request, x_auth_token: Optional[str] = Header(None)):
    """Verify the authentication token from the request header.
    
    Uses constant-time comparison to prevent timing attacks.
    """
    if not SECRET_AUTH_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: SECRET_AUTH_TOKEN not set"
        )
    
    # Get client identifier for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    
    # Check if provided token
    if x_auth_token is None:
        # Record failed attempt
        if not check_rate_limit(f"auth_fail_{client_ip}"):
            raise HTTPException(
                status_code=429,
                detail="Too many authentication attempts. Please try again later."
            )
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authentication token"
        )
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_auth_token, SECRET_AUTH_TOKEN):
        # Record failed attempt
        if not check_rate_limit(f"auth_fail_{client_ip}"):
            raise HTTPException(
                status_code=429,
                detail="Too many authentication attempts. Please try again later."
            )
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authentication token"
        )
    
    return True


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint - no sensitive information exposed."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/models")
async def list_models(request: Request = None, authenticated: bool = Depends(verify_token)):
    """
    Get list of available models from OpenRouter.
    Requires authentication.
    """
    try:
        models_data = await get_available_models()
        formatted = format_models_for_ui(models_data)
        return {"models": formatted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(request: Request, authenticated: bool = Depends(verify_token)):
    """List all conversations (metadata only). Requires authentication."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(create_req: CreateConversationRequest, request: Request = None, authenticated: bool = Depends(verify_token)):
    """Create a new conversation. Requires authentication."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str, request: Request = None, authenticated: bool = Depends(verify_token)):
    """Get a specific conversation with all its messages. Requires authentication."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.get("/api/conversations/{conversation_id}/models")
async def get_conversation_models(conversation_id: str, request: Request = None, authenticated: bool = Depends(verify_token)):
    """
    Get the model configuration for a conversation.
    Requires authentication.
    """
    model_config = storage.get_conversation_models(conversation_id)
    if model_config is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return model_config


class UpdateModelsRequest(BaseModel):
    """Request to update conversation models."""
    council_models: List[str]
    chairman_model: str


@app.put("/api/conversations/{conversation_id}/models")
async def update_conversation_models(
    conversation_id: str,
    models_request: UpdateModelsRequest,
    request: Request = None,
    authenticated: bool = Depends(verify_token)
):
    """
    Update the model configuration for a conversation.
    Requires authentication.
    """
    try:
        storage.update_conversation_models(
            conversation_id,
            models_request.council_models,
            models_request.chairman_model
        )
        return {"status": "ok", "message": "Models updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, msg_request: SendMessageRequest, request: Request = None, authenticated: bool = Depends(verify_token)):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    Requires authentication.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, msg_request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(msg_request.content)
        storage.update_conversation_title(conversation_id, title)

    # Get conversation-specific model configuration
    model_config = storage.get_conversation_models(conversation_id)
    
    # Run the 3-stage council process with conversation-specific models
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        msg_request.content,
        council_models=model_config['council_models'],
        chairman_model=model_config['chairman_model']
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, msg_request: SendMessageRequest, request: Request = None, authenticated: bool = Depends(verify_token)):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    Requires authentication.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, msg_request.content)
            
            # Get conversation-specific model configuration
            model_config = storage.get_conversation_models(conversation_id)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(msg_request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(
                msg_request.content,
                council_models=model_config['council_models']
            )
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(
                msg_request.content,
                stage1_results,
                council_models=model_config['council_models']
            )
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                msg_request.content,
                stage1_results,
                stage2_results,
                chairman_model=model_config['chairman_model']
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
