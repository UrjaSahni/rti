"""
Input validation utility for detecting gibberish or meaningless queries.

Validates user input before sending to the LLM to save API costs and
provide better user feedback.
"""
import re
from typing import Tuple

# Common English words for basic validation (RTI-related and general)
COMMON_WORDS = {
    # RTI-specific terms
    "rti", "right", "information", "act", "application", "appeal", "response",
    "department", "ministry", "government", "public", "officer", "pio", "apio",
    "section", "exemption", "fee", "deadline", "days", "penalty", "complaint",
    "cic", "commission", "authority", "disclosure", "transparency", "citizen",
    "applicant", "appellant", "denied", "rejected", "allowed", "partial",
    "transfer", "transferred", "file", "filing", "submit", "submitted",
    
    # Common question words
    "what", "how", "when", "where", "why", "who", "which", "can", "could",
    "would", "should", "will", "does", "do", "is", "are", "was", "were",
    
    # Common verbs
    "get", "give", "take", "make", "know", "need", "want", "find", "ask",
    "tell", "help", "use", "apply", "request", "receive", "send", "pay",
    
    # Common nouns
    "time", "day", "month", "year", "date", "money", "amount", "number",
    "name", "address", "email", "phone", "letter", "document", "form",
    "copy", "record", "report", "notice", "order", "reply", "answer",
    
    # Common adjectives
    "first", "second", "third", "last", "next", "new", "old", "late",
    "free", "paid", "valid", "invalid", "correct", "wrong", "important",
    
    # Common prepositions and articles
    "the", "a", "an", "of", "to", "in", "for", "on", "with", "at", "by",
    "from", "about", "into", "through", "under", "after", "before",
    
    # Common connectors
    "and", "or", "but", "if", "then", "because", "so", "that", "this",
    
    # Numbers as words
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "thirty", "sixty", "ninety", "hundred",
    
    # Indian government terms
    "india", "indian", "central", "state", "district", "block", "gram",
    "panchayat", "municipality", "corporation", "board", "council",
    "railway", "police", "income", "tax", "passport", "aadhar", "pan",
    "epfo", "pf", "pension", "provident", "fund", "employee", "employer",
}


def has_repeated_chars(text: str, threshold: int = 4) -> bool:
    """
    Check if text contains excessive repeated characters.
    
    Args:
        text: Input text to check.
        threshold: Number of consecutive same characters to flag.
    
    Returns:
        True if excessive repetition found.
    """
    # Check for same character repeated
    pattern = r'(.)\1{' + str(threshold - 1) + r',}'
    if re.search(pattern, text.lower()):
        return True
    
    # Check for repeated patterns like "abcabc"
    for length in range(2, 5):
        pattern = r'(.{' + str(length) + r'})\1{2,}'
        if re.search(pattern, text.lower()):
            return True
    
    return False


def has_keyboard_pattern(text: str) -> bool:
    """
    Check if text contains keyboard patterns like 'qwerty', 'asdfgh'.
    
    Args:
        text: Input text to check.
    
    Returns:
        True if keyboard pattern detected.
    """
    keyboard_patterns = [
        "qwerty", "qwert", "asdfg", "asdf", "zxcvb", "zxcv",
        "qazwsx", "1234", "12345", "123456", "abcdef", "abcd",
        "aaaaa", "bbbbb", "xxxxx", "zzzzz",
    ]
    text_lower = text.lower().replace(" ", "")
    return any(pattern in text_lower for pattern in keyboard_patterns)


def count_meaningful_words(text: str) -> int:
    """
    Count how many words in the text are meaningful English words.
    
    Args:
        text: Input text to check.
    
    Returns:
        Number of meaningful words found.
    """
    # Extract words (letters only, min 2 chars)
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    return sum(1 for word in words if word in COMMON_WORDS)


def is_mostly_punctuation(text: str) -> bool:
    """
    Check if text is mostly punctuation or special characters.
    
    Args:
        text: Input text to check.
    
    Returns:
        True if more than 50% is punctuation/numbers.
    """
    if not text:
        return True
    
    letters = sum(1 for c in text if c.isalpha())
    total = len(text.replace(" ", ""))
    
    if total == 0:
        return True
    
    return letters / total < 0.5


def is_lorem_ipsum(text: str) -> bool:
    """
    Check if text appears to be lorem ipsum or similar placeholder text.
    
    Args:
        text: Input text to check.
    
    Returns:
        True if lorem ipsum detected.
    """
    lorem_markers = [
        "lorem ipsum", "dolor sit amet", "consectetur adipiscing",
        "sed do eiusmod", "tempor incididunt", "ut labore",
    ]
    text_lower = text.lower()
    return any(marker in text_lower for marker in lorem_markers)


def is_valid_query(text: str) -> Tuple[bool, str]:
    """
    Validate if a query is meaningful and worth sending to the LLM.
    
    Args:
        text: User's query text.
    
    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is empty string.
    """
    if not text or not text.strip():
        return False, "Please enter a question."
    
    text = text.strip()
    
    # Check minimum length (at least 5 words)
    words = text.split()
    if len(words) < 3:
        return False, "Please enter a more detailed question (at least 3 words)."
    
    # Check if mostly punctuation or numbers
    if is_mostly_punctuation(text):
        return False, "Please enter a valid question with words, not just symbols or numbers."
    
    # Check for keyboard patterns
    if has_keyboard_pattern(text):
        return False, "Invalid input detected. Please enter a meaningful RTI-related question."
    
    # Check for excessive character repetition
    if has_repeated_chars(text):
        return False, "Invalid input detected. Please enter a meaningful RTI-related question."
    
    # Check for lorem ipsum
    if is_lorem_ipsum(text):
        return False, "Please enter a real RTI-related question, not placeholder text."
    
    # Check for meaningful words (at least 1 recognizable word)
    meaningful_count = count_meaningful_words(text)
    if meaningful_count < 1:
        return False, "Your question doesn't appear to contain recognizable words. Please rephrase your RTI-related question."
    
    # If query is short, require higher percentage of meaningful words
    if len(words) <= 5 and meaningful_count < 2:
        return False, "Please provide more context in your question."
    
    return True, ""
