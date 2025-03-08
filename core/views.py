from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
from django.db import transaction
from django.utils.translation import get_language, gettext_lazy as _
from django.utils import timezone

from .models import TaxHousehold, HouseholdMember, BankAccount, AccountType, TransactionCategory, CostCenter, Transaction, PaymentMethod
from .forms import TaxHouseholdForm, HouseholdMemberForm, HouseholdMemberFormSet, BankAccountForm, TransactionCategoryForm, CostCenterForm, TransactionForm

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')

@login_required
def dashboard(request):
    # Check if user just logged in
    if 'login_success' not in request.session:
        messages.success(request, f"Welcome back, {request.user.username}!")
        request.session['login_success'] = True
    
    # Initialize setup status variables
    has_household = False
    has_members = False
    has_bank_accounts = False
    has_categories = False
    setup_complete = False
    transaction_form = None
    recent_transactions = []
    payment_methods = []
    
    try:
        # Check if user has a tax household
        household = request.user.tax_household
        has_household = True
        
        # Check if the household has members
        members = household.members.all()
        has_members = members.exists()
        
        # Check if there are bank accounts linked to any household members
        if has_members:
            bank_accounts = BankAccount.objects.filter(members__in=members).distinct()
            has_bank_accounts = bank_accounts.exists()
        
        # Check if the household has any categories
        if has_bank_accounts:
            has_categories = TransactionCategory.objects.filter(tax_household=household).exists()
        
        # Financial environment is complete when all steps are done
        setup_complete = has_household and has_members and has_bank_accounts and has_categories
        
        # If setup is complete, create a transaction form and get recent transactions
        if setup_complete:
            # Handle transaction form submission
            if request.method == 'POST':
                # Debug - print all POST data
                print("DASHBOARD DEBUG - POST data:")
                for key, value in request.POST.items():
                    print(f"  {key}: {value}")
                
                # Create a modified POST data with recipient_type field added
                post_data = request.POST.copy()
                recipient_id = post_data.get('recipient')
                
                print(f"DASHBOARD DEBUG - Recipient from form: {recipient_id}")
                
                # Pre-process recipient value (now only family or member)
                if recipient_id == 'family':
                    post_data['recipient_type'] = 'family'
                    post_data['recipient_member'] = ''
                else:
                    try:
                        # Try to find member
                        member_id = int(recipient_id)
                        member = HouseholdMember.objects.get(id=member_id)
                        post_data['recipient_type'] = 'member'
                        post_data['recipient_member'] = member.id
                    except (ValueError, TypeError, HouseholdMember.DoesNotExist):
                        # Set a default if something goes wrong
                        post_data['recipient_type'] = 'family'  # Default to family if invalid
                        post_data['recipient_member'] = ''
                
                print(f"DASHBOARD DEBUG - Modified POST data:")
                for key, value in post_data.items():
                    print(f"  {key}: {value}")
                
                # Use modified data
                transaction_form = TransactionForm(post_data, household=household)
                
                if transaction_form.is_valid():
                    print("DASHBOARD DEBUG - Form is valid")
                    
                    # Create and save transaction
                    transaction = transaction_form.save(commit=False)
                    transaction.tax_household = household
                    
                    try:
                        transaction.save()
                        print(f"DASHBOARD DEBUG - Transaction saved with ID: {transaction.id}")
                        messages.success(request, _("Transaction created successfully."))
                        return redirect('dashboard')
                    except Exception as e:
                        print(f"DASHBOARD DEBUG - Error saving: {e}")
                        messages.error(request, _("Error creating transaction."))
                else:
                    print("DASHBOARD DEBUG - Form is invalid")
                    print(f"DASHBOARD DEBUG - Form errors: {transaction_form.errors}")
                    messages.error(request, f"Form validation errors: {transaction_form.errors}")
            else:
                # Initialize an empty form
                transaction_form = TransactionForm(household=household)
                
                # Set default date to today
                transaction_form.initial = {'date': timezone.now().date()}
            
            # Get recent transactions
            recent_transactions = Transaction.objects.filter(
                tax_household=household
            ).order_by('-date', '-created_at')[:5]
            
            # Get payment methods for the form
            payment_methods = PaymentMethod.objects.filter(is_active=True)
    
    except TaxHousehold.DoesNotExist:
        # User doesn't have a tax household yet
        pass
    
    return render(request, 'dashboard.html', {
        'username': request.user.username,
        'has_household': has_household,
        'has_members': has_members,
        'has_bank_accounts': has_bank_accounts,
        'has_categories': has_categories,
        'setup_complete': setup_complete,
        'transaction_form': transaction_form,
        'recent_transactions': recent_transactions,
        'payment_methods': payment_methods,
    })

