# Generated by Django 5.1.3 on 2024-12-03 06:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0010_alter_technicianjobstatus_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicerequest',
            name='warranty_status',
            field=models.CharField(blank=True, choices=[('in_warranty', 'อยู่ในประกัน'), ('out_of_warranty', 'ไม่อยู่ในประกัน')], max_length=20, null=True),
        ),
    ]
