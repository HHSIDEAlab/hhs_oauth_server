from django.conf.urls import url
from .views import (
    CheckInternal,
    CheckExternal,
)

urlpatterns = [
    url(r'external', CheckExternal.as_view()),
    url(r'external_v2', CheckExternal.as_view()),
    url(r'', CheckInternal.as_view()),
]