def logout_view(request):
    # Clear login_success from session to show welcome message on next login
    if 'login_success' in request.session:
        del request.session['login_success']
    
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')

# Financial Environment Views
@login_required
def financial_settings(request):
    """View to display financial environment settings"""
    try:
        tax_household = request.user.tax_household
        household_members = tax_household.members.all()
    except TaxHousehold.DoesNotExist:
        tax_household = None
        household_members = []
    
    context = {
        'tax_household': tax_household,
        'household_members': household_members,
    }
    return render(request, 'financial/settings.html', context)

@login_required
def household_create(request):
    """View to create a new tax household"""
    if hasattr(request.user, 'tax_household'):
        messages.warning(request, "You already have a tax household.")
        return redirect('financial_settings')
    
    if request.method == 'POST':
        form = TaxHouseholdForm(request.POST)
        if form.is_valid():
            household = form.save(commit=False)
            household.user = request.user
            household.save()
            messages.success(request, "Tax household created successfully!")
            return redirect('household_members')
    else:
        form = TaxHouseholdForm()
    
    return render(request, 'financial/household_form.html', {'form': form})

@login_required
def household_update(request):
    """View to update an existing tax household"""
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, "You don't have a tax household yet.")
        return redirect('household_create')
    
    if request.method == 'POST':
        form = TaxHouseholdForm(request.POST, instance=household)
        if form.is_valid():
            form.save()
            messages.success(request, "Tax household updated successfully!")
            return redirect('financial_settings')
    else:
        form = TaxHouseholdForm(instance=household)
    
    return render(request, 'financial/household_form.html', {'form': form, 'update': True})

@login_required
def household_members(request):
    """View to manage household members"""
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, "You need to create a tax household first.")
        return redirect('household_create')
    
    if request.method == 'POST':
        formset = HouseholdMemberFormSet(request.POST, instance=household)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Household members updated successfully!")
            return redirect('financial_settings')
    else:
        formset = HouseholdMemberFormSet(instance=household)
    
    return render(request, 'financial/household_members.html', {
        'formset': formset,
        'household': household
    })

@login_required
def member_create(request):
    """View to create a new household member"""
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, "You need to create a tax household first.")
        return redirect('household_create')
    
    if request.method == 'POST':
        form = HouseholdMemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.tax_household = household
            member.save()
            messages.success(request, f"Member {member.first_name} {member.last_name} created successfully!")
            return redirect('financial_settings')
    else:
        form = HouseholdMemberForm()
    
    return render(request, 'financial/member_form.html', {'form': form})

@login_required
def member_update(request, pk):
    """View to update a household member"""
    member = get_object_or_404(HouseholdMember, pk=pk)
    
    # Check that the member belongs to the user's household
    if member.tax_household.user != request.user:
        messages.error(request, "You don't have permission to edit this member.")
        return redirect('financial_settings')
    
    if request.method == 'POST':
        form = HouseholdMemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, f"Member {member.first_name} {member.last_name} updated successfully!")
            return redirect('financial_settings')
    else:
        form = HouseholdMemberForm(instance=member)
    
    return render(request, 'financial/member_form.html', {'form': form, 'member': member})

@login_required
def member_delete(request, pk):
    """View to delete a household member"""
    member = get_object_or_404(HouseholdMember, pk=pk)
    
    # Check that the member belongs to the user's household
    if member.tax_household.user != request.user:
        messages.error(request, "You don't have permission to delete this member.")
        return redirect('financial_settings')
    
    if request.method == 'POST':
        member_name = f"{member.first_name} {member.last_name}"
        member.delete()
        messages.success(request, f"Member {member_name} deleted successfully!")
        return redirect('financial_settings')
    
    return render(request, 'financial/member_confirm_delete.html', {'member': member})

