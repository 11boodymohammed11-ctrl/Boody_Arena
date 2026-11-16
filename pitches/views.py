from datetime import date, datetime, timedelta
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Pitch, Reservation, UserProfile, OpenMatch, OpenMatchRequest
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm
import urllib.parse

def home(request):
    pitches = Pitch.objects.all()
    today = timezone.now().date()
    # عرض الماتشات المفتوحة التي تاريخها اليوم أو في المستقبل فقط
    open_matches = OpenMatch.objects.filter(date__gte=today).order_by('date')
    return render(request, 'pitches/home.html', {
        'pitches': pitches,
        'open_matches': open_matches
    })

def open_matches_view(request):
    today = timezone.now().date()
    # إخفاء الماتشات التي انتهى تاريخها من الموقع وتظهر للأدمن فقط في قاعدة البيانات
    open_matches = OpenMatch.objects.filter(date__gte=today).order_by('date')
    return render(request, 'pitches/open_matches.html', {'open_matches': open_matches})

def book_pitch(request, pitch_id):
    pitch = get_object_or_404(Pitch, pk=pitch_id)

    now = timezone.localtime()
    # "اليوم" بتاع الحجز بيفضل لحد 3 الفجر (عشان ميعاد 2-3 الفجر يفضل متاح)
    today = (now - timedelta(hours=3)).date()
    max_day = today + timedelta(days=2)  # النهاردة + بكرة + بعده

    # التاريخ المختار: لو غلط أو برة المدى يرجع للنهاردة
    try:
        selected = datetime.strptime(
            request.GET.get('date', str(today)), '%Y-%m-%d'
        ).date()
    except ValueError:
        selected = today
    if selected < today or selected > max_day:
        selected = today
    selected_date = str(selected)

    # (الاسم, ساعة البداية)
    time_slots = [
        ("من 7 لـ 8 مساءً", 19),
        ("من 8 لـ 9 مساءً", 20),
        ("من 9 لـ 10 مساءً", 21),
        ("من 10 لـ 11 مساءً", 22),
        ("من 11 لـ 12 صباحاً", 23),
        ("من 12 لـ 1 صباحاً", 24),
        ("من 1 إلى 2 صباحاً", 25),
        ("من 2 إلى 3 صباحاً", 26),
    ]

    def slot_start(hour):
        # الساعات 24 و25 و26 معناها بعد نص الليل = اليوم اللي بعده
        return timezone.make_aware(
            datetime.combine(selected, datetime.min.time())
        ) + timedelta(hours=hour)

    def is_past(hour):
        return slot_start(hour) <= now

    active_reservations = Reservation.objects.filter(
        pitch=pitch, date=selected_date, is_cancelled=False
    )
    slot_status_map = {res.time_slot: res.status for res in active_reservations}

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name')
        phone = request.POST.get('phone')
        time_slot = request.POST.get('time_slot')

        slot_hour = dict(time_slots).get(time_slot)

        if slot_hour is None:
            messages.error(request, "ميعاد غير صالح.")
        elif is_past(slot_hour):
            messages.error(request, "عذراً، هذا الميعاد فات بالفعل.")
        elif active_reservations.filter(time_slot=time_slot).exists():
            messages.error(request, "عذراً، هذا الميعاد محجوز أو قيد التأكيد من قبل شخص آخر.")
        else:
            reservation = Reservation.objects.create(
                pitch=pitch,
                customer_name=customer_name,
                phone=phone,
                date=selected_date,
                time_slot=time_slot,
                status='pending',
                user=request.user if request.user.is_authenticated else None
            )
            return redirect('reservation_success', reservation_id=reservation.id)

    schedule = []
    for slot, hour in time_slots:
        status = slot_status_map.get(slot, None)
        past = is_past(hour)
        schedule.append({
            'time_slot': slot,
            'is_booked': status is not None or past,
            'is_past': past,
            'status': status
        })

    context = {
        'pitch': pitch,
        'schedule': schedule,
        'selected_date': selected_date,
        'min_date': str(today),
        'max_date': str(max_day),
    }
    return render(request, 'pitches/book_pitch.html', context)

def reservation_success(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)

    whatsapp_message = (
        f"=== [ طلب حجز جديد ] ===\n\n"
        f"رقم الحجز: #{reservation.id}\n"
        f"الملعب: {reservation.pitch.name}\n"
        f"التاريخ: {reservation.date}\n"
        f"الميعاد: {reservation.time_slot}\n"
        f"اسم العميل: {reservation.customer_name}\n"
        f"رقم الهاتف: {reservation.phone}\n"
        f"الحالة: معلق (بانتظار تأكيد الدفع)\n\n"
    )

    admin_whatsapp_number = "201094281051"

    whatsapp_url = f"https://wa.me/{admin_whatsapp_number}?text={urllib.parse.quote(whatsapp_message)}"

    context = {
        'reservation': reservation,
        'whatsapp_url': whatsapp_url,
    }
    return render(request, 'pitches/reservation_success.html', context)

