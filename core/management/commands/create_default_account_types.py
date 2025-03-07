from django.core.management.base import BaseCommand
from core.models import AccountType


class Command(BaseCommand):
    help = 'Creates default account types'

    def handle(self, *args, **kwargs):
        default_account_types = [
            {"designation": "Current Account", "short_designation": "CC"},
            {"designation": "Livret A", "short_designation": "LIVA"},
            {"designation": "Livret B", "short_designation": "LIVB"},
            {"designation": "Housing Savings Plan", "short_designation": "PEL"},
        ]
        
        created_count = 0
        existing_count = 0
        
        for account_type in default_account_types:
            obj, created = AccountType.objects.get_or_create(
                designation=account_type["designation"],
                defaults={"short_designation": account_type["short_designation"]}
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created account type: {obj}'))
            else:
                existing_count += 1
                self.stdout.write(self.style.WARNING(f'Account type already exists: {obj}'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} account types ({existing_count} already existed)'))