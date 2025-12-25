"""Text formatting utilities for different output styles."""

try:
    import spacy  # type: ignore

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None  # type: ignore


def format_as_sentences(text: str, language_model: str = "en_core_web_sm") -> str:
    """
    Format text with one sentence per line using spaCy.

    Args:
        text: Input text with paragraph breaks
        language_model: spaCy language model to use (default: "en_core_web_sm")

    Returns:
        Text with sentences separated by newlines (no blank lines between paragraphs)

    Raises:
        ImportError: If spaCy is not installed
        OSError: If spaCy language model is not downloaded
    """
    if not SPACY_AVAILABLE:
        raise ImportError(
            "spaCy is required for sentence formatting. "
            "Install with: pip install epub2text[sentences]"
        )

    try:
        # Load the language model
        nlp = spacy.load(language_model)  # type: ignore
    except OSError:
        raise OSError(
            f"spaCy language model '{language_model}' not found. "
            f"Download with: python -m spacy download {language_model}"
        ) from None

    # Process text in chunks to handle large documents
    # spaCy has a default max length of 1M characters
    sentences = []

    # Split by double newlines (paragraphs) first
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if para:
            # Process the paragraph
            doc = nlp(para)
            for sent in doc.sents:
                sentence_text = sent.text.strip()
                if sentence_text:
                    sentences.append(sentence_text)

    # Join with single newlines (Option B: no blank lines)
    return "\n".join(sentences)
