import os
from django.core.management.base import BaseCommand
from waffle.models import Switch


WAFFLE_FEATURE_SWITCHES = (('outreach_email', True),
                           ('wellknown_applications', True),
                           ('login', True),
                           ('signup', True),
                           ('require-scopes', True),
                           ('slsx-enable', True))


class Command(BaseCommand):
    help = 'Create Feature Switches for Local Testing.'

    def handle(self, *args, **options):
        # Create feature switches for testing in local development
        for switch in WAFFLE_FEATURE_SWITCHES:
            try:
                Switch.objects.get(name=switch[0])
                self._log('Feature switch already exists: %s' % (str(switch)))
            except Switch.DoesNotExist:
                sw = switch[1]
                if switch[0] == "slsx-enable":
                    # override for now
                    SLSX_ENABLED = os.environ['SLSX_ENABLED']
                    if SLSX_ENABLED is not None and SLSX_ENABLED == "False":
                        sw = False
                    Switch.objects.create(name=switch[0], active=sw)
                    self._log('Feature switch created: %s' % (str((switch[0], sw))))
                else:
                    Switch.objects.create(name=switch[0], active=switch[1])
                    self._log('Feature switch created: %s' % (str(switch)))

    def _log(self, message):
        self.stdout.write(message)
