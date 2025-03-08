from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
from django.db import transaction
from django.utils.translation import get_language

from .models import TaxHousehold, HouseholdMember, BankAccount, AccountType, TransactionCategory
from .forms import TaxHouseholdForm, HouseholdMemberForm, HouseholdMemberFormSet, BankAccountForm, TransactionCategoryForm

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

# Transaction Category Views
@login_required
def category_list(request):
    """View to list transaction categories"""
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
        
        return render(request, 'financial/category_list.html', {
            'categories': categories,
            'has_household': True,
            'has_bank_accounts': True,
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