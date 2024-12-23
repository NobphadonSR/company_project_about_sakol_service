from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from datetime import timedelta

class ServiceRequest(models.Model):
    REQUEST_TYPES = [
        ('repair', 'แจ้งซ่อม'),
        ('install', 'ซื้ออะไหล่'),
        ('all_in', 'ต้องการแจ้งซ่อมและซื้ออะไหล่'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'รอดำเนินการ'),
        ('assigned', 'มอบหมายงานแล้ว'),
        ('pending_advice', 'รอคำแนะนำจากช่าง'),
        ('advice_given', 'ให้คำแนะนำแล้ว'),
        ('accepted', 'รับงาน'),
        ('traveling', 'กำลังเดินทาง'),
        ('arrived', 'ถึงจุดหมาย'),
        ('fixing', 'กำลังแก้ไข'),
        ('completed_cash', 'เสร็จสิ้น - เก็บเงินหน้างาน'),
        ('completed_call', 'เสร็จสิ้น - โทรเก็บเงิน'),
        ('cancelled', 'ยกเลิก'),
        ('rescheduled', 'เลื่อนนัด'),
    ]

    WARRANTY_STATUS = [
        ('in_warranty', 'อยู่ในประกัน'),
        ('out_of_warranty', 'ไม่อยู่ในประกัน'),
        ('pending_warranty', 'รอการตัดสินใจ'),
    ]

    SERVICE_TYPES = [
        ('normal', 'ระบบไฟปกติ'),
        ('full_checkup', 'ระบบ Full Check Up'),
        ('air_flow', 'ระบบ Air flow/Air Plus'),
        ('checkup_air_plus', 'ระบบ Check up Program Air plus'),
    ]

    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE, related_name='service_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    technician = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_requests')
    appointment_date = models.DateField(null=True, blank=True)
    appointment_time = models.TimeField(null=True, blank=True)  # เพิ่มฟิลด์นี้
    description = models.TextField(verbose_name='รายละเอียดปัญหา')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='วันที่สร้าง')
    is_confirmed = models.BooleanField(default=False, verbose_name='ยืนยันโดยฝ่ายบริการ')
    warranty_status = models.CharField(max_length=20, choices=WARRANTY_STATUS, default='pending_warranty', verbose_name='สถานะประกัน')
    
    # เพิ่มฟิลด์ใหม่
    need_advice = models.BooleanField(default=False, verbose_name='ต้องการคำแนะนำจากช่าง',help_text='เลือกตัวเลือกนี้หากต้องการให้ช่างแนะนำก่อนดำเนินการ')
    customer_confirmed = models.BooleanField(default=False,verbose_name='ลูกค้ายืนยันการดำเนินการ')
    technician_advice = models.TextField(blank=True,null=True,verbose_name='คำแนะนำจากช่าง')
    estimated_cost = models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True,verbose_name='ประมาณการค่าใช้จ่าย')
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPES, null=True, blank=True, verbose_name='ประเภทการซ่อม')

    # เพิ่มฟิลด์ใหม่
    warranty_start_date = models.DateField(null=True, blank=True, verbose_name='วันที่เริ่มประกัน')
    warranty_end_date = models.DateField(null=True, blank=True, verbose_name='วันที่สิ้นสุดประกัน')

    def save(self, *args, **kwargs):
        # ตรวจสอบว่าเป็นการซื้ออะไหล่ใหม่หรือไม่
        if self.request_type in ['install', 'all_in'] and not self.warranty_start_date:
            # ตั้งค่าวันที่เริ่มประกันเป็นวันที่ปัจจุบัน
            self.warranty_start_date = timezone.now().date()
            # ตั้งค่าวันที่สิ้นสุดประกันเป็น 1 ปีนับจากวันที่เริ่ม
            self.warranty_end_date = self.warranty_start_date + timedelta(days=365)
            # ตั้งค่าสถานะประกัน
            self.warranty_status = 'in_warranty'
        
        # ตรวจสอบสถานะประกัน
        if self.warranty_end_date:
            if timezone.now().date() <= self.warranty_end_date:
                self.warranty_status = 'in_warranty'
            else:
                self.warranty_status = 'out_of_warranty'

        super().save(*args, **kwargs)

    def set_warranty(self, start_date=None):
        """ตั้งค่าประกัน 1 ปี"""
        if start_date is None:
            start_date = timezone.now().date()
        
        self.warranty_start_date = start_date
        self.warranty_end_date = start_date + timedelta(days=365)
        self.warranty_status = 'in_warranty'
        self.save()
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'การแจ้งซ่อม'
        verbose_name_plural = 'การแจ้งซ่อม'

    def __str__(self):
        return f"{self.get_request_type_display()} - {self.customer}"

