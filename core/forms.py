from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from .models import TaxHousehold, HouseholdMember, BankAccount, AccountType, PaymentMethod, TransactionCategory, CostCenter, Transaction

class DateInput(forms.DateInput):
    input_type = 'date'
    
    def __init__(self, attrs=None, format=None):
        # For HTML date input, we need to use ISO format for the value
        self.format = '%Y-%m-%d'
        super().__init__(attrs=attrs, format=self.format)
    
    def format_value(self, value):
        """Format a Python datetime.date object as a string for the HTML date input."""
        if value is None:
            return ''
        
        # If it's already a string, try to convert it to ISO format
        if isinstance(value, str):
            try:
                # Try to parse with Django's parsing (handles multiple formats)
                from django.utils.dateparse import parse_date
                date_obj = parse_date(value)
                if date_obj:
                    return date_obj.strftime(self.format)
            except:
                pass
            return value
            
        # Use the parent class's formatting
        return super().format_value(value)

class TaxHouseholdForm(forms.ModelForm):
    class Meta:
        model = TaxHousehold
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class HouseholdMemberForm(forms.ModelForm):
    class Meta:
        model = HouseholdMember
        fields = ['first_name', 'last_name', 'date_of_birth']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': DateInput(attrs={'class': 'form-control'}),
        }

# Create a formset for household members
HouseholdMemberFormSet = inlineformset_factory(
    TaxHousehold, 
    HouseholdMember,
    form=HouseholdMemberForm,
    extra=1,
    can_delete=True
)

class BankAccountForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Check if there are any account types
        if not AccountType.objects.exists():
            self.fields['account_type'].help_text = _(
                'No account types are available. Please contact the administrator to create account types.'
            )
    
    class Meta:
        model = BankAccount
        fields = ['name', 'bank_name', 'account_type', 'currency', 'members', 'balance', 'balance_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'members': forms.CheckboxSelectMultiple(),
            'balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'balance_date': DateInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'name': _('A descriptive name for the account, e.g., "Joint Checking" or "Savings"'),
            'bank_name': _('The name of the bank or financial institution'),
            'currency': _('The currency used for this account'),
            'members': _('Select all family members who have access to this account'),
            'balance': _('The current balance of this account'),
            'balance_date': _('The date when this balance was recorded'),
        }

class PaymentMethodForm(forms.ModelForm):
    icon_choices = [
        ('bi-credit-card', _('Credit Card')),
        ('bi-wallet2', _('Wallet')),
        ('bi-cash-stack', _('Cash')),
        ('bi-bank', _('Bank')),
        ('bi-phone', _('Mobile')),
        ('bi-phone-vibrate', _('Mobile Payment')),
        ('bi-paypal', _('PayPal')),
        ('bi-currency-exchange', _('Exchange')),
        ('bi-wallet', _('Purse')),
        ('bi-gift', _('Gift')),
        ('bi-basket', _('Basket')),
        ('bi-piggy-bank', _('Savings')),
    ]
    
    icon = forms.ChoiceField(
        choices=icon_choices, 
        widget=forms.RadioSelect(attrs={'class': 'icon-radio-list'}),
        help_text=_('Select an icon for the payment method')
    )
    
    class Meta:
        model = PaymentMethod
        fields = ['name', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'name': _('A descriptive name for the payment method (e.g., "American Express", "BNP Checkbook")'),
        }

class CostCenterForm(forms.ModelForm):
    color_choices = [
        ('#7295d8', _('Blue')),
        ('#8dc571', _('Green')),
        ('#eda6b8', _('Pink')),
        ('#a97e7e', _('Brown')),
        ('#c2b091', _('Beige')),
        ('#8a92a9', _('Grey')),
        ('#b38d97', _('Mauve')),
        ('#7ba59a', _('Teal')),
        ('#5b78a7', _('Navy')),
        ('#f2d184', _('Yellow')),
        ('#e36a6a', _('Red')),
        ('#9a7dd2', _('Purple')),
        ('#f39c5e', _('Orange')),
        ('#63cdd7', _('Turquoise')),
        ('#b5d38f', _('Lime')),
        ('#de9ed3', _('Lilac')),
        ('#737373', _('Dark Grey')),
        ('#e5a663', _('Gold')),
    ]
    
    color = forms.ChoiceField(
        choices=color_choices, 
        widget=forms.RadioSelect(attrs={'class': 'color-radio-list'}),
        help_text=_('Select a color for the cost center')
    )
    
    class Meta:
        model = CostCenter
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'name': _('Cost center name (e.g., "Housing", "Transportation", "Food")'),
        }

