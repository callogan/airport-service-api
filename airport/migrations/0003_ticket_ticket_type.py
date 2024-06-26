# Generated by Django 5.0.4 on 2024-04-30 12:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("airport", "0002_airplane_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="ticket_type",
            field=models.CharField(
                choices=[
                    ("check-in-pending", "Check-in-pending"),
                    ("check-in-completed", "Check-in-completed"),
                ],
                default="check-in-completed",
                max_length=20,
            ),
        ),
    ]
