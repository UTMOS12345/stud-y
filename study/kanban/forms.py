from django import forms

from .models import Card, Column


class ColumnForm(forms.ModelForm):
    class Meta:
        model = Column
        fields = ['name']


class NewCardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['title']


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['title', 'description', 'color']
