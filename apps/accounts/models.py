import logging
import binascii
import pytz
import random
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.db import models
from django.db.models import CASCADE
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from .emails import send_activation_key_via_email

ADDITION = 1
CHANGE = 2
DELETION = 3


logger = logging.getLogger('hhs_oauth_server.accounts')
admin_logger = logging.getLogger('admin_interface')


USER_CHOICES = (
    ('BEN', 'Beneficiary'),
    ('DEV', 'Developer'),
)


# Enrollment and Identity Proofing. NIST SP 800-63-A
# Level of Assurance - Legacy/Deprecated  See NIST SP 800-63-2
LOA_CHOICES = (
    ('', 'Undefined'),
    ('1', 'LOA-1'),
    ('2', 'LOA-2'),
    ('3', 'LOA-3'),
    ('4', 'LOA-4'),
)

# Enrollment and Identity Proofing. NIST SP 800-63-3 A
# Identity assurance level
IAL_CHOICES = (
    ('', 'Undefined'),
    ('0', 'IAL0'),
    ('1', 'IAL1'),
    ('2', 'IAL2'),
    ('3', 'IAL3'),
)


# Enrollment and Identity Proofing. NIST SP 800-63-33 B
# Authenticator Assurance Level
AAL_CHOICES = (
    ('', 'Undefined'),
    ('0', 'AAL0'),
    ('1', 'AAL1'),
    ('2', 'AAL2'),
    ('3', 'AAL3'),
)


QUESTION_1_CHOICES = (
    ('1', 'What is your favorite color?'),
    ('2', 'What is your favorite vegetable?'),
    ('3', 'What is your favorite movie?'),
)

QUESTION_2_CHOICES = (
    ('1', 'What was the name of your best friend from childhood?'),
    ('2', 'What was the name of your elementary school?'),
    ('3', 'What was the name of your favorite pet?'),
)

QUESTION_3_CHOICES = (
    ('1', 'What was the make of your first automobile?'),
    ('2', "What was your maternal grandmother's maiden name?"),
    ('3', "What was your paternal grandmother's maiden name?"),
)

ISSUE_INVITE = (
    ('', 'Not Set'),
    ('YES', 'Yes - Send Invite'),
    ('NO', 'NO - Do not send invite'),
    ('DONE', 'Invite has been sent')
)


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=CASCADE, )
    organization_name = models.CharField(max_length=255,
                                         blank=True,
                                         default='')
    loa = models.CharField(default='2',
                           choices=LOA_CHOICES,
                           max_length=1,
                           blank=True,
                           verbose_name="Level of Assurance",
                           help_text="Legacy and Deprecated. Using IAL AAL is recommended.")

    ial = models.CharField(default='2',
                           choices=IAL_CHOICES,
                           max_length=1,
                           blank=True,
                           verbose_name="Identity Assurance Level",
                           help_text="See NIST SP 800 63 3A for definitions.")

    aal = models.CharField(default='1',
                           choices=AAL_CHOICES,
                           max_length=1,
                           blank=True,
                           verbose_name="Authenticator Assurance Level",
                           help_text="See NIST SP 800 63 3 B for definitions.")

    user_type = models.CharField(default='DEV',
                                 choices=USER_CHOICES,
                                 max_length=5)

    remaining_user_invites = models.IntegerField(default=0)
    access_key_id = models.CharField(max_length=20,
                                     blank=True)
    access_key_secret = models.CharField(max_length=40,
                                         blank=True)
    access_key_reset = models.BooleanField(
        blank=True,
        default=False,
        help_text=_('Check this box to issue a new access key. '
                    'Doing so invalidates the existing key.'),
    )

    create_applications = models.BooleanField(
        blank=True,
        default=False,
        help_text=_(
            'Check this to allow the account to register applications.'),
    )

    authorize_applications = models.BooleanField(
        blank=True,
        default=False,
        help_text=_(
            'Check this to allow the account to authorize applications.'),
    )

    mobile_phone_number = models.CharField(
        max_length=12,
        blank=True,
        help_text=_('US numbers only.'),
    )

    password_reset_question_1 = models.CharField(default='1',
                                                 choices=QUESTION_1_CHOICES,
                                                 max_length=1)
    password_reset_answer_1 = models.CharField(default='',
                                               blank=True,
                                               max_length=50)
    password_reset_question_2 = models.CharField(default='1',
                                                 choices=QUESTION_2_CHOICES,
                                                 max_length=1)
    password_reset_answer_2 = models.CharField(default='',
                                               blank=True,
                                               max_length=50)
    password_reset_question_3 = models.CharField(default='1',
                                                 choices=QUESTION_3_CHOICES,
                                                 max_length=1)
    password_reset_answer_3 = models.CharField(default='',
                                               blank=True,
                                               max_length=50)

    def __str__(self):
        name = '%s %s (%s)' % (self.user.first_name,
                               self.user.last_name,
                               self.user.username)
        return name

    def name(self):
        if self.organization_name:
            return self.organization_name
        else:
            name = '%s %s' % (self.user.first_name, self.user.last_name)
        return name

    def vot(self):
        r = "P%s" % (self.ial)
        if self.aal in ('1', '2'):
            r = r + "Cc"
        if self.aal == '2':
            r = r + "Cb"
        return r

    def save(self, **kwargs):
        if not self.access_key_id or self.access_key_reset:
            self.access_key_id = random_key_id()
            self.access_key_secret = random_secret()
        self.access_key_reset = False
        super(UserProfile, self).save(**kwargs)


class ActivationKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE,)
    key = models.CharField(default=uuid.uuid4, max_length=40)
    expires = models.DateTimeField(blank=True)

    def __str__(self):
        return 'Key for %s expires at %s' % (self.user.username,
                                             self.expires)

    def save(self, **kwargs):
        now = pytz.utc.localize(datetime.utcnow())
        expires = now + timedelta(days=settings.SIGNUP_TIMEOUT_DAYS)
        self.expires = expires
        super(ActivationKey, self).save(**kwargs)
        send_activation_key_via_email(self.user, self.key)


class ValidPasswordResetKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE,)
    reset_password_key = models.CharField(max_length=50, blank=True)

    # switch from datetime.now to timezone.now
    expires = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return '%s for user %s expires at %s' % (self.reset_password_key,
                                                 self.user.username,
                                                 self.expires)

    def save(self, commit=True, **kwargs):
        if commit:
            self.reset_password_key = str(uuid.uuid4())
            # use timezone.now() instead of datetime.now()
            now = timezone.now()
            expires = now + timedelta(minutes=1440)
            self.expires = expires
            super(ValidPasswordResetKey, self).save(**kwargs)


class UserIdentificationLabel(models.Model):
    """
    Provides identification labels that map to developer users.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(db_index=True, unique=True)
    weight = models.IntegerField(verbose_name="List Weight", null=False, default=0,
                                 help_text="Integer value controlling the position of the label in lists.")
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True)

    def __str__(self):
        return self.slug + " - " + self.name


def random_key_id(y=20):
    return ''.join(random.choice('ABCDEFGHIJKLM'
                                 'NOPQRSTUVWXYZ') for x in range(y))


def random_secret(y=40):
    return ''.join(random.choice('abcdefghijklmnopqrstuvwxyz'
                                 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                                 '0123456789') for x in range(y))


def create_activation_key(user):
    # Create an new activation key and send the email.
    key = ActivationKey.objects.create(user=user)
    return key


@receiver(post_save)
def export_admin_log(sender, instance, **kwargs):

    msg = ""
    if isinstance(instance, LogEntry):
        if instance.action_flag == ADDITION:
            msg = ugettext('User "%(user)s" added %(content_type)s object. "%(object)s" added at %(action_time)s') % {
                'user': instance.user,
                'content_type': instance.get_edited_object,
                'object': instance.object_repr,
                'action_time': instance.action_time}

        elif instance.action_flag == CHANGE:
            msg = ugettext('User "%(user)s" changed %(content_type)s object. "%(object)s" - %(changes)s at %(action_time)s') % {
                'user': instance.user,
                'content_type': instance.content_type,
                'object': instance.object_repr,
                'changes': instance.change_message,
                'action_time': instance.action_time}

        elif instance.action_flag == DELETION:
            msg = ugettext('User  "%(user)s" deleted %(content_type)s object. "%(object)s" deleted at %(action_time)s') % {
                'user': instance.user,
                'content_type': instance.content_type,
                'object': instance.object_repr,
                'action_time': instance.action_time}

        admin_logger.info(msg)


def get_user_id_salt(salt=settings.USER_ID_SALT):
    """
    Assumes `USER_ID_SALT` is a hex encoded value. Decodes the salt val,
    returning binary data represented by the hexadecimal string.

    :param: salt
    :return: bytes
    """
    return binascii.unhexlify(salt)


class UserPasswordDescriptor(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        editable=False
    )
    date = models.DateTimeField(
        _('Descriptor Created On'),
        auto_now_add=True,
        editable=False
    )
    salt = models.CharField(
        verbose_name=_('Salt'),
        max_length=120,
        editable=False,
    )
    iterations = models.IntegerField(
        _('Iterations'),
        default=None,
        editable=False,
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = _('Password Descriptor')
        verbose_name_plural = _('Password Descriptors')
        unique_together = (("user", "iterations",),)
        ordering = ['-user', 'iterations', ]

    def create_hash(self, password):
        # use default password hasher, if not sufficient, can pull in stronger version
        return PasswordHasher().encode(password, self.salt, self.iterations)

    def _gen_salt(self):
        self.salt = get_random_string(length=self._meta.get_field('salt').max_length)

    def save(self, *args, **kwargs):
        if not self.salt:
            self._gen_salt()
        if not self.iterations:
            self.iterations = PasswordHasher.iterations
        return super(UserPasswordDescriptor, self).save(*args, **kwargs)

    def __str__(self):
        return '{} [{}]'.format(self.user, self.iterations)


class PastPassword(models.Model):
    userpassword_desc = models.ForeignKey(
        UserPasswordDescriptor,
        on_delete=models.CASCADE,
        editable=False
    )
    password = models.CharField(
        _('Password Hash'),
        max_length=255,
        editable=False
    )
    date_created = models.DateTimeField(
        _('Date Created'),
        auto_now_add=True,
        editable=False
    )

    class Meta:
        verbose_name = 'Past Password'
        verbose_name_plural = 'Past Passwords'
        unique_together = (("userpassword_desc", "password", "date_created"),)
        ordering = ['-userpassword_desc', 'password', ]

    def __str__(self):
        return "{} [{}]".format(self.userpassword_desc, self.date_created)


class PasswordHasher(PBKDF2PasswordHasher):
    """
    We need to keep the old password so that when you update django
    (or configuration change) hashes have not changed.
    Therefore, special hasher.
    """
    iterations = settings.PASSWORD_HASH_ITERATIONS
