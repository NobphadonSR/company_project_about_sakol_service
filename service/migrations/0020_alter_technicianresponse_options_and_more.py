# Generated by Django 5.1.3 on 2024-12-06 09:28

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0019_alter_technicianjobstatus_status'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='technicianresponse',
            options={'verbose_name': 'การตอบกลับของช่าง', 'verbose_name_plural': 'การตอบกลับของช่าง'},
        ),
        migrations.RemoveField(
            model_name='technicianresponse',
            name='estimated_cost',
        ),
        migrations.RemoveField(
            model_name='technicianresponse',
            name='notes',
        ),
        migrations.RemoveField(
            model_name='technicianresponse',
            name='response_date',
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='service_type',
            field=models.CharField(blank=True, choices=[('normal', 'ระบบไฟปกติ'), ('full_checkup', 'ระบบ Full Check Up'), ('air_flow', 'ระบบ Air flow/Air Plus'), ('checkup_air_plus', 'ระบบ Check up Program Air plus')], max_length=50, null=True, verbose_name='ประเภทการซ่อม'),
        ),
        migrations.AddField(
            model_name='technicianresponse',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='วันที่ตอบกลับ'),
        ),
        migrations.AddField(
            model_name='technicianresponse',
            name='response_text',
            field=models.TextField(default=django.utils.timezone.now, verbose_name='ข้อความตอบกลับ'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='technicianresponse',
            name='service_request',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='technician_responses', to='service.servicerequest'),
        ),
    ]
