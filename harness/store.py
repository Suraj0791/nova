import json
import os
from pathlib import Path

def save_facts(state_dir: str, facts: list[dict]) -> None:
    """Append facts to facts.jsonl in the state directory."""
    if not facts:
        return
    facts_file = Path(state_dir) / "facts.jsonl"
    with facts_file.open("a", encoding="utf-8") as f:
        for fact in facts:
            f.write(json.dumps(fact) + "\n")

def load_facts(state_dir: str) -> list[dict]:
    """Load all facts from facts.jsonl."""
    facts_file = Path(state_dir) / "facts.jsonl"
    if not facts_file.is_file():
        return []
    facts = []
    with facts_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                facts.append(json.loads(line))
    return facts

def save_feedback(state_dir: str, feedback_data: dict) -> None:
    """Append a feedback file's content to feedback.jsonl."""
    feedback_file = Path(state_dir) / "feedback.jsonl"
    with feedback_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(feedback_data) + "\n")

def load_feedback(state_dir: str) -> list[dict]:
    """Load all feedback records from feedback.jsonl."""
    feedback_file = Path(state_dir) / "feedback.jsonl"
    if not feedback_file.is_file():
        return []
    feedbacks = []
    with feedback_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                feedbacks.append(json.loads(line))
    return feedbacks

def save_cache(state_dir: str, doc_hash: str, extraction: dict) -> None:
    """Save LLM extraction cache."""
    cache_dir = Path(state_dir) / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / f"{doc_hash}.json"
    cache_file.write_text(json.dumps(extraction, indent=2), encoding="utf-8")

def load_cache(state_dir: str, doc_hash: str) -> dict | None:
    """Load LLM extraction cache if it exists."""
    cache_file = Path(state_dir) / "cache" / f"{doc_hash}.json"
    if cache_file.is_file():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return None
