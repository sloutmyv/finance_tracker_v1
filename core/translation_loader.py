import os
import json
from django.utils.translation import gettext as _
import gettext as gettext_module

def load_json_translations():
    """
    Load JSON translations into the gettext catalog.
    This function is called when the application starts.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Define the locale directories
    locales = ['en', 'fr']
    
    for locale in locales:
        locale_dir = os.path.join(base_dir, 'locale', locale, 'LC_MESSAGES')
        json_file = os.path.join(locale_dir, 'django.json')
        
        try:
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    
                    # Add translations to the gettext catalog
                    # This is a simplified version, in production you would use proper .mo files
                    print(f"Loaded {len(translations)} translations from {json_file}")
            else:
                print(f"Warning: Translation file not found at {json_file}")
        except Exception as e:
            print(f"Error loading translations from {json_file}: {e}")

# This function will be called when Django starts
def register_translations():
    """Register translations when Django starts."""
    load_json_translations()