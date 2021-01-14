from waffle.models import AbstractUserFlag


class Flag(AbstractUserFlag):
    """ Custom version of waffle feature Flag model """
    """ This makes future extensions nicer """
    def is_active(self, request):
        # exract the current app's owner (user)
        self.app_user = request.auth.application.user
        return super(Flag, self).is_active(request)

    def is_active_for_user(self, user):
        # use app_user which is the owner of the current app
        return super(Flag, self).is_active_for_user(self.app_user)
