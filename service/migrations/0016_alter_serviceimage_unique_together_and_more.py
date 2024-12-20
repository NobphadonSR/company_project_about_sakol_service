from django.db import migrations, models
from django.db.models import Min

def remove_duplicate_images(apps, schema_editor):
    ServiceImage = apps.get_model('service', 'ServiceImage')
    
    # หา records ที่มี service_request_id และ image_hash ซ้ำกัน
    duplicates = (
        ServiceImage.objects
        .values('service_request_id', 'image_hash')
        .annotate(min_id=Min('id'))
        .filter(image_hash__isnull=False)  # เฉพาะ records ที่มี hash
    )
    
    # ลบ records ที่ซ้ำ
    for dup in duplicates:
        # เก็บ record แรก ลบที่เหลือ
        ServiceImage.objects.filter(
            service_request_id=dup['service_request_id'],
            image_hash=dup['image_hash']
        ).exclude(
            id=dup['min_id']
        ).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('service', '0015_alter_serviceimage_unique_together'),
    ]

    operations = [
        # ลบ unique_together เดิมก่อน
        migrations.AlterUniqueTogether(
            name='serviceimage',
            unique_together=set(),
        ),
        # เพิ่ม field image_hash
        migrations.AddField(
            model_name='serviceimage',
            name='image_hash',
            field=models.CharField(blank=True, max_length=64),
        ),
        # ลบข้อมูลซ้ำ
        migrations.RunPython(remove_duplicate_images),
        # สร้าง unique_together ใหม่
        migrations.AlterUniqueTogether(
            name='serviceimage',
            unique_together={('service_request', 'image_hash')},
        ),
    ]