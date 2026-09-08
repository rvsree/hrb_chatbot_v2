# FAQ - RAG design questions, for gap-finding and interview prep

Deep-dive answers to specific RAG design questions, each split into **what
this project actually does today** (verified against the real code, not
assumed) and **the broader answer** (what a production system typically
does, and why) - written so the two are never confused with each other.
Use this list itself as an interview prep checklist: each heading below is
a question worth being able to answer cold. Sections 4 and 5 switch to a
mock-interview Q&A format for performance and evaluation-metric
questions - golden datasets, A/B testing, eval tooling, and (section 5's
closing table) a real diagnostic framework for turning "the metric is bad"
into "here's the specific layer to fix" - the kind of question an FDE
interview round tends to probe hardest.

---

## 1. How do you update an existing document - full re-index or selective section update?

**What this project does today**: full re-index only. `ai/doc_processing/indexing/vector_indexer.py`'s
`write_chunks()` re-chunks, re-embeds, and re-upserts the *entire* document
every time `POST /rag/documents/{id}/index` is called again - there is no
concept of "only section 3 changed, only re-embed section 3." Deterministic
chunk ids (`f"{document_id}:{chunk_index}"`) mean re-upserting naturally
overwrites chunks that still exist at the same position; a real
insert-vs-update distinction only shows up in stale-chunk cleanup - if the
new version produces *fewer* chunks than the old one, the extra old ones
(now orphaned) are explicitly deleted rather than left behind. See that
file's own docstring for the full reasoning.

**Why selective (section-level) update is harder, and what it needs**:
To re-embed only a changed section, you need three things this project
doesn't have yet:
1. **Stable section ids that survive an edit** - something like a markdown
   heading or a PDF bookmark id, not just "chunk number 7," because chunk
   *numbers* shift the instant text is added or removed anywhere earlier
   in the document, corrupting the "only chunk 7 changed" assumption on
   the very next edit.
2. **A diff step** - some way to know section 3 changed and sections 1, 2,
   4 didn't, before deciding what to re-embed.
3. **Chunk metadata tagged with which section it belongs to**, so "delete
   and re-insert every chunk under section 3" is a metadata-filtered
   operation, not a full-document one.

This connects directly to **document-structure-based chunking** (one of
the strategies planned for this project) - a chunker that already
respects document sections naturally produces chunks with a stable
section id in their metadata, which is most of what selective update
needs "for free," rather than needing a separate mechanism bolted on
after the fact.

**Timestamp-based retrieval - a related but different question**: "fetch
documents based on timestamp" usually means one of two things, and they
need different designs:
- **"Always prefer the newest version"** - this project's full-re-index
  design already gives this for free, implicitly: because old chunks are
  deleted on re-index rather than versioned, the vector store only ever
  contains the latest version of anything. No timestamp filter is needed
  because there's nothing older left to filter out.
