"""Task processing utilities for filtering, extracting, and structuring tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, cast

# Phrases to filter out as conversational noise
CONVERSATIONAL_NOISE = {
    "thank you",
    "thanks",
    "thankyou",
    "thx",
    "ty",
    "brb",
    "be right back",
    "ok",
    "okay",
    "k",
    "kk",
    "got it",
    "gotcha",
    "understood",
    "roger",
    "copy",
    "10-4",
    "lol",
    "haha",
    "hehe",
    "lmao",
    "lmfao",
    "nice",
    "great",
    "awesome",
    "perfect",
    "good",
    "excellent",
    "wow",
    "cool",
    "yep",
    "yes",
    "no",
    "nope",
    "nah",
    "sure",
    "of course",
    "np",
    "no problem",
    "you're welcome",
    "welcome",
    "hi",
    "hello",
    "hey",
    "morning",
    "afternoon",
    "evening",
    "bye",
    "goodbye",
    "cya",
    "see ya",
    "ttyl",
    "talk to you later",
    "done",
    "finished",
    "completed",
}

# Urgency keywords
URGENCY_KEYWORDS = {
    "asap": 3,
    "urgent": 3,
    "critical": 3,
    "emergency": 3,
    "blocked": 2,
    "stuck": 2,
    "help": 2,
    "issue": 2,
    "problem": 2,
    "error": 2,
    "broken": 2,
    "bug": 2,
    "deadline": 2,
    "due": 2,
    "today": 2,
    "tomorrow": 1,
    "priority": 1,
    "important": 1,
}

# Task indicators
TASK_INDICATORS = [
    r"^\s*[-•\*]\s+",  # Bullet points
    r"\btask\b",
    r"\btodo\b",
    r"\bto-do\b",
    r"\baction\b",
    r"\bfix\b",
    r"\bupdate\b",
    r"\badd\b",
    r"\bcreate\b",
    r"\bbuild\b",
    r"\bimplement\b",
    r"\bcomplete\b",
    r"\breview\b",
    r"\bcheck\b",
    r"\btest\b",
    r"\bdeploy\b",
    r"\blaunch\b",
]

DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
    re.IGNORECASE,
)

MENTION_RE = re.compile(r"<@([A-Z0-9]+)>")
URL_RE = re.compile(r"<https?://[^|>]+")


@dataclass
class Task:
    """Structured task representation."""

    text: str
    channel: str
    owner: str
    timestamp: str = ""
    permalink: str = ""
    source: str = "slack"
    status: str = "Open"
    priority: str = ""
    due_date: str = ""
    client: str = ""
    task_type: str = ""
    urgency_score: int = 0
    is_actionable: bool = True
    mentions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    """Normalize text by collapsing whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def extract_text_from_message(msg: dict[str, Any]) -> str:
    """Extract text from a Slack message."""
    text = msg.get("text") or ""
    if text:
        return text
    blocks = msg.get("blocks") or []
    for block in blocks:
        if isinstance(block, dict):
            btext = block.get("text", {})
            if isinstance(btext, dict):
                t = btext.get("text")
                if t:
                    return cast(str, t)
    return ""


def is_conversational_noise(text: str) -> bool:
    """Check if text is just conversational noise."""
    normalized = normalize_text(text).lower()

    # Check if it's just noise phrases
    words = set(re.findall(r"\b\w+\b", normalized))
    if len(words) <= 3 and any(phrase in normalized for phrase in CONVERSATIONAL_NOISE):
        return True

    # Check if text is too short
    if len(normalized) < 20:
        return True

    # Check if it's just emojis and mentions
    text_without_mentions = MENTION_RE.sub("", normalized)
    text_without_urls = URL_RE.sub("", text_without_mentions)
    text_clean = re.sub(r"[:\s]", "", text_without_urls)
    if len(text_clean) < 10:
        return True

    return False


def calculate_urgency_score(text: str) -> int:
    """Calculate urgency score based on keywords."""
    normalized = text.lower()
    score = 0
    for keyword, weight in URGENCY_KEYWORDS.items():
        if keyword in normalized:
            score += weight
    return min(score, 5)  # Cap at 5


def extract_mentions(text: str) -> list[str]:
    """Extract Slack user mentions from text."""
    return MENTION_RE.findall(text)


def extract_client_from_channel(channel_name: str) -> str:
    """Extract client name from channel name."""
    # Remove common prefixes
    prefixes = ["ss-", "mpdm-"]
    name = channel_name
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix) :]

    # Handle project channels
    if "-website" in name:
        parts = name.split("-website")[0].split("-")
        # Capitalize each part
        return " ".join(part.capitalize() for part in parts)

    # Handle dm channels
    if "--" in name:
        parts = name.split("--")
        return ", ".join(part.capitalize() for part in parts[:3])

    return name.replace("-", " ").title()


def extract_due_date(text: str) -> str:
    """Extract due date from text."""
    match = DATE_RE.search(text)
    return match.group(0) if match else ""


def determine_task_type(text: str) -> str:
    """Determine the type of task based on keywords."""
    normalized = text.lower()

    type_keywords = {
        "bug": ["bug", "fix", "broken", "error", "issue"],
        "feature": ["add", "create", "implement", "build", "new"],
        "content": ["content", "copy", "text", "write", "page"],
        "design": ["design", "layout", "css", "style", "ui", "ux"],
        "review": ["review", "check", "verify", "approve"],
        "deployment": ["deploy", "launch", "publish", "go live"],
        "update": ["update", "change", "modify", "edit"],
        "seo": ["seo", "meta", "keywords", "ranking"],
        "integration": ["integrate", "connect", "api", "webhook"],
    }

    for task_type, keywords in type_keywords.items():
        if any(kw in normalized for kw in keywords):
            return task_type

    return "general"


