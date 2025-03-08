# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_transaction'),
    ]

    operations = [
        # Rename is_family_transaction to is_family_recipient
        migrations.RenameField(
            model_name='transaction',
            old_name='is_family_transaction',
            new_name='is_family_recipient',
        ),
        
        # Add the recurrence_period field
        migrations.AddField(
            model_name='transaction',
            name='recurrence_period',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Not Recurring'),
                    ('daily', 'Daily'),
                    ('weekly', 'Weekly'),
                    ('monthly', 'Monthly'),
                    ('quarterly', 'Quarterly'),
                    ('annually', 'Annually'),
                ],
                default='',
                help_text='Frequency of recurrence for recurring transactions',
                max_length=10
            ),
        ),
    ]