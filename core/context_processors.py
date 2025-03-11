from django.conf import settings
from .utils.currency import CurrencyExchangeService

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

def currency_context(request):
    """
    Context processor that adds currency information to the template context.
    """
    # Get the currently selected currency from the session or default to EUR
    selected_currency = request.session.get('currency', 'EUR')
    
    return {
        'supported_currencies': CurrencyExchangeService.SUPPORTED_CURRENCIES,
        'selected_currency': selected_currency,
    }