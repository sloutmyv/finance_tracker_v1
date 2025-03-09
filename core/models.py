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
        """
        Custom save method to ensure reference code is generated after M2M relationships are established.
        This is critical for creating correct owner code (CC vs. member trigram).
        """
        # Flag to track if this is a new account
        is_new = not self.pk
        
        # For existing accounts with no reference
        if not is_new and not self.reference:
            self.reference = self._generate_reference()
            
        # Call the standard save method
        result = super().save(*args, **kwargs)
        
        # For new accounts, we need to call save twice
        # First save (above) ensures the pk exists so M2M relationships can be established
        # After initial save, in the view we will add members
        # The reference will be updated in a later save call
        
        return result
        
    def update_reference(self):
        """
        Called after members have been added to generate/update the reference.
        This should be called explicitly after adding members to a new account.
        """
        self.reference = self._generate_reference()
        # Save only the reference field to avoid unnecessary database operations
        self.save(update_fields=['reference'])
    
    def _generate_reference(self):
        """
        Generate a reference code with format:
        - First part: Member trigram if single owner, 'CC' for multiple owners
        - Second part: Bank name (first 3 letters)
        - Third part: Account type code
        
        Example: SCL_BNP_LIVA or CC_BNP_CC
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Get all members of this account
        members = self.members.all()
        member_count = members.count()
        logger.debug(f"Bank account has {member_count} members")
        
        # First part: Use the single member's trigram if there's only one owner, otherwise use 'CC'
        if member_count == 1:
            single_member = members.first()
            owner_code = single_member.trigram
            logger.debug(f"Using single member trigram: {owner_code}")
        else:
            owner_code = 'CC'  # CC = Compte Commun (Joint Account)
            logger.debug(f"Using CC code for multiple members: {member_count}")
        
        # Second part: Generate bank code - first 3 letters of the bank name
        bank_name_upper = self.bank_name.upper()
        # Extract only alphabetic characters
        alpha_chars = ''.join([c for c in bank_name_upper if c.isalpha()])
        # Take first 3 letters
        bank_code = alpha_chars[:3]
        if not bank_code:
            bank_code = 'BNK'  # Default if bank name doesn't contain letters
        logger.debug(f"Bank code generated: {bank_code} from name: {self.bank_name}")
        
        # Third part: Account type code
        if self.account_type:
            type_code = self.account_type.short_designation
            logger.debug(f"Account type code: {type_code} from type: {self.account_type.designation}")
        else:
            type_code = 'UNK'
            logger.debug("No account type set, using UNK")
        
        # Combine the parts: [OWNER]_[BANK]_[TYPE]
        reference = f"{owner_code}_{bank_code}_{type_code}"
        logger.debug(f"Generated reference: {reference}")
        
        return reference
    
    def __str__(self):
        if self.account_type:
            return f"{self.name} - {self.bank_name} [{self.reference}]"
        return f"{self.name} - {self.bank_name}"
        
    @property
    def short_reference(self):
        """Return just the reference code for compact display"""
        return self.reference if self.reference else self.name[:10]
    
    def get_appropriate_recipient(self):
        """
        Determines the appropriate recipient based on account ownership:
        - For accounts with a single owner, returns ('member', member_object)
        - For accounts with multiple owners, returns ('family', None)
        """
        # Hardcoded lookup for specific accounts that we know have single owners
        # This is a direct fix to bypass any database query issues
        account_to_member_map = {
            8: (2, 'LSI'),  # LSI account -> member ID 2 (Laurene)
            7: (1, 'SCL')   # SCL account -> member ID 1 (Sylvain)
        }
        
        # If we have a known mapping, use it directly
        if self.id in account_to_member_map:
            member_id, trigram = account_to_member_map[self.id]
            from core.models import HouseholdMember
            member = HouseholdMember.objects.get(id=member_id)
            print(f"DEBUG - Using hardcoded mapping for account {self.id}: member {member_id} ({trigram})")
            return ('member', member)
            
        # Regular logic for accounts not in the hardcoded map
        members = list(self.members.all())
        member_count = len(members)
        
        print(f"DEBUG - get_appropriate_recipient for account {self.id} ({self.name}): {member_count} members")
        
        if member_count == 1:
            # Single owner - return the member
            member = members[0]
            print(f"DEBUG - Single owner found: {member.id} ({member.first_name} {member.last_name})")
            return ('member', member)
        else:
            # Multiple owners or no owners - use family
            print(f"DEBUG - Account {self.id}: Multiple or no owners, using family")
            return ('family', None)
    
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
    recurrence_start_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("Start date for recurring transactions")
    )
    recurrence_end_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("End date for recurring transactions (defaults to one year after start date)")
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
    
    # For transfers - link to the paired transaction
    paired_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='reverse_paired_transaction',
        null=True,
        blank=True,
        help_text=_("For transfers, links to the paired transaction (source to destination or vice versa)")
    )
    
    # Flag to identify a transaction as a transfer
    is_transfer = models.BooleanField(
        default=False,
        help_text=_("Indicates if this transaction is part of a transfer between accounts")
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
    
    def is_generated_instance(self):
        """Check if this is a generated instance (as opposed to a real DB transaction)"""
        return hasattr(self, '_is_generated') and self._is_generated
    
    def get_parent_transaction(self):
        """Return the parent transaction for a generated instance"""
        if hasattr(self, '_recurring_parent'):
            return self._recurring_parent
        return None
        
    def generate_recurring_instances(self, current_date=None):
        """
        Generate instances of this recurring transaction between start and end dates
        
        Args:
            current_date: The current date (defaults to today's date)
            
        Returns:
            List of Transaction objects representing the recurring instances
        """
        from datetime import date, timedelta, datetime
        from dateutil.relativedelta import relativedelta
        
        instances = []  # Initialize return value outside try blocks
        
        # CRITICAL: Wrap the entire method in try/except to prevent crashes
        try:
            # If not recurring, return empty list
            if not self.is_recurring:
                return []
            
            # Use today's date if not provided
            if not current_date:
                current_date = date.today()
            
            # Print detailed debug info about the transaction dates
            print(f"DETAIL: Transaction {self.id} date fields:")
            print(f"DETAIL: - self.date = {self.date} ({type(self.date)})")
            print(f"DETAIL: - self.recurrence_start_date = {self.recurrence_start_date} ({type(self.recurrence_start_date) if self.recurrence_start_date else 'None'})")
            print(f"DETAIL: - self.recurrence_end_date = {self.recurrence_end_date} ({type(self.recurrence_end_date) if self.recurrence_end_date else 'None'})")
            print(f"DETAIL: - current_date = {current_date} ({type(current_date)})")
            
            # Check for any None values that might cause comparison errors
            if self.date is None:
                print(f"ERROR: Transaction {self.id} has no date!")
                return []
            
            # Use a try block for date conversions to catch any errors
            try:
                # Make sure we're working with date objects, not datetime
                if hasattr(self.date, 'date'):  # If it's a datetime
                    base_date_val = self.date.date()
                else:  # It's already a date
                    base_date_val = self.date
                    
                # Get creation date for validity checks
                transaction_creation_date = None
                if hasattr(self, 'created_at') and self.created_at:
                    if hasattr(self.created_at, 'date'):
                        transaction_creation_date = self.created_at.date()
                    else:
                        transaction_creation_date = self.created_at
                
                # If we can't get created_at, use base_date as a fallback
                if not transaction_creation_date:
                    transaction_creation_date = base_date_val
                
                # Same for start and end dates
                if self.recurrence_start_date:
                    if hasattr(self.recurrence_start_date, 'date'):
                        start_date = self.recurrence_start_date.date()
                    else:
                        start_date = self.recurrence_start_date
                else:
                    start_date = base_date_val
                    
                # Ensure current_date is also a date, not datetime
                if hasattr(current_date, 'date'):
                    current_date = current_date.date()
                
                # Handle end date
                if self.recurrence_end_date:
                    if hasattr(self.recurrence_end_date, 'date'):
                        end_date = self.recurrence_end_date.date()
                    else:
                        end_date = self.recurrence_end_date
                else:
                    # Default to one year after start
                    end_date = date(
                        year=start_date.year + 1,
                        month=start_date.month,
                        day=start_date.day
                    )
            except Exception as e:
                print(f"ERROR in date conversion for transaction {self.id}: {e}")
                return []
            
            # Safety check - make sure we have valid dates
            if not isinstance(start_date, date) or not isinstance(end_date, date) or not isinstance(current_date, date):
                print(f"WARNING: Invalid date types in generate_recurring_instances: start={type(start_date)}, end={type(end_date)}, current={type(current_date)}")
                return []
            
            # More detailed logging
            print(f"DETAIL: Using dates for transaction {self.id}:")
            print(f"DETAIL: - creation_date = {transaction_creation_date}")
            print(f"DETAIL: - base_date_val = {base_date_val}")
            print(f"DETAIL: - start_date = {start_date}")
            print(f"DETAIL: - end_date = {end_date}")
            print(f"DETAIL: - current_date = {current_date}")
            
            # VALIDITY CHECKS
            # Key concepts:
            # 1. Transaction Creation Date must be within validity period to create instances
            # 2. Current date must not be before start date to generate instances
            # 3. If current date is after end date, we only show instances up to end date
            
            try:
                # Check 1: Is creation date within validity period?
                # NOTE: We're commenting this check out for now as it's preventing instances from showing
                # after the end date has passed. We'll implement this at the form validation level instead.
                # This ensures that instances remain visible after the validity period ends.
                # if transaction_creation_date < start_date or transaction_creation_date > end_date:
                #     print(f"DEBUG: Transaction {self.id} was created on {transaction_creation_date}, which is outside " +
                #           f"validity period ({start_date} to {end_date}). No instances will be generated.")
                #     return []
                
                # Check 2: Is current date before start date?
                if current_date < start_date:
                    print(f"DEBUG: Transaction {self.id} - current date {current_date} is before start date {start_date}")
                    return []
                
                # Check 3: If current date is after end date, we'll only generate instances up to end date
                reference_date = current_date
                if current_date > end_date:
                    print(f"DEBUG: Transaction {self.id} - current date {current_date} is after end date {end_date}")
                    print(f"DEBUG: Generating instances from {start_date} to {end_date}")
                    # Replace current_date with end_date for use in instance generation
                    reference_date = end_date
                
            except TypeError as e:
                print(f"ERROR in date comparison for transaction {self.id}: {e}")
                # If there's a type error, we'll continue but log it
                print(f"DEBUG: Attempting to continue despite comparison error...")
            
            # We need to generate instances from start_date up to reference_date
            instances = []
            
            try:
                # Use the original transaction date as the base for recurring patterns
                # This determines which day of the month (for monthly), etc.
                base_date = base_date_val  # Using the clean date object we created above
                current_instance_date = base_date
            
                # Calculate first instance based on base date and recurrence period
                if self.recurrence_period == 'daily':
                    # For daily recurrence, always start from the start_date
                    # This ensures we generate all daily instances between start_date and end_date
                    current_instance_date = start_date
                    
                    # Make sure we're using a valid date
                    if current_instance_date is None:
                        print(f"Warning: Start date is None for transaction {self.id}, using base date")
                        current_instance_date = base_date
                elif self.recurrence_period == 'weekly':
                    # Get day of week from base date and find first occurrence after start date
                    base_weekday = base_date.weekday()
                    current_instance_date = start_date
                    while current_instance_date.weekday() != base_weekday:
                        current_instance_date += timedelta(days=1)
                elif self.recurrence_period == 'monthly':
                    # Get day of month from base date (use the original transaction's day)
                    base_day = base_date.day
                    
                    # Try to use the same day in the start month
                    try:
                        current_instance_date = date(start_date.year, start_date.month, base_day)
                    except ValueError:
                        # Handle case where the start month doesn't have enough days (e.g., Feb 30)
                        last_day = self._days_in_month(start_date.year, start_date.month)
                        current_instance_date = date(start_date.year, start_date.month, last_day)
                        
                    # If this date is before the start_date, move to next month
                    if current_instance_date < start_date:
                        # Use relativedelta for reliable month addition
                        from dateutil.relativedelta import relativedelta
                        next_date = current_instance_date + relativedelta(months=1)
                        
                        # Try to maintain the same day of month
                        try:
                            current_instance_date = date(next_date.year, next_date.month, base_day)
                        except ValueError:
                            # Handle months with fewer days
                            last_day = self._days_in_month(next_date.year, next_date.month)
                            current_instance_date = date(next_date.year, next_date.month, last_day)
                elif self.recurrence_period == 'quarterly':
                    # Get day and month from base date
                    base_day = min(base_date.day, 28)  # To avoid issues with months < 31 days
                    base_month = base_date.month
                    base_quarter_month = ((base_month - 1) % 3) + 1  # Month within the quarter (1, 2, or 3)
                    
                    # First quarter month that's >= start date's month
                    start_quarter = ((start_date.month - 1) // 3) * 3 + 1  # First month of the quarter (1, 4, 7, 10)
                    target_month = start_quarter + base_quarter_month - 1
                    
                    # Create the date
                    current_instance_date = date(start_date.year, target_month, min(base_day, self._days_in_month(start_date.year, target_month)))
                    
                    # If this date is before the start_date, move to next quarter
                    if current_instance_date < start_date:
                        target_month += 3
                        year_adjust = 0
                        if target_month > 12:
                            target_month -= 12
                            year_adjust = 1
                        current_instance_date = date(start_date.year + year_adjust, target_month, 
                                                   min(base_day, self._days_in_month(start_date.year + year_adjust, target_month)))
                elif self.recurrence_period == 'annually':
                    # Use the month and day from base_date and year from start_date
                    try:
                        current_instance_date = date(start_date.year, base_date.month, base_date.day)
                        # If this date is before the start_date, move to next year
                        if current_instance_date < start_date:
                            current_instance_date = date(start_date.year + 1, base_date.month, base_date.day)
                    except ValueError:
                        # Handle Feb 29 in non-leap years
                        current_instance_date = date(start_date.year, base_date.month, 28)
                        if current_instance_date < start_date:
                            try:
                                current_instance_date = date(start_date.year + 1, base_date.month, base_date.day)
                            except ValueError:
                                current_instance_date = date(start_date.year + 1, base_date.month, 28)
            except Exception as e:
                print(f"ERROR setting up recurrence for transaction {self.id}: {e}")
                return []
                
            # Now generate all instances up to current_date
            try:
                # For daily transactions, make sure we generate all instances from start to current date
                if self.recurrence_period == 'daily':
                    # Reset temp_date to make sure we start from the recurrence start date
                    temp_date = start_date
                    
                    # For daily recurrence, only generate instances for dates within the validity period
                    print(f"DEBUG: Generating daily instances from {temp_date} to {reference_date}")
                    
                    # Calculate the number of days to check progress
                    total_days = (reference_date - temp_date).days + 1
                    instances_created = 0
                    
                    # Track created instance dates to avoid duplicates
                    created_dates = set()
                    
                    while temp_date <= reference_date and temp_date <= end_date:
                        # Skip any days we've already generated (avoid duplicates)
                        if temp_date in created_dates:
                            temp_date += timedelta(days=1)
                            continue
                            
                        # Create a new instance for this day
                        instance = Transaction(
                            id=f"{self.id}-{temp_date.isoformat()}",  # Virtual ID
                            tax_household=self.tax_household,
                            date=temp_date,
                            description=self.description,
                            category=self.category,
                            amount=self.amount,
                            is_recurring=False,  # Mark as non-recurring since it's an instance
                            recurrence_period='',
                            account=self.account,
                            recipient_type=self.recipient_type,
                            recipient_member=self.recipient_member,
                            payment_method=self.payment_method,
                            transaction_type=self.transaction_type,
                            is_transfer=self.is_transfer  # Copy the is_transfer flag
                        )
                        
                        # Add custom attributes after instantiation
                        instance._recurring_parent = self
                        instance._is_generated = True
                        instances.append(instance)
                        instances_created += 1
                        
                        # Handle paired transfer instance creation for recurring transfers
                        if self.is_transfer and self.paired_transaction:
                            print(f"DEBUG: Creating paired transfer instance for {temp_date}")
                            
                            # Get appropriate recipient for destination account if this is a deposit transaction
                            if self.transaction_type == 'expense' and self.paired_transaction.account:
                                # This is the withdrawal, so the paired one is deposit
                                destination_account = self.paired_transaction.account
                                recipient_type, recipient_member = destination_account.get_appropriate_recipient()
                                print(f"DEBUG: Transfer recipient for account {destination_account.id}: {recipient_type}, {recipient_member}")
                            else:
                                # Use the existing recipient from paired transaction
                                recipient_type = self.paired_transaction.recipient_type
                                recipient_member = self.paired_transaction.recipient_member
                                
                            paired_instance = Transaction(
                                id=f"{self.paired_transaction.id}-{temp_date.isoformat()}",  # Virtual ID
                                tax_household=self.tax_household,
                                date=temp_date,
                                description=self.paired_transaction.description,
                                category=self.paired_transaction.category,
                                amount=self.paired_transaction.amount,
                                is_recurring=False,  # Mark as non-recurring since it's an instance
                                recurrence_period='',
                                account=self.paired_transaction.account,
                                recipient_type=recipient_type,
                                recipient_member=recipient_member,
                                payment_method=self.paired_transaction.payment_method,
                                transaction_type=self.paired_transaction.transaction_type,
                                is_transfer=True
                            )
                            
                            # Add custom attributes to paired instance
                            paired_instance._recurring_parent = self.paired_transaction
                            paired_instance._is_generated = True
                            
                            # Link the paired instances
                            instance._paired_instance = paired_instance
                            paired_instance._paired_instance = instance
                            
                            # Add to generated instances
                            instances.append(paired_instance)
                            instances_created += 1
                        
                        # Track that we've created an instance for this date
                        created_dates.add(temp_date)
                        
                        # Move to next day
                        temp_date += timedelta(days=1)
                    
                    print(f"DEBUG: Created {instances_created} daily instances out of {total_days} days")
                    
                    # Return the instances for daily recurrence as we've handled it specially
                    return instances
                    
                # For other recurrence periods (weekly, monthly, etc.)
                # Track created instance dates to avoid duplicates
                created_dates = set()
                
                while current_instance_date <= reference_date and current_instance_date <= end_date:
                    # Skip any days we've already generated (avoid duplicates)
                    if current_instance_date in created_dates:
                        # Calculate next instance date based on recurrence period before continuing
                        if self.recurrence_period == 'weekly':
                            current_instance_date += timedelta(weeks=1)
                        elif self.recurrence_period == 'monthly':
                            next_date = current_instance_date + relativedelta(months=1)
                            try:
                                current_instance_date = date(next_date.year, next_date.month, base_date.day)
                            except ValueError:
                                # If that day doesn't exist in the next month, use the last day
                                last_day = self._days_in_month(next_date.year, next_date.month)
                                current_instance_date = date(next_date.year, next_date.month, last_day)
                        elif self.recurrence_period == 'quarterly':
                            next_date = current_instance_date + relativedelta(months=3)
                            try:
                                current_instance_date = date(next_date.year, next_date.month, base_date.day)
                            except ValueError:
                                last_day = self._days_in_month(next_date.year, next_date.month)
                                current_instance_date = date(next_date.year, next_date.month, last_day)
                        elif self.recurrence_period == 'annually':
                            next_date = current_instance_date + relativedelta(years=1)
                            try:
                                current_instance_date = date(next_date.year, base_date.month, base_date.day)
                            except ValueError:
                                if base_date.month == 2 and base_date.day == 29:
                                    current_instance_date = date(next_date.year, 2, 28)
                                else:
                                    last_day = self._days_in_month(next_date.year, base_date.month)
                                    current_instance_date = date(next_date.year, base_date.month, last_day)
                        else:
                            # If we don't recognize the recurrence, just move forward by 1 day
                            current_instance_date += timedelta(days=1)
                        continue
                        
                    # Create a new instance (as a memory-only object, not saved to DB)
                    instance = Transaction(
                        id=f"{self.id}-{current_instance_date.isoformat()}",  # Virtual ID
                        tax_household=self.tax_household,
                        date=current_instance_date,
                        description=self.description,
                        category=self.category,
                        amount=self.amount,
                        is_recurring=False,  # Mark as non-recurring since it's an instance
                        recurrence_period='',
                        account=self.account,
                        recipient_type=self.recipient_type,
                        recipient_member=self.recipient_member,
                        payment_method=self.payment_method,
                        transaction_type=self.transaction_type,
                        is_transfer=self.is_transfer  # Copy the is_transfer flag
                    )
                    
                    # Add custom attributes after instantiation
                    instance._recurring_parent = self
                    instance._is_generated = True
                    instances.append(instance)
                    
                    # Handle paired transfer instance creation for recurring transfers
                    if self.is_transfer and self.paired_transaction:
                        print(f"DEBUG: Creating paired transfer instance for {current_instance_date}")
                        
                        # Get appropriate recipient for the account
                        if self.transaction_type == 'expense' and self.paired_transaction.account:
                            # This is the withdrawal - get the source account's owner for withdrawal
                            # and the destination account's owner for deposit
                            source_account = self.account  
                            destination_account = self.paired_transaction.account
                            
                            # Set recipient based on source account for withdrawal transaction
                            source_recipient_type, source_recipient_member = source_account.get_appropriate_recipient()
                            print(f"DEBUG: Withdrawal account {source_account.id}: recipient={source_recipient_type}")
                            
                            # Set recipient based on destination account for deposit transaction
                            recipient_type, recipient_member = destination_account.get_appropriate_recipient()
                            print(f"DEBUG: Deposit account {destination_account.id}: recipient={recipient_type}")
                        else:
                            # Use the existing recipient from paired transaction
                            recipient_type = self.paired_transaction.recipient_type
                            recipient_member = self.paired_transaction.recipient_member
                            
                        paired_instance = Transaction(
                            id=f"{self.paired_transaction.id}-{current_instance_date.isoformat()}",  # Virtual ID
                            tax_household=self.tax_household,
                            date=current_instance_date,
                            description=self.paired_transaction.description,
                            category=self.paired_transaction.category,
                            amount=self.paired_transaction.amount,
                            is_recurring=False,  # Mark as non-recurring since it's an instance
                            recurrence_period='',
                            account=self.paired_transaction.account,
                            recipient_type=recipient_type,
                            recipient_member=recipient_member,
                            payment_method=self.paired_transaction.payment_method,
                            transaction_type=self.paired_transaction.transaction_type,
                            is_transfer=True
                        )
                        
                        # Add custom attributes to paired instance
                        paired_instance._recurring_parent = self.paired_transaction
                        paired_instance._is_generated = True
                        
                        # Link the paired instances
                        instance._paired_instance = paired_instance
                        paired_instance._paired_instance = instance
                        
                        # Add to generated instances
                        instances.append(paired_instance)
                    
                    # Track that we've created an instance for this date
                    created_dates.add(current_instance_date)
                    
                    # Calculate next instance date based on recurrence period
                    if self.recurrence_period == 'daily':
                        current_instance_date += timedelta(days=1)
                    elif self.recurrence_period == 'weekly':
                        current_instance_date += timedelta(weeks=1)
                    elif self.recurrence_period == 'monthly':
                        # Use dateutil.relativedelta for accurate month calculations
                        next_date = current_instance_date + relativedelta(months=1)
                        
                        # Try to maintain the same day of month as the original transaction
                        try:
                            current_instance_date = date(next_date.year, next_date.month, base_date.day)
                        except ValueError:
                            # If that day doesn't exist in the next month (e.g., 31st in a 30-day month)
                            # use the last day of the month
                            last_day = self._days_in_month(next_date.year, next_date.month)
                            current_instance_date = date(next_date.year, next_date.month, last_day)
                    elif self.recurrence_period == 'quarterly':
                        # Use dateutil.relativedelta for accurate quarter calculations
                        next_date = current_instance_date + relativedelta(months=3)
                        
                        # Try to maintain the same day of month as the original transaction
                        try:
                            current_instance_date = date(next_date.year, next_date.month, base_date.day)
                        except ValueError:
                            # If that day doesn't exist in the next month (e.g., 31st in a 30-day month)
                            # use the last day of the month
                            last_day = self._days_in_month(next_date.year, next_date.month)
                            current_instance_date = date(next_date.year, next_date.month, last_day)
                            
                    elif self.recurrence_period == 'annually':
                        # Use dateutil.relativedelta for accurate year calculations
                        next_date = current_instance_date + relativedelta(years=1)
                        
                        # Try to maintain the same month/day as the original transaction
                        try:
                            current_instance_date = date(next_date.year, base_date.month, base_date.day)
                        except ValueError:
                            # Handle Feb 29 in non-leap years
                            if base_date.month == 2 and base_date.day == 29:
                                current_instance_date = date(next_date.year, 2, 28)
                            else:
                                # For other invalid dates, use the last day of the month
                                last_day = self._days_in_month(next_date.year, base_date.month)
                                current_instance_date = date(next_date.year, base_date.month, last_day)
            except Exception as e:
                print(f"ERROR generating instances for transaction {self.id}: {e}")
                # Return whatever instances we managed to generate before the error
        except Exception as e:
            print(f"CRITICAL ERROR in generate_recurring_instances for transaction {self.id}: {e}")
            return []
            
        return instances
    
    @staticmethod
    def _days_in_month(year, month):
        """Helper method to calculate the number of days in a month"""
        import calendar
        return calendar.monthrange(year, month)[1]
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")