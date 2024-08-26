# Generated by Django 3.1.12 on 2022-06-10 15:41

from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('inbox', '0013_messagelog_updated_at'),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY inbox_messa_send_at_d2c961_idx "
            "ON inbox_message (send_at);",
            state_operations=[
                migrations.AddIndex(
                    model_name='message',
                    index=models.Index(fields=['send_at'], name='inbox_messa_send_at_d2c961_idx'),
                ),
            ],
        )
    ]