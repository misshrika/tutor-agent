# AI Tutor Agent

**The problem:** turning a lecture PDF, a textbook chapter, or a set of notes into
actual study flashcards is tedious manual work — reading through the material,
picking out the concepts worth testing yourself on, and typing each one into a
flashcard app by hand. For any document longer than a page or two, this alone
can take longer than actually studying the material.

**What changed:** this tool reads a document, generates flashcards focused on
the concepts that actually matter for the subject (technical concepts for
Computer Science, vocabulary/grammar for language learning, key facts for
general notes), and pushes them straight into a new Anki deck — turning a
document into a ready-to-study deck in the time it takes to read it once.

---

## How it works

1. **Extract.** Reads the uploaded document (PDF, DOCX, or plain text) into raw text.
2. **Chunk.** Splits large documents into ~4000-character pieces with overlap,
   so no concept gets awkwardly split across a chunk boundary and no chunk
   exceeds the model's practical context size.
3. **Generate.** Each chunk is sent to an LLM with subject-specific instructions
   (a genuinely different prompt per persona, not one generic "make flashcards"
   request), forced into a structured question/answer format via Pydantic so
   the output is always parseable, never free-form prose to extract by hand.
4. **Push.** The finished flashcards are sent straight into a running Anki
   desktop instance via the AnkiConnect add-on's local API — no export/import
   step, no CSV to move by hand.

## The engineering worth reading

- **Persona-specific prompts, not one generic instruction.** A Computer
  Science persona is told to focus on algorithms, Big-O notation, and design
  patterns; a Language Learning persona is told to focus on vocabulary,
  grammar rules, and idioms. Same pipeline, meaningfully different flashcard
  quality per subject — a generic "make flashcards from this" prompt produces
  noticeably worse results across the board.
- **Structured output via Pydantic, not manual JSON parsing.** The flashcard
  schema is defined as a typed model and enforced through LangChain's
  structured-output binding, so a malformed response is caught and retried
  rather than silently breaking downstream code.
- **Retry with exponential backoff.** Each API call is wrapped in a retry
  decorator (3 attempts, exponential wait) so a single transient network
  failure doesn't kill a multi-chunk run partway through.
- **Duplicate-safe by default.** Cards are pushed with `allowDuplicate: false`,
  so re-running the tool on the same material (or a document with overlapping
  content) doesn't flood the deck with repeats.
- **A real local integration, not just a file export.** Pushing directly into
  a running desktop application via its local API (AnkiConnect on
  `localhost:8765`) is a different, more useful integration than generating a
  CSV the user then has to import by hand.

## Run it

Requires **Anki desktop** open with the **AnkiConnect** add-on installed
(Tools → Add-ons → Get Add-ons, code `2055492159`, then restart Anki).

```powershell
pip install -r requirements.txt
# Get a free API key at https://console.groq.com -> API Keys
# copy .env.example to .env and add it
cd src
python app.py
```

Open `http://localhost:5000`. Upload a document, pick a subject, name a deck,
and generate — the app checks Anki's connection status live and will tell you
clearly if Anki isn't reachable rather than failing silently.

## Tech stack

Python · Flask · LangChain + `langchain-groq` (free-tier hosted LLM) ·
Pydantic (structured output) · `tenacity` (retry logic) · `pypdf` /
`python-docx` (document parsing) · AnkiConnect (local Anki desktop
integration)

## Note

No API keys or personal study material are committed anywhere in this repo.
