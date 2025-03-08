from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

class TaxHousehold(models.Model):
    """Model representing a tax household for a user"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tax_household')
    name = models.CharField(max_length=100, help_text=_("Name of the tax household (e.g. 'Smith Family')"))
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

class AccountType(models.Model):
    """Model representing a type of bank account"""
    designation = models.CharField(max_length=100)
    short_designation = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.designation} ({self.short_designation})"
    
    class Meta:
        ordering = ['designation']

class BankAccount(models.Model):
    """Model representing a bank account that can be linked to household members"""
    CURRENCY_CHOICES = [
        ('EUR', _('Euro (€)')),
        ('USD', _('US Dollar ($)')),
        ('GBP', _('British Pound (£)')),
        ('JPY', _('Japanese Yen (¥)')),
        ('CHF', _('Swiss Franc (Fr)')),
        ('AUD', _('Australian Dollar (A$)')),
        ('CAD', _('Canadian Dollar (C$)')),
        ('XPF', _('CFP Franc (₣)')),
        ('CNY', _('Chinese Yuan (¥)')),
    ]
    
    name = models.CharField(max_length=100, help_text=_("Name of the account"))
    bank_name = models.CharField(max_length=100, help_text=_("Name of the bank"), default="")
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT, related_name='accounts', null=True)
    members = models.ManyToManyField(HouseholdMember, related_name='bank_accounts')
    reference = models.CharField(max_length=100, blank=True, help_text=_("Auto-generated reference code"))
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='EUR',
        help_text=_("Three-letter currency code")
    )
    timestamp = models.DateTimeField(default=timezone.now, help_text=_("Account creation date and time"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Generate reference if this is a new account (no pk) or reference is empty
        if not self.pk or not self.reference:
            # Need to save first if it's a new account to establish M2M relationships
            super().save(*args, **kwargs)
            
            # Now generate the reference
            self.reference = self._generate_reference()
            
            # Call save again to update the reference field
            return super().save(update_fields=['reference'] if self.pk else None)
        return super().save(*args, **kwargs)
    
    def _generate_reference(self):
        # Get all members of this account
        member_trigrams = [member.trigram for member in self.members.all()]
        
        # Use the owner's trigram if there's only one, otherwise use 'CC'
        owner_code = member_trigrams[0] if len(member_trigrams) == 1 else 'CC'
        
        # Get account type code
        type_code = self.account_type.short_designation if self.account_type else 'UNK'
        
        # Generate bank code - take the first 3 characters of the bank name
        bank_code = ''.join([c for c in self.bank_name.upper() if c.isalpha()])[:3]
        if not bank_code:
            bank_code = 'BNK'  # Default if bank name doesn't contain letters
        
        # Combine the parts
        reference = f"{owner_code}_{bank_code}_{type_code}"
        
        return reference
    
    def __str__(self):
        if self.account_type:
            return f"{self.name} - {self.bank_name} [{self.reference}]"
        return f"{self.name} - {self.bank_name}"
    
    class Meta:
        ordering = ['bank_name', 'name']

class PaymentMethod(models.Model):
    """Model representing a payment method for transactions (admin-only)"""
    name = models.CharField(max_length=100, help_text=_("Name of the payment method"))
    icon = models.CharField(max_length=50, blank=True, help_text=_("Bootstrap icon class (e.g., 'bi-credit-card')"))
    is_active = models.BooleanField(default=True, help_text=_("Whether this payment method is active"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
        
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        verbose_name = _("Payment Method")
        verbose_name_plural = _("Payment Methods")