@login_required
def join_open_match(request, match_id):
    match = get_object_or_404(OpenMatch, id=match_id)

    # لو اللاعب منضم بالفعل، يمكنه إلغاء الانضمام وحذف طلبه
    if request.user in match.players.all():
        match.players.remove(request.user)
        OpenMatchRequest.objects.filter(open_match=match, user=request.user).delete()
        messages.success(request, "تم إلغاء انضمامك للماتش المفتوح.")
        return redirect('home')

    # تحقق هل يوجد طلب معلق بالفعل لنفس المستخدم لهذا الماتش
    existing_request = OpenMatchRequest.objects.filter(open_match=match, user=request.user).first()

    if existing_request:
        if existing_request.status == 'approved':
            messages.info(request, "أنت منضم بالفعل لهذا الماتش.")
            return redirect('home')
        elif existing_request.status == 'pending':
            # توجيه لصفحة دفع العربون الخاصة بالماتش المفتوح
            return redirect('open_match_success', request_id=existing_request.id)

    # لو مفيش مكان فاضي في الماتش
    if match.players.count() >= match.max_players:
        messages.error(request, "عذراً، اكتمل عدد اللاعبين في هذا الماتش.")
        return redirect('home')

    # إنشاء طلب انضمام جديد (بانتظار دفع العربون وتأكيد الأدمن)
    new_req = OpenMatchRequest.objects.create(
        open_match=match,
        user=request.user,
        status='pending'
    )

    # التوجيه لصفحة تفاصيل الدفع (المشابهة لشاشة حجز الملاعب)
    return redirect('open_match_success', request_id=new_req.id)

@login_required
def open_match_success(request, request_id):
    join_req = get_object_or_404(OpenMatchRequest, id=request_id, user=request.user)
    match = join_req.open_match

    # رسالة الواتساب المظبوطة
    whatsapp_message = (
        f"=== [ تأكيد عربون ماتش مفتوح ] ===\n\n"
        f"رقم الطلب: #{join_req.id}\n"
        f"رقم الماتش: #{match.id}\n"
        f"الملعب: {match.pitch.name}\n"
        f"التاريخ: {match.date}\n"
        f"الميعاد: {match.time_slot}\n"
        f"اسم اللاعب: {request.user.username}\n\n"
        f"أنا حولت عربون الـ 50 جنيه، وده إثبات التحويل برجاء تأكيد انضمامي للماتش."
    )

    admin_whatsapp_number = "201094281051"
    whatsapp_url = f"https://wa.me/{admin_whatsapp_number}?text={urllib.parse.quote(whatsapp_message)}"

    context = {
        'join_req': join_req,
        'match': match,
        'whatsapp_url': whatsapp_url,
    }
    return render(request, 'pitches/open_match_success.html', context)

@login_required(login_url='login')
def customer_profile(request):
    reservations = Reservation.objects.filter(user=request.user).order_by('-id')
    return render(request, 'pitches/customer_profile.html', {'reservations': reservations})

@login_required
def edit_profile(request):
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)

    password_form = PasswordChangeForm(user)

    if request.method == 'POST':
        new_username = request.POST.get('username')
        new_email = request.POST.get('email')

        if new_username:
            user.username = new_username
        if new_email:
            user.email = new_email

        if 'old_password' in request.POST and request.POST['old_password']:
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)

        if 'remove_image' in request.POST:
            if profile.profile_image:
                profile.profile_image.delete(save=False)
                profile.profile_image = None
        elif 'profile_image' in request.FILES:
            profile.profile_image = request.FILES['profile_image']

        user.save()
        profile.save()
        messages.success(request, "تم تحديث البيانات وكلمة المرور بنجاح! ⚽")
        return redirect('edit_profile')

    return render(request, 'pitches/edit_profile.html', {'profile': profile, 'password_form': password_form})

def pitch_detail(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id)
    return render(request, 'pitches/pitch_detail.html', {'pitch': pitch})

def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    today = date.today()

    if request.user.is_staff or reservation.date > today:
        reservation.is_cancelled = True
        reservation.save()
        messages.success(request, "تم إلغاء الحجز بنجاح.")
    else:
        messages.error(request, "عذراً، لا يمكن إلغاء الحجز في نفس يوم المباراة أو بعده.")

    return redirect('customer_profile')

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "تم تسجيل الحساب وتسجيل الدخول بنجاح!")
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'pitches/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "تم تسجيل الدخول بنجاح!")
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'pitches/login.html', {'form': form})

def terms_view(request):
    return render(request, 'pitches/terms.html')
