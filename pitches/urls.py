from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', views.home, name='home'),
    path('pitch/<int:pitch_id>/', views.pitch_detail, name='pitch_detail'),
    path('book/<int:pitch_id>/', views.book_pitch, name='book_pitch'),
    path('reservation-success/<int:reservation_id>/', views.reservation_success, name='reservation_success'),
    path('profile/', views.customer_profile, name='customer_profile'),
    path('cancel/<int:reservation_id>/', views.cancel_reservation, name='cancel_reservation'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('join-match/<int:match_id>/', views.join_open_match, name='join_open_match'),
    path('open-matches/', views.open_matches_view, name='open_matches'), # <-- المسار الجديد
    path('terms/', views.terms_view, name='terms'),
    path('open-match-success/<int:request_id>/', views.open_match_success, name='open_match_success'),
]