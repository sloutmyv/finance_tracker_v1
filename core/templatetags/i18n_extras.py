import os
import json
from django import template
from django.utils.safestring import mark_safe
from django.conf import settings
from django.utils.translation import get_language

register = template.Library()

@register.simple_tag(takes_context=True)
def translate_json(context, text):
    """
    Custom template tag to translate text using our JSON files directly.
    This is a fallback method for when Django's built-in translation doesn't work.
    """
    lang = get_language()
    
    # Default to English if the current language is not found
    if not lang or lang not in [code for code, name in settings.LANGUAGES]:
        lang = 'en'
    
    base_dir = settings.BASE_DIR
    json_file = os.path.join(base_dir, 'locale', lang, 'LC_MESSAGES', 'django.json')
    
    try:
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
                
                # Return the translation if it exists, otherwise return the original text
                return mark_safe(translations.get(text, text))
    except Exception:
        pass
    
    # If anything goes wrong, return the original text
    return mark_safe(text)