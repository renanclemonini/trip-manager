from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm

from accounts.models import User


class UserCreationForm(BaseUserCreationForm):
    """Admin add form without username (RF25 security exception)."""

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ('email',)


class UserChangeForm(BaseUserChangeForm):
    """Admin change form without username (RF25 security exception)."""

    class Meta(BaseUserChangeForm.Meta):
        model = User
        fields = '__all__'
