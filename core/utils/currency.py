import requests
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.cache import cache

# Currency exchange rates service
class CurrencyExchangeService:
    # Cache key for exchange rates
    CACHE_KEY = 'exchange_rates'
    # Cache duration (1 day)
    CACHE_DURATION = 60 * 60 * 24
    
    # Supported currencies
    SUPPORTED_CURRENCIES = [
        ('EUR', 'Euro (€)'),
        ('USD', 'US Dollar ($)'),
        ('GBP', 'British Pound (£)'),
        ('JPY', 'Japanese Yen (¥)'),
        ('CHF', 'Swiss Franc (Fr)'),
        ('AUD', 'Australian Dollar (A$)'),
        ('CAD', 'Canadian Dollar (C$)'),
        ('XPF', 'CFP Franc (₣)'),
        ('CNY', 'Chinese Yuan (¥)'),
    ]
    
    @classmethod
    def get_exchange_rates(cls, base_currency='EUR', force_refresh=False):
        """
        Fetch current exchange rates with the specified base currency.
        Returns a dictionary of exchange rates.
        
        If rates are cached and not expired, returns cached rates unless force_refresh is True.
        """
        # Try to get rates from cache first
        cache_key = f"{cls.CACHE_KEY}_{base_currency}"
        cached_data = cache.get(cache_key)
        
        if cached_data and not force_refresh:
            return cached_data
            
        # ExchangeRate-API Free Plan (limited to EUR as base)
        # For a production app, you'd want to use a paid API or service that allows custom base currencies
        url = "https://open.er-api.com/v6/latest/EUR"
        
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise exception for non-200 status codes
            data = response.json()
            
            if data['result'] == 'success':
                rates = data['rates']
                
                # If the base currency isn't EUR, we need to convert rates
                if base_currency != 'EUR':
                    # Get the rate for the requested base currency
                    base_rate = rates[base_currency]
                    
                    # Convert all rates to the new base currency
                    converted_rates = {}
                    for currency, rate in rates.items():
                        converted_rates[currency] = Decimal(str(rate)) / Decimal(str(base_rate))
                    
                    rates = converted_rates
                else:
                    # Convert all rates to Decimal for precision
                    rates = {currency: Decimal(str(rate)) for currency, rate in rates.items()}
                
                # Add timestamp to rates
                result = {
                    'base': base_currency,
                    'rates': rates,
                    'timestamp': data['time_last_update_unix'],
                    'date': data['time_last_update_utc']
                }
                
                # Save to cache
                cache.set(cache_key, result, cls.CACHE_DURATION)
                
                return result
        except requests.RequestException as e:
            # Log the error (in production, you'd want better error handling)
            print(f"Error fetching exchange rates: {e}")
            
            # Return None or cached data if available
            return cached_data if cached_data else None
    
    @classmethod
    def convert_currency(cls, amount, from_currency, to_currency):
        """
        Convert an amount from one currency to another using the latest exchange rates.
        
        Args:
            amount (Decimal): The amount to convert
            from_currency (str): The currency code to convert from (e.g., 'EUR')
            to_currency (str): The currency code to convert to (e.g., 'USD')
            
        Returns:
            Decimal: The converted amount or None if conversion failed
        """
        # If the currencies are the same, no conversion needed
        if from_currency == to_currency:
            return amount
            
        # Get exchange rates with from_currency as base
        rates_data = cls.get_exchange_rates(base_currency=from_currency)
        
        if rates_data and 'rates' in rates_data:
            rates = rates_data['rates']
            
            # Find the rate for the target currency
            if to_currency in rates:
                # Convert the amount
                return amount * rates[to_currency]
        
        # If we get here, something went wrong
        return None
    
    @classmethod
    def get_formatted_amount(cls, amount, currency):
        """Format an amount with its currency symbol"""
        if currency == 'EUR':
            return f"€{amount:.2f}"
        elif currency == 'USD':
            return f"${amount:.2f}"
        elif currency == 'GBP':
            return f"£{amount:.2f}"
        elif currency == 'JPY':
            return f"¥{amount:.0f}"  # No decimals for Yen
        elif currency == 'CHF':
            return f"Fr{amount:.2f}"
        elif currency == 'AUD':
            return f"A${amount:.2f}"
        elif currency == 'CAD':
            return f"C${amount:.2f}"
        elif currency == 'XPF':
            return f"₣{amount:.0f}"  # No decimals for CFP Franc
        elif currency == 'CNY':
            return f"¥{amount:.2f}"
        else:
            return f"{amount:.2f} {currency}"