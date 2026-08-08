from pathlib import Path


def load_prompt_parts(*paths: str) -> str:
    """Loads and concatenates prompt markdown files."""
    base_dir = Path(__file__).parent.parent
    content = []
    for path in paths:
        full_path = base_dir / path
        if full_path.exists():
            content.append(full_path.read_text(encoding="utf-8"))
        else:
            content.append(f"Prompt part not found: {path}")
    return "\n\n".join(content)
