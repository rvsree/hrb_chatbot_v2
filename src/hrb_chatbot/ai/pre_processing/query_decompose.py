"""Query decomposition (Phase 5.1) - resolved, not built, as of Phase 68 (2026-10-04).

Live-tested whether a same-domain compound question (two different KB
topics in one query) needs a separate decomposition step before retrieval.
It doesn't: the Planner Agent (ai/agents/workflow_agents/planner_agent.py,
Phase 64) already splits it into two focused vector_kb_agent tasks on its
own, no prompt change needed - verified live, both the Planner's split and
the resulting retrieval/answer were correct (see RAG-ROADMAP.md Phase 68
and the golden-dataset case multi-agent-same-domain-01). A separate
decomposition component here would duplicate work the Planner already does.

Still genuinely open: genai-rag's own non-agentic pipeline
(ai/rag_pipeline/pipeline.py) has no Planner/agent step, so a same-domain
compound question there is not covered by this finding - a different,
unraised question, not resolved by this phase.
"""
