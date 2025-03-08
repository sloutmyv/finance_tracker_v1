from django.utils import translation
from django.conf import settings
import re
from core.translation_loader import load_json_translations, TRANSLATION_DICT

class LanguageMiddleware:
    """
    Simple middleware to handle language switching.
    This middleware checks the URL for a language code (e.g., /en/ or /fr/)
    and activates the corresponding language.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Compile the regex pattern once to improve performance
        self.language_pattern = re.compile(r'^/(?P<language>en|fr)/')
        
        # Make sure translations are loaded
        if not TRANSLATION_DICT:
            load_json_translations()
            print("DEBUG Middleware: Loaded translations in middleware init")
    
    def __call__(self, request):
        # Always reload translations to ensure we have the latest
        load_json_translations()
        print(f"DEBUG Middleware: Loaded translations in middleware call. English keys: {len(TRANSLATION_DICT.get('en', {}))}, French keys: {len(TRANSLATION_DICT.get('fr', {}))}")
            
        # Check if the URL contains a language code
        match = self.language_pattern.match(request.path_info)
        if match:
            language = match.group('language')
            
            # Activate the language
            if language in [lang[0] for lang in settings.LANGUAGES]:
                translation.activate(language)
                request.LANGUAGE_CODE = language
                print(f"DEBUG Middleware: Activated language from URL: {language}")
                
                # Store the language preference in the session
                if hasattr(request, 'session'):
                    request.session['django_language'] = language
                    print(f"DEBUG Middleware: Set session language to {language}")
        
        # If no language code in URL, check session
        elif hasattr(request, 'session') and 'django_language' in request.session:
            language = request.session['django_language']
            if language in [lang[0] for lang in settings.LANGUAGES]:
                translation.activate(language)
                request.LANGUAGE_CODE = language
                print(f"DEBUG Middleware: Activated language from session: {language}")
        
        # Get the response
        response = self.get_response(request)
        
        # Set the language cookie
        if hasattr(request, 'LANGUAGE_CODE'):
            current_lang = getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
            print(f"DEBUG Middleware: Setting language cookie to {current_lang}")
            
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                current_lang,
                max_age=settings.SESSION_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                domain=settings.LANGUAGE_COOKIE_DOMAIN,
                secure=settings.LANGUAGE_COOKIE_SECURE,
                httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
                samesite=settings.LANGUAGE_COOKIE_SAMESITE,
            )
        
        return response