class TransactionCategoryForm(forms.ModelForm):
    class Meta:
        model = TransactionCategory
        fields = ['name', 'cost_center']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'cost_center': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'name': _('Category name (e.g., "Groceries", "Rent", "Salary")'),
            'cost_center': _('Cost center this category belongs to (optional)'),
        }

class TransactionForm(forms.ModelForm):
    def __init__(self, *args, household=None, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        
        self.household = household
        
        if household:
            # Filter categories by the current household
            self.fields['category'].queryset = TransactionCategory.objects.filter(tax_household=household)
            
            # Filter bank accounts by the household members
            members = HouseholdMember.objects.filter(tax_household=household)
            self.fields['account'].queryset = BankAccount.objects.filter(members__in=members).distinct()
            
            # Make choices for the recipient selection
            member_choices = [(str(member.id), f"{member.first_name} {member.last_name}") for member in members]
            
            # Create a custom choice field with Family and members (no external option)
            self.fields['recipient'] = forms.ChoiceField(
                choices=[
                    ('family', _('Family')),  # Family option
                ] + member_choices,           # All household members
                required=True,  # Make it required since we removed the empty option
                widget=forms.Select(attrs={'class': 'form-control'})
            )
            
            # Set initial value for recipient field based on instance
            if instance:
                if instance.recipient_type == 'member' and instance.recipient_member:
                    self.initial['recipient'] = str(instance.recipient_member.id)
                else:
                    # For family or any other value, default to family
                    self.initial['recipient'] = 'family'
            
            # Hide the model fields we'll set in our form processing
            self.fields['recipient_type'].widget = forms.HiddenInput()
            self.fields['recipient_member'].widget = forms.HiddenInput()
            
            # Set up recurrence period field with proper choices and styling
            self.fields['recurrence_period'] = forms.ChoiceField(
                choices=Transaction.RECURRENCE_CHOICES,
                required=False,
                widget=forms.Select(attrs={
                    'class': 'form-control',
                })
            )
            
            # Don't disable the field even if not recurring yet - the JavaScript will handle this
            
        # Set default recurrence period to 'monthly'
        if instance and instance.is_recurring and not instance.recurrence_period:
            self.initial['recurrence_period'] = 'monthly'
        
        # Make sure date values are properly displayed
        if instance:
            # Ensure transaction date is properly set
            if instance.date:
                self.initial['date'] = instance.date
                
            # Set initial values for recurrence date fields if this is an existing recurring transaction
            if instance.is_recurring:
                if instance.recurrence_start_date:
                    self.initial['recurrence_start_date'] = instance.recurrence_start_date
                if instance.recurrence_end_date:
                    self.initial['recurrence_end_date'] = instance.recurrence_end_date
        
        # Add JavaScript for dynamic form behavior
        self.fields['is_recurring'].widget.attrs.update({
            'onchange': 'toggleRecurrenceOptions(this);'
        })
    
    class Meta:
        model = Transaction
        fields = [
            'date', 'description', 'amount', 'transaction_type', 'category', 
            'account', 'payment_method', 'recipient_type', 'recipient_member',
            'is_recurring', 'recurrence_period', 'recurrence_start_date', 'recurrence_end_date'
        ]
        widgets = {
            'date': DateInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'account': forms.Select(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'recipient_type': forms.HiddenInput(),
            'recipient_member': forms.HiddenInput(),
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recurrence_period': forms.Select(attrs={'class': 'form-control'}),
            'recurrence_start_date': DateInput(attrs={'class': 'form-control'}),
            'recurrence_end_date': DateInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'date': _('Date of the transaction'),
            'description': _('Description of what the transaction was for'),
            'amount': _('Amount of the transaction'),
            'transaction_type': _('Whether this is an expense or income'),
            'category': _('Category for this transaction'),
            'account': _('Account used for this transaction'),
            'payment_method': _('How this transaction was paid'),
            'recipient': _('Select "Family" or a specific household member'),
            'is_recurring': _('Check if this is a recurring transaction'),
            'recurrence_period': _('How often this transaction recurs'),
            'recurrence_start_date': _('When to start creating recurring transactions'),
            'recurrence_end_date': _('When to stop creating recurring transactions'),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Make sure transaction date is preserved
        if self.instance and self.instance.pk and self.instance.date:
            # If no date was provided in the form or if it was somehow reset
            if not cleaned_data.get('date'):
                cleaned_data['date'] = self.instance.date
        
        recipient_choice = cleaned_data.get('recipient')
        
        # Process recipient selection (now only Family or a specific member)
        if recipient_choice == 'family':
            # Family option selected
            cleaned_data['recipient_type'] = 'family'
            cleaned_data['recipient_member'] = None
        else:
            # Member selected - try to get the member
            try:
                member_id = int(recipient_choice)
                member = HouseholdMember.objects.get(id=member_id)
                cleaned_data['recipient_type'] = 'member'
                cleaned_data['recipient_member'] = member
            except (ValueError, TypeError, HouseholdMember.DoesNotExist):
                # Invalid member ID, this shouldn't happen with proper form validation
                raise forms.ValidationError(_("Invalid household member selected."))
        
        # Handle recurring transaction options
        is_recurring = cleaned_data.get('is_recurring')
        if is_recurring:
            from datetime import timedelta, date
            
            # Default to monthly if no recurrence period is selected
            if not cleaned_data.get('recurrence_period'):
                cleaned_data['recurrence_period'] = 'monthly'
                
            # Set default start date to transaction date if not provided
            if not cleaned_data.get('recurrence_start_date'):
                # Check if this is an edit of an existing transaction with a start date
                if self.instance and self.instance.pk and self.instance.recurrence_start_date:
                    cleaned_data['recurrence_start_date'] = self.instance.recurrence_start_date
                else:
                    # For new transactions, default to the transaction date
                    cleaned_data['recurrence_start_date'] = cleaned_data.get('date')
                
            # Set default end date to one year after start date if not provided
            if not cleaned_data.get('recurrence_end_date'):
                # Check if this is an edit of an existing transaction with an end date
                if self.instance and self.instance.pk and self.instance.recurrence_end_date:
                    cleaned_data['recurrence_end_date'] = self.instance.recurrence_end_date
                else:
                    # For new transactions, default to one year after start date
                    start_date = cleaned_data.get('recurrence_start_date')
                    if start_date:
                        # Set end date to one year after start date
                        cleaned_data['recurrence_end_date'] = date(
                            year=start_date.year + 1,
                            month=start_date.month,
                            day=start_date.day
                        )
            
            # VALIDATION: Ensure the transaction date (creation date) is within the validity period
            transaction_date = cleaned_data.get('date')
            start_date = cleaned_data.get('recurrence_start_date')
            end_date = cleaned_data.get('recurrence_end_date')
            
            if transaction_date and start_date and end_date:
                if transaction_date < start_date or transaction_date > end_date:
                    raise forms.ValidationError(
                        _("Transaction date must be within the recurrence validity period (%(start)s to %(end)s)."),
                        code='invalid_date_range',
                        params={'start': start_date.strftime('%Y-%m-%d'), 'end': end_date.strftime('%Y-%m-%d')}
                    )
        else:
            # Clear recurrence fields if not recurring
            cleaned_data['recurrence_period'] = ''
            cleaned_data['recurrence_start_date'] = None
            cleaned_data['recurrence_end_date'] = None
            
        return cleaned_data
        
    def save(self, commit=True):
        """Override save to handle recipient selection"""
        instance = super().save(commit=False)
        
        # Handle recipient selection
        recipient_choice = self.cleaned_data.get('recipient')
        instance.set_recipient(recipient_choice)
        
        if commit:
            instance.save()
        
        return instance
