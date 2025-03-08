from django.core.management.base import BaseCommand
from core.models import PaymentMethod


class Command(BaseCommand):
    help = 'Creates default payment methods'

    def handle(self, *args, **kwargs):
        default_payment_methods = [
            {"name": "Credit Card", "icon": "bi-credit-card"},
            {"name": "Check", "icon": "bi-wallet2"},
            {"name": "Cash", "icon": "bi-cash-stack"},
            {"name": "Bank Transfer", "icon": "bi-bank"},
            {"name": "Direct Debit", "icon": "bi-arrow-repeat"},
        ]
        
        created_count = 0
        existing_count = 0
        
        for payment_method in default_payment_methods:
            obj, created = PaymentMethod.objects.get_or_create(
                name=payment_method["name"],
                defaults={
                    "icon": payment_method["icon"],
                    "is_active": True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created payment method: {obj}'))
            else:
                existing_count += 1
                self.stdout.write(self.style.WARNING(f'Payment method already exists: {obj}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully created {created_count} payment methods ({existing_count} already existed)')
        )