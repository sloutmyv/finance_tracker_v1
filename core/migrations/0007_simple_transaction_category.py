# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_bankaccount_balance_bankaccount_balance_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransactionCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Category name', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tax_household', models.ForeignKey(help_text='The tax household this category belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='transaction_categories', to='core.taxhousehold')),
            ],
            options={
                'verbose_name': 'Transaction Category',
                'verbose_name_plural': 'Transaction Categories',
                'ordering': ['name'],
            },
        ),
    ]