# Generated by Django 3.1.12 on 2021-08-27 23:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inbox', '0011_auto_20210324_2238'),
    ]

    operations = [
        migrations.RenameField(
            model_name='messagelog',
            old_name='failure_reason',
            new_name='status_reason',
        ),
    ]