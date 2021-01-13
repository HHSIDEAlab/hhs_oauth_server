from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tokens', views.AuthorizedGrants, basename='token')

urlpatterns = [
    url(r'', include((router.urls, 'authorization'), namespace='token_management')),
]
