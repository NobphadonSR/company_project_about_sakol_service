# Library ที่เรียกใช้ทั้งหมด
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, TemplateView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Sum
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
        technician_id = request.POST.get('technician')  # ใช้ชื่อ field จากฟอร์ม
        
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
        return super().form_valid(form)

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
            ).order_by('-uploaded_at')  # เปลี่ยนจาก created_at เป็น uploaded_at
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
        ).order_by('created_at')  # ยังคงใช้ order_by created_at

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
class ServiceRecordListView(LoginRequiredMixin, ServiceStaffRequired, ListView):
    model = ServiceRecord
    template_name = 'service/record_list.html'
    context_object_name = 'records'

# สร้างบันทึกงาน
class ServiceRecordCreateView(LoginRequiredMixin, ServiceStaffRequired, CreateView):
    model = ServiceRecord
    form_class = ServiceRecordForm
    template_name = 'service/record_form.html'
    success_url = reverse_lazy('service:service_records')

# แก้ไขบันทึกงาน
class ServiceRecordUpdateView(LoginRequiredMixin, ServiceStaffRequired, UpdateView):
    model = ServiceRecord
    form_class = ServiceRecordForm
    template_name = 'service/record_form.html'
    success_url = reverse_lazy('service:service_records')

# ลบบันทึกงาน
class ServiceRecordDeleteView(LoginRequiredMixin, ServiceStaffRequired, DeleteView):
    model = ServiceRecord
    template_name = 'service/record_confirm_delete.html'
    success_url = reverse_lazy('service:service_records')

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
            'is_service': self.request.user.user_type == 'service',  # เพิ่มตัวแปรสำหรับเช็คว่าเป็นฝ่ายบริการ
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
            service_request.status = 'pending_confirmation'
            service_request.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'ส่งคำแนะนำเรียบร้อยแล้ว'
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
    if not request.user.is_authenticated or request.user.user_type != 'technician':
        messages.error(request, 'ไม่มีสิทธิ์เข้าถึงหน้านี้')
        return redirect('service:request_list')

    if service_request.technician != request.user:
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
            service_request.status = 'accepted'
            service_request.save()
            
            TechnicianJobStatus.objects.create(
                service_request=service_request,
                technician=service_request.technician,
                status='accepted',
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
    if request.method == 'POST' and request.user.user_type == 'technician':
        service_request = get_object_or_404(ServiceRequest, id=service_id)
        status = TechnicianJobStatus.objects.create(
            service_request=service_request,
            technician=request.user,
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
                        'confirmed': ['confirmed'],
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
                service_request.set_warranty(start_date)
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'ตั้งค่าประกันเรียบร้อยแล้ว',
                    'warranty_start': service_request.warranty_start_date.strftime('%d/%m/%Y'),
                    'warranty_end': service_request.warranty_end_date.strftime('%d/%m/%Y')
                })
            
            elif action == 'remove_warranty':
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