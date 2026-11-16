import re
from django import forms
from django.contrib.auth.models import User


class CustomUserCreationForm(forms.Form):
    # الاسم: حر تماماً (مسافات وتكرار مسموح)، بيتحفظ في first_name
    username = forms.CharField(
        label="الاسم",
        max_length=150,
    )

    # رقم الهاتف: هو اللي بيتسجل بيه الدخول (بيتحفظ كـ username داخلي)
    phone = forms.CharField(
        label="رقم الهاتف",
        widget=forms.TextInput(attrs={'inputmode': 'numeric'}),
    )

    password1 = forms.CharField(
        label="كلمة المرور",
        widget=forms.PasswordInput(attrs={'id': 'password-input'}),
        help_text="يجب أن تكون مكونة من 8 أرقام على الأقل.",
    )

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not re.fullmatch(r'01\d{9}', phone, re.ASCII):
            raise forms.ValidationError(
                "اكتب رقم الهاتف بالأرقام الإنجليزية، 11 رقم يبدأ بـ 01 (مثال: 01012345678)."
            )
        if User.objects.filter(username=phone).exists():
            raise forms.ValidationError("هذا الرقم مسجل بالفعل، سجّل الدخول بدل إنشاء حساب جديد.")
        return phone

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if not password or not password.isdigit() or len(password) < 8:
            raise forms.ValidationError("يجب أن تتكون كلمة المرور من 8 أرقام على الأقل (أرقام فقط).")
        return password

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data['phone'],
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data['username'],
        )
