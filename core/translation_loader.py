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
    
    # Clear the dictionary before loading to ensure fresh data
    TRANSLATION_DICT.clear()
    
    for locale in locales:
        locale_dir = base_dir / 'locale' / locale / 'LC_MESSAGES'
        json_file = locale_dir / 'django.json'
        
        try:
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    TRANSLATION_DICT[locale] = translations
                    print(f"DEBUG Translation Loader: Loaded {len(translations)} translations for {locale} from {json_file}")
                    
                    # Print the first 5 keys as a sample
                    sample_keys = list(translations.keys())[:5]
                    print(f"Sample keys for {locale}: {sample_keys}")
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
        for lang, trans in translations.items():
            print(f"Language {lang}: {len(trans)} translations available")
    except Exception as e:
        print(f"Error loading translations: {e}")
        
def get_translation(lang, text):
    """Get translation for the specified text in the specified language."""
    global TRANSLATION_DICT
    
    # Debug information
    if lang not in TRANSLATION_DICT:
        print(f"DEBUG Translation: Language {lang} not found in TRANSLATION_DICT")
        return text
        
    if text not in TRANSLATION_DICT[lang]:
        print(f"DEBUG Translation: Text '{text}' not found in language {lang}")
        return text
        
    # Return translation if available
    translation = TRANSLATION_DICT[lang][text]
    # Only log certain translations to avoid filling logs
    if len(text) < 30:  # Only log short texts to avoid spamming logs
        print(f"DEBUG Translation: '{text}' → '{translation}' ({lang})")
    return translation