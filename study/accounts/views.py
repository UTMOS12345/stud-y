from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.cache import cache
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import SignupForm, LoginForm

# Wrong-password limit: after MAX_LOGIN_FAILURES tries for the same email from
# the same IP, that login is blocked for LOGIN_LOCK_SECONDS.
MAX_LOGIN_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60


# Reset emails per hour, so nobody can use the form to flood an inbox
MAX_RESETS_PER_EMAIL = 3
MAX_RESETS_PER_IP = 10


def _login_key(request, email):
    ip = request.META.get('REMOTE_ADDR', '')
    return f"login-fails:{email.lower()}:{ip}"


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password1'])
        user.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f"Welcome, {user.username}!")
        return redirect('dashboard')

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_url = request.POST.get('next') or request.GET.get('next')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            key = _login_key(request, form.cleaned_data['email'])
            if cache.get(key, 0) >= MAX_LOGIN_FAILURES:
                messages.error(request, "Too many failed attempts. Try again in 15 minutes.")
                return render(request, 'accounts/login.html', {'form': form, 'next': next_url or ''}, status=429)

            user = authenticate(
                request,
                username=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )
            if user:
                cache.delete(key)
                login(request, user)
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                return redirect('dashboard')
            else:
                cache.add(key, 0, LOGIN_LOCK_SECONDS)
                cache.incr(key)
                messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form, 'next': next_url or ''})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


def _over_limit(key, limit):
    cache.add(key, 0, 60 * 60)
    return cache.incr(key) > limit


class ResetPasswordView(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.txt'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        # Over the limit looks the same as success, the page never reveals who has an account
        over_email = _over_limit(f"reset-email:{form.cleaned_data['email'].lower()}", MAX_RESETS_PER_EMAIL)
        over_ip = _over_limit(f"reset-ip:{self.request.META.get('REMOTE_ADDR', '')}", MAX_RESETS_PER_IP)
        if over_email or over_ip:
            return redirect(self.success_url)
        return super().form_valid(form)


class ResetPasswordConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        cache.delete(_login_key(self.request, self.user.email))  # a new password lifts the lockout
        return super().form_valid(form)
