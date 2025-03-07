from django.conf import settings

def language_context(request):
    """
    Context processor that adds language information to the template context.
    """
    # Ensure LANGUAGE_CODE is available even if not set on the request
    language_code = getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
    
    return {
        'LANGUAGE_CODE': language_code,
        'LANGUAGES': settings.LANGUAGES,
    }