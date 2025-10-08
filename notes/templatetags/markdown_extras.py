from django import template
from django.utils.safestring import mark_safe
from django.utils.html import strip_tags
import markdown as md
import re

register = template.Library()


@register.filter(name="markdown")
def markdown_format(text):
    """Convert markdown text to HTML with support for tables, checkboxes, etc."""
    return mark_safe(
        md.markdown(
            text,
            extensions=[
                "markdown.extensions.tables",
                "markdown.extensions.fenced_code",
                "markdown.extensions.nl2br",
                "markdown.extensions.sane_lists",
                "pymdownx.tasklist",
            ],
            extension_configs={
                "pymdownx.tasklist": {
                    "custom_checkbox": True,
                    "clickable_checkbox": True,
                }
            },
        )
    )


@register.filter(name="markdown_preview")
def markdown_preview(text, word_count=30):
    """Convert markdown to HTML and create a preview with limited words."""
    if not text:
        return ""

    # First render the markdown to HTML
    html = markdown_format(text)

    # Strip HTML tags to get plain text for word counting
    plain_text = strip_tags(html)

    # Split into words and truncate
    words = plain_text.split()
    if len(words) <= word_count:
        return html

    # If we need to truncate, take the first portion of the original text
    # and render it as markdown
    truncated_words = words[:word_count]
    truncated_text = " ".join(truncated_words)

    # Find approximately where this text ends in the original markdown
    # This is a simple approach - for more complex cases you might want
    # to use a proper HTML truncation library
    char_count = len(truncated_text)
    if char_count < len(text):
        # Find a good breaking point in the original markdown
        truncated_markdown = text[: char_count + 50]  # Add some buffer

        # Try to break at a word boundary
        last_space = truncated_markdown.rfind(" ")
        if last_space > char_count - 50:  # If we found a reasonable space
            truncated_markdown = truncated_markdown[:last_space]

        return mark_safe(markdown_format(truncated_markdown) + "...")

    return html
