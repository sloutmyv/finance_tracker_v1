from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from .models import TaxHousehold, HouseholdMember, BankAccount, AccountType, PaymentMethod

class DateInput(forms.DateInput):
    input_type = 'date'

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
        fields = ['name', 'bank_name', 'account_type', 'currency', 'members']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'members': forms.CheckboxSelectMultiple(),
        }
        help_texts = {
            'name': _('A descriptive name for the account, e.g., "Joint Checking" or "Savings"'),
            'bank_name': _('The name of the bank or financial institution'),
            'currency': _('The currency used for this account'),
            'members': _('Select all family members who have access to this account'),
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