@login_required
def bank_account_list(request):
    """View to list bank accounts"""
    try:
        household = request.user.tax_household
        # Get all members of the household
        members = household.members.all()
        
        # Check if there are any members in the household
        has_members = members.exists()
        
        # Get all bank accounts linked to any of these members
        bank_accounts = BankAccount.objects.filter(members__in=members).distinct() if has_members else []
        
        return render(request, 'financial/bank_account_list.html', {
            'bank_accounts': bank_accounts,
            'has_household': True,
            'has_members': has_members
        })
        
    except TaxHousehold.DoesNotExist:
        # Instead of redirecting, render the bank account page with a notification
        return render(request, 'financial/bank_account_list.html', {
            'bank_accounts': [],
            'has_household': False,
            'has_members': False
        })

@login_required
def bank_account_create(request):
    """View to create a new bank account"""
    try:
        household = request.user.tax_household
        if household.members.count() == 0:
            messages.error(request, "You need to add household members first.")
            return redirect('member_create')
    except TaxHousehold.DoesNotExist:
        messages.error(request, "You need to create a tax household first.")
        return redirect('household_create')
    
    # Ensure default account types are created
    if AccountType.objects.count() == 0:
        try:
            # Create default account types if none exist
            from django.core.management import call_command
            call_command('create_default_account_types')
            messages.info(request, "Default account types have been created.")
        except Exception as e:
            messages.error(request, f"Error creating default account types: {str(e)}")
            return redirect('bank_account_list')
    
    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        # Limit member choices to user's household members
        form.fields['members'].queryset = household.members.all()
        
        if form.is_valid():
            account = form.save()
            messages.success(request, f"Bank account '{account.name}' created successfully!")
            return redirect('bank_account_list')
    else:
        form = BankAccountForm()
        # Limit member choices to user's household members
        form.fields['members'].queryset = household.members.all()
    
    return render(request, 'financial/bank_account_form.html', {'form': form})

@login_required
def bank_account_update(request, pk):
    """View to update a bank account"""
    account = get_object_or_404(BankAccount, pk=pk)
    
    # Verify the account belongs to a member in the user's household
    if not account.members.filter(tax_household__user=request.user).exists():
        messages.error(request, "You don't have permission to edit this bank account.")
        return redirect('bank_account_list')
    
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, "You need to create a tax household first.")
        return redirect('household_create')
    
    # Ensure default account types are created
    if AccountType.objects.count() == 0:
        try:
            # Create default account types if none exist
            from django.core.management import call_command
            call_command('create_default_account_types')
            messages.info(request, "Default account types have been created.")
        except Exception as e:
            messages.error(request, f"Error creating default account types: {str(e)}")
            return redirect('bank_account_list')
    
    if request.method == 'POST':
        form = BankAccountForm(request.POST, instance=account)
        # Limit member choices to user's household members
        form.fields['members'].queryset = household.members.all()
        
        if form.is_valid():
            updated_account = form.save()
            messages.success(request, f"Bank account '{updated_account.name}' updated successfully!")
            return redirect('bank_account_list')
    else:
        form = BankAccountForm(instance=account)
        # Limit member choices to user's household members
        form.fields['members'].queryset = household.members.all()
    
    return render(request, 'financial/bank_account_form.html', {'form': form, 'account': account})

@login_required
def bank_account_delete(request, pk):
    """View to delete a bank account"""
    account = get_object_or_404(BankAccount, pk=pk)
    
    # Verify the account belongs to a member in the user's household
    if not account.members.filter(tax_household__user=request.user).exists():
        messages.error(request, "You don't have permission to delete this bank account.")
        return redirect('bank_account_list')
    
    if request.method == 'POST':
        account_name = account.name
        account.delete()
        messages.success(request, f"Bank account '{account_name}' deleted successfully!")
        return redirect('bank_account_list')
    
    return render(request, 'financial/bank_account_confirm_delete.html', {'account': account})