def is_likely_task(text: str) -> bool:
    """Determine if text is likely to be a task (general channels)."""
    normalized = normalize_text(text).lower()

    # Check for task indicators anywhere
    for indicator in TASK_INDICATORS:
        if re.search(indicator, normalized, re.IGNORECASE):
            return True

    # Questions that are likely requests
    if "?" in text and any(word in normalized for word in ["can", "could", "would", "please", "help"]):
        return True

    # Action verbs at start
    action_starts = [
        "need",
        "should",
        "must",
        "please",
        "can you",
        "could you",
        "would you",
    ]
    for start in action_starts:
        if normalized.startswith(start):
            return True

    return False


def is_likely_task_dm(text: str) -> bool:
    """Stricter task detection for DMs to reduce false positives."""
    normalized = normalize_text(text).lower()

    # Down-rank planning / FYI chatter common in DMs.
    non_task_markers = [
        "not for today",
        "fyi",
        "just letting you know",
        "heads up",
        "no worries",
        "haha",
        "lol",
        "soon as",
        "i'll let you know",
        "i will let you know",
    ]
    if any(m in normalized for m in non_task_markers):
        return False

    # Accept strong explicit patterns.
    strong_starts = [
        "todo:",
        "to-do:",
        "task:",
        "action:",
        "please",
        "can you",
        "could you",
        "would you",
        "need",
        "must",
        "should",
    ]
    if any(normalized.startswith(s) for s in strong_starts):
        return True

    # Bullets are usually actionable in DMs.
    if re.search(r"^\s*[-•\*]\s+", text):
        return True

    # A direct question request.
    if "?" in text and any(word in normalized for word in ["can", "could", "would", "please", "help"]):
        return True

    # Otherwise, be conservative in DMs.
    return False


def process_message(
    msg: dict[str, Any],
    channel_name: str,
    owner: str,
    team_members: set[str] | None = None,
) -> Task | None:
    """Process a Slack message into a structured Task."""
    text = normalize_text(extract_text_from_message(msg))

    if not text:
        return None

    # Filter conversational noise
    if is_conversational_noise(text):
        return None

    # Check if relevant to team
    if team_members and owner not in team_members:
        mentions = extract_mentions(text)
        if not any(m in team_members for m in mentions):
            return None

    # Determine if actionable (DMs are stricter to reduce false positives)
    if channel_name.startswith("dm--"):
        is_actionable = is_likely_task_dm(text)
    else:
        is_actionable = is_likely_task(text)

    # Calculate urgency
    urgency_score = calculate_urgency_score(text)

    # Extract due date
    due_date = extract_due_date(text)

    # Extract client
    client = extract_client_from_channel(channel_name)

    # Determine task type
    task_type = determine_task_type(text)

    # Extract mentions
    mentions = extract_mentions(text)

    # Determine priority
    priority = ""
    if urgency_score >= 3:
        priority = "High"
    elif urgency_score >= 2:
        priority = "Medium"
    elif is_actionable:
        priority = "Low"

    # Extract tags
    tags = []
    if "ticket" in text.lower():
        tags.append("ticket")
    if "notion" in text.lower():
        tags.append("notion")
    if "bug" in text.lower():
        tags.append("bug")
    if "urgent" in text.lower() or "asap" in text.lower():
        tags.append("urgent")

    return Task(
        text=text,
        channel=channel_name,
        owner=owner,
        timestamp=msg.get("ts", ""),
        permalink=msg.get("permalink", ""),
        source="slack",
        status="Open",
        priority=priority,
        due_date=due_date,
        client=client,
        task_type=task_type,
        urgency_score=urgency_score,
        is_actionable=is_actionable,
        mentions=mentions,
        tags=tags,
    )


def deduplicate_tasks(tasks: list[Task]) -> list[Task]:
    """Remove duplicate tasks based on text similarity."""
    seen: set[str] = set()
    unique_tasks: list[Task] = []

    for task in tasks:
        # Create a normalized key for comparison
        normalized_text = re.sub(r"\s+", " ", task.text.lower())
        normalized_text = MENTION_RE.sub("", normalized_text)
        normalized_text = URL_RE.sub("", normalized_text)
        normalized_text = normalized_text.strip()

        # Use first 100 chars as key
        key = normalized_text[:100]

        if key not in seen:
            seen.add(key)
            unique_tasks.append(task)

    return unique_tasks


def group_tasks_by_owner(tasks: list[Task]) -> dict[str, list[Task]]:
    """Group tasks by owner."""
    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        owner = task.owner or "Unknown"
        if owner not in grouped:
            grouped[owner] = []
        grouped[owner].append(task)
    return grouped


def group_tasks_by_client(tasks: list[Task]) -> dict[str, list[Task]]:
    """Group tasks by client."""
    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        client = task.client or "General"
        if client not in grouped:
            grouped[client] = []
        grouped[client].append(task)
    return grouped


def filter_actionable_tasks(tasks: list[Task]) -> list[Task]:
    """Filter to only actionable tasks."""
    return [t for t in tasks if t.is_actionable]


def sort_tasks_by_priority(tasks: list[Task]) -> list[Task]:
    """Sort tasks by urgency score (highest first)."""
    return sorted(tasks, key=lambda t: (t.urgency_score, t.priority), reverse=True)
