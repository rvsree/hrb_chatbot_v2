# FAQ - RAG design questions, for gap-finding and interview prep

Deep-dive answers to specific RAG design questions, each split into **what
this project actually does today** (verified against the real code, not
assumed) and **the broader answer** (what a production system typically
does, and why) - written so the two are never confused with each other.
Use this list itself as an interview prep checklist: each heading below is
a question worth being able to answer cold.

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

**What this project does today**: metadata lives in **two different
places for two different jobs**, and conflating them is the most common
mistake to watch for:
- **Per-chunk metadata inside the vector store itself** (`document_id`,
  `chunk_index`, and for Pinecone also the raw chunk text, since Pinecone
  has no native "document" field - see `pinecone_client.py`'s docstring).
  This is what `ChromaDBClient.query()`/`PineconeClient.query()`'s `where`
  argument filters against - already wired through
  `BaseVectorDBClient.query()`, not yet called with a real filter anywhere
  since retrieval (Phase 6) isn't built yet.
- **Per-document metadata in a separate relational store** (SQLite today,
  Postgres as a tested alternative) - filename, upload status, timestamps,
  and the `chunk_ids` list. This is application bookkeeping (what got
  uploaded, is it indexed yet), not retrieval filtering - nothing here
  is available inside a vector `where` clause today.

**Is the vector database the ideal place for metadata? Only for the
subset that needs to filter the search itself.** The reason is
mechanical, not stylistic: `where`/`filter` in Chroma and Pinecone is
applied *during* the approximate-nearest-neighbor search (pre-filtering)
- exactly the same operation that finds the closest vectors also excludes
non-matching metadata in the same pass. Filtering *after* the vector
search instead (fetch everything similar, then throw away rows that don't
match in application code) wastes most of the ANN search's precision and
is the wrong default, only excusable at very small scale.

**Which store is ideal in a real-world application - a genuine "both,"
not a pick-one**: vector databases are built for embeddings +
similarity + light metadata filtering; they are not built for rich
relational queries (joins, access-control lists, audit history, full-text
search across metadata, complex aggregate queries). The common real-world
pattern - and what this project's own two-store split already lines up
with - is:
- A **small, retrieval-relevant subset** of metadata duplicated into the
  vector store's own per-chunk fields (category, effective_date,
  document_id - whatever a query actually needs to filter on).
- The **full, authoritative metadata** in a real database (Postgres here)
  for everything else - ownership, access control, versioning, audit
  trail, anything requiring a join or a complex query the vector store was
  never designed to answer.

Frameworks like LlamaIndex formalize this same split explicitly (a
`DocStore` + `IndexStore` + `VectorStore`, not one store doing everything)
- this project's `metadata_store()` vs. `vector_store()` split in
`db_gateway.py` is the same idea under different names.

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