# Cost Center Views
# Redirect to category list since we're now showing cost centers there
@login_required
def cost_center_list(request):
    """Redirects to category list which now includes cost centers"""
    return redirect('category_list')

@login_required
def cost_center_create(request):
    """View to create a new cost center"""
    try:
        household = request.user.tax_household
        
        # Check if they have bank accounts (prerequisite)
        if not BankAccount.objects.filter(members__in=household.members.all()).exists():
            messages.error(request, "You need to create bank accounts first.")
            return redirect('bank_account_create')
    except TaxHousehold.DoesNotExist:
        messages.error(request, "You need to create a tax household first.")
        return redirect('household_create')
    
    if request.method == 'POST':
        form = CostCenterForm(request.POST)
        if form.is_valid():
            cost_center = form.save(commit=False)
            cost_center.tax_household = household
            cost_center.save()
            messages.success(request, f"Cost center '{cost_center.name}' created successfully!")
            return redirect('category_list')
    else:
        form = CostCenterForm()
    
    return render(request, 'financial/cost_center_form.html', {'form': form})

@login_required
def cost_center_update(request, pk):
    """View to update a cost center"""
    cost_center = get_object_or_404(CostCenter, pk=pk)
    
    # Verify the cost center belongs to the user's household
    if cost_center.tax_household.user != request.user:
        messages.error(request, "You don't have permission to edit this cost center.")
        return redirect('cost_center_list')
    
    if request.method == 'POST':
        form = CostCenterForm(request.POST, instance=cost_center)
        if form.is_valid():
            updated_cost_center = form.save()
            messages.success(request, f"Cost center '{updated_cost_center.name}' updated successfully!")
            return redirect('category_list')
    else:
        form = CostCenterForm(instance=cost_center)
    
    return render(request, 'financial/cost_center_form.html', {'form': form, 'cost_center': cost_center})

@login_required
def cost_center_delete(request, pk):
    """View to delete a cost center"""
    cost_center = get_object_or_404(CostCenter, pk=pk)
    
    # Verify the cost center belongs to the user's household
    if cost_center.tax_household.user != request.user:
        messages.error(request, "You don't have permission to delete this cost center.")
        return redirect('category_list')
    
    if request.method == 'POST':
        # Get all categories associated with this cost center
        categories = TransactionCategory.objects.filter(cost_center=cost_center)
        
        # Remove cost center association from all categories
        for category in categories:
            category.cost_center = None
            category.save()
        
        cost_center_name = cost_center.name
        cost_center.delete()
        messages.success(request, f"Cost center '{cost_center_name}' deleted successfully!")
        return redirect('category_list')
    
    return render(request, 'financial/cost_center_confirm_delete.html', {'cost_center': cost_center})

@login_required
def assign_categories_to_cost_center(request, pk):
    """View to assign multiple categories to a cost center"""
    cost_center = get_object_or_404(CostCenter, pk=pk)
    
    # Verify the cost center belongs to the user's household
    if cost_center.tax_household.user != request.user:
        messages.error(request, "You don't have permission to modify this cost center.")
        return redirect('category_list')
    
    # Get all categories from this household that aren't already assigned to this cost center
    available_categories = TransactionCategory.objects.filter(
        tax_household=cost_center.tax_household
    ).exclude(
        cost_center=cost_center
    ).order_by('name')
    
    if request.method == 'POST':
        category_ids = request.POST.getlist('categories')
        
        # Assign categories to this cost center
        if category_ids:
            assigned_count = 0
            for category_id in category_ids:
                try:
                    category = TransactionCategory.objects.get(
                        id=category_id,
                        tax_household=cost_center.tax_household
                    )
                    category.cost_center = cost_center
                    category.save()
                    assigned_count += 1
                except TransactionCategory.DoesNotExist:
                    continue
            
            messages.success(request, f"{assigned_count} categories assigned to cost center '{cost_center.name}'")
        else:
            messages.info(request, "No categories were selected.")
        
        return redirect('category_list')
    
    return render(request, 'financial/cost_center_assign_categories.html', {
        'cost_center': cost_center,
        'available_categories': available_categories
    })

