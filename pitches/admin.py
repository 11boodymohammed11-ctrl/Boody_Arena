from django.contrib import admin
from django import forms
from django.utils.html import format_html
from .models import Pitch, Reservation, OpenMatch, UserProfile, OpenMatchRequest
import urllib.parse

admin.site.register(Pitch)
admin.site.register(UserProfile)

TIME_SLOT_CHOICES = (
    ("من 7 لـ 8 مساءً", "من 7 لـ 8 مساءً"),
    ("من 8 لـ 9 مساءً", "من 8 لـ 9 مساءً"),
    ("من 9 لـ 10 مساءً", "من 9 لـ 10 مساءً"),
    ("من 10 لـ 11 مساءً", "من 10 لـ 11 مساءً"),
    ("من 11 لـ 12 صباحاً", "من 11 لـ 12 صباحاً"),
    ("من 12 لـ 1 صباحاً", "من 12 لـ 1 صباحاً"),
    ("من 1 إلى 2 صباحاً", "من 1 إلى 2 صباحاً"),
    ("من 2 إلى 3 صباحاً", "من 2 إلى 3 صباحاً"),
)

class OpenMatchAdminForm(forms.ModelForm):
    time_slot = forms.ChoiceField(choices=TIME_SLOT_CHOICES, label="الميعاد (Time Slot)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        instance = kwargs.get('instance')
        pitch = None
        date_val = None

        if instance and instance.pk:
            pitch = instance.pitch
            date_val = instance.date
        elif self.data:
            pitch_id = self.data.get('pitch')
            date_val = self.data.get('date')
            if pitch_id:
                pitch = Pitch.objects.filter(pk=pitch_id).first()

        if pitch and date_val:
            # 1. المواعيد المحجوزة في جدول Reservations (غير الملغاة)
            booked_slots = list(Reservation.objects.filter(
                pitch=pitch, 
                date=date_val, 
                is_cancelled=False
            ).values_list('time_slot', flat=True))

            # 2. المواعيد اللي معمول ليها OpenMatch بالفعل لنفس الملعب والتاريخ
            open_match_slots = list(OpenMatch.objects.filter(
                pitch=pitch,
                date=date_val
            ).exclude(pk=instance.pk if instance else None).values_list('time_slot', flat=True))

            # دمج القائمتين (الحجوزات + الماتشات المفتوحة)
            all_taken_slots = set(booked_slots + open_match_slots)

            # لو بنعدل الماتش الحالي، نسيب ميعاده ظاهر عادي
            if instance and instance.pk:
                if instance.time_slot in all_taken_slots:
                    # لو ميعاده الحالي محجوز في لستتنا، بنشيله عشان يظهر في القائمة
                    pass

            # تصفية المواعيد: نعرض فقط المواعيد اللي مش محجوزة ومش معمول لها ماتش مفتوح
            filtered_choices = [slot for slot in TIME_SLOT_CHOICES if slot[0] not in all_taken_slots]
            
            # لو بنعدل الماتش الحالي، نتأكد إن ميعاده الحالي موجود في القائمة حتى لو كان محجوز بنفسه
            if instance and instance.pk and instance.time_slot not in [c[0] for c in filtered_choices]:
                for slot in TIME_SLOT_CHOICES:
                    if slot[0] == instance.time_slot:
                        filtered_choices.append(slot)
                        break

            self.fields['time_slot'].choices = filtered_choices
        else:
            self.fields['time_slot'].choices = TIME_SLOT_CHOICES

    class Meta:
        model = OpenMatch
        fields = '__all__'

@admin.register(OpenMatch)
class OpenMatchAdmin(admin.ModelAdmin):
    form = OpenMatchAdminForm
    list_display = ('id', 'pitch', 'date', 'time_slot', 'max_players')
    list_filter = ('pitch', 'date')

@admin.register(OpenMatchRequest)
class OpenMatchRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'open_match', 'user', 'status', 'created_at', 'whatsapp_player_link')
    list_filter = ('status', 'created_at', 'open_match')
    search_fields = ('user__username', 'user__email')
    
    def save_model(self, request, obj, form, change):
        if change:
            old_obj = OpenMatchRequest.objects.get(pk=obj.pk)
            if old_obj.status != 'approved' and obj.status == 'approved':
                obj.open_match.players.add(obj.user)
            elif old_obj.status == 'approved' and obj.status != 'approved':
                obj.open_match.players.remove(obj.user)
        super().save_model(request, obj, form, change)

    def whatsapp_player_link(self, obj):
        user_profile = UserProfile.objects.filter(user=obj.user).first()
        phone = getattr(user_profile, 'phone', None) if user_profile else None
        
        if phone:
            phone = phone.strip()
            if phone.startswith('0'):
                phone = '20' + phone[1:]
            
            message = (
                f"=== [ متابعة عربون الماتش المفتوح ] ===\n\n"
                f"مرحباً {obj.user.username},\n"
                f"بخصوص طلب انضمامك للماتش المفتوح، نرجو إرسال إيصال تحويل العربون (50 جنيه) لتأكيد انضمامك.\n\n"
                f"شكراً لك!"
            )
            url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
            
            return format_html(
                '<a href="{}" target="_blank" style="background: #25d366; color: white; padding: 6px 12px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 12px;">متابعة العربون واتساب</a>',
                url
            )
        return '<span style="color: #6c757d; font-size: 11px;">رقم الهاتف غير متوفر</span>'
        
    whatsapp_player_link.short_description = "إجراءات العربون"


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'pitch', 'customer_name', 'phone', 'date', 'time_slot', 'status', 'is_cancelled')
    list_filter = ('status', 'date', 'pitch', 'is_cancelled')
    search_fields = ('customer_name', 'phone')
    
    readonly_fields = ('whatsapp_confirm_link',)

    def whatsapp_confirm_link(self, obj):
        if obj.phone:
            phone = obj.phone.strip()
            if phone.startswith('0'):
                phone = '20' + phone[1:]
            
            message = (
                f"=== [ تأكيد الحجز ] ===\n\n"
                f"مرحباً {obj.customer_name},\n"
                f"تم تأكيد حجزك في ملعب {obj.pitch.name} "
                f"بتاريخ {obj.date} في ميعاد ({obj.time_slot}).\n\n"
                f"نتمنى لك وقتاً ممتعاً!"
            )
            url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
            
            return format_html(
                '<a href="{}" target="_blank" style="background: #25d366; color: white; padding: 10px 15px; border-radius: 5px; text-decoration: none; font-weight: bold;">إرسال رسالة تأكيد للعميل عبر الواتساب</a>',
                url
            )
        return "رقم الهاتف غير متوفر"
    
    whatsapp_confirm_link.short_description = "تأكيد الحجز عبر الواتساب"