# Generated by Django 3.2.2 on 2021-12-17 16:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_auto_20211101_2053'),
    ]

    operations = [
        migrations.AddField(
            model_name='governanceprocess',
            name='url',
            field=models.CharField(blank=True, help_text='URL of the vote or process', max_length=150, null=True),
        ),
    ]
