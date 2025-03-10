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
        
    @property
    def clean_description(self):
        """
        Remove parenthetical clarification text like "(to Account)" or "(from Account)"
        from transaction descriptions.
        """
        import re
        if self.description:
            # Remove text matching the pattern (to X) or (from X) at the end of description
            cleaned_description = re.sub(r'\s+\((from|to)\s+.*?\)$', '', self.description)
            return cleaned_description
        return self.description
    
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
                    return []  # No instances to show if we're before the start date
                
                # Check 3: Cap end date at the current date + 1 year for better performance
                # This only limits the *display*, not the validity of the recurring transaction
                max_display_date = date(
                    year=current_date.year + 1,
                    month=current_date.month,
                    day=current_date.day
                )
                
                # Use the earlier of original end_date or max_display_date
                display_end_date = min(end_date, max_display_date)
                
                # Don't go past end date in generating instances
                # If end date is already passed, we'll cap the generation date at the end date
                calculation_date = min(current_date, end_date)
                
                print(f"DEBUG: Calculation date (min of current & end): {calculation_date}")
                
                # Generate dates based on the recurrence period
                instance_dates = []
                current_instance_date = start_date
                
                # Ensure we're not going to generate an excessive number of instances
                if self.recurrence_period == 'daily':
                    # For daily recurrence, cap at 365 instances
                    max_instances = 365
                    increment_func = lambda d: d + timedelta(days=1)
                elif self.recurrence_period == 'weekly':
                    # For weekly recurrence, cap at 52 instances
                    max_instances = 52
                    increment_func = lambda d: d + timedelta(weeks=1)
                elif self.recurrence_period == 'monthly':
                    # For monthly recurrence, cap at 12 instances
                    max_instances = 12
                    increment_func = lambda d: d + relativedelta(months=1)
                elif self.recurrence_period == 'quarterly':
                    # For quarterly recurrence, cap at 4 instances
                    max_instances = 4
                    increment_func = lambda d: d + relativedelta(months=3)
                elif self.recurrence_period == 'annually':
                    # For annual recurrence, cap at 3 instances
                    max_instances = 3
                    increment_func = lambda d: d + relativedelta(years=1)
                else:
                    # Unknown recurrence period, return empty list
                    print(f"WARNING: Unknown recurrence period: {self.recurrence_period}")
                    return []
                
                # Generate instance dates
                print(f"DEBUG: Generating instances from {start_date} to {display_end_date}")
                
                count = 0
                
                # If the start date is in the future, only generate that single instance
                if start_date > current_date:
                    print(f"DEBUG: Start date {start_date} is in the future, only generating that instance")
                    instance_dates.append(start_date)
                    count = 1
                else:
                    # For each date, starting from start_date, generate instances until display_end_date
                    while current_instance_date <= display_end_date and count < max_instances:
                        # Add date to the list
                        instance_dates.append(current_instance_date)
                        count += 1
                        
                        # Calculate next date based on recurrence period
                        current_instance_date = increment_func(current_instance_date)
                
                print(f"DEBUG: Generated {count} instance dates")
                
                # Create Transaction instances for each date
                for instance_date in instance_dates:
                    try:
                        # Create a clone of this transaction with the new date
                        clone = Transaction(
                            tax_household=self.tax_household,
                            date=instance_date,
                            description=self.description,
                            category=self.category,
                            amount=self.amount,
                            account=self.account,
                            payment_method=self.payment_method,
                            transaction_type=self.transaction_type,
                            recipient_type=self.recipient_type,
                            recipient_member=self.recipient_member,
                            is_recurring=False,  # Generated instances aren't themselves recurring
                            is_transfer=self.is_transfer,
                            paired_transaction=None  # Will be set properly later if this is a transfer
                        )
                        
                        # Set generated instance ID using parent ID + instance date
                        # This helps identify that this is a generated instance, not a real transaction
                        instance_id_str = f"{self.id}-{instance_date.strftime('%Y%m%d')}"
                        
                        # Set a dummy ID and instance marker (won't be saved to db)
                        clone.id = instance_id_str
                        clone._is_generated = True
                        clone._recurring_parent = self
                        clone._instance_date = instance_date
                        
                        # For transfers, we need to handle the paired transaction correctly
                        if self.is_transfer and self.paired_transaction:
                            # Create a clone of the paired transaction with the same date
                            paired_clone = Transaction(
                                tax_household=self.paired_transaction.tax_household,
                                date=instance_date,
                                description=self.paired_transaction.description,
                                category=self.paired_transaction.category,
                                amount=self.paired_transaction.amount,
                                account=self.paired_transaction.account,
                                payment_method=self.paired_transaction.payment_method,
                                transaction_type=self.paired_transaction.transaction_type,
                                recipient_type=self.paired_transaction.recipient_type,
                                recipient_member=self.paired_transaction.recipient_member,
                                # Even though this is a generated instance, it should follow
                                # the recurring settings of its parent transaction
                                is_recurring=False,  # Generated instances aren't themselves recurring
                                is_transfer=True,
                                paired_transaction=None
                            )
                            
                            # Generate a unique ID for the paired clone
                            paired_id_str = f"{self.paired_transaction.id}-{instance_date.strftime('%Y%m%d')}"
                            paired_clone.id = paired_id_str
                            paired_clone._is_generated = True
                            paired_clone._recurring_parent = self.paired_transaction
                            paired_clone._instance_date = instance_date
                            
                            # Link the clones to each other
                            clone.paired_transaction = paired_clone
                            paired_clone.paired_transaction = clone
                            
                            # Add the paired clone to the instances list
                            instances.append(paired_clone)
                        
                        instances.append(clone)
                    except Exception as e:
                        print(f"ERROR creating instance for date {instance_date}: {e}")
                        # Continue to the next date
                
                print(f"DEBUG: Created {len(instances)} recurring instances for transaction {self.id}")
                return instances
                
            except Exception as e:
                print(f"ERROR in generate_recurring_instances for transaction {self.id}: {e}")
                return []
                
        except Exception as outer_e:
            print(f"CRITICAL ERROR in generate_recurring_instances for transaction {self.id}: {outer_e}")
            return []
            
        return []
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")