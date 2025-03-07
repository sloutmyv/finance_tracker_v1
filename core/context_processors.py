def language_context(request):
    """
    Context processor that adds language information to the template context.
    """
    return {
        'LANGUAGE_CODE': request.LANGUAGE_CODE,
        'LANGUAGES': getattr(request, '_LANGUAGES', []),
    }