# Generated by Django 3.2.2 on 2021-07-22 16:16

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0003_alter_community_readable_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Twitter',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('core.plugin',),
        ),
    ]
