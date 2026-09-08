from fastapi import FastAPI

from src.hrb_chatbot.api.admin import routes_health
from src.hrb_chatbot.api.rag import routes_documents, routes_query

app = FastAPI(
    title="HRB Chatbot",
    version="0.1.0",
    description="An HR benefits chatbot backed by a RAG pipeline over the JPMC benefits knowledge base.",
)

# Routers are added here as each feature lands, one at a time.
app.include_router(routes_health.router)
app.include_router(routes_documents.router)
app.include_router(routes_query.router)
