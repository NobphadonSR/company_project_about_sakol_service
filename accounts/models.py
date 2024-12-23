from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('customer', 'ลูกค้า'),
        ('service', 'ฝ่ายบริการ'),
        ('technician', 'ช่าง'),
    )
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    project_name = models.CharField(max_length=100, verbose_name="ชื่อโครงการ")
    house_number = models.CharField(max_length=50, verbose_name="บ้านเลขที่")
    phone = models.CharField(max_length=15, verbose_name="เบอร์โทร")
    customer_name = models.CharField(max_length=100, verbose_name="ชื่อลูกค้า")
    # ลบ location ที่เป็น TextField ออก เพราะซ้ำซ้อนกับ CharField
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="ละติจูด"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="ลองจิจูด"
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ที่อยู่"
    )
    location_updates_count = models.PositiveIntegerField(
        default=0,
        verbose_name="จำนวนครั้งที่อัพเดทที่อยู่"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pk:  # ถ้าเป็นการอัพเดต
            old_instance = Customer.objects.get(pk=self.pk)
            # เพิ่ม location_updates_count เมื่อมีการเปลี่ยนแปลงพิกัดหรือที่อยู่
            if (old_instance.latitude != self.latitude or 
                old_instance.longitude != self.longitude or 
                old_instance.location != self.location):
                self.location_updates_count += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_name} - {self.project_name}"