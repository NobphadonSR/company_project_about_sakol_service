from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from datetime import timedelta
from accounts.models import Customer
class ServiceRequest(models.Model):
    REQUEST_TYPES = [
        ('repair', 'แจ้งซ่อม'),
        ('install', 'ซื้ออะไหล่'),
        ('all_in', 'ต้องการแจ้งซ่อมและซื้ออะไหล่'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'รอดำเนินการ'),
        ('assigned', 'มอบหมายงานแล้ว'),
        ('pending_advice', 'รอคำปรึกษาจากช่าง'),
        ('advice_given', 'ให้คำปรึกษาแล้ว'),
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


    # เพิ่ม choices ใหม่ต่อจาก SERVICE_TYPES
    SERVICE_CATEGORIES = [
        ('ELECTRICAL', 'ตู้ไฟ'),
        ('AIRPLUS', 'Air Plus'),
        ('OTHER', 'บริการอื่นๆ')
    ]
    
    SERVICE_LEVELS = [
        ('NORMAL', 'บริการแบบปกติ'),
        ('FULL', 'บริการแบบ Full Check up')
    ]
    
    AC_UNITS = [
        (1, '1 เครื่อง'),
        (2, '2 เครื่อง')
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
    # เพิ่มฟิลด์ใหม่สำหรับการจัดการค่าใช้จ่าย
    cost_note = models.TextField(
        blank=True, 
        verbose_name="หมายเหตุค่าใช้จ่าย"
    )
    cost_updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='cost_updates',
        verbose_name="ผู้กำหนดค่าใช้จ่าย"
    )
    cost_updated_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="วันที่กำหนดค่าใช้จ่าย"
    )
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPES, null=True, blank=True, verbose_name='ประเภทการซ่อม')

    # เพิ่มฟิลด์ใหม่
    warranty_start_date = models.DateField(null=True, blank=True, verbose_name='วันที่เริ่มประกัน')
    warranty_end_date = models.DateField(null=True, blank=True, verbose_name='วันที่สิ้นสุดประกัน')

    # เพิ่มฟิลด์ใหม่ต่อจากฟิลด์เดิม
    service_category = models.CharField(
        max_length=20, 
        choices=SERVICE_CATEGORIES,
        null=True,
        blank=True,
        verbose_name="ประเภทบริการ"
    )
    service_level = models.CharField(
        max_length=10, 
        choices=SERVICE_LEVELS,
        null=True,
        blank=True,
        verbose_name="ระดับบริการ"
    )
    ac_count = models.IntegerField(
        choices=AC_UNITS,
        null=True,
        blank=True,
        verbose_name="จำนวนเครื่องปรับอากาศ"
    )
    calculated_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="ราคาประเมิน"
    )

    def check_warranty_status(self):
        """ตรวจสอบสถานะประกันอัตโนมัติ"""
        today = timezone.now().date()
        
        # ตรวจสอบสถานะประกันจาก Customer
        customer = self.customer
        if customer.warranty_status == 'ACTIVE':
            self.warranty_status = 'in_warranty'
        elif customer.warranty_status == 'EXPIRED':
            self.warranty_status = 'out_of_warranty'
        else:
            self.warranty_status = 'pending_warranty'
        
        # อัพเดทวันที่ประกัน
        self.warranty_start_date = today
        self.warranty_end_date = customer.warranty_expiry_date
        self.save()

    @property
    def remaining_warranty_days(self):
        """คำนวณจำนวนวันประกันที่เหลือ"""
        if not self.warranty_end_date:
            return 0
            
        today = timezone.now().date()
        if today > self.warranty_end_date:
            return 0
            
        return (self.warranty_end_date - today).days

    def check_appointment_conflict(self, date, time):
        """ตรวจสอบการซ้ำซ้อนของการนัดหมาย"""
        if not self.technician:
            return False
            
        conflicts = ServiceRequest.objects.filter(
            technician=self.technician,
            appointment_date=date,
            appointment_time=time
        ).exclude(id=self.id)
        
        return conflicts.exists()

    def calculate_service_fee(self):
        """คำนวณค่าบริการตามประเภทงาน"""
        if not self.service_type:
            return 0
            
        base_fee = {
            'normal': 500,
            'full_checkup': 1500,
            'air_flow': 2000,
            'checkup_air_plus': 2500
        }.get(self.service_type, 0)
        
        # เพิ่มค่าบริการตามจำนวนเครื่อง
        if self.ac_count:
            base_fee *= self.ac_count
            
        return base_fee

    def is_within_service_hours(self, time):
        """ตรวจสอบว่าอยู่ในเวลาทำการหรือไม่"""
        if not time:
            return True
            
        # กำหนดเวลาทำการ 8:00-17:00
        service_start = time.replace(hour=8, minute=0)
        service_end = time.replace(hour=17, minute=0)
        
        return service_start <= time <= service_end

    # แก้ไขเมธอด save() เดิม
    def save(self, *args, **kwargs):
        # คำนวณราคาอัตโนมัติเมื่อมีการบันทึก
        if self.service_category:
            self.calculated_price = self.calculate_service_fee()
        
        # ตรวจสอบว่าเป็นการซื้ออะไหล่ใหม่หรือไม่
        if self.request_type in ['install', 'all_in'] and not self.warranty_start_date:
            self.warranty_start_date = timezone.now().date()
            self.warranty_end_date = self.warranty_start_date + timedelta(days=365)
            self.warranty_status = 'in_warranty'
            
            # อัพเดทสถานะประกันของลูกค้า
            self.customer.warranty_status = 'ACTIVE'
            self.customer.warranty_expiry_date = self.warranty_end_date
            self.customer.save()
        
        # ตรวจสอบสถานะประกัน
        self.check_warranty_status()
        
        # ตรวจสอบการนัดหมาย
        if self.appointment_date and self.appointment_time:
            if self.check_appointment_conflict(self.appointment_date, self.appointment_time):
                raise ValidationError('มีการนัดหมายซ้ำซ้อนกับช่างท่านนี้')
            
            # ตรวจสอบเวลาทำการ
            if not self.is_within_service_hours(self.appointment_time):
                raise ValidationError('เวลานัดหมายต้องอยู่ในช่วง 8:00-17:00 น.')

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
    STATUS_CHOICES = (
        ('pending', 'รอดำเนินการ'),
        ('in_progress', 'กำลังดำเนินการ'),
        ('completed', 'เสร็จสิ้น'),
        ('cancelled', 'ยกเลิก'),
    )

    # ข้อมูลพื้นฐาน
    sequence = models.IntegerField(verbose_name="ลำดับ", null=True, blank=True)
    completion_status = models.BooleanField(verbose_name="สถานะจบงาน", default=False)
    year = models.CharField(max_length=4, verbose_name="ปี พ.ศ.", null=True, blank=True)
    date = models.DateField(verbose_name="วันที่", default=timezone.now)
    month = models.IntegerField(verbose_name="เดือน", null=True, blank=True)
    time = models.CharField(max_length=10, verbose_name="เวลา", null=True, blank=True)
    
    # ข้อมูลงานและบิล
    job_number = models.CharField(max_length=20, verbose_name="เลขงาน", unique=True)
    bill_number = models.CharField(max_length=20, verbose_name="เลขที่บิล", null=True, blank=True)
    
    # ข้อมูลลูกค้าและเจ้าหน้าที่
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='service_records')
    customer_phone = models.CharField(max_length=15, verbose_name="เบอร์ติดต่อลูกค้า", null=True, blank=True)  # ทำให้เป็น optional
    technician_name = models.CharField(max_length=100, verbose_name="ชื่อเจ้าหน้าที่", null=True, blank=True)
    technician_phone = models.CharField(max_length=15, verbose_name="เบอร์ติดต่อเจ้าหน้าที่", null=True, blank=True)
    
    # ข้อมูลโครงการและบ้าน
    project_code = models.CharField(max_length=10, verbose_name="รหัสโครงการ", null=True, blank=True)
    project_name = models.CharField(max_length=100, verbose_name="ชื่อโครงการ", null=True, blank=True)
    house_number = models.CharField(max_length=20, verbose_name="บ้านเลขที่", null=True, blank=True)
    plot_number = models.CharField(max_length=20, verbose_name="เลขที่แปลง", null=True, blank=True)
    house_type = models.CharField(max_length=20, verbose_name="แบบบ้าน", null=True, blank=True)
    
    # วันที่สำคัญ
    transfer_date = models.DateField(verbose_name="วันที่โอน", null=True, blank=True)
    warranty_expiry = models.DateField(verbose_name="วันที่หมดประกัน", null=True, blank=True)
    
    # รายละเอียดการบริการ
    description = models.TextField(verbose_name="อาการที่รับแจ้ง")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="สถานะ")
    appointment_date = models.DateField(verbose_name="วันนัด", null=True, blank=True)
    appointment_time = models.CharField(max_length=10, verbose_name="เวลานัด", null=True, blank=True)
    
    # รายละเอียดการตรวจสอบและซ่อม
    equipment_status = models.CharField(max_length=100, verbose_name="สถานะวัสดุ/อุปกรณ์", null=True, blank=True)
    cause_found = models.TextField(verbose_name="สาเหตุที่ตรวจพบ", null=True, blank=True)
    solution = models.TextField(verbose_name="การแก้ไข", null=True, blank=True)
    technician_names = models.CharField(max_length=200, verbose_name="ชื่อช่างผู้ดำเนินการ", null=True, blank=True)
    
    # ข้อมูลเพิ่มเติม
    notes = models.TextField(verbose_name="หมายเหตุ", null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="จำนวนเงิน", null=True, blank=True)
    service_images = models.TextField(verbose_name="ลิงก์รูปภาพ", null=True, blank=True)
    additional_notes = models.TextField(verbose_name="หมายเหตุเพิ่มเติม", null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)  # ลบ default=timezone.now ออก
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time']
        verbose_name = "บันทึกการบริการ"
        verbose_name_plural = "บันทึกการบริการ"

    def __str__(self):
        return f"{self.job_number} - {self.customer.customer_name} ({self.date})"

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
