import datetime
from accounts.models import User
from django.db.models import CheckConstraint, Q, F
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction 

class Action(models.Model):
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

    
    def create_template_from_day(self, template_name, description=""):
        
        with transaction.atomic():
            
            new_template = DayTemplate.objects.create(
                user=self.user,
                name=template_name,
                description=description
            )

            for index, block in enumerate(self.blocks.all()):
                TemplateBlock.objects.create(
                    template=new_template,
                    action=block.action,
                    title=block.title,
                    description=block.description,
                    start_time=block.start_time,
                    end_time=block.end_time,
                    order=index,
                    block_type=block.block_type
                )
            
            return new_template

class ScheduleBlock(models.Model):
    class BlockType(models.TextChoices):
        FIXED = 'fixed', 'Fixed'
        FLEXIBLE = 'flexible', 'Flexible'
        
    schedule = models.ForeignKey(
        DaySchedule,
        on_delete=models.CASCADE,
        related_name='blocks'
    )
    action = models.ForeignKey(Action, on_delete=models.PROTECT, null=True, blank=True)

    
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def apply_to_date_merge(self, target_date):
        with transaction.atomic():
            # Get the schedule for that specific day
            from .models import DaySchedule, ScheduleBlock # local import to avoid circularity if needed
            schedule, _ = DaySchedule.objects.get_or_create(user=self.user, date=target_date)

            applied_count = 0
            skipped_count = 0

            for t_block in self.template_blocks.all():
                new_block = ScheduleBlock(
                    schedule=schedule,
                    action=t_block.action,
                    title=t_block.title,
                    description=t_block.description,
                    start_time=t_block.start_time,
                    end_time=t_block.end_time,
                    block_type=t_block.block_type # Ensure this matches
                )
            
                try:
                    new_block.full_clean() 
                    new_block.save()
                    applied_count += 1
                except ValidationError:
                    skipped_count += 1
                    continue
        
            return applied_count, skipped_count

    def __str__(self):
        return self.name



class TemplateBlock(models.Model):
    template = models.ForeignKey(
        DayTemplate, 
        on_delete=models.CASCADE, 
        related_name="template_blocks" 
    )
    action = models.ForeignKey(Action, on_delete=models.PROTECT, related_name='template_blocks', null=True, blank=True)
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # ADD THIS FIELD so it matches ScheduleBlock:
    block_type = models.CharField(max_length=20, default='fixed')
    
    order = models.PositiveSmallIntegerField(default=0)

    def clean(self):
        # Same rules as ScheduleBlock: end after start, no overlaps inside one template
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("End time must be after start time.")

            if self.template_id:
                overlapping_blocks = TemplateBlock.objects.filter(
                    template=self.template,
                    start_time__lt=self.end_time,
                    end_time__gt=self.start_time
                )
                if self.pk:
                    overlapping_blocks = overlapping_blocks.exclude(pk=self.pk)

                conflict = overlapping_blocks.first()
                if conflict:
                    raise ValidationError(
                        f"Overlaps with existing block: '{conflict.title}' "
                        f"({conflict.start_time} - {conflict.end_time})"
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['order', 'start_time']
