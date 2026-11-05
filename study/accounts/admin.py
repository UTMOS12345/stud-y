from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from .models import User, Profile


class UserAddForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('email', 'username')


class UserEditForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # Email is the login field, so show and sort by it
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'date_joined')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)
    inlines = [ProfileInline]
    form = UserEditForm
    add_form = UserAddForm
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'username', 'usable_password', 'password1', 'password2')}),
    )

    def get_inlines(self, request, obj):
        # The profile is created by a signal when the user is saved, so only show it when editing
        return self.inlines if obj else []


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'timezone', 'theme_preference', 'default_pomodoro_duration')
    search_fields = ('user__email',)
    list_select_related = ('user',)
