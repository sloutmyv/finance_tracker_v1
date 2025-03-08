# Generated by Django 5.1.7 on 2025-03-08 00:33

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_remove_bankaccount_account_number_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Name of the payment method', max_length=100)),
                ('icon', models.CharField(blank=True, help_text="Bootstrap icon class (e.g., 'bi-credit-card')", max_length=50)),
                ('is_system', models.BooleanField(default=False, help_text='Whether this is a system-defined payment method')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tax_household', models.ForeignKey(blank=True, help_text='The tax household this payment method belongs to (null for system-defined methods)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='payment_methods', to='core.taxhousehold')),
            ],
            options={
                'verbose_name': 'Payment Method',
                'verbose_name_plural': 'Payment Methods',
                'ordering': ['name'],
            },
        ),
    ]
