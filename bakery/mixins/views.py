from django.contrib.auth.mixins import UserPassesTestMixin


class RoleRequiredMixin(UserPassesTestMixin):
    allowed_roles = ()

    def test_func(self):
        from bakery.permissions import user_has_role

        return user_has_role(self.request.user, *self.allowed_roles)
