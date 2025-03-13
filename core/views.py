from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.db import transaction, models
from django.utils.translation import get_language, gettext_lazy as _
from django.utils import timezone
from datetime import datetime, timedelta
import json
from decimal import Decimal

from .models import TaxHousehold, HouseholdMember, BankAccount, AccountType, TransactionCategory, CostCenter, Transaction, PaymentMethod
from .utils.currency import CurrencyExchangeService
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
                    
                    # Check if this is a transfer transaction
                    is_transfer = transaction_form.cleaned_data.get('is_transfer', False)
                    
                    # Make sure payment_method and category are in cleaned_data for transfers
                    if is_transfer:
                        # Make sure we have a payment method
                        if not transaction_form.cleaned_data.get('payment_method'):
                            print("ERROR: Missing payment_method in cleaned_data for transfer")
                            messages.error(request, _("Error: Missing payment method for transfer. Please try again."))
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
                        
                        # Make sure we have a category
                        if not transaction_form.cleaned_data.get('category'):
                            print("ERROR: Missing category in cleaned_data for transfer")
                            messages.error(request, _("Error: Missing category for transfer. Please try again."))
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
                    
                    if is_transfer:
                        # For transfers, we need to create two transactions
                        try:
                            # Start a database transaction to ensure both operations succeed or fail together
                            from django.db import transaction as db_transaction
                            with db_transaction.atomic():
                                # Get source and destination accounts
                                source_account = transaction_form.cleaned_data['account']
                                destination_account = transaction_form.cleaned_data['destination_account']
                                
                                # Get or create a Transfer category (using _ renamed to avoid name conflict)
                                transfer_category, created = TransactionCategory.objects.get_or_create(
                                    tax_household=household,
                                    name="Transfer",
                                    defaults={'name': 'Transfer'}
                                )
                                
                                # For transfer transactions, we need to create a special payment method if it doesn't exist
                                bank_transfer_method, created = PaymentMethod.objects.get_or_create(
                                    name="Bank Transfer",
                                    defaults={
                                        'name': 'Bank Transfer',
                                        'icon': 'bi-bank',
                                        'is_active': True
                                    }
                                )
                                                            
                                # Get appropriate recipient for source account (debit/withdrawal)
                                source_recipient_type, source_recipient_member = source_account.get_appropriate_recipient()
                                
                                # 1. Create the withdrawal transaction (expense)
                                withdrawal = transaction_form.save(commit=False)
                                withdrawal.tax_household = household
                                withdrawal.transaction_type = 'expense'
                                withdrawal.category = transfer_category
                                withdrawal.payment_method = bank_transfer_method
                                withdrawal.recipient_type = source_recipient_type  # Set based on source account ownership
                                withdrawal.recipient_member = source_recipient_member
                                withdrawal.description = f"{withdrawal.description} (to {destination_account.name})"
                                withdrawal.is_transfer = True  # Mark as transfer
                                withdrawal.save()
                                
                                # Get appropriate recipient for destination account
                                recipient_type, recipient_member = destination_account.get_appropriate_recipient()
                                
                                # 2. Create the deposit transaction (income)
                                deposit = Transaction(
                                    tax_household=household,
                                    date=transaction_form.cleaned_data['date'],
                                    description=f"{transaction_form.cleaned_data['description']} (from {source_account.name})",
                                    category=transfer_category,
                                    amount=transaction_form.cleaned_data['amount'],
                                    account=destination_account,
                                    payment_method=bank_transfer_method, 
                                    transaction_type='income',
                                    recipient_type=recipient_type,  # Set based on destination account ownership
                                    recipient_member=recipient_member,
                                    is_recurring=withdrawal.is_recurring,  # Copy recurring setting from withdrawal transaction
                                    recurrence_period=withdrawal.recurrence_period,  # Copy recurrence period
                                    recurrence_start_date=withdrawal.recurrence_start_date,  # Copy start date
                                    recurrence_end_date=withdrawal.recurrence_end_date,  # Copy end date
                                    is_transfer=True     # Mark as transfer
                                )
                                deposit.save()
                                
                                # 3. Link the paired transactions
                                withdrawal.paired_transaction = deposit
                                withdrawal.save()
                                deposit.paired_transaction = withdrawal
                                deposit.save()
                                
                                print(f"DASHBOARD DEBUG - Created linked transfer transactions: {withdrawal.id} <-> {deposit.id}")
                            
                            messages.success(request, _("Transfer transaction created successfully."))
                            return redirect('dashboard')
                        except Exception as e:
                            print(f"DASHBOARD DEBUG - Error saving transfer: {e}")
                            messages.error(request, _("Error creating transfer transaction."))
                    else:
                        # Regular transaction (non-transfer)
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
            
            # Get transactions from the database for the dashboard
            db_transactions = Transaction.objects.filter(tax_household=household)
            
            # Get today's date for generating recurring instances
            from datetime import date
            today = date.today()
            
            # Separate recurring and non-recurring transactions
            recurring_db_transactions = list(db_transactions.filter(is_recurring=True))
            non_recurring_db_transactions = list(db_transactions.filter(is_recurring=False))
            
            # Generate instances for recurring transactions
            generated_instances = []
            for transaction in recurring_db_transactions:
                try:
                    # Generate instances for this recurring transaction
                    instances = transaction.generate_recurring_instances(current_date=today)
                    generated_instances.extend(instances)
                except Exception as e:
                    print(f"Error generating dashboard instances for transaction {transaction.id}: {e}")
            
            # Combine all transactions
            combined_transactions = non_recurring_db_transactions + recurring_db_transactions
            
            # Add generated instances, but skip any that would create duplicates or are in the future
            existing_dates = {(t.date, t.description, t.amount) for t in combined_transactions if t.date}
            
            unique_generated_instances = []
            for instance in generated_instances:
                # Skip future instances - only show instances up to and including today
                if instance.date > today:
                    continue
                    
                instance_key = (instance.date, instance.description, instance.amount)
                if instance_key not in existing_dates:
                    unique_generated_instances.append(instance)
                    existing_dates.add(instance_key)
                    
            all_transactions = combined_transactions + unique_generated_instances
            
            # Sort transactions by date and created_at (newest first)
            def safe_sort_key(transaction):
                # If transaction.date is None, use today as a fallback
                if transaction.date is None:
                    transaction_date = today
                else:
                    transaction_date = transaction.date
                    
                # Convert to date object if it's a datetime
                if hasattr(transaction_date, 'date'):
                    transaction_date = transaction_date.date()
                    
                # Handle created_at safely
                if hasattr(transaction, 'created_at') and transaction.created_at is not None:
                    created_at = transaction.created_at
                    if hasattr(created_at, 'date'):
                        created_at = created_at.date()
                else:
                    created_at = today
                    
                return (transaction_date, created_at)
                
            # Sort with our safe key function
            all_transactions.sort(key=safe_sort_key, reverse=True)
            
            # Take only the 7 most recent transactions
            recent_transactions = all_transactions[:7]
            
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

