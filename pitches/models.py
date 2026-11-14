from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

class Pitch(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    map_link = models.URLField(blank=True, null=True, help_text="رابط موقع الخريطة")
    image1 = models.ImageField(upload_to='pitches/', blank=True, null=True)
    image2 = models.ImageField(upload_to='pitches/', blank=True, null=True)
    price_per_hour = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return self.name

class Reservation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'معلق (بانتظار تأكيد الدفع)'),
        ('confirmed', 'مؤكد'),
        ('cancelled', 'ملغي'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    date = models.DateField()
    time_slot = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    is_cancelled = models.BooleanField(default=False)

    def __str__(self):
        return f"حجز {self.customer_name} في ملعب {self.pitch.name} ({self.get_status_display()})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return f"بروفايل {self.user.username}"

# جدول الماتشات المفتوحة (Kickoffs) للانضمام الفردي
class OpenMatch(models.Model):
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE)
    date = models.DateField()
    time_slot = models.CharField(max_length=50)
    max_players = models.IntegerField(default=10) 
    players = models.ManyToManyField(User, related_name='joined_open_matches', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ماتش مفتوح في {self.pitch.name} بتاريخ {self.date}"

# جدول طلبات انضمام اللاعبين للماتش المفتوح (بانتظار موافقة الأدمن ودفع العربون 50 جنيه)
class OpenMatchRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'معلق (بانتظار تأكيد الأدمن والدربون)'),
        ('approved', 'مؤكد ومنضم'),
        ('rejected', 'مرفوض'),
    )

    open_match = models.ForeignKey(OpenMatch, on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"طلب انضمام {self.user.username} للماتش #{self.open_match.id} ({self.get_status_display()})"


# إشارات (Signals) لإنشاء وتحديث بروفايل المستخدم أوتوماتيكياً مع كل يوزر جديد
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)

# إشارات (Signals) لربط الماتش المفتوح بحجز مؤكد تلقائياً لمنع ازدواجية الحجز
@receiver(post_save, sender=OpenMatch)
def create_reservation_for_open_match(sender, instance, created, **kwargs):
    Reservation.objects.update_or_create(
        pitch=instance.pitch,
        date=instance.date,
        time_slot=instance.time_slot,
        defaults={
            'customer_name': 'ماتش مفتوح (إدارة)',
            'phone': '00000000000',
            'status': 'confirmed',
            'is_cancelled': False,
        }
    )

@receiver(post_delete, sender=OpenMatch)
def delete_reservation_for_open_match(sender, instance, **kwargs):
    Reservation.objects.filter(
        pitch=instance.pitch,
        date=instance.date,
        time_slot=instance.time_slot,
        customer_name='ماتش مفتوح (إدارة)'
    ).delete()