from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
@stringfilter
def split(value, key):
    """
    Splits the string by the given key.
    Usage: {{ "apple,banana,cherry"|split:"," }}
    """
    if value:
        return value.split(key)
    return []

@register.filter
@stringfilter 
def trim(value):
    """
    Removes whitespace from both ends of the string.
    Usage: {{ "  hello world  "|trim }}
    """
    return value.strip()
