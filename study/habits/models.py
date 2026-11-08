from django.core.validators import RegexValidator
from django.db import models

from accounts.models import User


class Habit(models.Model):
    class Kind(models.TextChoices):
        CHECK = 'check', 'Done or not'
        THREE = 'three', 'Three states'
        PERCENT = 'percent', 'Percent'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habits')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, max_length=500)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CHECK)
    color = models.CharField(max_length=7, validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Pick a color')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return self.name

    def accepts(self, value):
        """Is this a value the habit's kind can store? 0 means no entry, so it is always fine."""
        if value == 0:
            return True
        if self.kind == self.Kind.CHECK:
            return value == 100
        if self.kind == self.Kind.THREE:
            return value in (50, 100)
        return 1 <= value <= 100


class HabitEntry(models.Model):
    """One day of one habit. value is how full the box is, 1-100; a day with no row is empty."""
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='entries')
    date = models.DateField()
    value = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['habit', 'date'], name='unique_habit_date')]
        verbose_name_plural = 'Habit entries'

    def __str__(self):
        return f"{self.habit} {self.date}: {self.value}%"
