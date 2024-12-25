from django import forms
from .models import ServiceRequest, ServiceRecord
from django.utils import timezone

class ServiceRequestForm(forms.ModelForm):
    # เพิ่มฟิลด์ใหม่
    warranty_check = forms.BooleanField(
        required=False,
        label='ตรวจสอบประกัน',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = ServiceRequest
        fields = [
            'need_advice',
            'request_type',
            'service_category',
            'service_level',
            'ac_count',
            'description',
            'appointment_date',
            'appointment_time',
            'warranty_check',  # เพิ่มฟิลด์ใหม่
        ]

        exclude = ['warranty_status', 'warranty_start_date', 'warranty_end_date', 'calculated_price']
        labels = {
            'need_advice': 'ต้องการคำแนะนำจากช่างก่อนดำเนินการ',
            'request_type': 'ประเภทการบริการ',
            'service_category': 'ประเภทบริการพิเศษ',
            'service_level': 'ระดับบริการ',
            'ac_count': 'จำนวนเครื่องปรับอากาศ',
            'description': 'รายละเอียด',
            'appointment_date': 'วันที่นัดหมาย (ถ้ามี)',
            'appointment_time': 'เวลานัดหมาย (ถ้ามี)',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time'}),
            'service_category': forms.Select(attrs={'class': 'form-control'}),
            'service_level': forms.Select(attrs={'class': 'form-control'}),
            'ac_count': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ทำให้ฟิลด์ใหม่เป็นตัวเลือก
        optional_fields = ['service_category', 'service_level', 'ac_count']
        for field in optional_fields:
            self.fields[field].required = False

        # เพิ่ม class Bootstrap
        for field in self.fields:
            if isinstance(self.fields[field].widget, forms.CheckboxInput):
                continue
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })

    def clean(self):
        cleaned_data = super().clean()
        
        # เพิ่มการตรวจสอบวันและเวลานัดหมาย
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')

        if appointment_date and appointment_time:
            # ตรวจสอบว่าเป็นเวลาทำการหรือไม่ (8:00-17:00)
            if not (8 <= appointment_time.hour < 17):
                raise forms.ValidationError(
                    'กรุณาเลือกเวลานัดหมายระหว่าง 8:00-17:00 น.'
                )
                
            # ตรวจสอบว่าไม่ใช่วันในอดีต
            if appointment_date < timezone.now().date():
                raise forms.ValidationError(
                    'ไม่สามารถเลือกวันที่ในอดีตได้'
                )

        # ตรวจสอบการเลือกประเภทบริการ
        service_category = cleaned_data.get('service_category')
        service_level = cleaned_data.get('service_level')
        ac_count = cleaned_data.get('ac_count')

        if service_category:
            if not service_level:
                raise forms.ValidationError('กรุณาเลือกระดับบริการ')
            
            if service_category == 'AIRPLUS' and not ac_count:
                raise forms.ValidationError('กรุณาระบุจำนวนเครื่องปรับอากาศ')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # คำนวณราคาอัตโนมัติถ้ามีการเลือกประเภทบริการ
        if instance.service_category:
            instance.calculated_price = instance.calculate_service_fee()
            
        # ตรวจสอบสถานะประกันถ้ามีการเลือก
        if self.cleaned_data.get('warranty_check'):
            instance.check_warranty_status()
            
        if commit:
            instance.save()
        return instance

class ServiceRecordForm(forms.ModelForm):
    class Meta:
        model = ServiceRecord
        fields = [
            # ข้อมูลพื้นฐาน
            'sequence',
            'completion_status',
            'year',
            'date',
            'month',
            'time',
            
            # ข้อมูลงานและบิล
            'job_number',
            'bill_number',
            
            # ข้อมูลลูกค้าและเจ้าหน้าที่
            'customer',
            'customer_phone',
            'technician_name',
            'technician_phone',
            
            # ข้อมูลโครงการและบ้าน
            'project_code',
            'project_name',
            'house_number',
            'plot_number',
            'house_type',
            
            # วันที่สำคัญ
            'transfer_date',
            'warranty_expiry',
            
            # รายละเอียดการบริการ
            'description',
            'status',
            'appointment_date',
            'appointment_time',
            
            # รายละเอียดการตรวจสอบและซ่อม
            'equipment_status',
            'cause_found',
            'solution',
            'technician_names',
            
            # ข้อมูลเพิ่มเติม
            'notes',
            'amount',
            'service_images',
            'additional_notes',
        ]
        widgets = {
            # Text areas
            'description': forms.Textarea(attrs={'rows': 3}),
            'cause_found': forms.Textarea(attrs={'rows': 3}),
            'solution': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'additional_notes': forms.Textarea(attrs={'rows': 3}),
            'service_images': forms.Textarea(attrs={'rows': 2}),
            
            # Date inputs
            'date': forms.DateInput(attrs={'type': 'date'}),
            'transfer_date': forms.DateInput(attrs={'type': 'date'}),
            'warranty_expiry': forms.DateInput(attrs={'type': 'date'}),
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            
            # Time input
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time'}),
            
            # Checkbox for completion status
            'completion_status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            # Number inputs
            'sequence': forms.NumberInput(attrs={'min': 0}),
            'month': forms.NumberInput(attrs={'min': 1, 'max': 12}),
            'amount': forms.NumberInput(attrs={'step': '0.01'}),
            
            # Year input
            'year': forms.TextInput(attrs={'maxlength': 4, 'pattern': '[0-9]{4}'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # เพิ่ม class Bootstrap ให้กับ fields
        for field in self.fields:
            if isinstance(self.fields[field].widget, forms.CheckboxInput):
                continue  # ข้าม checkbox เพราะใช้ class form-check-input แล้ว
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })
            
        # เพิ่ม placeholder และ help text ที่เป็นประโยชน์
        self.fields['job_number'].widget.attrs['placeholder'] = 'เช่น AF61-0001'
        self.fields['year'].widget.attrs['placeholder'] = 'เช่น 2566'
        self.fields['project_code'].widget.attrs['placeholder'] = 'เช่น CSN'
        self.fields['service_images'].widget.attrs['placeholder'] = 'วางลิงก์รูปภาพ แต่ละลิงก์ขึ้นบรรทัดใหม่'
        
        # ทำให้บางฟิลด์เป็นตัวเลือก
        optional_fields = ['bill_number', 'technician_name', 'technician_phone', 
                         'service_images', 'additional_notes']
        for field in optional_fields:
            self.fields[field].required = False