# Transaction Category Views
@login_required
def category_list(request):
    """View to list transaction categories and cost centers"""
    try:
        household = request.user.tax_household
        
        # Check if they have bank accounts (prerequisite)
        has_bank_accounts = BankAccount.objects.filter(members__in=household.members.all()).exists()
        
        if not has_bank_accounts:
            messages.warning(request, "You need to create bank accounts before adding categories.")
            return redirect('bank_account_create')
        
        # Get all categories, ordered alphabetically
        categories = TransactionCategory.objects.filter(
            tax_household=household
        ).order_by('name')
        
        # Get all cost centers
        cost_centers = CostCenter.objects.filter(
            tax_household=household
        ).order_by('name')
        
        # Group categories by cost center
        categorized = {}
        uncategorized = []
        
        for category in categories:
            if category.cost_center:
                if category.cost_center.id not in categorized:
                    categorized[category.cost_center.id] = {
                        'cost_center': category.cost_center,
                        'categories': []
                    }
                categorized[category.cost_center.id]['categories'].append(category)
            else:
                uncategorized.append(category)
        
        # Get statistics for the templates
        total_categories = categories.count()
        total_cost_centers = cost_centers.count()
        categorized_count = total_categories - len(uncategorized)
        
        return render(request, 'financial/category_list.html', {
            'categories': categories,
            'uncategorized': uncategorized,
            'categorized': categorized,
            'cost_centers': cost_centers,
            'has_household': True,
            'has_bank_accounts': True,
            'stats': {
                'total_categories': total_categories,
                'total_cost_centers': total_cost_centers,
                'categorized_count': categorized_count,
                'uncategorized_count': len(uncategorized)
            }
        })
        
    except TaxHousehold.DoesNotExist:
        messages.error(request, "You need to create a tax household first.")
        return redirect('household_create')

@login_required
def category_create(request):
    """View to create a new transaction category"""
    try:
        household = request.user.tax_household
        
        # Check if they have bank accounts (prerequisite)
        if not BankAccount.objects.filter(members__in=household.members.all()).exists():
            messages.error(request, "You need to create bank accounts first.")
            return redirect('bank_account_create')
    except TaxHousehold.DoesNotExist:
        messages.error(request, "You need to create a tax household first.")
        return redirect('household_create')
    
    if request.method == 'POST':
        form = TransactionCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.tax_household = household
            category.save()
            messages.success(request, f"Category '{category.name}' created successfully!")
            return redirect('category_list')
    else:
        form = TransactionCategoryForm()
        # Only show cost centers belonging to this household
        form.fields['cost_center'].queryset = CostCenter.objects.filter(tax_household=household)
    
    return render(request, 'financial/category_form.html', {'form': form})

@login_required
def category_update(request, pk):
    """View to update a transaction category"""
    category = get_object_or_404(TransactionCategory, pk=pk)
    
    # Verify the category belongs to the user's household
    if category.tax_household.user != request.user:
        messages.error(request, "You don't have permission to edit this category.")
        return redirect('category_list')
    
    if request.method == 'POST':
        form = TransactionCategoryForm(request.POST, instance=category)
        if form.is_valid():
            updated_category = form.save()
            messages.success(request, f"Category '{updated_category.name}' updated successfully!")
            return redirect('category_list')
    else:
        form = TransactionCategoryForm(instance=category)
        # Only show cost centers belonging to this household
        form.fields['cost_center'].queryset = CostCenter.objects.filter(tax_household=category.tax_household)
    
    return render(request, 'financial/category_form.html', {'form': form, 'category': category})

@login_required
def category_delete(request, pk):
    """View to delete a transaction category"""
    category = get_object_or_404(TransactionCategory, pk=pk)
    
    # Verify the category belongs to the user's household
    if category.tax_household.user != request.user:
        messages.error(request, "You don't have permission to delete this category.")
        return redirect('category_list')
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f"Category '{category_name}' deleted successfully!")
        return redirect('category_list')
    
    return render(request, 'financial/category_confirm_delete.html', {'category': category})

