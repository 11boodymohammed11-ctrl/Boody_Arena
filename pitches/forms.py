from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    phone = forms.CharField(required=True, label="رقم الهاتف")
    
    # استبدال خانة الباسورد الافتراضية المزدوجة بخانة واحدة فقط
    password1 = forms.CharField(
        label="كلمة المرور",
        widget=forms.PasswordInput(attrs={'id': 'password-input'}),
        help_text="يجب أن تكون مكونة من 8 أرقام."
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # إزالة حقل تأكيد كلمة المرور الافتراضي نهائياً من الفورم
        if 'password2' in self.fields:
            del self.fields['password2']

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if not password or not password.isdigit() or len(password) != 8:
            raise forms.ValidationError("يجب أن تتكون كلمة المرور من 8 أرقام فقط.")
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user