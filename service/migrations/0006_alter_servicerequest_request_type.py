# Generated by Django 5.1.3 on 2024-11-28 01:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0005_servicerequest_is_confirmed_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicerequest',
            name='request_type',
            field=models.CharField(choices=[('repair', 'แจ้งซ่อม'), ('install', 'ซื้ออะไหล่'), ('all_in', 'ต้องการแจ้งซ่อมและซื้ออะไหล่')], max_length=20),
        ),
    ]