# Helper function to process transactions
def process_transaction_from_form(form, household):
    """
    Helper function to create or update a transaction from a form.
    Completely bypasses form.save() to handle recipient field manually.
    """
    # Get existing instance or create a new one
    if form.instance.pk:
        transaction = form.instance  # Use existing instance for updates
    else:
        transaction = Transaction()  # Create a new instance for creates
    
    # Set basic fields from form data directly
    transaction.tax_household = household
    transaction.date = form.cleaned_data.get('date')
    transaction.description = form.cleaned_data.get('description')
    transaction.amount = form.cleaned_data.get('amount')
    transaction.transaction_type = form.cleaned_data.get('transaction_type')
    transaction.category = form.cleaned_data.get('category')
    transaction.account = form.cleaned_data.get('account')
    transaction.payment_method = form.cleaned_data.get('payment_method')
    transaction.is_recurring = form.cleaned_data.get('is_recurring', False)
    
    # Handle recipient field based on the selection
    recipient_value = form.cleaned_data.get('recipient')
    
    print(f"DEBUG: Raw recipient value: {recipient_value}, type: {type(recipient_value)}")
    
    if recipient_value == '-1':
        # Family option selected
        transaction.is_family_recipient = True
        transaction.recipient = None
        print("DEBUG: Setting as family recipient")
    elif recipient_value and recipient_value != '':
        # A specific member was selected
        transaction.is_family_recipient = False
        try:
            # Get the member by ID - make sure we convert string to int
            member_id = int(recipient_value)
            member = HouseholdMember.objects.get(id=member_id)
            print(f"DEBUG: Found member {member} with ID {member_id}")
            transaction.recipient = member
        except (ValueError, TypeError, HouseholdMember.DoesNotExist) as e:
            print(f"DEBUG: Error setting recipient: {e}")
            transaction.recipient = None
    else:
        # No recipient selected
        transaction.is_family_recipient = False
        transaction.recipient = None
        print("DEBUG: No recipient selected")
    
    # Handle recurring transaction options
    if transaction.is_recurring:
        recurrence = form.cleaned_data.get('recurrence_period')
        if not recurrence:
            transaction.recurrence_period = 'monthly'  # Default
        else:
            transaction.recurrence_period = recurrence
    else:
        transaction.recurrence_period = ''
    
    # Save the transaction
    transaction.save()
    print(f"DEBUG: Saved transaction with recipient: {transaction.recipient}, is_family: {transaction.is_family_recipient}")
    
    return transaction

# Transaction Views
@login_required
def transaction_list(request):
    """View to display all transactions with filtering options"""
    try:
        household = request.user.tax_household
        transactions = Transaction.objects.filter(tax_household=household).order_by('-date', '-created_at')
        
        # Handle filtering
        category_filter = request.GET.get('category')
        account_filter = request.GET.get('account')
        type_filter = request.GET.get('type')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if category_filter:
            transactions = transactions.filter(category_id=category_filter)
        
        if account_filter:
            transactions = transactions.filter(account_id=account_filter)
        
        if type_filter:
            transactions = transactions.filter(transaction_type=type_filter)
        
        if date_from:
            transactions = transactions.filter(date__gte=date_from)
        
        if date_to:
            transactions = transactions.filter(date__lte=date_to)
        
        # Get filter options
        categories = TransactionCategory.objects.filter(tax_household=household)
        members = household.members.all()
        accounts = BankAccount.objects.filter(members__in=members).distinct()
        
        context = {
            'transactions': transactions,
            'categories': categories,
            'accounts': accounts,
            'current_filters': {
                'category': category_filter,
                'account': account_filter,
                'type': type_filter,
                'date_from': date_from,
                'date_to': date_to,
            }
        }
        
        return render(request, 'financial/transaction_list.html', context)
    
    except TaxHousehold.DoesNotExist:
        messages.warning(request, _("You need to set up your financial environment first."))
        return redirect('dashboard')

@login_required
def recurring_transaction_list(request):
    """View to display recurring transactions"""
    try:
        household = request.user.tax_household
        transactions = Transaction.objects.filter(
            tax_household=household,
            is_recurring=True
        ).order_by('-date', '-created_at')
        
        context = {
            'transactions': transactions,
            'is_recurring_view': True,
        }
        
        return render(request, 'financial/transaction_list.html', context)
    
    except TaxHousehold.DoesNotExist:
        messages.warning(request, _("You need to set up your financial environment first."))
        return redirect('dashboard')

