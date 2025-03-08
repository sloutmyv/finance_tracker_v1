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
    # New fields for tracking account balance
    balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.0, 
        help_text=_("Current balance of the account")
    )
    balance_date = models.DateField(
        default=timezone.now,
        help_text=_("Date when the balance was last updated")
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

class CostCenter(models.Model):
    """Model representing a macro category (cost center) for grouping transaction categories"""
    
    tax_household = models.ForeignKey(
        TaxHousehold,
        on_delete=models.CASCADE,
        related_name='cost_centers',
        help_text=_("The tax household this cost center belongs to")
    )
    name = models.CharField(
        max_length=100, 
        help_text=_("Cost center name")
    )
    color = models.CharField(
        max_length=20, 
        default="#7295d8", 
        help_text=_("Color code for the cost center (hex format)")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Capitalize first letter of name
        if self.name:
            self.name = self.name[0].upper() + self.name[1:] if len(self.name) > 0 else self.name
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        verbose_name = _("Cost Center")
        verbose_name_plural = _("Cost Centers")

class TransactionCategory(models.Model):
    """Model representing a category for transactions"""
    
    tax_household = models.ForeignKey(
        TaxHousehold,
        on_delete=models.CASCADE,
        related_name='transaction_categories',
        help_text=_("The tax household this category belongs to")
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.SET_NULL,
        related_name='categories',
        null=True,
        blank=True,
        help_text=_("The cost center this category belongs to (optional)")
    )
    name = models.CharField(
        max_length=100, 
        help_text=_("Category name")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Capitalize first letter of name
        if self.name:
            self.name = self.name[0].upper() + self.name[1:] if len(self.name) > 0 else self.name
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        verbose_name = _("Transaction Category")
        verbose_name_plural = _("Transaction Categories")

class Transaction(models.Model):
    """Model representing a financial transaction"""
    
    TRANSACTION_TYPE_CHOICES = [
        ('expense', _('Expense')),
        ('income', _('Income')),
    ]
    
    RECURRENCE_CHOICES = [
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('monthly', _('Monthly')),
        ('quarterly', _('Quarterly')),
        ('annually', _('Annually')),
    ]
    
    tax_household = models.ForeignKey(
        TaxHousehold,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text=_("The tax household this transaction belongs to")
    )
    date = models.DateField(
        help_text=_("Date of the transaction")
    )
    description = models.CharField(
        max_length=255,
        help_text=_("Description of the transaction")
    )
    category = models.ForeignKey(
        TransactionCategory,
        on_delete=models.PROTECT,
        related_name='transactions',
        help_text=_("Category of the transaction")
    )
    # Cost center is derived from the category
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Amount of the transaction")
    )
    is_recurring = models.BooleanField(
        default=False,
        help_text=_("Whether this is a recurring transaction")
    )
    recurrence_period = models.CharField(
        max_length=10,
        choices=RECURRENCE_CHOICES,
        blank=True,
        default='',
        help_text=_("Frequency of recurrence for recurring transactions")
    )
    account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name='transactions',
        help_text=_("Account used for the transaction")
    )
    RECIPIENT_TYPE_CHOICES = [
        ('family', _('Family')),
        ('member', _('Household Member')),
        ('external', _('External')),
    ]
    
    # The type of recipient (family, specific member, or external)
    recipient_type = models.CharField(
        max_length=10,
        choices=RECIPIENT_TYPE_CHOICES,
        default='external',
        help_text=_("Type of recipient")
    )
    
    # Linked to a specific member when recipient_type is 'member'
    recipient_member = models.ForeignKey(
        HouseholdMember,
        on_delete=models.PROTECT,
        related_name='received_transactions',
        null=True,
        blank=True,
        help_text=_("Specific household member when recipient_type is 'member'")
    )
    
    # Helper method to set recipient from form selection
    def set_recipient(self, recipient_id):
        """
        Sets recipient_type and recipient_member based on form selection.
        recipient_id: 'family' for family, int for member ID, None/empty for external
        """
        if recipient_id == 'family':
            # Family option
            self.recipient_type = 'family'
            self.recipient_member = None
        elif recipient_id and recipient_id != '':
            # Try to get a household member
            try:
                member_id = int(recipient_id) if isinstance(recipient_id, str) else recipient_id
                self.recipient_member = HouseholdMember.objects.get(id=member_id)
                self.recipient_type = 'member'
            except (ValueError, TypeError, HouseholdMember.DoesNotExist):
                # Invalid member ID, set to external
                self.recipient_type = 'external'
                self.recipient_member = None
        else:
            # No selection, default to external
            self.recipient_type = 'external'
            self.recipient_member = None
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='transactions',
        help_text=_("Payment method used for the transaction")
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES,
        default='expense',
        help_text=_("Type of transaction (expense or income)")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.date} - {self.description} ({self.amount})"
    
    def get_cost_center(self):
        """Return the cost center associated with the transaction's category"""
        return self.category.cost_center if self.category else None
    
    @property
    def recipient_display(self):
        """Return a display string for the recipient (family or member name)"""
        if hasattr(self, 'recipient_type') and self.recipient_type == 'member' and self.recipient_member:
            return f"{self.recipient_member.first_name} {self.recipient_member.last_name}"
        # Default to Family for any other case
        return _("Family")
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")
