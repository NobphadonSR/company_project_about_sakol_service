from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('customer', 'ลูกค้า'),
        ('service', 'ฝ่ายบริการ'),
        ('technician', 'ช่าง'),
    )
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    phone = models.CharField(max_length=50, null=True, blank=True)
    address = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)

class Customer(models.Model):
    PROJECT_CATEGORIES = [
        ('SMALL', 'บ้านหลังเล็ก'),
        ('LARGE', 'บ้านหลังใหญ่')
    ]
    
    PROJECT_TYPES = [
        ('MANTANA', 'มัณฑนา'),
        ('PRUKLADA', 'พฤกษ์ลดา'),
        ('INIZIO', 'INIZIO'),
        ('VILLAGGIO', 'Villaggio'),
        ('SIVALI', 'สีวลี'),
        ('CHAIYAPRUEK', 'ชัยพฤกษ์'),
        ('VIVE', 'VIVE'),
        ('NANTAWAN', 'นันทวัน'),
        ('LADAWAN', 'ลดาวัลย์'),
        ('OTHER', 'อื่นๆ')
    ]
    WARRANTY_STATUS = [
        ('ACTIVE', 'อยู่ในประกัน'),
        ('EXPIRED', 'หมดประกัน'),
        ('NONE', 'ไม่มีประกัน')
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    project_name = models.CharField(max_length=100, verbose_name="ชื่อโครงการ")
    house_number = models.CharField(max_length=50, verbose_name="บ้านเลขที่")
    # เพิ่มฟิลด์ใหม่
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES, default='OTHER', verbose_name="ประเภทโครงการ")
    # เพิ่มฟิลด์ใหม่หลังจาก project_type
    warranty_status = models.CharField(
        max_length=10,
        choices=WARRANTY_STATUS,
        default='NONE',
        verbose_name="สถานะประกัน"
    )
    warranty_expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="วันหมดประกัน"
    )
    project_category = models.CharField(max_length=10, choices=PROJECT_CATEGORIES, default='OTHER', verbose_name="ขนาดบ้าน")
    phone = models.CharField(max_length=50, null=True, blank=True, verbose_name="เบอร์โทร")
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
        # ตรวจสอบและกำหนดสถานะประกันตาม project_type
        if self.project_type in ['MANTANA', 'PRUKLADA', 'INIZIO', 'VILLAGGIO', 
                               'SIVALI', 'CHAIYAPRUEK', 'VIVE', 'NANTAWAN', 'LADAWAN']:
            # ตรวจสอบวันหมดประกัน
            if self.warranty_expiry_date:
                if timezone.now().date() <= self.warranty_expiry_date:
                    self.warranty_status = 'ACTIVE'
                else:
                    self.warranty_status = 'EXPIRED'
            else:
                # ถ้าไม่มีวันหมดประกัน ให้กำหนดเป็น 1 ปีนับจากวันที่บันทึก
                self.warranty_status = 'ACTIVE'
                self.warranty_expiry_date = timezone.now().date() + timezone.timedelta(days=365)
        else:
            self.warranty_status = 'NONE'
            self.warranty_expiry_date = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_name} - {self.project_name}"