"""Generates a grounded answer from retrieved chunks - a real LCEL chain
(ChatPromptTemplate | GatewayChatModel | result-mapper), matching the IK
cohort's own Module 4 pattern instead of a hand-rolled ask() call."""

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from src.hrb_chatbot.common.clients.llm_client.client_gateway import get_client_gateway
from src.hrb_chatbot.common.clients.llm_client.langchain_chat_model import GatewayChatModel
from src.hrb_chatbot.common.enums import LlmProvider
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_pipeline.response_generator")

NO_CONTEXT_ANSWER = "I don't have any information about that in the knowledge base."

# Four few-shot examples, real KB text - see RAG-ROADMAP.md Phase 48 for why.
# No {{ }} below - plain str.format() would choke on literal braces.
SYSTEM_PROMPT_TEMPLATE = """You are the HR benefits assistant for JPMC employees. Use ONLY the context below to answer - if the answer isn't in it, say you don't know rather than guessing. Never invent information not present in the context. Always cite the source document by name after each fact.

Example 1 - direct fact lookup:
Context:
[JPMC Empower 401(k) Savings Plan.txt] Automatic enrollment at 5% contribution rate with annual auto-escalation up to 10%. Employer matching contributions of up to 5% (dollar-for-dollar) after one year of service. Immediate eligibility to participate with no waiting period.

Question: When can I start contributing to my 401(k), and does JPMC match?
Answer: You're eligible immediately, with no waiting period - you're auto-enrolled at a 5% contribution rate that auto-escalates to 10% over time. JPMorgan Chase matches up to 5% dollar-for-dollar, but only after one year of service [JPMC Empower 401(k) Savings Plan.txt].

Example 2 - eligibility/rule-based answer:
Context:
[JPMC Paid TimeOff.txt] To qualify for Parental Leave, employees must be actively employed on a U.S. payroll, regularly scheduled to work 20 or more hours per week, and have benefits-eligible status. New hires are eligible once they meet benefits eligibility.

Question: I just started - am I eligible for parental leave right away?
Answer: Only once you meet benefits-eligible status (regularly scheduled 20+ hours/week, not temporary/seasonal/contingent) - there's no separate waiting period beyond that [JPMC Paid TimeOff.txt].

Example 3 - tiered/multi-value answer:
Context:
[JPMC Guild Tuition Assistance.txt] 100% tuition coverage for select undergraduate and master's degree programs. Up to $7,500 annually for other graduate programs and certificates. Up to $5,250 annually for other undergraduate programs.

Question: How much tuition assistance do I get for a certificate program?
Answer: Up to $7,500 per year, unless it's one of the select degree programs covered at 100% - certificates fall under the graduate/certificate tier, not the fully-covered tier [JPMC Guild Tuition Assistance.txt].

Example 4 - refusal when the context doesn't cover it:
Context:
[JPMC Healthcare Benefits.txt] Medical plans: Aetna, Cigna Healthcare, UnitedHealthcare, Centivo. Dental plans: MetLife, Delta Dental. Vision plan: VSP.

Question: Does JPMC offer a monthly gym membership stipend?
Answer: I don't have that information in the available documents - the healthcare benefits context covers medical, dental, and vision plans, but says nothing about a gym stipend.

Now answer using only the context below:

Context:
{context}"""

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_TEMPLATE),
        ("human", "{question}"),
    ]
)


def _build_context(chunks: list[dict]) -> str:
    """One block per chunk, labeled with its source filename so the model's
    own answer can reference where a fact came from."""
    blocks = []
    for chunk in chunks:
        blocks.append(f"[{chunk['filename']}, chunk {chunk['chunk_index']}]\n{chunk['text']}")
    return "\n\n".join(blocks)


def _to_result(message: AIMessage) -> dict:
    # GatewayChatModel sets response_metadata["model"] - StrOutputParser()
    # alone would discard it, and this app's response needs model_used too.
    return {"answer": message.content, "model_used": message.response_metadata.get("model", "unknown")}


def generate_answer(
    query: str,
    chunks: list[dict],
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict:
    """Returns {"answer": str, "model_used": str} - model_used is the
    actually-resolved model."""
    if not chunks:
        logger.info("No chunks retrieved for %r - returning the no-context answer, not calling the LLM", query)
        return {"answer": NO_CONTEXT_ANSWER, "model_used": model_name or get_client_gateway().openai_chat().model}

    llm = GatewayChatModel(
        provider=LlmProvider.OPENAI,
        temperature=temperature,
        model_name_override=model_name,
        max_tokens=max_tokens,
    )
    chain = RAG_PROMPT | llm | RunnableLambda(_to_result)

    context = _build_context(chunks)
    result = chain.invoke({"context": context, "question": query})

    logger.info("Generated a %d-character answer from %d chunk(s)", len(result["answer"]), len(chunks))
    return result
