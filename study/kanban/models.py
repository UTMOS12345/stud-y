from django.core.validators import RegexValidator
from django.db import models

from accounts.models import User


class Column(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_columns')
    name = models.CharField(max_length=40)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return self.name


class Card(models.Model):
    column = models.ForeignKey(Column, on_delete=models.CASCADE, related_name='cards')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, max_length=2000)
    color = models.CharField(max_length=7, blank=True, validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Pick a color')])
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return self.title
