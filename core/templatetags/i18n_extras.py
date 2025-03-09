import os
import json
from django import template
from django.utils.safestring import mark_safe
from django.conf import settings
from django.utils.translation import get_language
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from core.translation_loader import get_translation, TRANSLATION_DICT, load_json_translations

register = template.Library()

@register.filter
def add_date_years(date_str, years=1):
    """
    Add a specified number of years to a date string.
    Format expected: DD/MM/YYYY
    """
    try:
        if isinstance(date_str, str):
            date_obj = datetime.strptime(date_str, '%d/%m/%Y').date()
        else:
            date_obj = date_str
            
        new_date = date_obj + relativedelta(years=years)
        return new_date.strftime('%d/%m/%y')
    except Exception as e:
        print(f"Error in add_date_years filter: {e}")
        return date_str
        
@register.filter
def split(value, delimiter):
    """
    Split a string by delimiter and return a list of parts.
    """
    if not value or not isinstance(value, str):
        return []
    return value.split(delimiter)

# Ensure translations are loaded
if not TRANSLATION_DICT:
    load_json_translations()

@register.simple_tag(takes_context=True)
def translate_json(context, text):
    """
    Custom template tag to translate text using our JSON files directly.
    This is a fallback method for when Django's built-in translation doesn't work.
    """
    lang = get_language()
    
    # Debug output to help diagnose issues
    print(f"translate_json called for text: '{text}' with language: '{lang}'")
    
    # Default to English if the current language is not found
    if not lang or lang not in [code for code, name in settings.LANGUAGES]:
        print(f"Language '{lang}' not found in LANGUAGES, defaulting to 'en'")
        lang = 'en'
    
    # Reload translations if the dictionary is empty
    global TRANSLATION_DICT
    if not TRANSLATION_DICT:
        print("TRANSLATION_DICT is empty, reloading translations")
        load_json_translations()
    
    try:
        # Check if the translations for this language are loaded
        if lang not in TRANSLATION_DICT:
            print(f"Language '{lang}' not found in TRANSLATION_DICT, reloading translations")
            load_json_translations()
        
        # If still not found after reload, default to English
        if lang not in TRANSLATION_DICT:
            print(f"Language '{lang}' still not found after reload, defaulting to 'en'")
            lang = 'en'
            
            # If English is also not found, we have a serious problem
            if 'en' not in TRANSLATION_DICT:
                print("English translations not found, loading translations again")
                load_json_translations()
                
                # If still no English translations, we can't proceed
                if 'en' not in TRANSLATION_DICT:
                    print("Critical error: unable to load any translations")
                    return mark_safe(text)
        
        # Try to translate using our TRANSLATION_DICT directly
        if text in TRANSLATION_DICT[lang]:
            translated = TRANSLATION_DICT[lang][text]
            print(f"Found translation for '{text}' in {lang}: '{translated}'")
            return mark_safe(translated)
        
        # If not found in the current language, try English as a fallback
        if lang != 'en' and 'en' in TRANSLATION_DICT and text in TRANSLATION_DICT['en']:
            english_text = TRANSLATION_DICT['en'][text]
            print(f"Translation not found in {lang}, using English: '{english_text}'")
            return mark_safe(english_text)
            
        # If the text is not found in any language, return the original
        print(f"No translation found for '{text}' in any language")
        return mark_safe(text)
        
    except Exception as e:
        print(f"Error in translate_json: {e}")
        
        # Fallback to reading the file directly as a last resort
        try:
            base_dir = settings.BASE_DIR
            json_file = os.path.join(base_dir, 'locale', lang, 'LC_MESSAGES', 'django.json')
            
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    if text in translations:
                        translated = translations[text]
                        print(f"Fallback loaded translation for '{text}': '{translated}'")
                        return mark_safe(translated)
                    else:
                        print(f"Text '{text}' not found in fallback translation file")
        except Exception as e2:
            print(f"Error in translate_json fallback: {e2}")
    
    # If anything goes wrong, return the original text
    return mark_safe(text)