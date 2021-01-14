from django.contrib.auth.models import User, Group
from django.core.management.base import BaseCommand
from waffle.models import Switch
from apps.core.models import Flag

WAFFLE_FEATURE_SWITCHES = (('outreach_email', True),
                           ('wellknown_applications', True),
                           ('login', True),
                           ('signup', True),
                           ('require-scopes', True),
                           ('bfd_v2', True),
                           ('slsx-enable', True))


class Command(BaseCommand):
    help = 'Create Feature Switches/Flags for Local Testing'

    def handle(self, *args, **options):
        # Create feature switches for testing in local development
        for switch in WAFFLE_FEATURE_SWITCHES:
            try:
                Switch.objects.get(name=switch[0])
                self._log('Feature switch already exists: %s' % (str(switch)))
            except Switch.DoesNotExist:
                Switch.objects.create(name=switch[0], active=switch[1])
                self._log('Feature switch created: %s' % (str(switch)))

        # Create feature flag bfd_v2
        flag_name = 'bfd_v2_flag'
        flag = None

        try:
            flag = Flag.objects.get(name=flag_name)
            self._log('Feature flag already exists: %s' % flag_name)
        except Flag.DoesNotExist:
            flag = Flag.objects.create(name=flag_name)
            self._log('Feature flag created: %s' % flag_name)

        bfd_v2_grp = Group.objects.get(name='BFDV2Parteners')
        if bfd_v2_grp is not None:
            flag.groups.add(bfd_v2_grp)

        fred = User.objects.get(username="fred")
        if fred is not None:
            flag.users.add(fred)

    def _log(self, message):
        self.stdout.write(message)
