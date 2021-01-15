from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from apps.authorization import views

router = DefaultRouter()
router.register(r'tokens', views.AuthorizedGrants, base_name='token')

urlpatterns = [
    url(r'', include((router.urls, 'authorization'), namespace='token_management_v2')),
]
