import datetime
from django.db import models
from accounts.models import User
from django.db.models import CheckConstraint, Q, F
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

class Action(models.Model):
    """
    Presets that define the look and feel of a block.
    Example: 'Gym' with a 'dumbbell' icon and 'red' color.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='actions')
    name = models.CharField(max_length=100)
    icon_name = models.CharField(max_length=50, default='activity', help_text="Lucide or FontAwesome icon name")
    color = models.CharField(max_length=7, default='#3B82F6')

    class Meta:
        unique_together = ('user', 'name')
        verbose_name = "Action"
        verbose_name_plural = "Actions"

    def __str__(self):
        return self.name

class DaySchedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='day_schedules')
    date = models.DateField(db_index=True)
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
    # Linked Action
    action = models.ForeignKey(Action, on_delete=models.PROTECT, null=True, blank=True)

    
    # Custom fields for this specific instance
    title = models.CharField(max_length=200, help_text="Specific title for this session")
    description = models.TextField(blank=True, null=True)
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    block_type = models.CharField(
        max_length=20,
        choices=BlockType.choices,
        default=BlockType.FIXED
    )

    @property
    def duration_minutes(self):
        dummy_date = datetime.date.min
        delta = datetime.datetime.combine(dummy_date, self.end_time) - \
                datetime.datetime.combine(dummy_date, self.start_time)
        return int(delta.total_seconds() / 60)

    @property
    def duration_display(self):
        total_mins = self.duration_minutes
        h = total_mins // 60
        m = total_mins % 60
        if h > 0:
            return f"{h} h. {m} m." if m > 0 else f"{h} h."
        return f"{m} m."

    def clean(self):
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("End time must be after start time.")
            
            # Use self.schedule_id to check if schedule is assigned without triggering query
            if self.schedule_id:
                overlapping_blocks = ScheduleBlock.objects.filter(
                    schedule=self.schedule,
                    start_time__lt=self.end_time,
                    end_time__gt=self.start_time
                )
            
                if self.pk:
                    overlapping_blocks = overlapping_blocks.exclude(pk=self.pk)

                if overlapping_blocks.exists():
                    conflict = overlapping_blocks.first()
                    raise ValidationError(
                        f"Overlaps with existing block: '{conflict.title}' "
                        f"({conflict.start_time} - {conflict.end_time})"
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
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
        related_name="template_blocks" 
    )
    # Linked Action
    action = models.ForeignKey(Action, on_delete=models.PROTECT, related_name='template_blocks')
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'start_time']