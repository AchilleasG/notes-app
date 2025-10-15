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


@register.filter(name="text_color_for_bg")
def text_color_for_background(background_color):
    """
    Calculate the appropriate text color (white or black) based on background color brightness.
    Uses the relative luminance formula to determine if the background is light or dark.
    """
    if not background_color:
        return "#000000"

    # Remove the # if present
    color = background_color.lstrip("#")

    # Handle 3-character hex colors by expanding them
    if len(color) == 3:
        color = "".join([c * 2 for c in color])

    if len(color) != 6:
        return "#000000"  # Default to black for invalid colors

    try:
        # Convert hex to RGB
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)

        # Calculate relative luminance using ITU-R BT.709 formula
        # Convert RGB to linear RGB first
        def to_linear(c):
            c = c / 255.0
            if c <= 0.03928:
                return c / 12.92
            else:
                return pow((c + 0.055) / 1.055, 2.4)

        r_linear = to_linear(r)
        g_linear = to_linear(g)
        b_linear = to_linear(b)

        # Calculate luminance
        luminance = 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear

        # If luminance is greater than 0.5, use black text, otherwise white
        return "#000000" if luminance > 0.5 else "#ffffff"

    except ValueError:
        return "#000000"  # Default to black for invalid hex values
