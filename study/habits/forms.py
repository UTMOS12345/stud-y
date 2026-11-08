from django import forms

from .models import Habit


class HabitEditForm(forms.ModelForm):
    """Name, description and color. The kind stays fixed, old entries were saved for it."""

    class Meta:
        model = Habit
        fields = ['name', 'description', 'color']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        others = Habit.objects.filter(user=self.user, name__iexact=name)
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise forms.ValidationError(f"You already have a habit called '{name}'")
        return name


class HabitForm(HabitEditForm):
    class Meta(HabitEditForm.Meta):
        fields = ['name', 'description', 'kind', 'color']
