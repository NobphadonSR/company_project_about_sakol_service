from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Customer

class CustomerRegistrationForm(UserCreationForm):
    project_name = forms.CharField(max_length=100, label="ชื่อโครงการ")
    house_number = forms.CharField(max_length=50, label="บ้านเลขที่")
    phone = forms.CharField(max_length=15, label="เบอร์โทร")
    customer_name = forms.CharField(max_length=100, label="ชื่อลูกค้า")
    location = forms.CharField(widget=forms.Textarea, label="ที่อยู่")

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'customer'
        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                project_name=self.cleaned_data['project_name'],
                house_number=self.cleaned_data['house_number'],
                phone=self.cleaned_data['phone'],
                customer_name=self.cleaned_data['customer_name'],
                location=self.cleaned_data['location']
            )
        return user
    
from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['customer_name', 'project_name', 'house_number', 'phone', 'location']
        widgets = {
            'location': forms.Textarea(attrs={'rows': 3}),
        }