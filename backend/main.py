import os
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
from pymongo import MongoClient

from rag_engine import get_rag_pipeline

# -----------------------------------------------------
# Environment & Config
# -----------------------------------------------------
load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

BASE_DIR = os.path.dirname(__file__)
PDF_PATH = os.path.join(BASE_DIR, "data", "insurance.pdf")

MAX_CONTEXT_CHARS = 4000
LLM_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"

MAX_TURNS = 4  # conversation memory window

# -----------------------------------------------------
# FastAPI App
# -----------------------------------------------------
app = FastAPI(title="Insurance Conversational RAG Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------
# Load RAG Components
# -----------------------------------------------------
rag_pipeline = get_rag_pipeline(PDF_PATH)
llm_client = InferenceClient(token=HF_TOKEN)

# -----------------------------------------------------
# MongoDB – Conversation Memory
# -----------------------------------------------------
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["rag_chatbot"]
chat_collection = db["conversations"]

# Create index for fast session queries
chat_collection.create_index("session_id")
chat_collection.create_index([("session_id", 1), ("timestamp", 1)])

print(f"✅ Connected to MongoDB at {MONGO_URI}")


# -----------------------------------------------------
# Request Models
# -----------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str


# -----------------------------------------------------
# MongoDB Helpers
# -----------------------------------------------------
def get_recent_history(session_id: str, limit: int = MAX_TURNS):
    """Fetch the last `limit` user-assistant turn pairs from MongoDB."""
    docs = list(
        chat_collection.find(
            {"session_id": session_id},
            {"_id": 0, "role": 1, "content": 1, "timestamp": 1},
        )
        .sort("timestamp", 1)  # oldest first
    )
    # Return last `limit * 2` messages (each turn = user + assistant)
    return docs[-(limit * 2):]


def store_message(session_id: str, role: str, content: str):
    """Insert a single message into MongoDB."""
    chat_collection.insert_one({
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc),
    })


# -----------------------------------------------------
# Helper Functions
# -----------------------------------------------------
def rewrite_query_if_needed(session_id: str, query: str) -> str:
    """
    Rewrite follow-up questions into standalone questions
    using recent conversation memory from MongoDB.
    """
    history_docs = get_recent_history(session_id)

    if not history_docs:
        return query

    history_text = ""
    for msg in history_docs:
        label = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{label}: {msg['content']}\n"

    prompt = (
        "Rewrite the user's question into a standalone question.\n"
        "Use the conversation history only to resolve references.\n"
        "Do NOT answer the question.\n\n"
        f"Conversation History:\n{history_text}\n"
        f"Question:\n{query}"
    )

    response = llm_client.chat_completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=80,
        temperature=0.0,
    )

    return response.choices[0].message.content.strip()


def format_docs_with_sources(docs):
    """
    Format retrieved documents with citations
    and enforce a max context length.
    """
    context = ""
    sources = []

    for idx, doc in enumerate(docs, start=1):
        page = doc.metadata.get("page", "N/A")
        text = doc.page_content.strip()

        if len(context) + len(text) > MAX_CONTEXT_CHARS:
            break

        context += f"[Source {idx} | Page {page}]\n{text}\n\n"

        sources.append({
            "source_id": idx,
            "page": page,
            "preview": text[:200]
        })

    return context.strip(), sources


def build_system_prompt(context: str) -> str:
    return (
        "You are an insurance assistant.\n"
        "Answer the user's question using ONLY the information in the context.\n"
        "Explain clearly and simply.\n"
        "Do NOT copy text word-for-word.\n"
        "If the answer is not in the context, say you don't have enough information.\n"
        "If discussing coverage, claims, or eligibility, be conservative and factual.\n\n"
        f"Context:\n{context}"
    )


# -----------------------------------------------------
# Chat Endpoint
# -----------------------------------------------------
@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id
    user_query = req.message.strip()

    if not user_query:
        return {"answer": "Please ask a valid insurance-related question."}

    try:
        # 1️⃣ Rewrite query if conversational
        standalone_query = rewrite_query_if_needed(session_id, user_query)

        # 2️⃣ Retrieve + rerank documents
        docs = rag_pipeline(standalone_query)

        # 3️⃣ Build LLM context
        context, sources = format_docs_with_sources(docs)

        if not context or len(context) < 300:
            return {
                "answer": (
                    "I couldn't find enough information in the document "
                    "to answer this accurately."
                )
            }

        # 4️⃣ LLM call
        system_prompt = build_system_prompt(context)

        response = llm_client.chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
            max_tokens=250,
            temperature=0.1,
        )

        answer = response.choices[0].message.content.strip()

        # 5️⃣ Insurance disclaimer
        if any(word in user_query.lower() for word in ["coverage", "claim", "insured", "policy"]):
            answer += (
                "\n\n⚠️ Disclaimer: This response is based on the provided document. "
                "Actual coverage depends on full policy terms and conditions."
            )

        # 6️⃣ Store conversation in MongoDB
        store_message(session_id, "user", user_query)
        store_message(session_id, "assistant", answer)

        return {
            "answer": answer,
            "sources": sources
        }

    except Exception as e:
        print(f"Chat error: {e}")
        return {
            "answer": (
                "I'm currently unable to process your request. "
                "Please try again later."
            )
        }


# -----------------------------------------------------
# History Endpoint – Get messages for a session
# -----------------------------------------------------
@app.get("/history/{session_id}")
async def get_history(session_id: str):
    docs = list(
        chat_collection.find(
            {"session_id": session_id},
            {"_id": 0, "role": 1, "content": 1, "timestamp": 1},
        )
        .sort("timestamp", 1)
    )
    # Convert datetime to ISO string for JSON serialization
    for doc in docs:
        if "timestamp" in doc:
            doc["timestamp"] = doc["timestamp"].isoformat()
    return {"session_id": session_id, "messages": docs}


# -----------------------------------------------------
# Sessions Endpoint – List all past sessions
# -----------------------------------------------------
@app.get("/sessions")
async def list_sessions():
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {
            "$group": {
                "_id": "$session_id",
                "last_message": {"$first": "$content"},
                "last_timestamp": {"$first": "$timestamp"},
                "message_count": {"$sum": 1},
            }
        },
        {"$sort": {"last_timestamp": -1}},
        {"$limit": 20},
    ]
    results = list(chat_collection.aggregate(pipeline))

    sessions = []
    for r in results:
        sessions.append({
            "session_id": r["_id"],
            "preview": (r["last_message"] or "")[:80],
            "last_timestamp": r["last_timestamp"].isoformat() if r.get("last_timestamp") else None,
            "message_count": r["message_count"],
        })

    return {"sessions": sessions}


# -----------------------------------------------------
# Debug Endpoint – Inspect RAG Retrieval
# -----------------------------------------------------
@app.post("/debug/rag")
async def debug_rag(req: ChatRequest):
    if not req.message.strip():
        return {"error": "Empty query"}

    standalone_query = rewrite_query_if_needed(
        req.session_id, req.message.strip()
    )

    docs = rag_pipeline(standalone_query)

    return {
        "query_used_for_retrieval": standalone_query,
        "documents": [
            {
                "page": d.metadata.get("page"),
                "content": d.page_content[:500]
            }
            for d in docs
        ]
    }
