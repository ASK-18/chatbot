import os
from collections import defaultdict, deque

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

from rag_engine import get_rag_pipeline

# -----------------------------------------------------
# Environment & Config
# -----------------------------------------------------
load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

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
# Conversation Memory (in‑memory, session‑based)
# -----------------------------------------------------
chat_memory = defaultdict(lambda: deque(maxlen=MAX_TURNS))

# -----------------------------------------------------
# Request Models
# -----------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str


# -----------------------------------------------------
# Helper Functions
# -----------------------------------------------------
def rewrite_query_if_needed(session_id: str, query: str) -> str:
    """
    Rewrite follow‑up questions into standalone questions
    using recent conversation memory.
    """
    history = chat_memory[session_id]

    if not history:
        return query

    history_text = ""
    for turn in history:
        history_text += f"User: {turn['user']}\nAssistant: {turn['assistant']}\n"

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
        return {"answer": "Please ask a valid insurance‑related question."}

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
                    "I couldn’t find enough information in the document "
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

        # 6️⃣ Store conversation memory
        chat_memory[session_id].append({
            "user": user_query,
            "assistant": answer
        })

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
