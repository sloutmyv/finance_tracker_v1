from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class TaxHousehold(models.Model):
    """Model representing a tax household for a user"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tax_household')
    name = models.CharField(max_length=100, help_text="Name of the tax household (e.g. 'Smith Family')")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Owner: {self.user.username})"

class HouseholdMember(models.Model):
    """Model representing a member of a tax household"""
    tax_household = models.ForeignKey(TaxHousehold, on_delete=models.CASCADE, related_name='members')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    trigram = models.CharField(max_length=3, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Generate trigram when saving (first letter of first name + first two letters of last name)
        if self.first_name and self.last_name:
            self.trigram = (self.first_name[0] + self.last_name[:2]).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.trigram})"

# This model is a placeholder for future bank account implementation
class BankAccount(models.Model):
    """Model representing a bank account that can be linked to household members"""
    name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    members = models.ManyToManyField(HouseholdMember, related_name='bank_accounts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
