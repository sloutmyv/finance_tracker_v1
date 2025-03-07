#!/usr/bin/env python
import os
import polib
import json

def compile_po_to_json(po_file_path, json_file_path):
    """
    Compile a .po file to a JSON file that can be used for client-side translations
    """
    po = polib.pofile(po_file_path)
    translations = {}
    
    for entry in po:
        if entry.msgid and entry.msgstr:
            translations[entry.msgid] = entry.msgstr
    
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)
    
    print(f"Compiled {po_file_path} to {json_file_path}")

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