from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='auth/password_change.html',
        success_url='/password_change/done/'
    ), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='auth/password_change_done.html'
    ), name='password_change_done'),
    
    # Reporting & Analytics URLs
    path('reporting/balance-evolution/', views.balance_evolution, name='balance_evolution'),
    
    # Financial Environment URLs
    path('financial/', views.financial_settings, name='financial_settings'),
    path('financial/household/create/', views.household_create, name='household_create'),
    path('financial/household/update/', views.household_update, name='household_update'),
    path('financial/household/members/', views.household_members, name='household_members'),
    path('financial/member/create/', views.member_create, name='member_create'),
    path('financial/member/<int:pk>/update/', views.member_update, name='member_update'),
    path('financial/member/<int:pk>/delete/', views.member_delete, name='member_delete'),
    path('financial/bank-accounts/', views.bank_account_list, name='bank_account_list'),
    path('financial/bank-account/create/', views.bank_account_create, name='bank_account_create'),
    path('financial/bank-account/<int:pk>/update/', views.bank_account_update, name='bank_account_update'),
    path('financial/bank-account/<int:pk>/delete/', views.bank_account_delete, name='bank_account_delete'),
    
    # Cost Center URLs
    path('financial/cost-centers/', views.cost_center_list, name='cost_center_list'),
    path('financial/cost-center/create/', views.cost_center_create, name='cost_center_create'),
    path('financial/cost-center/<int:pk>/update/', views.cost_center_update, name='cost_center_update'),
    path('financial/cost-center/<int:pk>/delete/', views.cost_center_delete, name='cost_center_delete'),
    path('financial/cost-center/<int:pk>/assign/', views.assign_categories_to_cost_center, name='cost_center_assign_categories'),
    
    # Transaction Category URLs
    path('financial/categories/', views.category_list, name='category_list'),
    path('financial/category/create/', views.category_create, name='category_create'),
    path('financial/category/<int:pk>/update/', views.category_update, name='category_update'),
    path('financial/category/<int:pk>/delete/', views.category_delete, name='category_delete'),
    
    # Transaction URLs
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/recurring/', views.recurring_transaction_list, name='recurring_transaction_list'),
    path('transactions/recurring-transfers/', views.recurring_transfer_list, name='recurring_transfer_list'),
    path('transaction/create/', views.transaction_create, name='transaction_create'),
    path('transaction/<int:pk>/update/', views.transaction_update, name='transaction_update'),
    path('transaction/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),
    path('transaction/<int:pk>/duplicate/', views.transaction_duplicate, name='transaction_duplicate'),
    
    # Currency selection
    path('set-currency/', views.set_currency, name='set_currency'),
]