@login_required
def transaction_create(request):
    """View to create a new transaction"""
    try:
        household = request.user.tax_household
        
        # Check if there are payment methods available
        payment_methods = PaymentMethod.objects.filter(is_active=True)
        if not payment_methods.exists():
            # Create a default payment method if none exists
            PaymentMethod.objects.create(
                name=_("Credit Card"),
                icon="bi-credit-card",
                is_active=True
            )
        
        if request.method == 'POST':
            # Debug - print all POST data
            print("DEBUG - POST data:")
            for key, value in request.POST.items():
                print(f"  {key}: {value}")
            
            # Create a modified POST data with recipient_type field added
            post_data = request.POST.copy()
            recipient_id = post_data.get('recipient')
            
            print(f"DEBUG - Recipient from form: {recipient_id}")
            
            # Pre-process recipient value (now only family or member)
            if recipient_id == 'family':
                post_data['recipient_type'] = 'family'
                post_data['recipient_member'] = ''
            else:
                try:
                    # Try to find member
                    member_id = int(recipient_id)
                    member = HouseholdMember.objects.get(id=member_id)
                    post_data['recipient_type'] = 'member'
                    post_data['recipient_member'] = member.id
                except (ValueError, TypeError, HouseholdMember.DoesNotExist):
                    # Set a default if something goes wrong
                    post_data['recipient_type'] = 'family'  # Default to family if invalid
                    post_data['recipient_member'] = ''
            
            print(f"DEBUG - Modified POST data:")
            for key, value in post_data.items():
                print(f"  {key}: {value}")
            
            # Use modified data
            form = TransactionForm(post_data, household=household)
            
            if form.is_valid():
                print("DEBUG - Form is valid")
                
                # Create and save transaction
                transaction = form.save(commit=False)
                transaction.tax_household = household
                
                try:
                    transaction.save()
                    print(f"DEBUG - Transaction saved with ID: {transaction.id}")
                    messages.success(request, _("Transaction created successfully."))
                    return redirect('dashboard')
                except Exception as e:
                    print(f"DEBUG - Error saving: {e}")
                    messages.error(request, _("Error creating transaction."))
            else:
                print("DEBUG - Form is invalid")
                print(f"DEBUG - Form errors: {form.errors}")
                messages.error(request, f"Form validation errors: {form.errors}")
        else:
            form = TransactionForm(household=household)
            form.initial = {'date': timezone.now().date()}
        
        return render(request, 'financial/transaction_form.html', {
            'form': form,
            'title': _('Create Transaction'),
        })
    
    except TaxHousehold.DoesNotExist:
        messages.warning(request, _("You need to set up your financial environment first."))
        return redirect('dashboard')

@login_required
def transaction_update(request, pk):
    """View to update an existing transaction"""
    try:
        household = request.user.tax_household
        transaction = get_object_or_404(Transaction, pk=pk, tax_household=household)
        
        # Check if there are payment methods available
        payment_methods = PaymentMethod.objects.filter(is_active=True)
        if not payment_methods.exists():
            # Create a default payment method if none exists
            PaymentMethod.objects.create(
                name=_("Credit Card"),
                icon="bi-credit-card",
                is_active=True
            )
        
        if request.method == 'POST':
            # Debug - print all POST data
            print("DEBUG - POST data:")
            for key, value in request.POST.items():
                print(f"  {key}: {value}")
            
            # Create a modified POST data with recipient_type field added
            post_data = request.POST.copy()
            recipient_id = post_data.get('recipient')
            
            print(f"DEBUG - Update - Recipient from form: {recipient_id}")
            
            # Pre-process recipient value (now only family or member)
            if recipient_id == 'family':
                post_data['recipient_type'] = 'family'
                post_data['recipient_member'] = ''
            else:
                try:
                    # Try to find member
                    member_id = int(recipient_id)
                    member = HouseholdMember.objects.get(id=member_id)
                    post_data['recipient_type'] = 'member'
                    post_data['recipient_member'] = member.id
                except (ValueError, TypeError, HouseholdMember.DoesNotExist):
                    # Set a default if something goes wrong
                    post_data['recipient_type'] = 'family'  # Default to family if invalid
                    post_data['recipient_member'] = ''
            
            print(f"DEBUG - Update - Modified POST data:")
            for key, value in post_data.items():
                print(f"  {key}: {value}")
                
            # Use modified data
            form = TransactionForm(post_data, household=household, instance=transaction)
            
            if form.is_valid():
                print("DEBUG - Update - Form is valid")
                
                # Save the transaction
                updated_transaction = form.save()
                
                print(f"DEBUG - Transaction updated with ID: {updated_transaction.id}")
                messages.success(request, _("Transaction updated successfully."))
                return redirect('transaction_list')
            else:
                print("DEBUG - Form is invalid")
                print(f"DEBUG - Form errors: {form.errors}")
        else:
            form = TransactionForm(household=household, instance=transaction)
        
        return render(request, 'financial/transaction_form.html', {
            'form': form,
            'transaction': transaction,
            'title': _('Update Transaction'),
        })
    
    except TaxHousehold.DoesNotExist:
        messages.warning(request, _("You need to set up your financial environment first."))
        return redirect('dashboard')

