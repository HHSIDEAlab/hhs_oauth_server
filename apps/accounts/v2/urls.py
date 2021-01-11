from django.conf import settings
from django.conf.urls import url
from django.contrib.auth.views import (LogoutView, PasswordResetView, PasswordResetDoneView,
                                       PasswordResetConfirmView, PasswordResetCompleteView)
from waffle.decorators import waffle_switch
from apps.accounts.views.api_profile import my_profile
from apps.accounts.views.core import (create_account, account_settings, activation_verify)
from apps.accounts.views.login import LoginView, PasswordChangeView


urlpatterns = [

    url(r'^api/profile$', my_profile, name='my_profile_v2'),

    url(r'^logout$', waffle_switch('login')(LogoutView.as_view()), name='logout_v2'),

    url(r'^create$', waffle_switch('signup')(create_account),
        name='accounts_create_account_v2'),

    url(r'^settings$', account_settings, name='account_settings_v2'),

    url(r'^login$|^mfa/login$', waffle_switch('login')(LoginView.as_view()), name='login_v2'),

    url(r'^password-change$',
        waffle_switch('login')(PasswordChangeView.as_view(
                               template_name='registration/passwd_change_form.html',
                               success_url='settings')),
        name='password_change_v2'),

    url(r'^expired-password-change$',
        waffle_switch('login')(PasswordChangeView.as_view(
                               template_name='registration/passwd_change_form.html',
                               success_url='settings')),
        name='expired_password_change_v2'),

    url(r'^forgot-password$',
        waffle_switch('login')(PasswordResetView.as_view(
                               template_name='registration/password_forgot_form.html',
                               email_template_name='email/email-password-forgot-link.txt',
                               html_email_template_name='email/email-password-forgot-link.html',
                               from_email=settings.DEFAULT_FROM_EMAIL)),
        name='forgot_password_v2'),

    url(r'^password-reset-done$',
        waffle_switch('login')(PasswordResetDoneView.as_view(
                               template_name='registration/password_forgot_reset_done.html')),
        name='password_reset_done_v2'),

    url(r'^password-reset-confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        waffle_switch('login')(PasswordResetConfirmView.as_view(
                               template_name='registration/password_forgot_reset_confirm_form.html')),
        name='password_reset_confirm_v2'),


    url(r'^password-reset-complete$',
        waffle_switch('login')(PasswordResetCompleteView.as_view(
                               template_name='registration/password_forgot_reset_complete.html')),
        name='password_reset_complete_v2'),

    url(r'^activation-verify/(?P<activation_key>[^/]+)/$',
        waffle_switch('login')(activation_verify),
        name='activation_verify_v2'),
]
