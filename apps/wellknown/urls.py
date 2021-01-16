from django.conf.urls import url
from waffle.decorators import waffle_switch
from .views import (
    openid_configuration,
    ApplicationListView,
    ApplicationLabelView,
    PublicApplicationListView,
)


urlpatterns = [
    url(r'^openid-configuration$',
        openid_configuration,
        name='openid-configuration'),
    url(r'^applications$',
        waffle_switch('wellknown_applications')(ApplicationListView.as_view()),
        name='applications-list'),
    url(r'^application-labels$',
        waffle_switch('wellknown_applications')(ApplicationLabelView.as_view()),
        name='application-labels'),
    url(r'^public-applications$',
        waffle_switch('wellknown_applications')(PublicApplicationListView.as_view()),
        name='public-applications-list'),

    url(r'^openid-configuration-v2$',
        openid_configuration,
        name='openid-configuration-v2'),
    url(r'^applications-v2$',
        waffle_switch('wellknown_applications')(ApplicationListView.as_view()),
        name='applications-list-v2'),
    url(r'^application-labels-v2$',
        waffle_switch('wellknown_applications')(ApplicationLabelView.as_view()),
        name='application-labels-v2'),
    url(r'^public-applications-v2$',
        waffle_switch('wellknown_applications')(PublicApplicationListView.as_view()),
        name='public-applications-list-v2'),
]
