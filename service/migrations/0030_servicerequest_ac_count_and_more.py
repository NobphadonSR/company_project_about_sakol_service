# Generated by Django 5.1.3 on 2024-12-25 04:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0029_servicerequest_cost_note_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicerequest',
            name='ac_count',
            field=models.IntegerField(blank=True, choices=[(1, '1 เครื่อง'), (2, '2 เครื่อง')], null=True, verbose_name='จำนวนเครื่องปรับอากาศ'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='calculated_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='ราคาประเมิน'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='service_category',
            field=models.CharField(blank=True, choices=[('ELECTRICAL', 'ตู้ไฟ'), ('AIRPLUS', 'Air Plus'), ('OTHER', 'บริการอื่นๆ')], max_length=20, null=True, verbose_name='ประเภทบริการ'),
        ),
        migrations.AddField(
            model_name='servicerequest',
            name='service_level',
            field=models.CharField(blank=True, choices=[('NORMAL', 'บริการแบบปกติ'), ('FULL', 'บริการแบบ Full Check up')], max_length=10, null=True, verbose_name='ระดับบริการ'),
        ),
    ]
