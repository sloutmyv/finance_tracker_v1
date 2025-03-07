import os
import json
import gettext
from pathlib import Path
from django.utils.translation import gettext as _
from django.conf import settings

# Dictionary to store our loaded translations
TRANSLATION_DICT = {}

def load_json_translations():
    """
    Load JSON translations into our global dictionary.
    This function is called when the application starts.
    """
    base_dir = Path(__file__).resolve().parent.parent
    
    # Define the locale directories
    locales = ['en', 'fr']
    
    # Dictionary to store translations for each language
    global TRANSLATION_DICT
    
    for locale in locales:
        locale_dir = base_dir / 'locale' / locale / 'LC_MESSAGES'
        json_file = locale_dir / 'django.json'
        
        try:
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    TRANSLATION_DICT[locale] = translations
                    print(f"Loaded {len(translations)} translations from {json_file}")
            else:
                print(f"Warning: Translation file not found at {json_file}")
        except Exception as e:
            print(f"Error loading translations from {json_file}: {e}")
    
    return TRANSLATION_DICT

# This function will be called when Django starts
def register_translations():
    """Register translations when Django starts."""
    try:
        translations = load_json_translations()
        print(f"Successfully loaded translations for {len(translations)} languages")
    except Exception as e:
        print(f"Error loading translations: {e}")
        
def get_translation(lang, text):
    """Get translation for the specified text in the specified language."""
    global TRANSLATION_DICT
    if lang in TRANSLATION_DICT and text in TRANSLATION_DICT[lang]:
        return TRANSLATION_DICT[lang][text]
    return text