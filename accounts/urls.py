from django.urls import path
from . import views

app_name = 'accounts'
urlpatterns = [
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('customer/list/', views.CustomerListView.as_view(), name='customer_list'),
    path('customer/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customer/update/<int:pk>/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('customer/delete/<int:pk>/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    path('customer/map/', views.CustomerMapView.as_view(), name='customer_map'),
]