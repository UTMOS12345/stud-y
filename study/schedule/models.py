from django.db import models
from django.contrib.auth.models import User
from django.db.models import CheckConstraint , Q , F
from django.core.validators import MinValueValidator , MaxValueValidator
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators


# Create your models here.
class DaySchedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='day_schedules')
    date = models.DateField(db_index = True) # Index for fast calendar lookups
    template = models.ForeignKey(
        'DayTemplate', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='applied_schedules')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_user_date_schedule')
        ]
        ordering = ['-date']

class ScheduleBlock(models.Model):
    class BlockType(models.TextChoices):
        FIXED = 'fixed', 'Fixed'
        FLEXIBLE = 'flexible', 'Flexible'
        
    schedule = models.ForeignKey(
        DaySchedule,
        on_delete=models.CASCADE,
        related_name='blocks'
    )
    title = models.CharField(max_length=200)
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    color = models.CharField(max_length=7, default='#3B82F6')
    block_type = models.CharField(
        max_length = 20,
        choices = BlockType.choices,
        default = BlockType.FIXED
    )

    class Meta:
        ordering = ['start_time']
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F('start_time')), 
                name='check_block_time_valid'
            ),
        ]


class BlockSession(models.Model):
    block = models.ForeignKey(
        ScheduleBlock,
        on_delete=models.CASCADE,
        related_name='sessions'
    )

    start_time = models.DateTimeField(db_index = True)
    end_time = models.DateTimeField(null = True, blank = True)
    
    @property
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    
class DayTemplate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='day_templates')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    

    
    def __str__(self):
        return f"{self.name} ({self.user.email})"
    

    
class TemplateBlock(models.Model):
    template = models.ForeignKey(
        DayTemplate, 
        on_delete=models.CASCADE, 
        related_name="template_blocks" # Renamed for clarity
    )
    title = models.CharField(max_length=255)
    start_time = models.TimeField()
    end_time = models.TimeField()
    color = models.CharField(max_length=7, default="#3B82F6")
    order = models.PositiveSmallIntegerField(default=0) # Smaller footprint

    class Meta:
        ordering = ['order', 'start_time']

    
    