# Reporting & Analytics Views
@login_required
def balance_evolution(request):
    """View for displaying bank account balance evolution chart"""
    
    # Get user's household
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, _("You need to set up a household first"))
        return redirect('financial_settings')
    
    # Get members and their bank accounts
    members = household.members.all()
    if not members.exists():
        messages.error(request, _("You need to add members to your household first"))
        return redirect('household_members')
    
    # Get all bank accounts linked to household members
    bank_accounts = BankAccount.objects.filter(members__in=members).distinct()
    if not bank_accounts.exists():
        messages.error(request, _("You need to create at least one bank account first"))
        return redirect('bank_account_list')
    
    # Default date range (last 30 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Process any filter parameters
    selected_account_id = request.GET.get('account', None)
    custom_start_date = request.GET.get('start_date', None)
    custom_end_date = request.GET.get('end_date', None)
    
    # Process custom date range if provided
    if custom_start_date and custom_end_date:
        try:
            start_date = datetime.strptime(custom_start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(custom_end_date, '%Y-%m-%d').date()
        except ValueError:
            # If invalid dates, use default
            messages.warning(request, _("Invalid date format. Using default date range."))
    
    # Handle AJAX request for chart data
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        account_id = request.GET.get('account_id')
        display_currency = request.GET.get('display_currency', request.session.get('currency', 'EUR'))
        
        if not account_id:
            return JsonResponse({'error': 'Account ID is required'}, status=400)
        
        try:
            account = bank_accounts.get(id=account_id)
        except BankAccount.DoesNotExist:
            return JsonResponse({'error': 'Account not found'}, status=404)
        
        # Get balance evolution data with the selected display currency
        balance_data = calculate_balance_evolution(account, start_date, end_date, display_currency)
        
        return JsonResponse(balance_data)
    
    # For regular page request, render the template
    context = {
        'bank_accounts': bank_accounts,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'reporting/balance_evolution.html', context)

def calculate_balance_evolution(account, start_date, end_date, display_currency=None):
    """
    Calculate balance evolution for a specific account over a time period.
    Returns data formatted for a chart.
    
    Args:
        account: The BankAccount to analyze
        start_date: The start date for the chart
        end_date: The end date for the chart
        display_currency: The currency to display amounts in (defaults to account's currency)
    """
    # Import Decimal for consistent financial calculations
    from decimal import Decimal
    
    # If no display currency specified, use the account's currency
    if not display_currency:
        display_currency = account.currency
    
    # Get the initial balance (starting point)
    initial_balance = account.balance
    initial_balance_date = account.balance_date
    
    # Ensure we're working with Decimal from the start
    if not isinstance(initial_balance, Decimal):
        initial_balance = Decimal(str(initial_balance))
    
    # Get all stored transactions for this account
    base_transactions = Transaction.objects.filter(
        account=account
    ).order_by('date')
    
    # Get recurring transactions that need to be included
    recurring_transactions = Transaction.objects.filter(
        account=account,
        is_recurring=True
    )
    
    # Initialize data structures
    dates = []
    balances = []
    
    # Start with the recorded balance
    current_balance = initial_balance
    
    # Determine the chart start date (use requested start_date even if it's before the balance_date)
    chart_start_date = start_date
    
    # Generate recurring transaction instances for the entire period
    # This ensures we capture all instances that might affect the balance
    all_recurring_instances = []
    processed_recurring_transfers = set()  # Track processed recurring transfers to avoid duplicates
    
    for txn in recurring_transactions:
        # Skip paired transactions that are already processed
        if txn.is_transfer and txn.paired_transaction_id:
            # Create a unique key for this transfer pair
            transfer_pair_key = tuple(sorted([txn.id, txn.paired_transaction_id]))
            if transfer_pair_key in processed_recurring_transfers:
                continue
            processed_recurring_transfers.add(transfer_pair_key)
        
        instances = txn.generate_recurring_instances(current_date=end_date)
        all_recurring_instances.extend(instances)
    
    # Create a combined list of all transactions (stored + recurring instances)
    all_transactions = list(base_transactions)
    
    # Add recurring instances, ensuring we don't double count
    # Track processed instances of paired transactions
    processed_instance_pairs = set()
    
    for instance in all_recurring_instances:
        # Only include instances that aren't already in the base transactions
        # (the first instance is often the same as the base transaction)
        is_unique = True
        instance_date = instance.date
        instance_amount = instance.amount
        
        # Skip instance if it's part of a transfer pair we've already processed
        if hasattr(instance, 'paired_transaction') and instance.paired_transaction:
            if hasattr(instance, '_instance_date'):
                instance_date_str = instance._instance_date.strftime('%Y%m%d')
                
                # Create a unique key for this instance pair
                if hasattr(instance, '_recurring_parent') and hasattr(instance.paired_transaction, '_recurring_parent'):
                    parent_ids = tuple(sorted([
                        instance._recurring_parent.id, 
                        instance.paired_transaction._recurring_parent.id
                    ]))
                    pair_key = (parent_ids, instance_date_str)
                    
                    if pair_key in processed_instance_pairs:
                        continue  # Skip this instance as its pair was already processed
                    
                    processed_instance_pairs.add(pair_key)
        
        # Check if the instance is already in base transactions
        for base_txn in base_transactions:
            if (base_txn.date == instance_date and 
                base_txn.amount == instance_amount and
                base_txn.transaction_type == instance.transaction_type):
                is_unique = False
                break
                
        if is_unique:
            all_transactions.append(instance)
    
    # Sort transactions by date
    all_transactions.sort(key=lambda x: x.date)
    
    # For debugging, print all transaction dates with more details
    print(f"DEBUG - All transactions in date order (total: {len(all_transactions)}):")
    for idx, tx in enumerate(all_transactions):
        transfer_info = ""
        recurring_info = ""
        
        if tx.is_transfer:
            if hasattr(tx, 'paired_transaction') and tx.paired_transaction:
                paired_id = tx.paired_transaction.id if hasattr(tx.paired_transaction, 'id') else 'unknown'
                transfer_info = f", Transfer pair: {paired_id}"
            else:
                transfer_info = ", Transfer (unpaired)"
        
        if hasattr(tx, '_is_generated') and tx._is_generated:
            recurring_info = ", Recurring instance"
            if hasattr(tx, '_recurring_parent'):
                parent_id = tx._recurring_parent.id
                recurring_info += f" (parent: {parent_id})"
        elif tx.is_recurring:
            recurring_info = ", Recurring parent"
            
        print(f"  {idx+1}. Date: {tx.date}, Type: {tx.transaction_type}, Amount: {tx.amount}{transfer_info}{recurring_info}")
    
    # If we need to show balance before the recorded balance date, we need to work backwards
    if start_date < initial_balance_date:
        # Filter transactions that occurred before the initial balance date but after start date
        backward_transactions = [tx for tx in all_transactions 
                                if tx.date < initial_balance_date and tx.date >= start_date]
        # Sort in reverse order
        backward_transactions.sort(key=lambda x: x.date, reverse=True)
        
        # Adjust the current balance by reversing the effect of earlier transactions
        for txn in backward_transactions:
            # Ensure amount is a Decimal
            amount = txn.amount
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
                
            if txn.transaction_type == 'income':
                current_balance -= amount  # Subtract income that hasn't happened yet (from past perspective)
            else:  # expense
                current_balance += amount  # Add back expenses that haven't happened yet (from past perspective)
                
        # We've now calculated what the balance would have been at our start date
    else:
        # If start date is after initial balance date, adjust balance forward to start date
        forward_transactions = [tx for tx in all_transactions 
                               if tx.date >= initial_balance_date and tx.date < start_date]
        
        for txn in forward_transactions:
            # Ensure amount is a Decimal
            amount = txn.amount
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
                
            if txn.transaction_type == 'income':
                current_balance += amount
            else:  # expense
                current_balance -= amount
    
    # Generate dates between start and end
    current_date = chart_start_date
    day_delta = timedelta(days=1)
    
    # For debugging
    print(f"DEBUG - Chart start date: {chart_start_date}")
    print(f"DEBUG - Initial balance: {current_balance}")
    
    # Add initial balance point
    dates.append(chart_start_date.strftime('%Y-%m-%d'))
    balances.append(float(current_balance))
    
    # Create a dictionary to track balance changes by date for more efficient lookup
    balance_changes_by_date = {}
    
    # Ensure current_balance is a Decimal
    from decimal import Decimal
    if not isinstance(current_balance, Decimal):
        current_balance = Decimal(str(current_balance))
    
    # Group transactions by date
    for txn in all_transactions:
        if start_date <= txn.date <= end_date:
            date_str = txn.date.strftime('%Y-%m-%d')
            if date_str not in balance_changes_by_date:
                balance_changes_by_date[date_str] = Decimal('0.0')
                
            # Add or subtract based on transaction type
            # Make sure we're working with Decimal objects consistently
            amount = txn.amount
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
                
            if txn.transaction_type == 'income':
                balance_changes_by_date[date_str] += amount
            else:  # expense
                balance_changes_by_date[date_str] -= amount
    
    # Process each date in the range - add a data point for EVERY day
    print(f"DEBUG - Generating data points from {current_date} to {end_date}")
    data_point_count = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # If we have transactions on this date, update the balance
        if date_str in balance_changes_by_date:
            current_balance += balance_changes_by_date[date_str]
            print(f"DEBUG - Date {date_str} has transaction(s), new balance: {current_balance}")
        
        # Add a data point for this date (whether or not we have transactions)
        dates.append(date_str)
        balances.append(float(current_balance))
        data_point_count += 1
        
        # Move to next day
        current_date += day_delta
    
    print(f"DEBUG - Generated {data_point_count} data points for the chart")
    
    # Convert balances to display currency if needed
    converted_balances = balances
    if display_currency != account.currency:
        try:
            print(f"DEBUG - Converting from {account.currency} to {display_currency}")
            converted_balances = []
            for balance in balances:
                # Convert each balance point to the display currency
                converted_amount = CurrencyExchangeService.convert_currency(
                    Decimal(str(balance)), 
                    account.currency, 
                    display_currency
                )
                converted_balances.append(float(converted_amount) if converted_amount else balance)
        except Exception as e:
            # Log the error and fall back to original values
            print(f"ERROR - Failed to convert currency: {e}")
            # Keep using original balances
    
    # Return properly formatted data for the chart
    return {
        'dates': dates,
        'balances': converted_balances,
        'account_name': account.name,
        'currency': display_currency,  # Use display currency here
        'original_currency': account.currency
    }

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
            # Save the account first to get the primary key
            account = form.save()
            
            # After saving the form (which handles the M2M relationships),
            # explicitly update the reference code to ensure it's based on the actual members
            account.update_reference()
            
            messages.success(request, f"Bank account '{account.name}' created successfully with reference {account.reference}!")
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
            # Save the account with the form data
            updated_account = form.save()
            
            # After saving the form (which handles the M2M relationships),
            # explicitly update the reference code to ensure it reflects the current members
            updated_account.update_reference()
            
            messages.success(request, f"Bank account '{updated_account.name}' updated successfully with reference {updated_account.reference}!")
            return redirect('bank_account_list')
    else:
        form = BankAccountForm(instance=account)
        # Limit member choices to user's household members
        form.fields['members'].queryset = household.members.all()
    
    return render(request, 'financial/bank_account_form.html', {'form': form, 'account': account})

@login_required
def bank_account_delete(request, pk):
    """View to delete a bank account and all associated transactions"""
    account = get_object_or_404(BankAccount, pk=pk)
    
    # Verify the account belongs to a member in the user's household
    if not account.members.filter(tax_household__user=request.user).exists():
        messages.error(request, "You don't have permission to delete this bank account.")
        return redirect('bank_account_list')
    
    # Count related transactions
    transactions_count = Transaction.objects.filter(account=account).count()
    
    if request.method == 'POST':
        account_name = account.name
        
        # Use transaction to ensure data integrity
        with transaction.atomic():
            # First delete all related transactions
            deleted_transactions = Transaction.objects.filter(account=account).delete()
            
            # Now delete the account
            account.delete()
            
        # Show success message with transaction count
        if transactions_count > 0:
            messages.success(request, f"Bank account '{account_name}' and {transactions_count} related transactions were deleted successfully!")
        else:
            messages.success(request, f"Bank account '{account_name}' deleted successfully!")
        
        return redirect('bank_account_list')
    
    # Pass transaction count to the template
    return render(request, 'financial/bank_account_confirm_delete.html', {
        'account': account,
        'transactions_count': transactions_count
    })

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
    """View to display all transactions with filtering options, including recurring instances"""
    try:
        household = request.user.tax_household
        # Get all actual transactions from the database
        db_transactions = Transaction.objects.filter(tax_household=household)
        
        # Handle filtering
        category_filter = request.GET.get('category')
        account_filter = request.GET.get('account')
        type_filter = request.GET.get('type')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Apply filters to the database query
        if category_filter:
            db_transactions = db_transactions.filter(category_id=category_filter)
        
        if account_filter:
            db_transactions = db_transactions.filter(account_id=account_filter)
        
        if type_filter:
            db_transactions = db_transactions.filter(transaction_type=type_filter)
        
        # Don't apply date filters here yet, as we need to generate recurring instances first
        
        # Separate recurring and non-recurring transactions
        from datetime import date
        today = date.today()
        
        # Get all recurring and non-recurring transactions
        recurring_transactions = list(db_transactions.filter(is_recurring=True))
        non_recurring_transactions = list(db_transactions.filter(is_recurring=False))
        
        # Generate instances for recurring transactions
        generated_instances = []
        for transaction in recurring_transactions:
            # Detailed debug for transaction dates
            print(f"DEBUG: Processing transaction ID {transaction.id}")
            print(f"DEBUG: Transaction date: {transaction.date} (type: {type(transaction.date)})")
            print(f"DEBUG: Recurrence start date: {transaction.recurrence_start_date} (type: {type(transaction.recurrence_start_date) if transaction.recurrence_start_date else 'None'})")
            print(f"DEBUG: Recurrence end date: {transaction.recurrence_end_date} (type: {type(transaction.recurrence_end_date) if transaction.recurrence_end_date else 'None'})")
            
            try:
                # The transaction model will handle all validation logic:
                # 1. Check if creation date is within validity period
                # 2. Generate instances only within validity period
                # 3. Prevent duplicate instances
                instances = transaction.generate_recurring_instances(current_date=today)
                
                # Debug logging to help diagnose issues
                print(f"DEBUG: Generated {len(instances)} instances for transaction {transaction.id} ({transaction.description}) with recurrence {transaction.recurrence_period}")
                if instances:
                    print(f"DEBUG: First instance: {instances[0].date}, Last instance: {instances[-1].date}")
                    
                # Apply category and account filters to generated instances
                if category_filter:
                    instances = [inst for inst in instances if inst.category_id == int(category_filter)]
                if account_filter:
                    instances = [inst for inst in instances if inst.account_id == int(account_filter)]
                if type_filter:
                    instances = [inst for inst in instances if inst.transaction_type == type_filter]
                    
                generated_instances.extend(instances)
            except Exception as e:
                print(f"ERROR generating instances for transaction {transaction.id}: {e}")
                # Continue with other transactions instead of crashing
        
        # Combine all transactions
        combined_transactions = non_recurring_transactions + recurring_transactions
        
        # Add generated instances, but skip any that would create duplicates and any future instances
        # This prevents duplicates on the creation date of recurring transactions
        existing_dates = {(t.date, t.description, t.amount) for t in combined_transactions if t.date}
        
        unique_generated_instances = []
        for instance in generated_instances:
            # Skip future instances - only show instances up to and including today
            if instance.date > today:
                continue
                
            instance_key = (instance.date, instance.description, instance.amount)
            if instance_key not in existing_dates:
                unique_generated_instances.append(instance)
                existing_dates.add(instance_key)
                
        all_transactions = combined_transactions + unique_generated_instances
        
        # Apply date filters to the combined list
        if date_from:
            # Convert to date object if it's a string
            if isinstance(date_from, str):
                from django.utils.dateparse import parse_date
                date_from = parse_date(date_from)
                
            if date_from:  # Make sure we have a valid date
                all_transactions = [t for t in all_transactions if t.date and t.date >= date_from]
        
        if date_to:
            # Convert to date object if it's a string
            if isinstance(date_to, str):
                from django.utils.dateparse import parse_date
                date_to = parse_date(date_to)
                
            if date_to:  # Make sure we have a valid date
                all_transactions = [t for t in all_transactions if t.date and t.date <= date_to]
        
        # Sort transactions by date (newest first)
        # Use a safer sort key that handles None values
        def safe_sort_key(transaction):
            # If transaction.date is None, use today as a fallback
            if transaction.date is None:
                transaction_date = today
            else:
                transaction_date = transaction.date
                
            # Convert to date object if it's a datetime
            if hasattr(transaction_date, 'date'):
                transaction_date = transaction_date.date()
                
            # Handle created_at safely
            if hasattr(transaction, 'created_at') and transaction.created_at is not None:
                created_at = transaction.created_at
                if hasattr(created_at, 'date'):
                    created_at = created_at.date()
            else:
                created_at = today
                
            return (transaction_date, created_at)
            
        # Sort with our safe key function
        all_transactions.sort(key=safe_sort_key, reverse=True)
        
        # Get filter options
        categories = TransactionCategory.objects.filter(tax_household=household)
        members = household.members.all()
        accounts = BankAccount.objects.filter(members__in=members).distinct()
        
        context = {
            'transactions': all_transactions,
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
    """View to display non-transfer recurring transactions"""
    try:
        household = request.user.tax_household
        recurring_transactions = Transaction.objects.filter(
            tax_household=household,
            is_recurring=True,
            is_transfer=False  # Only include non-transfers
        ).order_by('-date', '-created_at')
        
        context = {
            'transactions': recurring_transactions,
            'is_recurring_view': True,
            'show_recurrence_details': True,  # Flag to show recurrence details in template
        }
        
        return render(request, 'financial/recurring_transaction_list.html', context)
    
    except TaxHousehold.DoesNotExist:
        messages.warning(request, _("You need to set up your financial environment first."))
        return redirect('dashboard')

@login_required
def recurring_transfer_list(request):
    """View to display recurring transfers"""
    try:
        household = request.user.tax_household
        
        # Get all recurring transfers (withdrawal side only)
        recurring_transfers = Transaction.objects.filter(
            tax_household=household,
            is_recurring=True,
            is_transfer=True,
            transaction_type='expense'  # Only get the withdrawal side of each transfer
        ).select_related(
            'account', 
            'paired_transaction',
            'paired_transaction__account'
        ).order_by('-date', '-created_at')
        
        context = {
            'transfers': recurring_transfers,
            'is_recurring_view': True,
            'show_recurrence_details': True,
        }
        
        return render(request, 'financial/recurring_transfer_list.html', context)
    
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
                
                # Check if this is a transfer transaction
                is_transfer = form.cleaned_data.get('is_transfer', False)
                
                # Make sure payment_method and category are in cleaned_data for transfers
                if is_transfer:
                    # Make sure we have a payment method
                    if not form.cleaned_data.get('payment_method'):
                        print("ERROR: Missing payment_method in cleaned_data for transfer")
                        messages.error(request, _("Error: Missing payment method for transfer. Please try again."))
                        return render(request, 'financial/transaction_form.html', {
                            'form': form,
                            'title': _('Create Transaction'),
                        })
                    
                    # Make sure we have a category
                    if not form.cleaned_data.get('category'):
                        print("ERROR: Missing category in cleaned_data for transfer")
                        messages.error(request, _("Error: Missing category for transfer. Please try again."))
                        return render(request, 'financial/transaction_form.html', {
                            'form': form,
                            'title': _('Create Transaction'),
                        })
                
                if is_transfer:
                    # For transfers, we need to create two transactions
                    try:
                        # Start a database transaction to ensure both operations succeed or fail together
                        from django.db import transaction as db_transaction
                        with db_transaction.atomic():
                            # Get source and destination accounts
                            source_account = form.cleaned_data['account']
                            destination_account = form.cleaned_data['destination_account']
                            
                            # Get or create a Transfer category (using _ renamed to avoid name conflict)
                            transfer_category, created = TransactionCategory.objects.get_or_create(
                                tax_household=household,
                                name="Transfer",
                                defaults={'name': 'Transfer'}
                            )
                            
                            # For transfer transactions, we need to create a special payment method if it doesn't exist
                            bank_transfer_method, created = PaymentMethod.objects.get_or_create(
                                name="Bank Transfer",
                                defaults={
                                    'name': 'Bank Transfer',
                                    'icon': 'bi-bank',
                                    'is_active': True
                                }
                            )
                                                        
                            # Get appropriate recipient for source account (debit/withdrawal)
                            source_recipient_type, source_recipient_member = source_account.get_appropriate_recipient()
                            
                            # 1. Create the withdrawal transaction (expense)
                            withdrawal = form.save(commit=False)
                            withdrawal.tax_household = household
                            withdrawal.transaction_type = 'expense'
                            withdrawal.category = transfer_category
                            withdrawal.payment_method = bank_transfer_method
                            withdrawal.recipient_type = source_recipient_type  # Set based on source account ownership
                            withdrawal.recipient_member = source_recipient_member
                            withdrawal.description = f"{withdrawal.description} (to {destination_account.name})"
                            withdrawal.is_transfer = True  # Mark as transfer
                            withdrawal.save()
                            
                            # Get appropriate recipient for destination account
                            recipient_type, recipient_member = destination_account.get_appropriate_recipient()
                            
                            # 2. Create the deposit transaction (income)
                            deposit = Transaction(
                                tax_household=household,
                                date=form.cleaned_data['date'],
                                description=f"{form.cleaned_data['description']} (from {source_account.name})",
                                category=transfer_category,
                                amount=form.cleaned_data['amount'],
                                account=destination_account,
                                payment_method=bank_transfer_method, 
                                transaction_type='income',
                                recipient_type=recipient_type,  # Set based on destination account ownership
                                recipient_member=recipient_member,
                                is_recurring=withdrawal.is_recurring,  # Copy recurring setting from withdrawal transaction
                                recurrence_period=withdrawal.recurrence_period,  # Copy recurrence period
                                recurrence_start_date=withdrawal.recurrence_start_date,  # Copy start date
                                recurrence_end_date=withdrawal.recurrence_end_date,  # Copy end date
                                is_transfer=True     # Mark as transfer
                            )
                            deposit.save()
                            
                            # 3. Link the paired transactions
                            withdrawal.paired_transaction = deposit
                            withdrawal.save()
                            deposit.paired_transaction = withdrawal
                            deposit.save()
                            
                            print(f"DEBUG - Created linked transfer transactions: {withdrawal.id} <-> {deposit.id}")
                            
                        messages.success(request, _("Transfer transaction created successfully."))
                        return redirect('dashboard')
                    except Exception as e:
                        print(f"DEBUG - Error saving transfer: {e}")
                        messages.error(request, _("Error creating transfer transaction."))
                else:
                    # Regular transaction
                    transaction_obj = form.save(commit=False)
                    transaction_obj.tax_household = household
                    
                    try:
                        transaction_obj.save()
                        print(f"DEBUG - Transaction saved with ID: {transaction_obj.id}")
                        messages.success(request, _("Transaction created successfully."))
                        return redirect('dashboard')
                    except Exception as e:
                        print(f"DEBUG - Error saving: {e}")
                        messages.error(request, _("Error creating transaction."))
            else:
                print("DEBUG - Form is invalid")
                print(f"DEBUG - Form errors: {form.errors}")
                print(f"DEBUG - Form non-field errors: {form.non_field_errors()}")
                # Print the detailed form data to see what's missing
                print("DEBUG - Form data details:")
                for field_name in form.fields:
                    value = form.data.get(field_name, "NOT PRESENT")
                    required = form.fields[field_name].required
                    print(f"  {field_name}: value={value}, required={required}")
                
                # Display detailed error messages to help debugging
                error_message = _("There were errors in your form. Please check the error messages below.")
                if form.errors:
                    error_details = "<br>".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
                    error_message = f"{error_message}<br><br><small>{error_details}</small>"
                
                messages.error(request, error_message)
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
        
        # Check if this is a transfer transaction
        is_transfer = transaction.is_transfer
        paired_transaction = transaction.paired_transaction
        
        print(f"DEBUG - Transaction is a transfer: {is_transfer}")
        print(f"DEBUG - Paired transaction: {paired_transaction}")
        
        # If this is a transfer transaction, redirect to a new transfer form with the data pre-filled
        if is_transfer and request.method == 'GET':
            # We need to handle transfer editing differently - create a pre-filled transfer form
            withdrawal = transaction if transaction.transaction_type == 'expense' else paired_transaction
            deposit = transaction if transaction.transaction_type == 'income' else paired_transaction
            
            if not withdrawal or not deposit:
                messages.error(request, _("Cannot edit this transfer - the paired transaction is missing."))
                return redirect('transaction_list')
            
            # Create initial data for a transfer form
            initial_data = {
                'is_transfer': True,
                'date': withdrawal.date,
                'description': withdrawal.description,
                'amount': withdrawal.amount,
                'account': withdrawal.account.id,  # Source account
                'destination_account': deposit.account.id,  # Destination account
                'is_recurring': withdrawal.is_recurring,
                'recurrence_period': withdrawal.recurrence_period,
                'recurrence_start_date': withdrawal.recurrence_start_date,
                'recurrence_end_date': withdrawal.recurrence_end_date
            }
            
            # Create a form pre-filled with transfer data
            form = TransactionForm(initial=initial_data, household=household)
            
            # Pre-check the transfer checkbox (the form will initialize accordingly)
            form.initial['is_transfer'] = True
            
            return render(request, 'financial/transaction_form.html', {
                'form': form,
                'title': _('Edit Transfer'),
                'is_transfer_edit': True,
                'transfer_id': withdrawal.id,  # Store the original withdrawal ID for processing
                'paired_id': deposit.id        # Store the original deposit ID for processing
            })
        
        # For non-transfer transactions, or for POST requests to update transfers
        if is_transfer and request.method == 'POST':
            # If this is a transfer update POST, we need to handle it specially
            # This happens when the form is submitted from the pre-filled transfer form
            withdrawal_id = request.POST.get('transfer_id')
            deposit_id = request.POST.get('paired_id')
            
            if withdrawal_id and deposit_id:
                # Get the original transactions
                withdrawal = get_object_or_404(Transaction, pk=withdrawal_id, tax_household=household)
                deposit = get_object_or_404(Transaction, pk=deposit_id, tax_household=household)
                
                # Process the form as a transfer update
                post_data = request.POST.copy()
                post_data['is_transfer'] = 'on'  # Ensure it's marked as a transfer
                
                # Leave the recipient fields in POST data as they were submitted
                # They will be set appropriately when the transactions are updated
                
                form = TransactionForm(post_data, household=household)
                
                if form.is_valid():
                    print("DEBUG - Transfer Update - Form is valid")
                    
                    # Get the form data
                    date = form.cleaned_data['date']
                    description = form.cleaned_data['description']
                    amount = form.cleaned_data['amount']
                    source_account = form.cleaned_data['account']
                    destination_account = form.cleaned_data['destination_account']
                    
                    # Get or create the transfer category and payment method
                    transfer_category = None
                    try:
                        transfer_category = TransactionCategory.objects.get(
                            tax_household=household,
                            name="Transfer"
                        )
                    except TransactionCategory.DoesNotExist:
                        messages.error(request, _("Transfer category not found."))
                        return redirect('transaction_list')
                        
                    bank_transfer_method = None
                    try:
                        bank_transfer_method = PaymentMethod.objects.get(name="Bank Transfer")
                    except PaymentMethod.DoesNotExist:
                        messages.error(request, _("Bank Transfer payment method not found."))
                        return redirect('transaction_list')
                    
                    # Start a database transaction to ensure both updates are atomic
                    from django.db import transaction as db_transaction
                    with db_transaction.atomic():
                        # Get appropriate recipient for source account (withdrawal)
                        source_recipient_type, source_recipient_member = source_account.get_appropriate_recipient()
                        
                        # Get appropriate recipient for destination account (deposit)
                        dest_recipient_type, dest_recipient_member = destination_account.get_appropriate_recipient()
                        
                        # Get recurring fields from form
                        is_recurring = form.cleaned_data.get('is_recurring', False)
                        recurrence_period = form.cleaned_data.get('recurrence_period', '')
                        recurrence_start_date = form.cleaned_data.get('recurrence_start_date')
                        recurrence_end_date = form.cleaned_data.get('recurrence_end_date')
                        
                        # Update withdrawal (expense) side of the transfer
                        withdrawal.date = date
                        # Update description with new destination account name
                        clean_desc = description.split(" (to ")[0]  # Remove any existing account info
                        withdrawal.description = f"{clean_desc} (to {destination_account.name})"
                        withdrawal.amount = amount
                        withdrawal.account = source_account
                        withdrawal.recipient_type = source_recipient_type
                        withdrawal.recipient_member = source_recipient_member
                        withdrawal.is_recurring = is_recurring
                        withdrawal.recurrence_period = recurrence_period
                        withdrawal.recurrence_start_date = recurrence_start_date
                        withdrawal.recurrence_end_date = recurrence_end_date
                        withdrawal.category = transfer_category
                        withdrawal.payment_method = bank_transfer_method
                        withdrawal.transaction_type = 'expense'
                        withdrawal.is_transfer = True
                        withdrawal.save()
                        
                        # Update deposit (income) side of the transfer
                        deposit.date = date
                        # Update description with new source account name
                        clean_desc = description.split(" (from ")[0]  # Remove any existing account info
                        deposit.description = f"{clean_desc} (from {source_account.name})"
                        deposit.amount = amount
                        deposit.account = destination_account
                        deposit.recipient_type = dest_recipient_type
                        deposit.recipient_member = dest_recipient_member
                        deposit.is_recurring = is_recurring
                        deposit.recurrence_period = recurrence_period
                        deposit.recurrence_start_date = recurrence_start_date
                        deposit.recurrence_end_date = recurrence_end_date
                        deposit.category = transfer_category
                        deposit.payment_method = bank_transfer_method
                        deposit.transaction_type = 'income'
                        deposit.is_transfer = True
                        deposit.save()
                        
                        # Ensure paired_transaction links are correct
                        withdrawal.paired_transaction = deposit
                        withdrawal.save(update_fields=['paired_transaction'])
                        deposit.paired_transaction = withdrawal
                        deposit.save(update_fields=['paired_transaction'])
                    
                    messages.success(request, _("Transfer updated successfully."))
                    return redirect('transaction_list')
                else:
                    print("DEBUG - Transfer Update Form is invalid")
                    print(f"DEBUG - Form errors: {form.errors}")
                    
                    # Display form errors to the user
                    error_message = _("There were errors in your form. Please check the error messages below.")
                    if form.errors:
                        error_details = "<br>".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
                        error_message = f"{error_message}<br><br><small>{error_details}</small>"
                    
                    messages.error(request, error_message)
                    
                    # Render the form again with errors
                    return render(request, 'financial/transaction_form.html', {
                        'form': form,
                        'title': _('Edit Transfer'),
                        'is_transfer_edit': True,
                        'transfer_id': withdrawal_id,
                        'paired_id': deposit_id
                    })
            
        # Check if there are payment methods available
        payment_methods = PaymentMethod.objects.filter(is_active=True)
        if not payment_methods.exists():
            # Create a default payment method if none exists
            PaymentMethod.objects.create(
                name=_("Credit Card"),
                icon="bi-credit-card",
                is_active=True
            )
        
        # Normal (non-transfer) transaction update
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
                # Display form errors to the user
                messages.error(request, _("There were errors in your form. Please check the error messages below."))
        else:
            form = TransactionForm(household=household, instance=transaction)
            print(f"DEBUG - Transaction instance date: {transaction.date}")
            print(f"DEBUG - Form initial date value: {form.initial.get('date')}")
        
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
        
        # Check if this is a transfer transaction
        is_transfer = transaction.is_transfer
        paired_transaction = transaction.paired_transaction
        
        print(f"DEBUG - Deleting a transfer: {is_transfer}")
        print(f"DEBUG - Paired transaction: {paired_transaction}")
        
        if request.method == 'POST':
            if is_transfer and paired_transaction:
                # For transfers, delete both transactions in a database transaction
                # Import with different name to avoid conflict with the transaction object
                from django.db import transaction as db_transaction
                with db_transaction.atomic():
                    # Store the IDs for the confirmation message
                    tx_id = transaction.id
                    paired_id = paired_transaction.id
                    
                    # Delete the paired transaction first to avoid database constraint issues
                    paired_transaction.delete()
                    
                    # Then delete the main transaction
                    transaction.delete()
                    
                    messages.success(request, _("Transfer transactions (IDs: {}, {}) deleted successfully.").format(tx_id, paired_id))
            else:
                # Normal single transaction deletion
                transaction.delete()
                messages.success(request, _("Transaction deleted successfully."))
                
            return redirect('transaction_list')
        
        # For GET requests, show the confirmation page
        context = {
            'transaction': transaction,
        }
        
        # If this is a transfer, add info about the paired transaction
        if is_transfer and paired_transaction:
            context['is_transfer'] = True
            context['paired_transaction'] = paired_transaction
            
            # Determine which is the source and which is the destination
            if transaction.transaction_type == 'expense':
                context['source_transaction'] = transaction
                context['destination_transaction'] = paired_transaction
            else:
                context['source_transaction'] = paired_transaction
                context['destination_transaction'] = transaction
        
        return render(request, 'financial/transaction_confirm_delete.html', context)
    
    except TaxHousehold.DoesNotExist:
        messages.warning(request, _("You need to set up your financial environment first."))
        return redirect('dashboard')

@login_required
def transaction_duplicate(request, pk):
    """View to duplicate a transaction"""
    try:
        household = request.user.tax_household
        original_transaction = get_object_or_404(Transaction, pk=pk, tax_household=household)
        
        # Check if this is a transfer transaction
        is_transfer = original_transaction.is_transfer
        paired_transaction = original_transaction.paired_transaction
        
        print(f"DEBUG - Duplicating a transfer: {is_transfer}")
        print(f"DEBUG - Paired transaction: {paired_transaction}")
        
        # If this is a transfer, create a special transfer duplicate form
        if is_transfer:
            # We need to handle transfer duplication differently
            withdrawal = original_transaction if original_transaction.transaction_type == 'expense' else paired_transaction
            deposit = original_transaction if original_transaction.transaction_type == 'income' else paired_transaction
            
            if not withdrawal or not deposit:
                messages.error(request, _("Cannot duplicate this transfer - the paired transaction is missing."))
                return redirect('transaction_list')
            
            # Create initial data for a transfer form
            initial_data = {
                'is_transfer': True,
                'date': timezone.now().date(),  # Set date to today
                'description': withdrawal.description,
                'amount': withdrawal.amount,
                'account': withdrawal.account.id,  # Source account
                'destination_account': deposit.account.id,  # Destination account
                'is_recurring': withdrawal.is_recurring,
                'recurrence_period': withdrawal.recurrence_period,
                'recurrence_start_date': withdrawal.recurrence_start_date,
                'recurrence_end_date': withdrawal.recurrence_end_date
            }
            
            # For POST requests, handle transfer creation
            if request.method == 'POST':
                post_data = request.POST.copy()
                post_data['is_transfer'] = 'on'  # Ensure it's marked as a transfer
                
                # Leave the recipient fields in POST data as they were submitted
                # They will be set appropriately when the transactions are created
                
                form = TransactionForm(post_data, household=household)
                
                if form.is_valid():
                    # Handle transfer creation (this is already implemented in transaction_create view)
                    # which uses form.is_transfer to create paired transactions
                    print("DEBUG - Duplicate Transfer - Form is valid")
                    
                    # This is a new transfer, so we use the same code path as creating a new transfer
                    is_transfer = form.cleaned_data.get('is_transfer', False)
                    
                    # Since this is a duplicate, we're creating new transactions
                    if is_transfer:
                        # For transfers, we need to create two transactions
                        try:
                            # Start a database transaction to ensure both operations succeed or fail together
                            from django.db import transaction as db_transaction
                            with db_transaction.atomic():
                                # Get source and destination accounts
                                source_account = form.cleaned_data['account']
                                destination_account = form.cleaned_data['destination_account']
                                
                                # Get or create a Transfer category
                                try:
                                    transfer_category = TransactionCategory.objects.get(
                                        tax_household=household,
                                        name="Transfer"
                                    )
                                except TransactionCategory.DoesNotExist:
                                    messages.error(request, _("Transfer category not found."))
                                    return redirect('transaction_list')
                                
                                # Get or create Bank Transfer payment method
                                try:
                                    bank_transfer_method = PaymentMethod.objects.get(name="Bank Transfer")
                                except PaymentMethod.DoesNotExist:
                                    messages.error(request, _("Bank Transfer payment method not found."))
                                    return redirect('transaction_list')
                                
                                # Get appropriate recipient for source and destination accounts
                                source_recipient_type, source_recipient_member = source_account.get_appropriate_recipient()
                                dest_recipient_type, dest_recipient_member = destination_account.get_appropriate_recipient()
                                
                                # 1. Create the withdrawal transaction (expense)
                                withdrawal = Transaction(
                                    tax_household=household,
                                    date=form.cleaned_data['date'],
                                    description=f"{form.cleaned_data['description']} (to {destination_account.name})",
                                    category=transfer_category,
                                    amount=form.cleaned_data['amount'],
                                    account=source_account,
                                    payment_method=bank_transfer_method,
                                    transaction_type='expense',
                                    recipient_type=source_recipient_type,
                                    recipient_member=source_recipient_member,
                                    is_recurring=form.cleaned_data.get('is_recurring', False),
                                    recurrence_period=form.cleaned_data.get('recurrence_period', ''),
                                    recurrence_start_date=form.cleaned_data.get('recurrence_start_date'),
                                    recurrence_end_date=form.cleaned_data.get('recurrence_end_date'),
                                    is_transfer=True
                                )
                                withdrawal.save()
                                
                                # 2. Create the deposit transaction (income)
                                deposit = Transaction(
                                    tax_household=household,
                                    date=form.cleaned_data['date'],
                                    description=f"{form.cleaned_data['description']} (from {source_account.name})",
                                    category=transfer_category,
                                    amount=form.cleaned_data['amount'],
                                    account=destination_account,
                                    payment_method=bank_transfer_method, 
                                    transaction_type='income',
                                    recipient_type=dest_recipient_type,
                                    recipient_member=dest_recipient_member,
                                    is_recurring=form.cleaned_data.get('is_recurring', False),
                                    recurrence_period=form.cleaned_data.get('recurrence_period', ''),
                                    recurrence_start_date=form.cleaned_data.get('recurrence_start_date'),
                                    recurrence_end_date=form.cleaned_data.get('recurrence_end_date'),
                                    is_transfer=True
                                )
                                deposit.save()
                                
                                # 3. Link the paired transactions
                                withdrawal.paired_transaction = deposit
                                withdrawal.save()
                                deposit.paired_transaction = withdrawal
                                deposit.save()
                            
                            messages.success(request, _("Transfer duplicated successfully."))
                            return redirect('transaction_list')
                        except Exception as e:
                            print(f"DEBUG - Error duplicating transfer: {e}")
                            messages.error(request, _("Error duplicating transfer."))
                            
                    # Should not reach here since we validated is_transfer above
                    messages.error(request, _("Invalid transfer data."))
                    return redirect('transaction_list')
                else:
                    print("DEBUG - Duplicate Transfer Form is invalid")
                    print(f"DEBUG - Form errors: {form.errors}")
                    
                    # Display form errors to the user
                    error_message = _("There were errors in your form. Please check the error messages below.")
                    if form.errors:
                        error_details = "<br>".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
                        error_message = f"{error_message}<br><br><small>{error_details}</small>"
                    
                    messages.error(request, error_message)
            else:
                # For GET requests, create a new form with the initial data
                form = TransactionForm(initial=initial_data, household=household)
                form.initial['is_transfer'] = True
            
            return render(request, 'financial/transaction_form.html', {
                'form': form,
                'title': _('Duplicate Transfer'),
                'is_duplicate': True,
                'is_transfer_duplicate': True
            })
        
        # For non-transfer transactions
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
                transaction_obj = form.save(commit=False)
                transaction_obj.tax_household = household
                transaction_obj.save()
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
@login_required
def set_currency(request):
    """View to set the display currency for reports and analyses"""
    # Get the currency from POST data
    if request.method == 'POST':
        currency = request.POST.get('currency')
        next_url = request.POST.get('next', '/')
        
        # Validate the currency is supported
        valid_currencies = [code for code, name in CurrencyExchangeService.SUPPORTED_CURRENCIES]
        if currency in valid_currencies:
            # Store in session
            request.session['currency'] = currency
            messages.success(request, _("Display currency changed to {}").format(currency))
        
        # Redirect back to the page the user was on
        return HttpResponseRedirect(next_url)
    
    # If not POST, redirect to home
    return HttpResponseRedirect('/')
@login_required
def expense_analysis(request):
    """
    View for expense analysis dashboard
    Handles regular page requests and AJAX requests for data
    """
    # Get user's household
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, _("You need to set up a household first"))
        return redirect('financial_settings')
    
    # Get members and their bank accounts
    members = household.members.all()
    if not members.exists():
        messages.error(request, _("You need to add members to your household first"))
        return redirect('household_members')
    
    # Get all bank accounts linked to household members
    bank_accounts = BankAccount.objects.filter(members__in=members).distinct()
    if not bank_accounts.exists():
        messages.error(request, _("You need to create at least one bank account first"))
        return redirect('bank_account_list')
    
    # Default date range (last year)
    end_date = timezone.now().date()
    start_date = end_date.replace(year=end_date.year-1)
    
    # Process date range parameters
    custom_start_date = request.GET.get('start_date')
    custom_end_date = request.GET.get('end_date')
    
    if custom_start_date and custom_end_date:
        try:
            start_date = datetime.strptime(custom_start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(custom_end_date, '%Y-%m-%d').date()
        except ValueError:
            # If invalid dates, use default
            messages.warning(request, _("Invalid date format. Using default date range."))
    
    # Get currency for display/conversion
    display_currency = request.GET.get('display_currency', request.session.get('currency', 'EUR'))
    
    # Handle AJAX request for loading filter options (categories, cost centers, and bank accounts)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('load_options') == 'true':
        # Get categories for this household excluding Transfer category
        transfer_categories = TransactionCategory.objects.filter(
            tax_household=household,
            name='Transfer'
        )
        
        categories = TransactionCategory.objects.filter(
            tax_household=household
        ).exclude(
            id__in=transfer_categories
        ).order_by('name').values('id', 'name')
        
        # Get cost centers for this household
        cost_centers = CostCenter.objects.filter(
            tax_household=household
        ).order_by('name').values('id', 'name')
        
        # Add a special option for "Not associated with a cost center"
        cost_centers_list = list(cost_centers)
        cost_centers_list.append({'id': 'none', 'name': _("Not associated with a cost center")})
        
        # Get bank accounts for this household
        all_bank_accounts = BankAccount.objects.filter(
            members__in=members
        ).distinct().order_by('name').values('id', 'name', 'currency')
        
        # Return as JSON response
        return JsonResponse({
            'categories': list(categories),
            'cost_centers': cost_centers_list,
            'bank_accounts': list(all_bank_accounts)
        })
    
    # Handle AJAX request for chart data
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Parse filter parameters
        cost_centers_param = request.GET.get('cost_centers', '')
        cost_center_ids = cost_centers_param.split(',') if cost_centers_param else []
        
        # Parse bank account filter parameters
        bank_accounts_param = request.GET.get('bank_accounts', '')
        bank_account_ids = bank_accounts_param.split(',') if bank_accounts_param else []
        
        # Build base query for expense transactions
        # Exclude transfers to avoid double counting
        base_query = Transaction.objects.filter(
            tax_household=household,
            transaction_type='expense',
            date__gte=start_date,
            date__lte=end_date,
            is_transfer=False  # Exclude transfers
        )
        
        # Get all recurring expense transactions for generating instances
        recurring_transactions = Transaction.objects.filter(
            tax_household=household,
            transaction_type='expense',
            is_recurring=True,
            is_transfer=False  # Exclude transfers
        )
        
        # Apply cost center filter if provided
        if cost_center_ids and cost_center_ids[0]:
            # Check if we need to filter for transactions without cost centers
            if 'none' in cost_center_ids:
                # If 'none' is the only selected option, just show transactions without cost centers
                if len(cost_center_ids) == 1:
                    base_query = base_query.filter(
                        category__cost_center__isnull=True
                    )
                else:
                    # Show transactions without cost centers AND those with selected cost centers
                    # First, create a query for categories in selected cost centers
                    cost_center_ids_without_none = [cid for cid in cost_center_ids if cid != 'none']
                    categories_in_cost_centers = TransactionCategory.objects.filter(
                        cost_center_id__in=cost_center_ids_without_none,
                        tax_household=household
                    )
                    
                    # Then, combine with categories without cost center
                    base_query = base_query.filter(
                        # Either matches a category with one of the selected cost centers
                        # OR matches a category without any cost center
                        models.Q(category__in=categories_in_cost_centers) |
                        models.Q(category__cost_center__isnull=True)
                    )
            else:
                # Regular cost center filtering (no "none" option selected)
                try:
                    # Get all categories belonging to the selected cost centers
                    categories_in_cost_centers = TransactionCategory.objects.filter(
                        cost_center_id__in=cost_center_ids,
                        tax_household=household
                    )
                    
                    base_query = base_query.filter(category__in=categories_in_cost_centers)
                except ValueError:
                    # Handle invalid IDs
                    pass
        
        # Apply bank account filter if provided
        if bank_account_ids and bank_account_ids[0]:
            base_query = base_query.filter(account_id__in=bank_account_ids)
            # Also filter recurring transactions to only include those with the selected accounts
            recurring_transactions = recurring_transactions.filter(account_id__in=bank_account_ids)
        
        # Get base database transactions (non-recurring + parent recurring transactions)
        db_expenses = base_query.select_related(
            'category', 'account', 'payment_method'
        ).prefetch_related(
            'category__cost_center'
        )
        
        # Generate instances for recurring transactions to include in the analysis
        recurring_instances = []
        today = timezone.now().date()
        
        # Generate instances for all recurring transactions
        for transaction in recurring_transactions:
            try:
                # Generate recurring instances for this transaction
                instances = transaction.generate_recurring_instances(current_date=today)
                
                # Filter instances to include only those in the selected date range
                filtered_instances = [
                    instance for instance in instances 
                    if instance.date >= start_date and instance.date <= end_date
                ]
                
                # Apply cost center filters to instances if needed
                if cost_center_ids and cost_center_ids[0]:
                    if 'none' in cost_center_ids:
                        # Complex filter for "none" option (handled below)
                        pass
                    else:
                        # Filter by categories in selected cost centers
                        categories_in_cost_centers = TransactionCategory.objects.filter(
                            cost_center_id__in=cost_center_ids,
                            tax_household=household
                        )
                        filtered_instances = [
                            instance for instance in filtered_instances
                            if instance.category in categories_in_cost_centers
                        ]
                
                # Add filtered instances to our list
                recurring_instances.extend(filtered_instances)
                
            except Exception as e:
                print(f"Error generating recurring instances for expense analysis: {e}")
        
        # Combine actual transactions with recurring instances, avoiding duplicates
        # Create a dictionary to track expenses we've already seen, using date+description+amount as key
        seen_expenses = {}
        all_expenses = []
        
        # Add database expenses first
        for expense in db_expenses:
            key = (expense.date, expense.description, expense.amount)
            seen_expenses[key] = expense
            all_expenses.append(expense)
        
        # Then add recurring instances, avoiding duplicates
        for instance in recurring_instances:
            key = (instance.date, instance.description, instance.amount)
            if key not in seen_expenses:
                seen_expenses[key] = instance
                all_expenses.append(instance)
        
        # Use combined expenses for analysis
        expenses = all_expenses
        
        # Convert all amounts to the display currency
        converted_expenses = []
        total_expenses = Decimal('0.00')
        
        # Prepare data structures for charts
        category_data = {}  # For pie chart
        cost_center_data = {}  # For bar chart
        monthly_data = []  # For trend chart
        
        # Process expense data
        for expense in expenses:
            converted_amount = expense.amount
            
            # Convert currency if needed
            if expense.account.currency != display_currency:
                try:
                    converted_amount = CurrencyExchangeService.convert_currency(
                        expense.amount,
                        expense.account.currency,
                        display_currency
                    )
                except Exception as e:
                    print(f"ERROR - Failed to convert currency: {e}")
                    # Keep original amount if conversion fails
            
            # Add to total
            total_expenses += converted_amount
            
            # For category pie chart
            category_name = expense.category.name
            if category_name in category_data:
                category_data[category_name] += float(converted_amount)
            else:
                category_data[category_name] = float(converted_amount)
            
            # For cost center bar chart
            cost_center_name = expense.category.cost_center.name if expense.category.cost_center else _("Not associated with a cost center")
            if cost_center_name in cost_center_data:
                cost_center_data[cost_center_name] += float(converted_amount)
            else:
                cost_center_data[cost_center_name] = float(converted_amount)
            
            # For monthly trend chart
            month_key = expense.date.strftime('%Y-%m')
            
            # Find existing entry or create new one
            month_entry = next((item for item in monthly_data if item['month'] == month_key), None)
            
            if month_entry:
                # Update existing monthly entry
                if category_name in month_entry:
                    month_entry[category_name] += float(converted_amount)
                else:
                    month_entry[category_name] = float(converted_amount)
            else:
                # Create new monthly entry
                new_entry = {
                    'month': month_key,
                    'display_month': expense.date.strftime('%b %Y'),
                    category_name: float(converted_amount)
                }
                monthly_data.append(new_entry)
            
            # Get recipient information
            recipient_name = "External"
            if expense.recipient_type == 'family':
                recipient_name = "Family"
            elif expense.recipient_type == 'member' and expense.recipient_member:
                recipient_name = f"{expense.recipient_member.first_name} {expense.recipient_member.last_name}"
            
            # Add to expense list for table
            converted_expenses.append({
                'date': expense.date.strftime('%Y-%m-%d'),
                'description': expense.description,
                'category': expense.category.name,
                'cost_center': cost_center_name,
                'recipient': recipient_name,
                'amount': float(converted_amount)
            })
        
        # Format data for charts
        categories_data = [{'name': cat, 'amount': amount} for cat, amount in category_data.items()]
        cost_centers_data = [{'name': cc, 'amount': amount} for cc, amount in cost_center_data.items()]
        
        # Sort categories by amount (descending)
        categories_data.sort(key=lambda x: x['amount'], reverse=True)
        cost_centers_data.sort(key=lambda x: x['amount'], reverse=True)
        
        # Sort monthly data chronologically
        monthly_data.sort(key=lambda x: x['month'])
        
        # Transform monthly data for the chart
        chart_monthly_data = []
        for entry in monthly_data:
            month = entry['display_month']
            for category, amount in entry.items():
                if category not in ['month', 'display_month']:
                    chart_monthly_data.append({
                        'month': month,
                        'category': category,
                        'amount': amount
                    })
        
        # Calculate monthly average
        days_in_range = (end_date - start_date).days + 1
        months_in_range = max(1, days_in_range / 30)  # Approximate
        monthly_average = total_expenses / Decimal(str(months_in_range))
        
        # Find top category and cost center
        top_category = max(category_data.items(), key=lambda x: x[1], default=(None, 0))
        top_cost_center = max(cost_center_data.items(), key=lambda x: x[1], default=(None, 0))
        
        # Sort expenses by date (newest first)
        converted_expenses.sort(key=lambda x: x['date'], reverse=True)
        
        # Build response
        response_data = {
            'currency': display_currency,
            'total_expenses': float(total_expenses),
            'avg_monthly': float(monthly_average),
            'top_category': top_category[0],
            'top_cost_center': top_cost_center[0],
            'categories_data': categories_data,
            'cost_centers_data': cost_centers_data,
            'monthly_data': chart_monthly_data,
            'expenses': converted_expenses
        }
        
        return JsonResponse(response_data)
    
    # For regular page request, render the template with context
    context = {
        'supported_currencies': CurrencyExchangeService.SUPPORTED_CURRENCIES,
        'selected_currency': display_currency,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d')
    }
    
    return render(request, 'reporting/expense_analysis.html', context)

@login_required
def income_analysis(request):
    """
    View for income analysis dashboard
    Handles regular page requests and AJAX requests for data
    This should match the expense_analysis view's functionality but for income data
    """
    # Debug logging
    print(f"Income analysis view called - method: {request.method}, ajax: {request.headers.get('x-requested-with') == 'XMLHttpRequest'}")
    
    # Get user's household first
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, _("You need to set up a household first"))
        return redirect('financial_settings')
    
    # For AJAX requests, use a simplified approach with real cost center data
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Get display currency
        display_currency = request.GET.get('display_currency', request.session.get('currency', 'EUR'))
        
        # Check if this is a request for filter options
        if request.GET.get('load_options') == 'true':
            # Get cost centers for filtering
            cost_centers = CostCenter.objects.filter(tax_household=household).values('id', 'name')
            
            # Return cost centers data for filtering
            return JsonResponse({
                'cost_centers': list(cost_centers)
            })
        
        # Check for income transactions in the database
        income_transactions = Transaction.objects.filter(
            tax_household=household,
            transaction_type='income',
            is_transfer=False  # Exclude transfers
        )
        income_count = income_transactions.count()
        print(f"Direct DB check: found {income_count} income transactions")
        
        # If there are no income transactions, return empty data structure
        if income_count == 0:
            return JsonResponse({
                'currency': display_currency,
                'total_expenses': 0.0,
                'avg_monthly': 0.0,
                'top_category': None,
                'top_cost_center': None,
                'categories_data': [],
                'cost_centers_data': [],
                'monthly_data': [],
                'expenses': []
            })
        
        # Get the first income transaction as a sample
        sample_transaction = income_transactions.first()
        category_name = sample_transaction.category.name if sample_transaction.category else "Uncategorized"
        cost_center_name = (sample_transaction.category.cost_center.name if sample_transaction.category and 
                            sample_transaction.category.cost_center else "Not associated with a cost center")
        
        # Return data based on actual transactions
        return JsonResponse({
            'currency': display_currency,
            'total_expenses': float(sample_transaction.amount),
            'avg_monthly': float(sample_transaction.amount),
            'top_category': category_name,
            'top_cost_center': cost_center_name,
            'categories_data': [{'name': category_name, 'amount': float(sample_transaction.amount)}],
            'cost_centers_data': [{'name': cost_center_name, 'amount': float(sample_transaction.amount)}],
            'monthly_data': [{'month': sample_transaction.date.strftime('%Y-%m'), 
                             'category': category_name, 
                             'amount': float(sample_transaction.amount)}],
            'expenses': [{
                'date': sample_transaction.date.strftime('%Y-%m-%d'),
                'description': sample_transaction.description,
                'category': category_name,
                'cost_center': cost_center_name,
                'recipient': 'Family' if sample_transaction.recipient_type == 'family' else 'External',
                'amount': float(sample_transaction.amount)
            }]
        })
    
    # Get user's household
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, _("You need to set up a household first"))
        return redirect('financial_settings')
    
    # Get members and their bank accounts
    members = household.members.all()
    if not members.exists():
        messages.error(request, _("You need to add members to your household first"))
        return redirect('household_members')
    
    # Get all bank accounts linked to household members
    bank_accounts = BankAccount.objects.filter(members__in=members).distinct()
    if not bank_accounts.exists():
        messages.error(request, _("You need to create at least one bank account first"))
        return redirect('bank_account_list')
    
    # Default date range (last year)
    end_date = timezone.now().date()
    start_date = end_date.replace(year=end_date.year-1)
    
    # Process date range parameters
    custom_start_date = request.GET.get('start_date')
    custom_end_date = request.GET.get('end_date')
    
    if custom_start_date and custom_end_date:
        try:
            start_date = datetime.strptime(custom_start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(custom_end_date, '%Y-%m-%d').date()
        except ValueError:
            # If invalid dates, use default
            messages.warning(request, _("Invalid date format. Using default date range."))
    
    # Get currency for display/conversion
    display_currency = request.GET.get('display_currency', request.session.get('currency', 'EUR'))
    
    # Handle AJAX request for loading filter options (categories and cost centers)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('load_options') == 'true':
        # Get categories for this household excluding Transfer category
        transfer_categories = TransactionCategory.objects.filter(
            tax_household=household,
            name='Transfer'
        )
        
        categories = TransactionCategory.objects.filter(
            tax_household=household
        ).exclude(
            id__in=transfer_categories
        ).order_by('name').values('id', 'name')
        
        # Get cost centers for this household
        cost_centers = CostCenter.objects.filter(
            tax_household=household
        ).order_by('name').values('id', 'name')
        
        # Add a special option for "Not associated with a cost center"
        cost_centers_list = list(cost_centers)
        cost_centers_list.append({'id': 'none', 'name': _("Not associated with a cost center")})
        
        # Get bank accounts for this household
        all_bank_accounts = BankAccount.objects.filter(
            members__in=members
        ).distinct().order_by('name').values('id', 'name', 'currency')
        
        # Return as JSON response
        return JsonResponse({
            'categories': list(categories),
            'cost_centers': cost_centers_list,
            'bank_accounts': list(all_bank_accounts)
        })
    
    # Handle AJAX request for chart data
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Parse filter parameters
        cost_centers_param = request.GET.get('cost_centers', '')
        cost_center_ids = cost_centers_param.split(',') if cost_centers_param else []
        
        # Parse bank account filter parameters
        bank_accounts_param = request.GET.get('bank_accounts', '')
        bank_account_ids = bank_accounts_param.split(',') if bank_accounts_param else []
        
        # Build base query for income transactions
        # Exclude transfers to avoid double counting
        base_query = Transaction.objects.filter(
            tax_household=household,
            transaction_type='income',  # This is the key difference from expense_analysis
            date__gte=start_date,
            date__lte=end_date,
            is_transfer=False  # Exclude transfers
        )
        
        # Get all recurring income transactions for generating instances
        recurring_transactions = Transaction.objects.filter(
            tax_household=household,
            transaction_type='income',
            is_recurring=True,
            is_transfer=False  # Exclude transfers
        )
        
        # Debug info to see if any income transactions are found
        total_income_count = base_query.count()
        print(f"Found {total_income_count} income transactions for the selected period")
        
        # Apply cost center filter if provided
        if cost_center_ids and cost_center_ids[0]:
            # Check if we need to filter for transactions without cost centers
            if 'none' in cost_center_ids:
                # If 'none' is the only selected option, just show transactions without cost centers
                if len(cost_center_ids) == 1:
                    base_query = base_query.filter(
                        category__cost_center__isnull=True
                    )
                else:
                    # Show transactions without cost centers AND those with selected cost centers
                    # First, create a query for categories in selected cost centers
                    cost_center_ids_without_none = [cid for cid in cost_center_ids if cid != 'none']
                    categories_in_cost_centers = TransactionCategory.objects.filter(
                        cost_center_id__in=cost_center_ids_without_none,
                        tax_household=household
                    )
                    
                    # Then, combine with categories without cost center
                    base_query = base_query.filter(
                        # Either matches a category with one of the selected cost centers
                        # OR matches a category without any cost center
                        models.Q(category__in=categories_in_cost_centers) |
                        models.Q(category__cost_center__isnull=True)
                    )
            else:
                # Regular cost center filtering (no "none" option selected)
                try:
                    # Get all categories belonging to the selected cost centers
                    categories_in_cost_centers = TransactionCategory.objects.filter(
                        cost_center_id__in=cost_center_ids,
                        tax_household=household
                    )
                    
                    base_query = base_query.filter(category__in=categories_in_cost_centers)
                except ValueError:
                    # Handle invalid IDs
                    pass
        
        # Apply bank account filter if provided
        if bank_account_ids and bank_account_ids[0]:
            base_query = base_query.filter(account_id__in=bank_account_ids)
            # Also filter recurring transactions to only include those with the selected accounts
            recurring_transactions = recurring_transactions.filter(account_id__in=bank_account_ids)
        
        # Get base database transactions (non-recurring + parent recurring transactions)
        db_incomes = base_query.select_related(
            'category', 'account', 'payment_method'
        ).prefetch_related(
            'category__cost_center'
        )
        
        # Generate instances for recurring transactions to include in the analysis
        recurring_instances = []
        today = timezone.now().date()
        
        # Generate instances for all recurring transactions
        for transaction in recurring_transactions:
            try:
                # Generate recurring instances for this transaction
                instances = transaction.generate_recurring_instances(current_date=today)
                
                # Filter instances to include only those in the selected date range
                filtered_instances = [
                    instance for instance in instances 
                    if instance.date >= start_date and instance.date <= end_date
                ]
                
                # Apply cost center filters to instances if needed
                if cost_center_ids and cost_center_ids[0]:
                    if 'none' in cost_center_ids:
                        # Complex filter for "none" option (handled below)
                        pass
                    else:
                        # Filter by categories in selected cost centers
                        categories_in_cost_centers = TransactionCategory.objects.filter(
                            cost_center_id__in=cost_center_ids,
                            tax_household=household
                        )
                        filtered_instances = [
                            instance for instance in filtered_instances
                            if instance.category in categories_in_cost_centers
                        ]
                
                # Add filtered instances to our list
                recurring_instances.extend(filtered_instances)
                
            except Exception as e:
                print(f"Error generating recurring instances for income analysis: {e}")
        
        # Combine actual transactions with recurring instances, avoiding duplicates
        # Create a dictionary to track incomes we've already seen, using date+description+amount as key
        seen_incomes = {}
        all_incomes = []
        
        # Add database incomes first
        for income in db_incomes:
            key = (income.date, income.description, income.amount)
            seen_incomes[key] = income
            all_incomes.append(income)
        
        # Then add recurring instances, avoiding duplicates
        for instance in recurring_instances:
            key = (instance.date, instance.description, instance.amount)
            if key not in seen_incomes:
                seen_incomes[key] = instance
                all_incomes.append(instance)
        
        # Use combined incomes for analysis
        incomes = all_incomes
        
        # Convert all amounts to the display currency
        converted_incomes = []
        total_income = Decimal('0.00')
        
        # Prepare data structures for charts
        category_data = {}  # For pie chart
        cost_center_data = {}  # For bar chart
        monthly_data = []  # For trend chart
        
        # Process income data
        for income in incomes:
            converted_amount = income.amount
            
            # Convert currency if needed
            if income.account.currency != display_currency:
                try:
                    converted_amount = CurrencyExchangeService.convert_currency(
                        income.amount,
                        income.account.currency,
                        display_currency
                    )
                except Exception as e:
                    print(f"ERROR - Failed to convert currency: {e}")
                    # Keep original amount if conversion fails
            
            # Add to total
            total_income += converted_amount
            
            # For category pie chart
            category_name = income.category.name
            if category_name in category_data:
                category_data[category_name] += float(converted_amount)
            else:
                category_data[category_name] = float(converted_amount)
            
            # For cost center bar chart
            cost_center_name = income.category.cost_center.name if income.category.cost_center else _("Not associated with a cost center")
            if cost_center_name in cost_center_data:
                cost_center_data[cost_center_name] += float(converted_amount)
            else:
                cost_center_data[cost_center_name] = float(converted_amount)
            
            # For monthly trend chart
            month_key = income.date.strftime('%Y-%m')
            
            # Find existing entry or create new one
            month_entry = next((item for item in monthly_data if item['month'] == month_key), None)
            
            if month_entry:
                # Update existing monthly entry
                if category_name in month_entry:
                    month_entry[category_name] += float(converted_amount)
                else:
                    month_entry[category_name] = float(converted_amount)
            else:
                # Create new monthly entry
                new_entry = {
                    'month': month_key,
                    'display_month': income.date.strftime('%b %Y'),  # Use same format 'Mon YYYY' as expense page
                    category_name: float(converted_amount)
                }
                monthly_data.append(new_entry)
            
            # Get source information (opposite of recipient for expenses)
            source_name = "External"
            if income.recipient_type == 'family':
                source_name = "Family"
            elif income.recipient_type == 'member' and income.recipient_member:
                source_name = f"{income.recipient_member.first_name} {income.recipient_member.last_name}"
            
            # Add to income list
            converted_incomes.append({
                'date': income.date.strftime('%Y-%m-%d'),
                'description': income.description,
                'category': income.category.name,
                'cost_center': cost_center_name,
                'recipient': source_name,  # This is our "source" for income
                'amount': float(converted_amount)
            })
        
        # Format data for charts
        categories_data = [{'name': cat, 'amount': amount} for cat, amount in category_data.items()]
        cost_centers_data = [{'name': cc, 'amount': amount} for cc, amount in cost_center_data.items()]
        
        # Sort categories by amount (descending)
        categories_data.sort(key=lambda x: x['amount'], reverse=True)
        cost_centers_data.sort(key=lambda x: x['amount'], reverse=True)
        
        # Sort monthly data chronologically
        monthly_data.sort(key=lambda x: x['month'])
        
        # Transform monthly data for the chart
        chart_monthly_data = []
        for entry in monthly_data:
            month = entry['display_month']
            for category, amount in entry.items():
                if category not in ['month', 'display_month']:
                    chart_monthly_data.append({
                        'month': month,
                        'category': category,
                        'amount': amount
                    })
        
        # Calculate monthly average
        days_in_range = (end_date - start_date).days + 1
        months_in_range = max(1, days_in_range / 30)  # Approximate
        monthly_average = total_income / Decimal(str(months_in_range))
        
        # Find top category and cost center
        top_category = max(category_data.items(), key=lambda x: x[1], default=(None, 0))
        top_cost_center = max(cost_center_data.items(), key=lambda x: x[1], default=(None, 0))
        
        # Sort incomes by date (newest first)
        converted_incomes.sort(key=lambda x: x['date'], reverse=True)
        
        # Log data for debugging
        print(f"Income data summary: {len(converted_incomes)} transactions, {len(categories_data)} categories, {len(cost_centers_data)} cost centers, {len(chart_monthly_data)} monthly data points")
        
        # Ensure we have valid data for the top items
        top_category_name = top_category[0] if top_category and len(top_category) > 0 else None
        top_cost_center_name = top_cost_center[0] if top_cost_center and len(top_cost_center) > 0 else None
        
        # Build response
        response_data = {
            'currency': display_currency,
            'total_expenses': float(total_income),  # Using same field name as expense page for JS compatibility
            'avg_monthly': float(monthly_average),
            'top_category': top_category_name,
            'top_cost_center': top_cost_center_name,
            'categories_data': categories_data,
            'cost_centers_data': cost_centers_data,
            'monthly_data': chart_monthly_data,
            'expenses': converted_incomes  # Using same field name as expense page for JS compatibility
        }
        
        return JsonResponse(response_data)
    
    # For regular page request, render the template with context
    context = {
        'supported_currencies': CurrencyExchangeService.SUPPORTED_CURRENCIES,
        'selected_currency': display_currency,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d')
    }
    
    # Use the rebuilt income analysis template
    return render(request, 'reporting/income_analysis.html', context)

@login_required
def account_overview(request):
    """View for displaying account overview with balances by member and account type"""
    
    # Get user's household
    try:
        household = request.user.tax_household
    except TaxHousehold.DoesNotExist:
        messages.error(request, _("You need to set up a household first"))
        return redirect('financial_settings')
    
    # Get members and their bank accounts
    members = household.members.all()
    if not members.exists():
        messages.error(request, _("You need to add members to your household first"))
        return redirect('household_members')
    
    # Get all bank accounts linked to household members
    bank_accounts = BankAccount.objects.filter(members__in=members).distinct()
    if not bank_accounts.exists():
        messages.error(request, _("You need to create at least one bank account first"))
        return redirect('bank_account_list')
    
    # Handle AJAX request for chart data
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        display_currency = request.GET.get('display_currency', request.session.get('currency', 'EUR'))
        
        # Prepare data for the account overview chart
        data = {
            'currency': display_currency,
            'members': [],
            'account_types': [],
            'totals': []
        }
        
        # Get all account types in use
        account_types = AccountType.objects.filter(
            accounts__in=bank_accounts
        ).distinct()
        
        # Add account types to data
        for account_type in account_types:
            data['account_types'].append({
                'id': account_type.id,
                'name': account_type.designation
            })
        
        # Initialize totals for each account type
        account_type_totals = {at.id: Decimal('0.00') for at in account_types}
        
        # Create a special family entry for family accounts
        family_data = {
            'id': 'family',
            'name': _("Family"),
            'accounts': []
        }
        
        # Track which accounts have been processed
        processed_accounts = set()
        
        # Process each member
        for member in members:
            member_accounts = bank_accounts.filter(members=member)
            member_data = {
                'id': member.id,
                'name': f"{member.first_name} {member.last_name}",
                'accounts': []
            }
            
            # Process each account for this member
            for account in member_accounts:
                # Skip if this account has already been fully processed for this member
                if account.id in processed_accounts:
                    continue
                
                # Calculate current balance for this account
                today = timezone.now().date()
                initial_balance = account.balance or Decimal('0.00')
                initial_balance_date = account.balance_date or today
                
                # Get transactions since balance date
                transactions = Transaction.objects.filter(
                    account=account,
                    date__gt=initial_balance_date,
                    date__lte=today
                )
                
                # Calculate current balance by applying transactions
                current_balance = initial_balance
                for txn in transactions:
                    amount = Decimal(str(txn.amount)) if not isinstance(txn.amount, Decimal) else txn.amount
                    if txn.transaction_type == 'income':
                        current_balance += amount
                    else:  # expense
                        current_balance -= amount
                
                # Convert to display currency if needed
                display_balance = current_balance
                if display_currency != account.currency:
                    try:
                        display_balance = CurrencyExchangeService.convert_currency(
                            current_balance,
                            account.currency,
                            display_currency
                        )
                    except Exception as e:
                        print(f"ERROR - Failed to convert currency: {e}")
                        # Keep using original balance if conversion fails
                
                # Check if this is a personal account (1 owner) or family account (multiple owners)
                account_owners_count = account.members.count()
                
                if account_owners_count == 1:
                    # Personal account - add to member's data
                    member_data['accounts'].append({
                        'type_id': account.account_type.id,
                        'balance': float(display_balance)
                    })
                    
                    # Add to the account type totals
                    account_type_totals[account.account_type.id] += display_balance
                    
                    # Mark as processed to avoid duplicates
                    processed_accounts.add(account.id)
                elif account_owners_count > 1 and account.id not in processed_accounts:
                    # Family account - add to family data
                    family_data['accounts'].append({
                        'type_id': account.account_type.id,
                        'balance': float(display_balance)
                    })
                    
                    # Add to the account type totals
                    account_type_totals[account.account_type.id] += display_balance
                    
                    # Mark as processed to avoid duplicates
                    processed_accounts.add(account.id)
            
            # Add member data to result if they have accounts
            if member_data['accounts']:
                data['members'].append(member_data)
        
        # Add family data to result if it has accounts
        if family_data['accounts']:
            data['members'].append(family_data)
        
        # Format account type totals for the response
        for account_type_id, total in account_type_totals.items():
            data['totals'].append({
                'type_id': account_type_id,
                'balance': float(total)
            })
        
        return JsonResponse(data)
    
    # For regular page request, render the template with context
    context = {
        'members': members,
        'account_types': AccountType.objects.filter(accounts__in=bank_accounts).distinct(),
        'supported_currencies': CurrencyExchangeService.SUPPORTED_CURRENCIES,
        'selected_currency': request.session.get('currency', 'EUR')
    }
    
    return render(request, 'reporting/account_overview.html', context)