@login_required
def transaction_delete(request, pk):
    """View to delete a transaction"""
    try:
        household = request.user.tax_household
        transaction = get_object_or_404(Transaction, pk=pk, tax_household=household)
        
        if request.method == 'POST':
            transaction.delete()
            messages.success(request, _("Transaction deleted successfully."))
            return redirect('transaction_list')
        
        return render(request, 'financial/transaction_confirm_delete.html', {
            'transaction': transaction,
        })
    
    except TaxHousehold.DoesNotExist:
        messages.warning(request, _("You need to set up your financial environment first."))
        return redirect('dashboard')

@login_required
def transaction_duplicate(request, pk):
    """View to duplicate a transaction"""
    try:
        household = request.user.tax_household
        original_transaction = get_object_or_404(Transaction, pk=pk, tax_household=household)
        
        # Create initial data for the form
        initial_data = {
            'date': timezone.now().date(),  # Set date to today
            'description': original_transaction.description,
            'amount': original_transaction.amount,
            'transaction_type': original_transaction.transaction_type,
            'category': original_transaction.category.id,
            'account': original_transaction.account.id,
            'payment_method': original_transaction.payment_method.id,
            'is_recurring': original_transaction.is_recurring,
            'recurrence_period': original_transaction.recurrence_period
        }
        
        # Handle recipient
        if original_transaction.recipient_type == 'family':
            initial_data['recipient'] = 'family'
        elif original_transaction.recipient_type == 'member' and original_transaction.recipient_member:
            initial_data['recipient'] = original_transaction.recipient_member.id
        
        # Create a new form instance with initial data
        form = TransactionForm(initial=initial_data, household=household)
        
        if request.method == 'POST':
            # Handle form submission
            post_data = request.POST.copy()
            recipient_id = post_data.get('recipient')
            
            # Pre-process recipient value (now only family or member)
            if recipient_id == 'family':
                post_data['recipient_type'] = 'family'
                post_data['recipient_member'] = ''
            else:
                try:
                    # Try to find member
                    member_id = int(recipient_id)
                    member = HouseholdMember.objects.get(id=member_id)
                    post_data['recipient_type'] = 'member'
                    post_data['recipient_member'] = member.id
                except (ValueError, TypeError, HouseholdMember.DoesNotExist):
                    # Set a default if something goes wrong
                    post_data['recipient_type'] = 'family'  # Default to family if invalid
                    post_data['recipient_member'] = ''
            
            form = TransactionForm(post_data, household=household)
            
            if form.is_valid():
                transaction = form.save(commit=False)
                transaction.tax_household = household
                transaction.save()
                messages.success(request, _("Transaction duplicated successfully."))
                return redirect('transaction_list')
        
        return render(request, 'financial/transaction_form.html', {
            'form': form,
            'title': _('Duplicate Transaction'),
            'is_duplicate': True,
            'original_transaction': original_transaction
        })
    
    except TaxHousehold.DoesNotExist:
        messages.warning(request, _("You need to set up your financial environment first."))
        return redirect('dashboard')