from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .forms import CustomerRegistrationForm
from service.models import ServiceRequest
from .models import Customer
from .forms import CustomerForm
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.urls import reverse_lazy
from .models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import TemplateView
from decimal import Decimal, InvalidOperation

def register(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CustomerRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profile(request):
    context = {
        'user': request.user
    }
    
    if request.user.user_type == 'service':
        context['service_requests'] = ServiceRequest.objects.all().order_by('-created_at')
    
    return render(request, 'accounts/profile.html', context)

@login_required
def edit_profile(request):
    if request.method == 'POST':
        # อัพเดทข้อมูลพื้นฐาน
        user = request.user
        user.email = request.POST.get('email')
        user.phone = request.POST.get('phone')
        
        if user.user_type == 'technician':
            technician = user.customer
            technician.customer_name = request.POST.get('customer_name')
            technician.address = request.POST.get('address','')
            technician.save()
        user.save()
        
        # อัพเดทข้อมูลลูกค้า (ถ้าเป็นลูกค้า)
        if user.user_type == 'customer':
            customer = user.customer
            customer.customer_name = request.POST.get('customer_name')
            customer.project_name = request.POST.get('project_name')
            customer.house_number = request.POST.get('house_number')
            customer.phone = request.POST.get('phone')
            customer.location = request.POST.get('location')
            customer.save()
        
        messages.success(request, 'อัพเดทข้อมูลเรียบร้อยแล้ว')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/edit_profile.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
    return render(request, 'accounts/login.html')

@login_required
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('login')
    return redirect('home')

class ServiceStaffRequired(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.user_type == 'service'

class CustomerListView(LoginRequiredMixin, ServiceStaffRequired, ListView):
    model = Customer
    template_name = 'accounts/customer_list.html'
    context_object_name = 'customers'

class CustomerCreateView(LoginRequiredMixin, ServiceStaffRequired, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'accounts/customer_form.html'
    success_url = reverse_lazy('accounts:customer_list')

    def form_valid(self, form):
        # สร้าง User account สำหรับลูกค้า
        user = User.objects.create_user(
            username=form.cleaned_data['phone'],  # ใช้เบอร์โทรเป็น username
            password=form.cleaned_data['phone'],  # ใช้เบอร์โทรเป็นรหัสผ่านเริ่มต้น
            user_type='customer'
        )
        form.instance.user = user
        return super().form_valid(form)

class CustomerUpdateView(LoginRequiredMixin, ServiceStaffRequired, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'accounts/customer_form.html'
    success_url = reverse_lazy('accounts:customer_list')

class CustomerDeleteView(LoginRequiredMixin, ServiceStaffRequired, DeleteView):
    model = Customer
    template_name = 'accounts/customer_confirm_delete.html'
    success_url = reverse_lazy('accounts:customer_list')

class CustomerMapView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/customer_map_form.html'
    
    def post(self, request, *args, **kwargs):
        if request.user.user_type == 'customer':
            try:
                customer = request.user.customer
                
                # รับค่าและตรวจสอบความถูกต้อง
                lat = request.POST.get('latitude', '').strip()
                lng = request.POST.get('longitude', '').strip()
                location = request.POST.get('location', '').strip()
                
                # ตรวจสอบว่ามีค่าพิกัดหรือไม่
                if lat and lng:
                    try:
                        # เก็บค่าเดิมไว้เพื่อเช็คการเปลี่ยนแปลง
                        lat = customer.latitude
                        lng = customer.longitude
                        location = customer.location

                        # แปลงค่าเป็น Decimal
                        customer.latitude = Decimal(lat)
                        customer.longitude = Decimal(lng)
                        customer.location = location
                        
                        # บันทึกข้อมูล
                        customer.save()
                        
                        return JsonResponse({
                            'status': 'success',
                            'message': 'บันทึกที่อยู่เรียบร้อยแล้ว',
                            'updates_count': customer.location_updates_count
                        })
                    except (ValueError, InvalidOperation, TypeError) as e:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'รูปแบบพิกัดไม่ถูกต้อง: {str(e)}'
                        }, status=400)
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'กรุณาระบุพิกัด'
                    }, status=400)
                    
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f'เกิดข้อผิดพลาด: {str(e)}'
                }, status=500)
                
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่มีสิทธิ์ในการบันทึกข้อมูล'
        }, status=403)