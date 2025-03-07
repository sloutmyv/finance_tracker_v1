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
]