# Generated by Django 5.1.3 on 2024-12-07 03:21

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0021_remove_technicianresponse_response_text_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='technicianresponse',
            options={'ordering': ['-created_at'], 'verbose_name': 'การตอบกลับของช่าง', 'verbose_name_plural': 'การตอบกลับของช่าง'},
        ),
    ]