- **"Answer as of a specific past date"** (e.g., "what was the leave
  policy before 2025?") - this is a genuinely different requirement:
  *keeping* old versions rather than deleting them, tagging each chunk
  with an `effective_date`/`version` in its metadata, and filtering by
  that field at query time (`where={"effective_date": {"$lte": query_date}}`
  in Chroma/Pinecone's own filter syntax). This project doesn't do this
  today, and adding it later means changing the "stale chunks get
  deleted" behavior, not just adding a filter on top of it.

---

## 2. Where does metadata live, and which store is ideal for filtering during RAG search - is that the vector database?

Short version: **two stores, two different jobs** - not one store doing
everything, and not really a choice between them.

Right now, this project keeps metadata in two places. The vector store
itself (Chroma or Pinecone) holds a small amount of metadata on every
chunk - `document_id`, `chunk_index`, and for Pinecone the raw chunk text
too, since Pinecone doesn't have a native "document" field the way Chroma
does. Separately, SQLite (Postgres is the tested alternative) holds one
row per *document* - filename, upload status, timestamps, the list of
chunk ids. That second one is really just application bookkeeping - "what
got uploaded, is it indexed yet" - not something retrieval reaches into.

So is the vector database the *right* place for metadata? For the bit
that needs to filter the search itself - yes, has to be. `where`/`filter`
in Chroma and Pinecone runs *during* the similarity search, not after -
same pass that finds the closest vectors also throws out the ones that
don't match your filter. Filter after the fact instead (pull back
everything similar, then discard in your own code) and you've thrown away
most of what made the ANN search fast in the first place.

But for everything else - who owns a document, access control, audit
history, anything that needs a join - that's not what a vector database
is built for. So in practice you end up duplicating a *small*,
retrieval-relevant slice of metadata into the vector store's own
per-chunk fields (category, effective date, whatever a query needs to
filter on), and keeping the full, authoritative record in a real
database. That's exactly the split this project already has -
`metadata_store()` vs. `vector_store()` in `db_gateway.py` - and it's the
same idea LlamaIndex formalizes as a separate `DocStore` / `IndexStore` /
`VectorStore` rather than one store trying to do all three jobs.

---

## 3. How are indexes created, and did you classify documents into categories to speed up search?

**What "index" means here - two different things worth not confusing**:
in this project's code, "index" (`POST /rag/documents/{id}/index`, `index_document()`)
means *writing a document's chunks into the vector store* - an
application-level operation. The vector store's own internal search
*structure* (an ANN index - typically HNSW for both Chroma and Pinecone)
is built and maintained automatically by Chroma/Pinecone themselves, not
manually tuned or even visible in this project's code. Chroma's collection
is created lazily via `get_or_create_collection()`;
Pinecone's index is created explicitly by `_ensure_index()` with a fixed
dimension/metric, because unlike a Chroma collection, a Pinecone index is
a real provisioned resource that has to exist before any vector can be
written to it.

**Did this project classify documents into categories? No - not yet.**
Every document goes into one flat collection/namespace
(`vector_indexer.COLLECTION_NAME = "hrb_chatbot_kb"`) regardless of
whether it's a 401(k) plan, a healthcare policy, or a tuition benefit.
There is no category field, no per-category sub-index, and no
classification step anywhere in the pipeline today.

**How categorization would actually speed up (and improve) search, and
the two ways to do it**:
1. **Metadata-based pre-filtering** (the lighter-weight option, and the
   natural first step given this project's existing `where`/`filter`
   support): tag each chunk's metadata with a category
   (`"benefit_type": "leave"` / `"healthcare"` / `"401k"` / `"tuition"`),
   then filter to the right category before or during the ANN search.
   This mostly buys **precision**, not raw speed, at this project's
   current scale (six documents, roughly 250 chunks total) - it stops a
   401(k) chunk from ever competing with a real match from the healthcare
   policy, which matters more here than shaving milliseconds off a search
   that's already sub-second either way.
2. **Separate collections/namespaces per category** (heavier-weight):
   one Chroma collection or Pinecone namespace per category instead of one
   shared one - genuinely faster per-search since each search only ever
   scans one category's worth of vectors, but it requires knowing *which*
   category to search *before* the vector search runs. That means a
   classification step ahead of retrieval - either a lightweight
   classifier or (more commonly in a RAG pipeline already calling an LLM
   anyway) folding it into the same LLM call already planned for **query
   decomposition** (Phase 5.1) - "which of these N categories does this
   question belong to" is a natural first sub-question, not a separate
   system.

**Where this is heading, and why it matters now, not just later**: the
document-structure-based chunking strategy already planned for this
project is a natural, cheap source of category metadata - a chunk that
already knows "I came from Section 2: Critical Caregiver Leave" can carry
that as a category tag for free, without a separate classification pass.
Worth designing the chunker's output shape with this in mind from the
start, rather than retrofitting category tags onto chunks that were never
built to carry them.

**Real scale, for calibration**: at six documents this is a non-issue
either way - a flat collection with no filtering already answers in low
tens of milliseconds. Category-based pre-filtering and per-category
namespaces earn their complexity once a knowledge base reaches thousands
of documents and tens of thousands of chunks, where an unfiltered search
genuinely has more to sift through and precision genuinely degrades from
unrelated categories crowding the top-k results. Building it now, on six
documents, is really about learning the pattern before it's load-bearing -
which is exactly the position this project is in.

---

## 4. Mock interview: performance, faithfulness, and evaluation metrics

Framed as an actual FDE interview round would go - a question, then the
answer you'd want to give, grounded in this project's real specifics
wherever it can be rather than textbook definitions alone. Worth
practicing saying these out loud, not just reading them.

### "How would you go about optimizing this RAG pipeline's performance?"

Break it into the three stages a request actually passes through, because
"performance" means something different at each one:

- **Indexing time** (happens once per document, not per query) - chunk
  size/overlap trade off chunk count against context quality; embedding
  calls batch naturally (`get_embeddings()` here already takes a list, not
  one call per chunk - 45 chunks is one API call, not 45).
- **Retrieval time** (per query, latency-sensitive) - `top_k` tuning
  (fewer candidates = faster, but risks missing the right chunk),
  metadata pre-filtering to shrink the search space before the ANN search
  runs (see question 3), and eventually a reranker if embedding-similarity
  alone isn't precise enough - a fast, cheap first pass followed by a
  slower, more accurate rerank of just the top candidates.
- **Generation time** (usually the biggest single cost) - a smaller/
  cheaper model for query decomposition than for the final answer (you
  don't need your best model to split a question into sub-questions),
  and prompt caching (both OpenAI and Anthropic support this) if the same
  system prompt or context repeats across calls.

And the honest first move, before touching any of that: **you can't
optimize what you can't see**. This project didn't have per-call latency
visibility at all until a recent pass added `log_backend_call()` around
every LLM and vector-store call - now every index or query logs its own
duration (`embeddings.create succeeded in 2184.2ms`, `vector.upsert
succeeded in 145.3ms`). That's the actual starting point for any real
optimization work: measure which stage is slow *first*, then optimize
that one, not the one that feels slow.

### "What does 'faithfulness' or 'groundedness' mean, and how do you measure it?"

A grounded (or faithful) answer is one where every claim traces back to
the retrieved context - the model isn't allowed to add anything from its
own training data, even if that added fact happens to be true. This
matters most in exactly this project's domain: an HR benefits chatbot
that confidently states a wrong number of parental-leave weeks is worse
than one that says "I don't have that in my sources," because someone
might actually act on it.

How it's measured in practice: usually an **LLM-as-judge** pass - a
second model call, given the generated answer and the retrieved chunks,
asked to score whether each claim in the answer is actually supported by
that context (sometimes phrased as an entailment check: does the context
*entail* the claim, the same task NLI models are trained on). This
project's golden dataset already has a head start on this - the
adversarial cases (`edge-out-of-scope-01`, `edge-adversarial-numeric-01`)
exist specifically to catch a model that answers confidently instead of
admitting it doesn't know, or that agrees with a wrong number instead of
correcting it.

### "What does 'completeness' mean for a RAG answer, and how would you check it?"

Different failure mode than faithfulness: a completely faithful answer
can still be *incomplete* if the question had multiple parts and the
answer only covers one. "How does parental leave interact with FMLA, and
what happens to my 401(k) contributions during it?" has (at least) two
sub-answers - a response that's 100% accurate about FMLA but silent on
the 401(k) part is faithful and incomplete at the same time.

Checking it usually means either an LLM-as-judge again (asked
specifically "does this answer address every part of the question," not
just "is this true"), or a checklist-style check against known required
facts. This project's golden dataset already has a lightweight version of
the second approach - `expected_keywords` on every case
(`resources/golden_dataset/golden_dataset.json`) is exactly a checklist:
a real evaluator would check what fraction of those keywords actually
show up in the generated answer, which is a cheap, deterministic proxy
for completeness before ever reaching for an LLM judge.

### "Walk me through Precision@K, Recall@K, and F1 - and how would you compute them here?"

For one query, at cutoff K:
- **Precision@K** = (number of retrieved chunks in the top K that are
  actually relevant) / K - "of what I handed the model, how much was
  useful."
- **Recall@K** = (number of relevant chunks retrieved in the top K) /
  (total number of relevant chunks that exist anywhere in the corpus for
  that query) - "of everything that mattered, how much did I actually
  find."
- **F1@K** = the harmonic mean of the two: `2 * Precision@K * Recall@K /
  (Precision@K + Recall@K)` - useful when you need one number and don't
  want to optimize one metric at the other's expense (retrieving
  everything gets perfect recall and terrible precision; retrieving
  nothing relevant-looking gets neither).

**The honest gap, worth naming unprompted in an interview, not waiting to
be asked**: computing these for real needs *chunk-level* relevance
labels - for a given question, exactly which chunks are the right ones to
retrieve. This project's golden dataset only labels `expected_source_document`
(which *document* the answer should come from), not which specific chunks
within it. That's enough to evaluate document-level retrieval, but not
enough to compute a real Precision@K/Recall@K today - extending the
golden dataset with chunk-level ground truth (or the specific sentence/
section a fact came from) is the concrete next step before those metrics
could actually be computed here, not just defined.

---

## 5. Mock interview, continued: golden datasets, A/B testing, eval tooling, and where to actually fix a bad metric

### "In your own words - what is a golden dataset, and what's it actually for?"

A fixed, hand-curated set of (input, expected output) pairs that acts as
ground truth - the thing every future change gets measured against
instead of eyeballing "does this feel better." Without one, "I improved
the prompt" is a feeling; with one, it's "Precision@3 went from 0.62 to
0.71 on the same 22 questions, and none of the other 21 regressed."

Concretely, this project's own
`resources/golden_dataset/golden_dataset.json` is one: 22 cases, each
with a real question, the document it should be grounded in, and either
an expected answer/keywords or (for the adversarial cases) an explicit
expectation that the system *shouldn't* confidently answer at all. Every
fact in it was pulled from the real PDF text, not invented - a golden
dataset built from guessed answers is worse than no golden dataset,
because it fails silently: a wrong "expected" answer makes a *correct*
system look broken.

**Use case**: regression testing. Change `chunk_size` from 1000 to 500,
rerun all 22 cases, compare. If case 3 got better but case 17 (which used
to retrieve cleanly) now fails, you've caught a real trade-off *before*
it ships, not after a user complains that a previously-working question
now gets a wrong answer.

### "How would A/B testing actually work here, concretely - not just 'try two things and see'?"

Two flavors, and it matters which one you mean:

- **Offline A/B (evaluation-time)** - run configuration A and
  configuration B against the *same* golden dataset, compare a metric
  deterministically, no live users involved. This is what
  `tests/hrb_chatbot/test_ab_testing_demo.py` demonstrates the shape of
  today (chunk_size 300 vs. 1000, comparing chunk count) - swap the metric
  for something like average Precision@3 across all 22 golden-dataset
  cases once retrieval is real, and the same test structure holds.
  Fast, cheap, repeatable - the right place to start.
- **Online A/B (production traffic)** - route a percentage of *real*
  user queries to variant B, measure a real outcome (thumbs-up rate,
  follow-up-question rate, session abandonment), and check the difference
  is bigger than random noise (a t-test, or something simpler like a
  confidence interval on the difference) before trusting it. Needs real
  traffic volume to mean anything - not something a six-document, single-
  user project like this one has yet, but the natural next step once it
  does.

**Concrete example use case for this project**: comparing
`text-embedding-3-small` (1536 dimensions, cheaper) against
`text-embedding-3-large` (3072 dimensions, pricier) - offline A/B first
(does Recall@5 actually improve enough on the golden dataset to justify
2x the embedding cost and needing to re-index everything?), and only
then, if it's genuinely close, consider an online test.

### "What eval scoring methods or libraries would you actually use?"

Two families, and they trade off cost against nuance:

- **Deterministic / rule-based** - no LLM call, fast, cheap, but rigid.
  Exact match, keyword/substring presence (exactly what
  `expected_keywords` in this project's golden dataset already gives you
  for free), or embedding-similarity between the generated answer and a
  reference answer (catches paraphrases exact-match would miss, but
  "similar wording" isn't the same claim as "correct").
- **LLM-as-judge** - a second model call scores faithfulness,
  completeness, or relevance against a rubric. More flexible, catches
  what keyword-matching can't, but costs real money per evaluation run
  and needs its own calibration (a judge model can be inconsistent
  between runs, or biased toward longer/more confident-sounding answers).

**Libraries actually built for this**: **RAGAS** is the one purpose-built
for RAG specifically - faithfulness, answer relevancy, context precision,
and context recall as first-class metrics, and it's worth naming
by name in an interview because it's the closest thing to an industry
standard here. **DeepEval** and **TruLens** cover similar ground with
different integration styles. **LangSmith's** own dataset + evaluator
framework is the natural fit *for this project specifically*, since
LangSmith tracing is already the planned next step for the logging just
added (`call_logger.py`) - the same traces LangSmith would capture are
what an evaluator would score. For plain retrieval metrics once
chunk-level labels exist (see question 3 above), scikit-learn's
`precision_score`/`recall_score`/`f1_score` are enough - no RAG-specific
library needed for that part.

### "Given a metric that's bad, how do you know whether to fix chunking, retrieval, generation, context engineering, or the LLM call itself?"

This is the actual skill, more than knowing the metric definitions - a
bad end-to-end score doesn't say *where* the problem is on its own. Work
it as a decision tree, checking retrieval before generation, since a
wrong answer built on the wrong context can't be fixed by prompting
alone:

| Symptom | Likely layer | What to check first | Example fix |
|---|---|---|---|
| Right chunk never shows up in top K at all | **Chunking / indexing** | Is the fact split awkwardly across two chunks? Is a chunk too large and noisy, diluting its embedding? | Adjust `chunk_size`/`chunk_overlap`, or switch to document-structure-based chunking so a section stays whole |
| Right chunk shows up, but ranked low (e.g. #6 when `top_k=5`) | **Retrieval tuning** | Is `top_k` just too small? Would a reranker (cheap embedding search, then a slower/pricier rerank of the candidates) help? | Raise `top_k`, or add a rerank pass |
| Right chunks retrieved (Precision@K looks fine), but the answer states facts not in them | **Generation / prompt** | Is the "only use the provided context" instruction actually strong enough? Is temperature too high? | Strengthen the anti-hallucination instruction (Workshop Module 4's own focus), lower `temperature` toward 0 |
| Retrieval and faithfulness both fine, but a multi-part question only gets a partial answer | **Context engineering** | Is `top_k` too low to cover every sub-topic? Is the question being decomposed into sub-questions at all? | Raise `top_k`, or add query decomposition (Phase 5.1) so each sub-question gets its own retrieval pass |
| Answer quality is fine but inconsistent across repeated runs of the same question | **LLM call parameters** | What's `temperature` actually set to? | This project already defaults `temperature=0.0` for exactly this reason - see `models/rag.py`'s own field description |
| Everything above looks fine, but it's *slow* | **Measure, don't guess** | Which stage is actually slow - embedding, vector search, or generation? | Read the per-call duration logs `log_backend_call()` already produces (see question 4's performance answer) before touching anything |

The general rule underneath the table: **retrieval problems have
generation-layer symptoms, but generation problems never fix retrieval-
layer causes** - a beautifully-prompted model still can't answer
correctly from the wrong chunk. Check retrieval quality (would a human,
looking only at the retrieved chunks, be able to answer the question at
all?) before touching the prompt.
