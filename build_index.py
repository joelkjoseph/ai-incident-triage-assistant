"""
Build the vector index (Step 1 of RAG)

Reads resolution_notes.csv and stores each note in a local ChromaDB
collection, so triage.py can later search it for similar past cases.

This only needs to be run once (or whenever resolution_notes.csv changes) -
the index is saved to disk in ./chroma_db so you don't have to rebuild it
every time you run triage.py.

Run:
    python3 build_index.py
"""

import csv
import chromadb

# PersistentClient saves the index to disk (in a "chroma_db" folder) so it
# survives between runs, rather than living only in memory.
client = chromadb.PersistentClient(path="./chroma_db")

# get_or_create_collection: if this collection already exists from a
# previous run, delete and rebuild it so we don't get duplicate entries.
try:
    client.delete_collection("resolution_notes")
except Exception:
    pass  # collection didn't exist yet, nothing to delete

collection = client.create_collection("resolution_notes")


def load_notes(csv_path: str):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_index():
    notes = load_notes("resolution_notes.csv")

    # Chroma needs three parallel lists: unique IDs, the text to embed and
    # search over, and metadata to retrieve alongside each match.
    ids = [note["note_id"] for note in notes]
    documents = [f"{note['issue_summary']} — {note['resolution']}" for note in notes]
    metadatas = [
        {
            "category": note["category"],
            "issue_summary": note["issue_summary"],
            "resolution": note["resolution"],
        }
        for note in notes
    ]

    # This is the step that actually converts each document's text into an
    # embedding (a vector of numbers capturing its meaning) using Chroma's
    # default local embedding model, and stores it for later search.
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    print(f"Indexed {len(notes)} resolution notes into ./chroma_db")


if __name__ == "__main__":
    build_index()
