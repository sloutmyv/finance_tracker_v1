#!/usr/bin/env python
import os
import polib
import json

def compile_po_to_json(po_file_path, json_file_path):
    """
    Compile a .po file to a JSON file that can be used for client-side translations
    while preserving any existing translations in the JSON file
    """
    po = polib.pofile(po_file_path)
    
    # First, try to load existing translations from JSON file
    existing_translations = {}
    try:
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r', encoding='utf-8') as f:
                existing_translations = json.load(f)
            
            # Make a backup of the existing translations just in case
            backup_path = f"{json_file_path}.backup-{int(os.path.getmtime(json_file_path))}"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(existing_translations, f, ensure_ascii=False, indent=2)
            print(f"Created backup of existing translations at {backup_path}")
    except Exception as e:
        print(f"Warning: Could not load existing translations from {json_file_path}: {e}")
    
    # Now add translations from PO file, without overwriting existing ones
    po_translations = {}
    for entry in po:
        if entry.msgid and entry.msgstr:
            po_translations[entry.msgid] = entry.msgstr
    
    # Merge translations - make sure existing JSON translations take precedence
    # This ensures manual edits to the JSON files are not lost
    merged_translations = {}
    merged_translations.update(po_translations)  # First add PO translations
    merged_translations.update(existing_translations)  # Then override with existing JSON translations
    
    # Print some debug info
    print(f"PO entries: {len(po_translations)}, Existing JSON entries: {len(existing_translations)}, Merged: {len(merged_translations)}")
    
    # Write back the merged translations
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(merged_translations, f, ensure_ascii=False, indent=2)
    
    print(f"Compiled {po_file_path} to {json_file_path}, preserving existing translations")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the locale directories
    locale_dirs = [
        os.path.join(base_dir, 'locale', 'en', 'LC_MESSAGES'),
        os.path.join(base_dir, 'locale', 'fr', 'LC_MESSAGES'),
    ]
    
    for locale_dir in locale_dirs:
        po_file = os.path.join(locale_dir, 'django.po')
        json_file = os.path.join(locale_dir, 'django.json')
        
        if os.path.exists(po_file):
            compile_po_to_json(po_file, json_file)
            print(f"Processed: {po_file}")
        else:
            print(f"Warning: PO file not found at {po_file}")

if __name__ == "__main__":
    main()
    print("Translation compilation complete. NOTE: In a production environment, you would use Django's compilemessages command.")