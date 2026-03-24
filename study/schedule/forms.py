from django import forms
from .models import ScheduleBlock

class ScheduleBlockForm(forms.ModelForm):
    class Meta:
        model = ScheduleBlock
        fields = ['title', 'start_time', 'end_time', 'block_type', 'color']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full bg-base-300 border border-neutral/20 rounded-xl p-4 text-base-content focus:outline-none focus:border-primary/50 font-mono placeholder:opacity-30',
                'placeholder': 'TASK_NAME_01'
            }),
            'start_time': forms.TextInput( 
                attrs={
                    'class': 'timepicker w-full bg-base-300 border border-neutral/20 rounded-xl p-4 text-base-content focus:outline-none focus:border-primary/50 font-mono',
                    'placeholder': '00:00',
                }
            ),
            'end_time': forms.TextInput( 
                attrs={
                    'class': 'timepicker w-full bg-base-300 border border-neutral/20 rounded-xl p-4 text-base-content focus:outline-none focus:border-primary/50 font-mono',
                    'placeholder': '00:00',
                }
            ),
            'block_type': forms.Select(attrs={
                'class': 'w-full bg-base-300 border border-neutral/20 rounded-xl p-4 text-base-content focus:outline-none focus:border-primary/50 font-mono'
            }),
            'color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'w-full bg-base-300 border border-neutral/20 rounded-xl h-[58px] p-2 cursor-pointer'
            }),
        }