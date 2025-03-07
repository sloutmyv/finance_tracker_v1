from django.contrib import admin
from .models import TaxHousehold, HouseholdMember, BankAccount

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
    
@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_number', 'created_at')
    search_fields = ('name', 'account_number')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('members',)
