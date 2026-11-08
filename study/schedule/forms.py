from django import forms
from .models import ScheduleBlock, Action

class ScheduleBlockForm(forms.ModelForm):
    class Meta:
        model = ScheduleBlock
        fields = ['action', 'title', 'start_time', 'end_time', 'ends_next_day', 'block_type', 'description']
        widgets = {
            'action': forms.Select(attrs={
                'class': 'hidden',
                'id': 'id_action'
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full bg-base-300 border border-neutral/20 rounded-lg p-4 text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary/50 placeholder:opacity-30',
                'placeholder': 'TASK_IDENTIFIER'
            }),
            'start_time': forms.TextInput(attrs={
                'class': 'military-time bg-base-300 text-base-content text-3xl font-mono text-center border-none rounded-lg focus:ring-1 focus:ring-primary/50 w-full py-4',
                'placeholder': '00:00',
                'type': 'time'
            }),
            'end_time': forms.TextInput(attrs={
                'class': 'military-time bg-base-300 text-base-content text-3xl font-mono text-center border-none rounded-lg focus:ring-1 focus:ring-primary/50 w-full py-4',
                'placeholder': '00:00',
                'type': 'time'
            }),
            'ends_next_day': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary toggle-sm'}),
            'block_type': forms.Select(attrs={
                'class': 'w-full bg-base-300 border border-neutral/20 rounded-lg p-4 text-primary font-mono focus:outline-none'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full bg-base-300 border border-neutral/20 rounded-lg p-4 text-primary font-mono focus:outline-none focus:ring-1 focus:ring-primary/50 placeholder:opacity-30',
                'placeholder': 'DESCRIPTION',
                'rows': 3
            }),
        }

    def __init__(self, *args, **kwargs):
        # We take 'user' from the view so we can filter the Actions
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['action'].queryset = Action.objects.filter(user=user)
            self.fields['action'].empty_label = "SELECT_ACTION_PROTOCOL"
