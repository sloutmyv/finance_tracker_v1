from django.contrib import admin
from .models import TaxHousehold, HouseholdMember, BankAccount, AccountType

class HouseholdMemberInline(admin.TabularInline):
    model = HouseholdMember
    extra = 1
    readonly_fields = ('trigram', 'created_at', 'updated_at')

@admin.register(TaxHousehold)
class TaxHouseholdAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at', 'updated_at')
    search_fields = ('name', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [HouseholdMemberInline]

@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'trigram', 'date_of_birth', 'tax_household')
    list_filter = ('tax_household',)
    search_fields = ('first_name', 'last_name', 'trigram')
    readonly_fields = ('trigram', 'created_at', 'updated_at')

@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ('designation', 'short_designation', 'created_at', 'updated_at')
    search_fields = ('designation', 'short_designation')
    readonly_fields = ('created_at', 'updated_at')
    
@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'bank_name', 'account_type', 'currency', 'reference', 'timestamp')
    list_filter = ('account_type', 'currency', 'bank_name')
    search_fields = ('name', 'bank_name', 'reference')
    readonly_fields = ('reference', 'timestamp', 'created_at', 'updated_at')
    filter_horizontal = ('members',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'bank_name', 'account_type', 'currency', 'reference')
        }),
        ('Ownership', {
            'fields': ('members',)
        }),
        ('Timestamps', {
            'fields': ('timestamp', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
