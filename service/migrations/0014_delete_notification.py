# Generated by Django 5.1.3 on 2024-12-04 01:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0013_alter_servicerequest_warranty_status'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Notification',
        ),
    ]
