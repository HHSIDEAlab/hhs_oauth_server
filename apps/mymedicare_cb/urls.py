from django.conf.urls import url
from .views import callback, mymedicare_login

urlpatterns = [
    url(r'sls-callback$', callback, name='mymedicare-sls-callback'),
    url(r'login$', mymedicare_login, name='mymedicare-login'),
    url(r'sls-callback-v2$', callback, name='mymedicare-sls-callback-v2'),
    url(r'login-v2$', mymedicare_login, name='mymedicare-login-v2'),
]