class ServiceProposal(models.Model):
    service_request = models.ForeignKey(
        ServiceRequest, 
        on_delete=models.CASCADE,
        related_name='service_proposals'  # เปลี่ยนจาก proposals เป็น service_proposals
    )
    technician = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE
    )
    description = models.TextField()
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class ServiceImage(models.Model):
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='service_images')
    image = models.ImageField(upload_to='service_images/')
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    image_hash = models.CharField(max_length=64, blank=True)  # เพิ่มฟิลด์นี้

    class Meta:
        ordering = ['-uploaded_at']
        unique_together = ['service_request', 'image_hash']  # เปลี่ยนจาก image เป็น image_hash

    def generate_hash(self):
        import hashlib
        if self.image:
            # สร้าง hash จากเนื้อหาของไฟล์
            md5hash = hashlib.md5()
            for chunk in self.image.chunks():
                md5hash.update(chunk)
            return md5hash.hexdigest()
        return ''

    def save(self, *args, **kwargs):
        if not self.pk:  # ถ้าเป็นการสร้างใหม่
            # ตรวจสอบจำนวนรูปภาพ
            current_images = ServiceImage.objects.filter(
                service_request=self.service_request
            ).count()
            if current_images >= 6:
                raise ValidationError('ไม่สามารถอัพโหลดรูปภาพเกิน 6 รูปได้')
            
            # สร้าง hash และตรวจสอบรูปซ้ำ
            self.image_hash = self.generate_hash()
            if ServiceImage.objects.filter(
                service_request=self.service_request,
                image_hash=self.image_hash
            ).exists():
                raise ValidationError('รูปภาพนี้ถูกอัพโหลดไปแล้ว')

        super().save(*args, **kwargs)

class ServiceRecord(models.Model):
    COMPLETION_STATUS = [
        ('completed', 'เสร็จสมบูรณ์'),
        ('partial', 'เสร็จบางส่วน'),
        ('pending_parts', 'รออะไหล่'),
        ('cancelled', 'ยกเลิก'),
    ]

    job_number = models.CharField(max_length=50, unique=True, verbose_name='เลขที่งาน')
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE, related_name='service_records')
    project_code = models.CharField(max_length=50, verbose_name='รหัสโครงการ')
    plot_number = models.CharField(max_length=50, verbose_name='เลขที่แปลง')
    reported_issue = models.TextField(verbose_name='ปัญหาที่แจ้ง')
    appointment_date = models.DateField(verbose_name='วันที่นัดหมาย')
    appointment_time = models.TimeField(verbose_name='เวลานัดหมาย')
    completion_status = models.CharField(max_length=50, choices=COMPLETION_STATUS, verbose_name='สถานะการดำเนินการ')
    faulty_equipment = models.TextField(blank=True, verbose_name='อุปกรณ์ที่เสีย')
    cause = models.TextField(blank=True, verbose_name='สาเหตุ')
    solution = models.TextField(blank=True, verbose_name='การแก้ไข')
    service_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='ค่าบริการ'
    )
    notes = models.TextField(blank=True, verbose_name='หมายเหตุ')
    record_date = models.DateTimeField(default=timezone.now, verbose_name='วันที่บันทึก')
    last_modified = models.DateTimeField(auto_now=True, verbose_name='แก้ไขล่าสุด')

    class Meta:
        ordering = ['-record_date']
        verbose_name = 'บันทึกการซ่อม'
        verbose_name_plural = 'บันทึกการซ่อม'

    def __str__(self):
        return f"บันทึกการซ่อม {self.job_number}"

class TechnicianProposal(models.Model):
    service_request = models.ForeignKey(
        ServiceRequest, 
        on_delete=models.CASCADE,
        related_name='technician_proposals'  # เปลี่ยนจาก proposals เป็น technician_proposals
    )
    technician = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE
    )
    description = models.TextField()
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class TechnicianJobStatus(models.Model):
    TECHNICIAN_STATUS_CHOICES = [
        ('accepted', 'รับงาน'),
        ('traveling', 'กำลังเดินทาง'),
        ('arrived', 'ถึงจุดหมาย'),
        ('fixing', 'กำลังแก้ไข'),
        ('completed_cash', 'เสร็จสิ้น - เก็บเงินหน้างาน'),
        ('completed_call', 'เสร็จสิ้น - โทรเก็บเงิน'),
        ('cancelled', 'ยกเลิก'),
        ('rescheduled', 'เลื่อนนัด'),
    ]

    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='status_updates')
    technician = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='status_updates')
    status = models.CharField(max_length=20, choices=TECHNICIAN_STATUS_CHOICES, verbose_name='สถานะ')
    notes = models.TextField(blank=True, verbose_name='หมายเหตุ')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='เวลาอัพเดท')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'สถานะงานช่าง'
        verbose_name_plural = 'สถานะงานช่าง'

    def __str__(self):
        return f"อัพเดทสถานะสำหรับ {self.service_request}"
    
    def save(self, *args, **kwargs):
        # บันทึก TechnicianJobStatus
        super().save(*args, **kwargs)
        
        # อัพเดทสถานะใน ServiceRequest
        self.service_request.status = self.status
        self.service_request.save()

class TechnicianResponse(models.Model):
    service_request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name='technician_responses'
    )
    description = models.TextField(
        verbose_name='รายละเอียดการตอบกลับ',
        null=True,  # อนุญาตให้เป็น null ได้
        blank=True  # อนุญาตให้เว้นว่างได้ในฟอร์ม
    )
    service_type = models.CharField(
        max_length=50,
        choices=ServiceRequest.SERVICE_TYPES,
        null=True,
        blank=True,
        verbose_name='ประเภทการซ่อม'
    )
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='ประมาณการค่าใช้จ่าย'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='วันที่ตอบกลับ'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'การตอบกลับของช่าง'
        verbose_name_plural = 'การตอบกลับของช่าง'

    def __str__(self):
        return f"คำตอบจากช่างสำหรับ {self.service_request}"
