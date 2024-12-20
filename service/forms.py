from django import forms
from .models import ServiceRequest, ServiceRecord

class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = [
            'need_advice',
            'request_type',
            'description',
            'appointment_date',
            'appointment_time',
        ]
        # ไม่แสดงฟิลด์ warranty ในฟอร์ม เพราะจะจัดการอัตโนมัติ
        exclude = ['warranty_status', 'warranty_start_date', 'warranty_end_date']
        labels = {
            'need_advice': 'ต้องการคำแนะนำจากช่างก่อนดำเนินการ',
            'request_type': 'ประเภทการบริการ',
            'description': 'รายละเอียด',
            'appointment_date': 'วันที่นัดหมาย (ถ้ามี)',
            'appointment_time': 'เวลานัดหมาย (ถ้ามี)',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time'}),
        }

class ServiceRecordForm(forms.ModelForm):
    class Meta:
        model = ServiceRecord
        fields = [
            'job_number', 'customer', 'project_code', 
            'plot_number', 'reported_issue', 'appointment_date',
            'appointment_time', 'completion_status', 'faulty_equipment',
            'cause', 'solution', 'service_cost', 'notes'
        ]
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time'}),
            'reported_issue': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }