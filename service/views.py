# Library ที่เรียกใช้ทั้งหมด
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, TemplateView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Sum, Q
from datetime import datetime, timedelta
import pandas as pd
from .models import (
    ServiceRequest, 
    TechnicianProposal, 
    ServiceRecord,
    TechnicianJobStatus, 
    ServiceImage
)
from accounts.models import Customer
from .forms import ServiceRequestForm, ServiceRecordForm
from django.utils import timezone
from accounts.models import User
from django.views.generic.detail import BaseDetailView
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from openpyxl import Workbook
import io
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()

# หน้าแรก
class HomeView(TemplateView):
    template_name = 'service/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['user_type'] = self.request.user.user_type
        return context

# มอบหมายงานให้กับช่าง
@login_required
def assign_technician(request, pk):
    if request.method == 'POST' and request.user.user_type == 'service':
        service_request = get_object_or_404(ServiceRequest, pk=pk)
        technician_id = request.POST.get('technician')
        
        if technician_id:
            try:
                technician = User.objects.get(id=technician_id, user_type='technician')
                service_request.technician = technician
                service_request.status = 'assigned'
                service_request.save()
                
                # สร้างประวัติการมอบหมายงาน
                TechnicianJobStatus.objects.create(
                    service_request=service_request,
                    technician=technician,
                    status='assigned',
                    notes='มอบหมายงานโดยฝ่ายบริการ'
                )
                
                messages.success(request, f'มอบหมายงานให้ช่าง {technician.customer.customer_name} เรียบร้อยแล้ว')
                
                # ตรวจสอบว่าเป็น AJAX request หรือไม่
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'success',
                        'message': f'มอบหมายงานให้ช่าง {technician.customer.customer_name} เรียบร้อยแล้ว'
                    })
                
            except User.DoesNotExist:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'ไม่พบข้อมูลช่างที่เลือก'
                    }, status=404)
                messages.error(request, 'ไม่พบข้อมูลช่างที่เลือก')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': 'กรุณาเลือกช่าง'
                }, status=400)
            messages.error(request, 'กรุณาเลือกช่าง')
    
    # สำหรับ non-AJAX requests หรือเมื่อเสร็จสิ้นการทำงาน
    return redirect('service:request_detail', pk=pk)
# ตรวจสอบสิทธิ์การเข้าถึงข้อมูล
class ServiceStaffRequired(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.user_type == 'service'

# ตรวจสอบสิทธิ์การเข้าถึงข้อมูลช่าง
class TechnicianRequired(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.user_type == 'technician'

# สร้างงานใหม่
class CreateServiceRequestView(LoginRequiredMixin, CreateView):
    model = ServiceRequest
    form_class = ServiceRequestForm
    template_name = 'service/create_request.html'
    success_url = reverse_lazy('service:request_list')

    def form_valid(self, form):
        form.instance.customer = self.request.user.customer
        
        # คำนวณราคาอัตโนมัติถ้ามีการเลือกประเภทบริการ
        if form.instance.service_category:
            form.instance.calculated_price = form.instance.calculate_service_fee()
            
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.customer:
            context['project_type'] = self.request.user.customer.project_type
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.customer:
            kwargs['initial'] = {'customer': self.request.user.customer}
        return kwargs

# ดูรายการงาน
class ServiceRequestListView(LoginRequiredMixin, ListView):
    model = ServiceRequest
    template_name = 'service/request_list.html'
    context_object_name = 'requests'

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'customer':
            return ServiceRequest.objects.filter(customer=user.customer)
        elif user.user_type in ['service', 'technician']:
            return ServiceRequest.objects.all()
        return ServiceRequest.objects.none()

# ดูรายละเอียดงาน
class ServiceRequestDetailView(LoginRequiredMixin, DetailView):
    model = ServiceRequest
    template_name = 'service/request_detail.html'
    context_object_name = 'request'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # เพิ่มบรรทัดนี้เพื่อดึงรายชื่อช่าง
        context['available_technicians'] = User.objects.filter(user_type='technician', is_active=True)
        
        context.update({
            'service_proposals': self.object.service_proposals.all().order_by('-created_at'),
            'technician_proposals': self.object.technician_proposals.all().order_by('-created_at'),
            'job_statuses': TechnicianJobStatus.objects.filter(
                service_request=self.object
            ).order_by('-created_at'),
            'service_images': ServiceImage.objects.filter(
                service_request=self.object
            ).order_by('-uploaded_at')
        })
        return context

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'customer':
            return ServiceRequest.objects.filter(customer=user.customer)
        elif user.user_type in ['service', 'technician']:
            return ServiceRequest.objects.all()
        return ServiceRequest.objects.none()

# หน้า Dashboard ของฝ่ายบริการ
class DashboardView(LoginRequiredMixin, ServiceStaffRequired, TemplateView):
    template_name = 'service/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ดึงข้อมูลงานที่รอดำเนินการ
        context['pending_records'] = ServiceRequest.objects.filter(
            status__in=['pending', 'new']
        ).select_related('customer').order_by('-created_at')

        # ดึงข้อมูลงานที่กำลังดำเนินการ
        context['in_progress_records'] = ServiceRequest.objects.filter(
            status__in=['assigned', 'accepted','traveling', 'arrived', 'fixing']
        ).select_related('technician').order_by('-created_at')

        # ข้อมูลกราฟ
        period = self.request.GET.get('period', 'month')
        today = timezone.now()
        
        if period == 'day':
            start_date = today - timedelta(days=7)
            date_format = '%Y-%m-%d'
        elif period == 'week':
            start_date = today - timedelta(weeks=4)
            date_format = '%Y-%W'
        elif period == 'year':
            start_date = today - timedelta(days=365)
            date_format = '%Y-%m'
        else:  # month
            start_date = today - timedelta(days=30)
            date_format = '%Y-%m-%d'

        # ใช้ Django ORM แทน raw SQL
        issues = ServiceRequest.objects.filter(
            created_at__gte=start_date
        ).order_by('created_at')

        # จัดกลุ่มข้อมูลตามวันที่
        data_points = {}
        for issue in issues:
            if period == 'day':
                date_key = issue.created_at.strftime('%d/%m')
            elif period == 'week':
                date_key = f"W{issue.created_at.strftime('%W')}"
            elif period == 'year':
                date_key = issue.created_at.strftime('%m/%Y')
            else:  # month
                date_key = issue.created_at.strftime('%d/%m')
            
            data_points[date_key] = data_points.get(date_key, 0) + 1

        # เรียงข้อมูลตามวันที่แบบย้อนกลับ
        sorted_data = sorted(data_points.items(), key=lambda x: (
            int(x[0].split('/')[1]) if '/' in x[0] else 0,  # เดือน
            int(x[0].split('/')[0]) if '/' in x[0] else int(x[0].replace('W', ''))  # วันหรือสัปดาห์
        ))
        
        context['issues_labels'] = [item[0] for item in sorted_data]
        context['issues_data'] = [item[1] for item in sorted_data]

        if not context['issues_labels']:
            context['issues_labels'] = ['ไม่มีข้อมูล']
            context['issues_data'] = [0]
        
        return context

# ดูรายการบันทึกงาน
class ServiceRecordListView(LoginRequiredMixin, ListView):
    model = ServiceRecord
    template_name = 'service/record_list.html'
    context_object_name = 'records'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search')
        
        if search_query:
            queryset = queryset.filter(
                Q(customer__customer_name__icontains=search_query) |
                Q(job_number__icontains=search_query) |
                Q(customer__phone__icontains=search_query)
            )
        
        return queryset.order_by('sequence')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # คำนวณลำดับเริ่มต้นสำหรับแต่ละหน้า
        page_number = self.request.GET.get('page', 1)
        context['start_index'] = (int(page_number) - 1) * self.paginate_by
        
        # เพิ่มข้อมูลสำหรับการแสดงผล
        context['total_records'] = self.get_queryset().count()
        context['current_page'] = page_number
        
        # สร้างรายการลำดับสำหรับแต่ละรายการในหน้าปัจจุบัน
        records_with_index = []
        for index, record in enumerate(context['records'], start=context['start_index'] + 1):
            records_with_index.append({
                'index': index,
                'record': record
            })
        context['records_with_index'] = records_with_index
        
        print(f"จำนวนรายการที่จะแสดง: {context['total_records']}")
        print(f"หน้าปัจจุบัน: {context['current_page']}")
        print(f"เริ่มต้นที่ลำดับ: {context['start_index'] + 1}")
        
        return context

class ServiceRecordDeleteView(LoginRequiredMixin, DeleteView):
    model = ServiceRecord
    success_url = reverse_lazy('service:service_records')
    
    def delete(self, request, *args, **kwargs):
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, 'ลบรายการเรียบร้อยแล้ว')
            return response
        except Exception as e:
            messages.error(request, f'เกิดข้อผิดพลาด: {str(e)}')
            return redirect('service:service_records')

# สร้างบันทึกงาน
class ServiceRecordCreateView(LoginRequiredMixin, ServiceStaffRequired, CreateView):
    model = ServiceRecord
    form_class = ServiceRecordForm
    template_name = 'service/record_form.html'
    success_url = reverse_lazy('service:service_records')

class ServiceRecordDetailView(LoginRequiredMixin, DetailView):
    model = ServiceRecord
    template_name = 'service/record_detail.html'
    context_object_name = 'record'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.get_object()
        
        # เพิ่มข้อมูลสถานะการรับประกัน
        if record.warranty_expiry:
            today = timezone.now().date()
            context['warranty_status'] = 'ในประกัน' if record.warranty_expiry >= today else 'หมดประกัน'
            context['days_remaining'] = (record.warranty_expiry - today).days if record.warranty_expiry >= today else 0
        
        # เพิ่มข้อมูลการนัดหมาย
        if record.appointment_date:
            today = timezone.now().date()
            context['appointment_status'] = 'รอดำเนินการ' if record.appointment_date >= today else 'เลยกำหนด'
            context['days_to_appointment'] = (record.appointment_date - today).days
        
        # เพิ่มข้อมูลประวัติการบริการของลูกค้า
        context['service_history'] = ServiceRecord.objects.filter(
            customer=record.customer
        ).exclude(
            id=record.id
        ).order_by('-date', '-time')[:5]  # แสดง 5 รายการล่าสุด
        
        # เพิ่มข้อมูลสถิติ
        context['stats'] = {
            'total_services': ServiceRecord.objects.filter(customer=record.customer).count(),
            'completed_services': ServiceRecord.objects.filter(
                customer=record.customer,
                completion_status=True
            ).count(),
            'pending_services': ServiceRecord.objects.filter(
                customer=record.customer,
                completion_status=False
            ).count()
        }
        
        # เพิ่มข้อมูลโครงการ
        context['project_info'] = {
            'total_houses': ServiceRecord.objects.filter(project_name=record.project_name).count(),
            'total_services': ServiceRecord.objects.filter(
                project_name=record.project_name
            ).exclude(id=record.id).count()
        }
        
        # เพิ่มข้อมูลช่างเทคนิค
        if record.technician_name:
            context['technician_stats'] = {
                'total_services': ServiceRecord.objects.filter(
                    technician_name=record.technician_name
                ).count(),
                'completed_services': ServiceRecord.objects.filter(
                    technician_name=record.technician_name,
                    completion_status=True
                ).count()
            }
        
        # เพิ่มข้อมูลสำหรับการติดตาม
        context['timeline'] = [
            {
                'date': record.date,
                'event': 'รับแจ้งงาน',
                'details': record.description
            }
        ]
        if record.appointment_date:
            context['timeline'].append({
                'date': record.appointment_date,
                'event': 'นัดหมาย',
                'details': f'เวลา: {record.appointment_time}'
            })
        
        return context

# แก้ไขบันทึกงาน
class ServiceRecordUpdateView(LoginRequiredMixin, ServiceStaffRequired, UpdateView):
    model = ServiceRecord
    form_class = ServiceRecordForm
    template_name = 'service/record_form.html'
    
    def get_success_url(self):
        messages.success(self.request, 'บันทึกการแก้ไขเรียบร้อยแล้ว')
        return reverse_lazy('service:record_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'แก้ไขบันทึกการบริการ'
        context['is_update'] = True
        return context
        
    def form_valid(self, form):
        response = super().form_valid(form)
        # บันทึกประวัติการแก้ไข
        ServiceRecord.objects.create(
            service_record=self.object,
            modified_by=self.request.user,
            modified_fields=form.changed_data,
            action='update'
        )
        return response

# ลบบันทึกงาน
class ServiceRecordDeleteView(LoginRequiredMixin, DeleteView):
    model = ServiceRecord
    success_url = reverse_lazy('service:service_records')
    template_name = 'service/record_confirm_delete.html'
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'ลบข้อมูลเรียบร้อยแล้ว')
        return super().delete(request, *args, **kwargs)

# ปฏิทินของช่าง
class TechnicianCalendarView(LoginRequiredMixin, TechnicianRequired, TemplateView):
    template_name = 'service/technician_calendar.html'
    
    def get_status_colors(self):
        return {
            'assigned': {'bg': 'warning', 'color': '#ffc107'},
            'accepted': {'bg': 'info', 'color': '#17a2b8'},
            'traveling': {'bg': 'primary', 'color': '#007bff'},
            'arrived': {'bg': 'purple', 'color': '#6f42c1'},
            'fixing': {'bg': 'orange', 'color': '#fd7e14'},
            'completed_cash': {'bg': 'success', 'color': '#28a745'},
            'completed_call': {'bg': 'success', 'color': '#28a745'},
            'cancelled': {'bg': 'danger', 'color': '#dc3545'},
            'rescheduled': {'bg': 'secondary', 'color': '#6c757d'}
        }
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # ดึงงานวันนี้
        today_tasks = ServiceRequest.objects.filter(
            appointment_date=today,
            technician=self.request.user
        ).select_related('customer')
        
        # เพิ่ม status_color สำหรับ badge
        status_colors = self.get_status_colors()
        for task in today_tasks:
            task.status_color = status_colors.get(task.status, {}).get('bg', 'secondary')
        
        context['today_tasks'] = today_tasks
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                events = []
                appointments = ServiceRequest.objects.filter(
                    technician=self.request.user,
                    appointment_date__isnull=False
                ).select_related('customer')

                status_colors = self.get_status_colors()

                for appointment in appointments:
                    event = {
                        'id': appointment.id,
                        'title': f"{appointment.customer.customer_name}",
                        'start': appointment.appointment_date.isoformat(),
                        'backgroundColor': status_colors.get(appointment.status, {}).get('color', '#6c757d'),
                        'borderColor': status_colors.get(appointment.status, {}).get('color', '#6c757d'),
                        'extendedProps': {
                            'id': appointment.id,  # เพิ่ม id ใน extendedProps
                            'customer': appointment.customer.customer_name,
                            'request_type': appointment.get_request_type_display(),
                            'status': appointment.status,
                            'status_display': appointment.get_status_display(),
                            'description': appointment.description,
                            'warranty_status': appointment.warranty_status,
                        }
                    }
                    
                    if appointment.appointment_time:
                        event['start'] = f"{appointment.appointment_date.isoformat()}T{appointment.appointment_time.strftime('%H:%M:%S')}"
                    
                    
                    events.append(event)
                
                return JsonResponse(events, safe=False)
            except Exception as e:
                print(f"Error in get_events: {e}")
                return JsonResponse({'error': str(e)}, status=500)
        return super().get(request, *args, **kwargs)

class TechnicianDailySummaryView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'service/technician_daily_summary.html'

    def get_status_color(self, status):
        status_colors = {
            'assigned': 'warning',
            'accepted': 'info',
            'traveling': 'primary',
            'arrived': 'purple',
            'fixing': 'orange',
            'completed_cash': 'success',
            'completed_call': 'success',
        }
        return status_colors.get(status, 'secondary')

    def test_func(self):
        # อนุญาตให้ทั้งช่างและฝ่ายบริการเข้าถึงได้
        allowed_types = ['technician', 'service']
        return self.request.user.is_authenticated and self.request.user.user_type in allowed_types

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # รับวันที่จาก URL parameter หรือใช้วันนี้
        date_str = self.request.GET.get('date')
        if date_str:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            selected_date = timezone.now().date()
            
        # กำหนดช่วงเวลา
        start_date = timezone.make_aware(datetime.combine(selected_date, datetime.min.time()))
        end_date = timezone.make_aware(datetime.combine(selected_date, datetime.max.time()))
        
        # ดึงงานตามประเภทผู้ใช้
        if self.request.user.user_type == 'technician':
            # ถ้าเป็นช่าง ดึงเฉพาะงานของตัวเอง
            daily_jobs = ServiceRequest.objects.filter(
                appointment_date__range=(start_date, end_date),
                technician=self.request.user
            )
        else:
            # ถ้าเป็นฝ่ายบริการ ดึงงานทั้งหมด
            daily_jobs = ServiceRequest.objects.filter(
                appointment_date__range=(start_date, end_date)
            )

        daily_jobs = daily_jobs.select_related('customer', 'technician').order_by('appointment_time')
        
        # ดึงงานที่เสร็จสิ้น
        completed_jobs = daily_jobs.filter(
            status__in=['completed_cash', 'completed_call']
        )
        
        # คำนวณสถิติ
        total_jobs = daily_jobs.count()
        completion_rate = (completed_jobs.count() / total_jobs * 100) if total_jobs > 0 else 0
        total_revenue = completed_jobs.aggregate(Sum('estimated_cost'))['estimated_cost__sum'] or 0
        
        # สรุปสถานะงาน
        job_summary = []
        status_choices = ServiceRequest.STATUS_CHOICES
        for status_code, status_display in status_choices:
            count = daily_jobs.filter(status=status_code).count()
            if count > 0:
                job_summary.append({
                    'status_display': status_display,
                    'status_color': self.get_status_color(status_code),
                    'count': count
                })

        # เพิ่มข้อมูลเพิ่มเติมสำหรับแต่ละงาน
        for job in daily_jobs:
            job.status_color = self.get_status_color(job.status)
            job.customer_name = job.customer.customer_name if job.customer else "ไม่ระบุลูกค้า"
            job.formatted_time = job.appointment_time.strftime("%H:%M") if job.appointment_time else "ไม่ระบุเวลา"
            job.technician_name = job.technician.customer.customer_name if job.technician else "ยังไม่ได้กำหนดช่าง"

        # ไทม์ไลน์การอัพเดทสถานะ
        timeline_filter = {
            'service_request__appointment_date': selected_date  # เปลี่ยนเป็นใช้ appointment_date แทน
        }
        
        if self.request.user.user_type == 'technician':
            timeline_filter['service_request__technician'] = self.request.user

        job_timeline = TechnicianJobStatus.objects.filter(  # เปลี่ยนจาก TechnicianResponse เป็น TechnicianJobStatus
            **timeline_filter
        ).select_related(
            'service_request',
            'service_request__customer',
            'service_request__technician',
            'service_request__technician__customer'
        ).order_by('-created_at')

        context.update({
            'selected_date': selected_date,
            'prev_date': selected_date - timedelta(days=1),
            'next_date': selected_date + timedelta(days=1),
            'daily_jobs': daily_jobs,
            'total_jobs': total_jobs,
            'completion_rate': completion_rate,
            'total_revenue': total_revenue,
            'job_summary': job_summary,
            'job_timeline': job_timeline,
            'is_service': self.request.user.user_type == 'service',
            'job_timeline': job_timeline,
        })
        return context

# ดูรายละเอียดงานของช่าง
class TechnicianTaskDetailView(LoginRequiredMixin, TechnicianRequired, BaseDetailView):
    model = ServiceRequest
    
    def render_to_response(self, context):
        task = self.object
        data = {
            'customer_name': task.customer.customer_name,
            'request_type': task.get_request_type_display(),
            'status': task.get_status_display(),
            'created_at': task.created_at.strftime('%d/%m/%Y %H:%M'),
            'appointment_date': task.appointment_date.strftime('%d/%m/%Y') if task.appointment_date else None,
            'appointment_time': task.appointment_time.strftime('%H:%M') if task.appointment_time else None,
            'description': task.description
        }
        return JsonResponse(data)

@login_required
def submit_technician_advice(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id)
    
    if request.method == 'POST' and request.user.user_type == 'technician':
        advice = request.POST.get('advice')
        estimated_cost = request.POST.get('estimated_cost')
        
        if advice and estimated_cost:
            service_request.technician_advice = advice
            service_request.estimated_cost = estimated_cost
            service_request.status = 'advice_given'
            service_request.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'ส่งคำปรึกษาเรียบร้อยแล้ว'
            })
            
    return JsonResponse({
        'status': 'error',
        'message': 'ไม่สามารถส่งคำแนะนำได้'
    }, status=400)

@login_required
def confirm_customer_request(request, request_id):
    """สำหรับลูกค้ายืนยันหรือปฏิเสธคำแนะนำ"""
    if request.user.user_type != 'customer':
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่มีสิทธิ์ดำเนินการ'
        }, status=403)

    service_request = get_object_or_404(ServiceRequest, id=request_id)
    
    if not hasattr(request.user, 'customer') or request.user.customer != service_request.customer:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่มีสิทธิ์ดำเนินการ'
        }, status=403)

    action = request.POST.get('action')
    if action not in ['confirm', 'reject']:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid action'
        }, status=400)

    try:
        if action == 'confirm':
            service_request.customer_confirmed = True
            service_request.status = 'accepted'
            message = 'ยืนยันการดำเนินการเรียบร้อย'
        else:
            service_request.status = 'cancelled'
            message = 'ปฏิเสธการดำเนินการเรียบร้อย'
            
        service_request.save()
        
        return JsonResponse({
            'status': 'success',
            'message': message
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def submit_service_recommendation(request, service_id):
    # ดึงข้อมูล ServiceRequest พร้อมข้อมูลที่เกี่ยวข้อง
    service_request = get_object_or_404(
        ServiceRequest.objects.select_related(
            'customer',
            'technician'
        ), 
        id=service_id
    )

    # ตรวจสอบว่าผู้ใช้เป็นช่างที่ได้รับมอบหมายงานนี้
    if not request.user.is_authenticated or request.user.user_type not in ['technician', 'service']:
        messages.error(request, 'ไม่มีสิทธิ์เข้าถึงหน้านี้')
        return redirect('service:request_list')

    # ถ้าเป็นช่าง ต้องตรวจสอบว่าเป็นช่างที่ได้รับมอบหมายงานนี้
    if request.user.user_type == 'technician' and service_request.technician != request.user:
        messages.error(request, 'คุณไม่ได้รับมอบหมายงานนี้')
        return redirect('service:request_list')

    if request.method == 'POST':
        try:
            # รับข้อมูลจากฟอร์ม
            description = request.POST.get('description')
            estimated_cost = request.POST.get('estimated_cost')
            service_type = request.POST.get('service_type')

            # ตรวจสอบข้อมูลที่จำเป็น
            if not all([description, service_type]):
                return JsonResponse({
                    'status': 'error',
                    'message': 'กรุณากรอกข้อมูลให้ครบถ้วน'
                }, status=400)

            # แปลงค่าใช้จ่ายเป็นตัวเลข
            try:
                estimated_cost = float(estimated_cost or 0)
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'ราคาประเมินไม่ถูกต้อง'
                }, status=400)

            # สร้างข้อเสนอแนะ
            proposal = TechnicianProposal.objects.create(
                service_request=service_request,
                technician=request.user,
                description=f"ประเภทงาน: {service_type}\n\nรายละเอียด: {description}",
                estimated_cost=estimated_cost
            )

            return JsonResponse({
                'status': 'success',
                'message': 'ส่งข้อเสนอแนะเรียบร้อยแล้ว'
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'เกิดข้อผิดพลาด: {str(e)}'
            }, status=500)

    # สำหรับ GET request
    context = {
        'service_request': service_request,
        'customer': service_request.customer,
    }
    return render(request, 'service/service_recommendation.html', context)

# ดูปฏิทินของช่าง
@login_required
def get_technician_events(request):
    try:
        # ตรวจสอบว่ามี request.GET หรือไม่
        if not request.GET:
            return JsonResponse([], safe=False)

        status_colors = {
            'assigned': '#ffc107',
            'accepted': '#17a2b8',
            'traveling': '#007bff',
            'arrived': '#6f42c1',
            'fixing': '#fd7e14',
            'completed_cash': '#28a745',
            'completed_call': '#28a745',
            'cancelled': '#dc3545',
            'rescheduled': '#6c757d'
        }

        start = request.GET.get('start')
        end = request.GET.get('end')

        # ส่งค่าว่างถ้าไม่มีวันที่
        if not start or not end:
            return JsonResponse([], safe=False)

        # แปลงวันที่
        try:
            start_date = start.split('T')[0] if 'T' in start else start
            end_date = end.split('T')[0] if 'T' in end else end
            
            # ตรวจสอบรูปแบบวันที่
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except (ValueError, AttributeError) as e:
            print(f"Date parsing error: {str(e)}")
            return JsonResponse([], safe=False)

        # ดึงข้อมูลงาน
        events = ServiceRequest.objects.filter(
            technician=request.user,
            appointment_date__range=[start_date, end_date]
        ).select_related('customer')

        calendar_events = []
        for event in events:
            try:
                if event.appointment_date:
                    event_time = event.appointment_time or timezone.now().time()
                    start_datetime = datetime.combine(event.appointment_date, event_time)
                    
                    # สร้าง customer_info ที่รวมชื่อลูกค้า, โครงการ และบ้านเลขที่
                    project_info = f"{event.customer.project_name} {event.customer.house_number}"
                    technician_info = f"{event.technician.customer.customer_name} ({event.technician.get_user_type_display()})"

                    event_data = {
                        'id': str(event.id),
                        'title': str(event.customer.customer_name),  # แสดงข้อมูลที่รวมแล้วเป็นชื่องาน
                        'start': start_datetime.isoformat(),
                        'status': str(event.status),
                        'backgroundColor': status_colors.get(event.status, '#6c757d'),
                        'borderColor': status_colors.get(event.status, '#6c757d'),
                        'extendedProps': {
                            'id': str(event.id),
                            'customer': str(event.customer.customer_name),
                            'project_info': project_info,
                            'project_name': str(event.customer.project_name),
                            'house_number': str(event.customer.house_number),
                            'phone': str(event.customer.phone),
                            'appointment_time': str(event.appointment_time),
                            'description': str(event.description or ''),
                            'status': str(event.status),
                            'status_display': str(event.get_status_display()),
                            'request_type': str(event.get_request_type_display()),
                            'technician_info': technician_info,
                            'technician_username': str(event.technician.customer.customer_name),
                            'technician_display': str(event.technician.get_user_type_display()),
                            'warranty_status': str(event.warranty_status),
                        }
                    }
                    calendar_events.append(event_data)
            except Exception as e:
                print(f"Error processing event {event.id}: {str(e)}")
                continue

        # ตรวจสอบว่า calendar_events ไม่เป็นค่าว่าง
        if not calendar_events:
            return JsonResponse([], safe=False)

        return JsonResponse(calendar_events, safe=False)

    except Exception as e:
        print(f"Error in get_technician_events: {str(e)}")
        # ส่งค่าว่างแทนที่จะส่ง error
        return JsonResponse([], safe=False)

@login_required
def accept_request(request, pk):
    if request.method == 'POST' and request.user.user_type == 'technician':
        service_request = get_object_or_404(ServiceRequest, pk=pk)
        
        if service_request.technician == request.user:
            service_request.status = 'pending_advice'
            service_request.save()
            
            TechnicianJobStatus.objects.create(
                service_request=service_request,
                technician=request.user,
                status='accepted',
                notes='ช่างรับงานและเตรียมให้คำแนะนำ'
            )
            
            messages.success(request, 'รับงานเรียบร้อยแล้ว กรุณาให้คำแนะนำแก่ลูกค้า')
            
    return redirect('service:request_detail', pk=pk)

@login_required
def confirm_advice(request, pk):
    if request.method == 'POST':
        service_request = get_object_or_404(ServiceRequest, pk=pk)
        
        if request.user == service_request.customer:
            service_request.status = 'assigned'
            service_request.save()
            
            TechnicianJobStatus.objects.create(
                service_request=service_request,
                technician=service_request.technician,
                status='assigned',
                notes='ลูกค้ายืนยันคำแนะนำและพร้อมดำเนินการ'
            )
            
            messages.success(request, 'ยืนยันคำแนะนำเรียบร้อยแล้ว ช่างจะดำเนินการในขั้นตอนต่อไป')
            
    return redirect('service:request_detail', pk=pk)

# อนุญาติการตอบรับของลูกค้า
@login_required
def approve_proposal(request, proposal_id):
    proposal = get_object_or_404(TechnicianProposal, id=proposal_id)
    if request.method == 'POST' and request.user.user_type == 'customer':
        proposal.is_approved = True
        proposal.save()
        proposal.service_request.status = 'customer_approved'
        proposal.service_request.save()
        return redirect('service:request_detail', pk=proposal.service_request.pk)
    return redirect('service:request_list')

# ส่งข้อเสนอแนะการซ่อม
@login_required
def submit_service_recommendation(request, service_id):
    # ตรวจสอบว่าเป็นช่างหรือไม่
    if request.user.user_type != 'technician':
        return HttpResponseForbidden("ไม่มีสิทธิ์เข้าถึง")
        
    service_request = get_object_or_404(ServiceRequest, id=service_id)
    
    if request.method == 'POST':
        try:
            # รับข้อมูลจากฟอร์ม
            service_type = request.POST.get('service_type')
            description = request.POST.get('description')
            estimated_cost = request.POST.get('estimated_cost')
            
            # บันทึกคำแนะนำ
            service_request.technician_advice = description
            service_request.estimated_cost = estimated_cost
            service_request.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'บันทึกคำแนะนำเรียบร้อยแล้ว'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    else:
        # แสดงหน้าฟอร์มให้คำแนะนำ
        context = {
            'service_request': service_request,
            'customer': service_request.customer
        }
        return render(request, 'service/service_recommendation.html', context)

# อัพเดทสถานะงานของช่าง
@login_required
def update_job_status(request, service_id):
    if request.method == 'POST' and request.user.user_type == 'technician' and request.user.user_type == 'service':
        service_request = get_object_or_404(ServiceRequest, id=service_id)
        status = TechnicianJobStatus.objects.create(
            service_request=service_request,
            technician=request.user,
            service=request.user,
            status=request.POST.get('status')
        )
        
        if 'photos' in request.FILES:
            for photo in request.FILES.getlist('photos'):
                try:
                    # สร้าง ServiceImage object แต่ยังไม่บันทึก
                    image = ServiceImage(
                        service_request=service_request,
                        image=photo,
                        description=request.POST.get('image_description', '')
                    )
                    
                    # ตรวจสอบรูปซ้ำด้วย hash
                    image_hash = image.generate_hash()
                    if not ServiceImage.objects.filter(
                        service_request=service_request,
                        image_hash=image_hash
                    ).exists():
                        image.save()  # บันทึกเฉพาะรูปที่ไม่ซ้ำ
                    
                except ValidationError as e:
                    return JsonResponse({
                        'status': 'error',
                        'message': str(e)
                    }, status=400)
        
        if status.status in ['completed_cash', 'completed_call']:
            service_request.status = 'completed'
            service_request.save()
            
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=403)

# อัพเดทสถานะงานของฝ่ายบริการ
@login_required
def update_service_status(request, service_id):
    if request.method == 'POST':
        service_request = get_object_or_404(ServiceRequest, id=service_id)
        action = request.POST.get('action')
        new_status = request.POST.get('status')

        try:
            # ส่วนสำหรับลูกค้า
            if request.user.user_type == 'customer' and service_request.customer == request.user.customer:
                if action == 'cancel':
                    if service_request.status not in ['completed_cash', 'completed_call', 'cancelled']:
                        service_request.status = 'cancelled'
                        service_request.save()
                        return JsonResponse({'status': 'success'})

                elif action == 'reschedule':
                    if service_request.status not in ['completed_cash', 'completed_call', 'cancelled']:
                        new_date = request.POST.get('new_appointment_date')
                        new_time = request.POST.get('new_appointment_time')
                        
                        if new_date and new_time:
                            service_request.status = 'rescheduled'
                            service_request.appointment_date = new_date
                            service_request.appointment_time = new_time
                            service_request.save()
                            return JsonResponse({'status': 'success'})

            # ส่วนสำหรับช่าง
            if request.user.user_type == 'technician' and service_request.technician == request.user:
                if not service_request.is_confirmed:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'รอการยืนยันจากฝ่ายบริการ'
                    }, status=403)

                if new_status:
                    current_status = service_request.status

                    # ตรวจสอบลำดับการอัพเดทสถานะ
                    status_flow = {
                        'confirmed': ['assigned'],
                        'assigned': ['accepted'],
                        'accepted': ['traveling'],
                        'traveling': ['arrived'],
                        'arrived': ['fixing'],
                        'fixing': ['completed_cash', 'completed_call'],
                    }

                    # ตรวจสอบว่าสถานะที่จะอัพเดทถูกต้องตามลำดับหรือไม่
                    if current_status in status_flow and new_status not in status_flow[current_status]:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'ไม่สามารถอัพเดทสถานะนี้ได้ในขั้นตอนนี้'
                        }, status=400)

                    # อัพเดทสถานะ
                    service_request.status = new_status
                    service_request.save()

                    # บันทึกประวัติการอัพเดทสถานะ
                    status_update = TechnicianJobStatus.objects.create(
                        service_request=service_request,
                        technician=request.user,
                        status=new_status,
                        notes=request.POST.get('notes', '')
                    )

                    # จัดการรูปภาพ
                    if 'photos' in request.FILES:
                        for photo in request.FILES.getlist('photos'):
                            try:
                                # ตรวจสอบว่ารูปน้เคยอัพโหลดแล้วหรือไม่
                                existing_image = ServiceImage.objects.filter(
                                    service_request=service_request,
                                    image=photo.name
                                ).first()

                                if not existing_image:
                                    image = ServiceImage.objects.create(
                                        service_request=service_request,
                                        image=photo,
                                        description=request.POST.get('image_description', '')
                                    )
                            except ValidationError as e:
                                return JsonResponse({
                                    'status': 'error',
                                    'message': str(e)
                                }, status=400)

                    return JsonResponse({'status': 'success'})

            return JsonResponse({
                'status': 'error',
                'message': 'ไม่มีสิทธิ์ในการอัพเดทสถานะ'
            }, status=403)

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed'
    }, status=405)

# ยืนยันการแจ้งซ่อม
@login_required
def confirm_service_request(request, request_id):
    """สำหรับฝ่ายบริการยืนยันการแจ้งซ่อม"""
    if request.user.user_type != 'service':
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่มีสิทธิ์ดำเนินการ'
        }, status=403)

    service_request = get_object_or_404(ServiceRequest, id=request_id)
    
    try:
        service_request.is_confirmed = True
        service_request.status = 'confirmed'
        service_request.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'ยืนยันการแจ้งซ่อมเรียบร้อย'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def manage_warranty(request, pk):
    """จัดการประกันสินค้า"""
    if request.user.user_type != 'service':
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่มีสิทธิ์ดำเนินการ'
        }, status=403)

    service_request = get_object_or_404(ServiceRequest, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        warranty_date = request.POST.get('warranty_date')
        
        try:
            if action == 'set_warranty':
                # แปลงวันที่จาก string เป็น date object
                start_date = datetime.strptime(warranty_date, '%Y-%m-%d').date() if warranty_date else None
                
                # อัพเดทข้อมูลประกันของลูกค้า
                customer = service_request.customer
                customer.warranty_status = 'ACTIVE'
                customer.warranty_expiry_date = start_date + timedelta(days=365) if start_date else None
                customer.save()
                
                # อัพเดทข้อมูลประกันของ service request
                service_request.set_warranty(start_date)
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'ตั้งค่าประกันเรียบร้อยแล้ว',
                    'warranty_start': service_request.warranty_start_date.strftime('%d/%m/%Y'),
                    'warranty_end': service_request.warranty_end_date.strftime('%d/%m/%Y')
                })
            
            elif action == 'remove_warranty':
                # อัพเดทข้อมูลประกันของลูกค้า
                customer = service_request.customer
                customer.warranty_status = 'NONE'
                customer.warranty_expiry_date = None
                customer.save()
                
                # อัพเดทข้อมูลประกันของ service request
                service_request.warranty_status = 'out_of_warranty'
                service_request.warranty_start_date = None
                service_request.warranty_end_date = None
                service_request.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'ยกเลิกประกันเรียบร้อยแล้ว'
                })
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
            
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed'
    }, status=405)

# ลบรูปภาพงาน
@login_required
def delete_service_image(request, image_id):
    if request.method == 'POST':
        try:
            image = ServiceImage.objects.get(id=image_id)
            
            # ตรวจสอบสิทธิ์
            if request.user.user_type != 'technician' and request.user.user_type != 'service':
                return JsonResponse({
                    'status': 'error',
                    'message': 'ไม่มีสิทธิ์ลบรูปภาพนี้'
                }, status=403)
            
            # ลบไฟล์รูปภาพ
            if image.image:
                if os.path.isfile(image.image.path):
                    os.remove(image.image.path)
            
            # ลบข้อมูลในฐานข้อมูล
            image.delete()
            
            return JsonResponse({'status': 'success'})
            
        except ServiceImage.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'ไม่พบรูปภาพ'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed'
    }, status=405)

# สร้างใบกำกับภาษี
@login_required
def generate_bill(request, service_id):
    if request.user.user_type != 'service':
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        
    service_request = get_object_or_404(ServiceRequest, id=service_id)
    bill_data = {
        'customer_name': service_request.customer.customer_name,
        'project_name': service_request.customer.project_name,
        'service_date': service_request.created_at,
        'service_details': service_request.description,
        'amount': service_request.technician_response.estimated_cost if hasattr(service_request, 'technician_response') else 0,
    }
    
    return JsonResponse({
        'status': 'success',
        'bill_data': bill_data
    })

# ตรวจสอบสิทธิ์การเข้าถึงข้อมูล
class StaffRequired(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.user_type in ['service', 'technician']

# ดูรายการงานของฝ่ายบริการ
class ServiceRequestManageView(LoginRequiredMixin, StaffRequired, ListView):
    model = ServiceRequest
    template_name = 'service/service_request_manage.html'
    context_object_name = 'service_requests'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # เพิ่ม status_colors dictionary
        context['status_colors'] = {
            'assigned': 'warning',
            'accepted': 'info',
            'traveling': 'primary',
            'arrived': 'purple',
            'fixing': 'orange',
            'completed_cash': 'success',
            'completed_call': 'success',
            'cancelled': 'danger',
            'rescheduled': 'secondary'
        }
        return context

    def get_queryset(self):
        queryset = ServiceRequest.objects.select_related('customer', 'technician')
        if self.request.user.user_type == 'technician':
            # ช่างจะเห็นเฉพาะงานที่ได้รับมอบหมาย
            return queryset.filter(technician=self.request.user)
        # ฝ่ายบริการเห็นทุกงาน
        return queryset.all()

# ส่งออกข้อมูลงาน excel สำหรับฝ่ายบริการ
@login_required
def export_service_requests(request):
    """ส่งออกข้อมูลการแจ้งซ่อมเป็นไฟล์ Excel"""
    if request.user.user_type not in ['service', 'technician']:
        return HttpResponseForbidden("ไม่มีสิทธิ์เข้าถึง")

    # สร้าง Workbook ใหม่
    wb = Workbook()
    ws = wb.active
    ws.title = "Service Requests"

    # กำหนดหัวคอลัมน์
    headers = [
        'เลขที่คำขอ',
        'วันที่แจ้ง',
        'วันที่นัดหมาย',
        'เวลานัดหมาย',
        'ลูกค้า',
        'โครงการ',
        'บ้านเลขที่',
        'เบอร์โทร',
        'ประเภทงาน',
        'รายละเอียด',
        'ช่างผู้รับผิดชอบ',
        'สถานะ',
        'สถานะประกัน',
        'ค่าใช้จ่าย',
        'หมายเหตุค่าใช้จ่าย'
    ]
    ws.append(headers)

    # ดึงข้อมูลตามสิทธิ์การเข้าถึง
    if request.user.user_type == 'technician':
        queryset = ServiceRequest.objects.filter(technician=request.user).order_by('id')
    else:
        queryset = ServiceRequest.objects.all().order_by('id')

    # เพิ่มข้อมูลลงในไฟล์ Excel
    for service_request in queryset.select_related('customer', 'technician'):
        row = [
            service_request.id,
            service_request.created_at.strftime('%d/%m/%Y'),
            service_request.appointment_date.strftime('%d/%m/%Y') if service_request.appointment_date else '',
            service_request.appointment_time.strftime('%H:%M') if service_request.appointment_time else '',
            service_request.customer.customer_name,
            service_request.customer.project_name,
            service_request.customer.house_number,
            service_request.customer.phone,
            service_request.get_request_type_display(),
            service_request.description,
            service_request.technician.customer.customer_name if service_request.technician else '',
            service_request.get_status_display(),
            service_request.get_warranty_status_display(),
            str(service_request.estimated_cost) if service_request.estimated_cost else '0',
            service_request.cost_note or ''
        ]
        ws.append(row)

    # ปรับความกว้างคอลัมน์อัตโนมัติ
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column_letter].width = adjusted_width

    # สร้าง response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=service_requests.xlsx'

    # บันทึกไฟล์
    wb.save(response)
    return response


# อัพเดทสถานะงานของฝ่ายบริการ
class UpdateServiceStatusView(LoginRequiredMixin, StaffRequired, UpdateView):
    model = ServiceRequest
    template_name = 'service/update_service_status.html'
    fields = ['status', 'technician']
    success_url = reverse_lazy('service:manage_requests')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # เลือกตัวเลือกสถานะตามประเภทผู้ใช้
        if self.request.user.user_type == 'technician':
            # ช่างจะเห็นเฉพาะสถานะที่กำหนดใน TechnicianJobStatus
            form.fields['status'].choices = TechnicianJobStatus.TECHNICIAN_STATUS_CHOICES
        else:
            # ฝ่ายบริการจะเห็นสถานะทั้งหมดจาก ServiceRequest
            form.fields['status'].choices = ServiceRequest.STATUS_CHOICES
        
        return form

    def form_valid(self, form):
        new_status = form.cleaned_data['status']
        
        # ตรวจสอบสถานะตามประเภทผู้ใช้
        if self.request.user.user_type == 'technician':
            valid_statuses = dict(TechnicianJobStatus.TECHNICIAN_STATUS_CHOICES)
            if new_status not in valid_statuses:
                messages.error(self.request, 'สถานะที่เลือกไม่ถูกต้องสำหรับช่าง')
                return self.form_invalid(form)
        else:
            valid_statuses = dict(ServiceRequest.STATUS_CHOICES)
            if new_status not in valid_statuses:
                messages.error(self.request, 'สถานะที่เลือกไม่ถูกต้อง')
                return self.form_invalid(form)

        response = super().form_valid(form)
        
        # บันทึกประวัติการอัพเดทสถานะ
        TechnicianJobStatus.objects.create(
            service_request=self.object,
            technician=self.request.user,
            status=new_status,
            notes=self.request.POST.get('notes', '')
        )
        
        messages.success(self.request, 'อัพเดทสถานะเรียบร้อยแล้ว')
        return response

class CustomerMapView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'service/customer_map.html'
    
    def test_func(self):
        return self.request.user.user_type in ['service', 'technician']
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ดึงข้อมูลลูกค้าที่มีพิกัด
        customers = Customer.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('user')
        
        # สร้าง markers สำหรับแสดงบนแผนที่
        markers = []
        for customer in customers:
            markers.append({
                'lat': float(customer.latitude),
                'lng': float(customer.longitude),
                'name': customer.customer_name,
                'project': customer.project_name,
                'house_number': customer.house_number,
                'location': customer.location,
                'phone': customer.phone
            })
            
        context['markers'] = markers
        return context
