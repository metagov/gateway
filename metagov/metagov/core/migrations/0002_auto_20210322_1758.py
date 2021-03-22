# Generated by Django 3.1.5 on 2021-03-22 17:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='datastore',
            name='data_store',
        ),
        migrations.RemoveField(
            model_name='plugin',
            name='data',
        ),
        migrations.AddField(
            model_name='datastore',
            name='datastore',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='plugin',
            name='state',
            field=models.OneToOneField(help_text='Datastore to persist any state', null=True, on_delete=django.db.models.deletion.CASCADE, to='core.datastore'),
        ),
    ]
