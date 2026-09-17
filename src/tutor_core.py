"""
tutor_core.py
=============
Turns a document (PDF, DOCX, or plain text) into a deck of flashcards
using a subject-specific persona, then pushes them straight into a
running Anki desktop instance via the AnkiConnect add-on.

No web framework code here — this module is pure logic, importable and
testable on its own.
"""
import os
import logging
import requests
from pathlib import Path

from pydantic import BaseModel, Field
from typing import List

from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pypdf import PdfReader
import docx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("tutor_agent.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
ANKI_CONNECT_URL = os.environ.get("ANKI_CONNECT_URL", "http://localhost:8765")

PERSONAS = {
    "cs": {
        "label": "Computer Science",
        "instructions": """
        You are an expert Computer Science professor. Read the text and identify ONLY the most critical concepts:
        - Algorithms and Big-O notation
        - Code syntax, best practices, and design patterns
        - System architecture and technical definitions
        Ignore filler text. Create highly technical flashcards.
        """,
    },
    "language": {
        "label": "Language Learning",
        "instructions": """
        You are an expert Language Tutor. Read the text and identify ONLY the most critical concepts:
        - Important vocabulary words and their definitions
        - Grammar rules and conjugations
        - Idioms and cultural context
        Ignore filler text. Create flashcards to help a student become fluent.
        """,
    },
    "general": {
        "label": "General Study Notes",
        "instructions": """
        You are an expert tutor across any subject. Read the text and identify the most
        important facts, definitions, and relationships a student would need to
        remember. Ignore filler text, examples used only for illustration, and
        formatting artifacts. Create clear, exam-focused flashcards.
        """,
    },
}


class Flashcard(BaseModel):
    question: str = Field(description="The question to test the user's knowledge.")
    answer: str = Field(description="The concise answer to the question.")


class FlashcardDeck(BaseModel):
    flashcards: List[Flashcard] = Field(description="A list of flashcards generated from the text.")


class AnkiNotReachable(Exception):
    """Anki desktop isn't running, or AnkiConnect isn't installed/enabled."""


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _llm = ChatGroq(groq_api_key=api_key, model_name=GROQ_MODEL, temperature=0.2)
    return _llm


# ==========================================
# Document processing
# ==========================================

def extract_text(file_path: str) -> str:
    """Extract text from a given file (txt, pdf, docx)."""
    ext = Path(file_path).suffix.lower()
    text = ""

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    elif ext == ".pdf":
        reader = PdfReader(file_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    elif ext == ".docx":
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    else:
        raise ValueError(f"Unsupported file extension: {ext}. Please use .txt, .pdf, or .docx")

    if not text.strip():
        raise ValueError("No extractable text found in this file (it may be a scanned/image-only PDF).")
    return text


def chunk_text(text: str) -> List[str]:
    """Splits large documents into safe chunk sizes to avoid API limits."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=4000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
    return text_splitter.split_text(text)


# ==========================================
# AI generation
# ==========================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def process_chunk_with_groq(chunk: str, persona_key: str) -> FlashcardDeck:
    """Sends a chunk of text to Groq and strictly parses the output into the Pydantic model."""
    llm = _get_llm()
    persona = PERSONAS.get(persona_key, PERSONAS["general"])

    prompt = PromptTemplate.from_template(
        """{instructions}

        Material to study:
        {text}
        """
    )

    structured_llm = llm.with_structured_output(FlashcardDeck)
    chain = prompt | structured_llm

    logger.info("Sending chunk to Groq API...")
    return chain.invoke({"instructions": persona["instructions"], "text": chunk})


def generate_flashcards(file_path: str, persona_key: str, progress_cb=None) -> List[Flashcard]:
    """Full pipeline: extract -> chunk -> generate. progress_cb(i, total) is
    called after each chunk if provided, so a caller (e.g. a web UI) can
    show live progress on a potentially multi-minute run."""
    raw_text = extract_text(file_path)
    chunks = chunk_text(raw_text)
    logger.info(f"Document split into {len(chunks)} chunks.")

    all_flashcards = []
    for i, chunk in enumerate(chunks):
        deck = process_chunk_with_groq(chunk, persona_key)
        if deck and deck.flashcards:
            all_flashcards.extend(deck.flashcards)
        if progress_cb:
            progress_cb(i + 1, len(chunks))

    return all_flashcards


# ==========================================
# Anki integration
# ==========================================

def invoke_anki_action(action: str, params: dict):
    """Helper to send requests to AnkiConnect."""
    payload = {"action": action, "version": 6, "params": params}
    try:
        response = requests.post(ANKI_CONNECT_URL, json=payload, timeout=10)
        response_data = response.json()
        if response_data.get("error"):
            logger.error(f"AnkiConnect Error: {response_data['error']}")
        return response_data
    except requests.exceptions.ConnectionError:
        raise AnkiNotReachable(
            "Could not reach Anki. Make sure Anki desktop is open and the "
            "AnkiConnect add-on is installed (Tools -> Add-ons -> Get Add-ons, "
            "code: 2055492159, then restart Anki)."
        )
    except Exception as e:
        logger.error(f"Failed to connect to AnkiConnect: {e}")
        raise


def check_anki_reachable() -> bool:
    try:
        result = invoke_anki_action("version", {})
        return bool(result and not result.get("error"))
    except AnkiNotReachable:
        return False


def push_to_anki(flashcards: List[Flashcard], deck_name: str) -> dict:
    """Creates a deck (if needed) and pushes cards directly into Anki desktop.
    Returns a summary dict: {added, duplicates_skipped, total}."""
    logger.info(f"Connecting to Anki to create deck '{deck_name}'...")

    invoke_anki_action("createDeck", {"deck": deck_name})

    notes = [
        {
            "deckName": deck_name,
            "modelName": "Basic",
            "fields": {"Front": card.question, "Back": card.answer},
            "options": {"allowDuplicate": False},
            "tags": ["AI_Tutor"],
        }
        for card in flashcards
    ]

    result = invoke_anki_action("addNotes", {"notes": notes})
    if result is None or result.get("error"):
        raise RuntimeError(f"Failed to push cards to Anki: {result.get('error') if result else 'no response'}")

    # addNotes returns a list of note IDs, or null per-note for duplicates/failures
    note_ids = result.get("result", [])
    added = sum(1 for n in note_ids if n is not None)
    skipped = len(note_ids) - added
    logger.info(f"Pushed {added} flashcards to Anki ({skipped} skipped as duplicates).")
    return {"added": added, "duplicates_skipped": skipped, "total": len(flashcards)}
