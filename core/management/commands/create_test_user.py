from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Creates a test user for development purposes'

    def handle(self, *args, **kwargs):
        username = 'testuser'
        email = 'testuser@example.com'
        password = 'password123'

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists'))
            return

        User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully created test user: {username}'))
        self.stdout.write(self.style.SUCCESS(f'Email: {email}'))
        self.stdout.write(self.style.SUCCESS(f'Password: {password}'))