@require_POST
def upload_excel(request):
    try:
        excel_file = request.FILES['excel_file']
        df = pd.read_excel(excel_file)
        # สร้าง default user สำหรับ customer ถ้ายังไม่มี
        default_user, created = User.objects.get_or_create(
            username='default_customer',
            defaults={
                'email': 'default@example.com',
                'first_name': 'Default',
                'last_name': 'Customer',
                'is_active': False
            }
        )
        if created:
            default_user.set_password('some-very-secure-password')
            default_user.save()

        success_count = 0
        error_records = []
        duplicate_records = []
        
        for index, row in df.iterrows():
            try:
                # แปลงวันที่
                try:
                    date_str = str(row['วดป.'])
                    date_obj = pd.to_datetime(date_str).date()
                except:
                    date_obj = None
                    print(f"Error parsing date: {date_str}")

                # แปลงเวลา
                try:
                    time_str = str(row['เวลา'])
                    if 'น.' in time_str:
                        time_str = time_str.replace(' น.', '')
                    if '.' in time_str:
                        hour, minute = time_str.split('.')
                        time_str = f"{hour.zfill(2)}:{minute.zfill(2)}"
                    time_obj = datetime.strptime(time_str, '%H:%M').time()
                except:
                    time_obj = None
                    print(f"Error parsing time: {row['เวลา']}")

                # สร้างหรือดึงข้อมูลลูกค้า
                customer_name = str(row['ชื่อลูกบ้าน'])[:100]
                phone = str(row['เบอร์ติดต่อ'])[:15] if pd.notna(row['เบอร์ติดต่อ']) else ''
                
                customer, created = Customer.objects.get_or_create(
                    customer_name=customer_name,
                    defaults={
                        'phone': phone,
                        'user': default_user,
                        'project_name': str(row['โครงการ'])[:100] if pd.notna(row['โครงการ']) else '',
                        'house_number': str(row['บ้านเลขที่'])[:50] if pd.notna(row['บ้านเลขที่']) else ''
                    }
                )

                # ตรวจสอบว่ามีข้อมูลอยู่แล้วหรือไม่
                job_number = str(row['เลขงาน'])[:50] if pd.notna(row['เลขงาน']) else ''
                existing_record = ServiceRecord.objects.filter(
                    job_number=job_number,
                    customer=customer,
                    date=date_obj
                ).exists()

                if existing_record:
                    duplicate_records.append({
                        'row': index + 2,
                        'job_number': job_number,
                        'customer': customer_name,
                        'date': date_obj
                    })
                    continue

                # สร้าง ServiceRecord
                service_record = ServiceRecord.objects.create(
                    sequence=int(row['ลำดับ']) if pd.notna(row['ลำดับ']) else 0,
                    completion_status=True if str(row['สถานะจบงาน']).lower() == 'เสร็จ' else False,
                    year=str(row['ปี พ.ศ.'])[:4] if pd.notna(row['ปี พ.ศ.']) else '',
                    date=date_obj,
                    month=int(row['ด.']) if pd.notna(row['ด.']) else None,
                    time=time_obj,
                    job_number=job_number,
                    bill_number=str(row['เลขที่บิล'])[:50] if pd.notna(row['เลขที่บิล']) else '',
                    customer=customer,
                    technician_name=str(row['จนท.'])[:100] if pd.notna(row['จนท.']) else '',
                    technician_phone=str(row['เบอร์ติดต่อ จนท.'])[:15] if pd.notna(row['เบอร์ติดต่อ จนท.']) else '',
                    project_code=str(row['รหัสโครงการ'])[:50] if pd.notna(row['รหัสโครงการ']) else '',
                    project_name=str(row['โครงการ'])[:100] if pd.notna(row['โครงการ']) else '',
                    house_number=str(row['บ้านเลขที่'])[:50] if pd.notna(row['บ้านเลขที่']) else '',
                    description=str(row['อาการรับแจ้ง']) if pd.notna(row['อาการรับแจ้ง']) else '',
                    status=str(row['สถานะ'])[:50] if pd.notna(row['สถานะ']) else '',
                    equipment_status=str(row['วัสดุ/อุปกรณ์ที่ผิดปกติ']) if pd.notna(row['วัสดุ/อุปกรณ์ที่ผิดปกติ']) else '',
                    cause_found=str(row['สาเหตุที่ตรวจพบ']) if pd.notna(row['สาเหตุที่ตรวจพบ']) else '',
                    solution=str(row['การแก้ไข']) if pd.notna(row['การแก้ไข']) else '',
                    notes=str(row['หมายเหตุ']) if pd.notna(row['หมายเหตุ']) else ''
                )
                
                success_count += 1
                print(f"Created record: {service_record}")

            except Exception as e:
                error_records.append({
                    'row': index + 2,
                    'error': str(e)
                })
                print(f"Error on row {index + 2}: {str(e)}")

        response_data = {
            'status': 'success',
            'message': f'นำเข้าข้อมูลสำเร็จ {success_count} รายการ',
            'errors': error_records if error_records else None,
        }

        if duplicate_records:
            response_data['duplicates'] = duplicate_records
            response_data['message'] += f'\nพบข้อมูลซ้ำ {len(duplicate_records)} รายการ'

        return JsonResponse(response_data)

    except Exception as e:
        print(f"Upload error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาด: {str(e)}'
        }, status=400)

def download_template(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Template"
    
    # กำหนดหัวคอลัมน์
    headers = [
        'ลำดับ', 'สถานะจบงาน', 'ปี พ.ศ.', 'วดป.', 'ด.', 'เวลา', 
        'เลขงาน', 'เลขที่บิล', 'ชื่อลูกบ้าน', 'เบอร์ติดต่อ', 'จนท.', 
        'เบอร์ติดต่อ จนท.', 'รหัสโครงการ', 'โครงการ', 'บ้านเลขที่', 
        'แปลง', 'แบบ', 'โอน', 'วันที่หมดประกัน', 'อาการรับแจ้ง', 
        'สถานะ', 'วันนัด', 'เวลานัด', 'วัสดุ/อุปกรณ์ที่ผิดปกติ', 
        'สาเหตุที่ตรวจพบ', 'การแก้ไข', 'ชื่อ', 'หมายเหตุ', 'จำนวน', 
        'Link รูปภาพที่ออกSERVICE', 'หมายเหตุเพิ่มเติม'
    ]
    ws.append(headers)
    
    # ตัวอย่างข้อมูล
    sample_data = [
        1, 'เสร็จ', '2566', '2566-01-01', 1, '09:00',
        'AF66-0001', 'BILL001', 'คุณลูกค้า', '0812345678', 'ช่างA',
        '0898765432', 'CSN', 'โครงการA', '123/45', 
        'A-01', 'Type-A', '2565-01-01', '2567-01-01', 'เครื่องปรับอากาศไม่เย็น',
        'รอดำเนินการ', '2566-01-02', '10:00', 'คอยล์เย็นสกปรก',
        'ฝุ่นอุดตัน', 'ล้างทำความสะอาด', 'ช่างA,ช่างB', 'งานเสร็จเรียบร้อย', 1500,
        'http://example.com/image1.jpg', 'ลูกค้าพอใจมาก'
    ]
    ws.append(sample_data)

    # ปรับความกว้างคอลัมน์
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width

    # สร้าง response
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=service_record_template.xlsx'
    return response

# เพิ่มเมธอดใหม่สำหรับจัดการการคำนวณราคา
def calculate_service_fee(request, service_id):
    if request.user.user_type != 'service':
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    service_request = get_object_or_404(ServiceRequest, id=service_id)
    
    try:
        # เรียกใช้เมธอด calculate_service_fee จาก model
        fee = service_request.calculate_service_fee()
        
        return JsonResponse({
            'status': 'success',
            'fee': str(fee)
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

# แก้ไขเมธอด set_service_cost เดิม
@login_required
@require_POST
def set_service_cost(request, request_id):
    if request.user.user_type != 'service':
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่มีสิทธิ์ดำเนินการ'
        }, status=403)

    try:
        service_request = ServiceRequest.objects.get(id=request_id)
        
        # ตรวจสอบสถานะประกันก่อนกำหนดค่าใช้จ่าย
        service_request.check_warranty_status()
        
        if service_request.warranty_status == 'in_warranty':
            estimated_cost = Decimal('0.00')
            cost_note = 'งานอยู่ในประกัน'
        else:
            estimated_cost = Decimal(request.POST.get('estimated_cost', '0'))
            cost_note = request.POST.get('cost_note', '')

        if estimated_cost < 0:
            raise ValueError('ค่าใช้จ่ายต้องไม่ติดลบ')

        service_request.estimated_cost = estimated_cost
        service_request.cost_note = cost_note
        service_request.cost_updated_by = request.user
        service_request.cost_updated_at = timezone.now()
        service_request.save()

        return JsonResponse({
            'status': 'success',
            'message': 'บันทึกค่าใช้จ่ายเรียบร้อย',
            'estimated_cost': str(estimated_cost),
            'warranty_status': service_request.warranty_status
        })

    except (ServiceRequest.DoesNotExist, ValueError) as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)