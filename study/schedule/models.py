import datetime
from accounts.models import User
from django.db.models import CheckConstraint, Q, F
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction 

# Default colors for new actions, picked in this order so every action looks different
ACTION_COLORS = [
    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899',
    '#06B6D4', '#84CC16', '#F97316', '#14B8A6', '#6366F1', '#EAB308',
]


def next_palette_color(colors):
    """The first palette color not in `colors` (after all twelve are taken, start again)."""
    used = {c.upper() for c in colors}
    for color in ACTION_COLORS:
        if color not in used:
            return color
    return ACTION_COLORS[len(used) % len(ACTION_COLORS)]


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

    @classmethod
    def next_color(cls, user, colors=None):
        """The first palette color this user's actions don't use yet
        (after all twelve are taken, start the palette again).
        Pass `colors` when the user's actions are already loaded."""
        if colors is None:
            colors = cls.objects.filter(user=user).values_list('color', flat=True)
        return next_palette_color(colors)

MINUTES_IN_DAY = 24 * 60


class BlockTimes:
    """Time arithmetic shared by ScheduleBlock and TemplateBlock.
    Minutes count from midnight of the block's own day, so a block that ends
    the next day has an end above 1440."""

    @property
    def start_minutes(self):
        return self.start_time.hour * 60 + self.start_time.minute

    @property
    def end_minutes(self):
        end = self.end_time.hour * 60 + self.end_time.minute
        return end + MINUTES_IN_DAY if self.ends_next_day else end

    @property
    def duration_minutes(self):
        return self.end_minutes - self.start_minutes

    @property
    def duration_display(self):
        h, m = divmod(self.duration_minutes, 60)
        if h > 0:
            return f"{h} h. {m} m." if m > 0 else f"{h} h."
        return f"{m} m."

    @property
    def display_density(self):
        """How much of the card a block shows, from its length."""
        if self.duration_minutes < 60:
            return 'compact'
        return 'medium' if self.duration_minutes < 180 else 'large'

    @property
    def display_height(self):
        """Card height in pixels: longer blocks are taller, with a cap so a
        nine hour block doesn't fill the screen."""
        minutes = self.duration_minutes
        if minutes < 60:
            return 56 + minutes * 2 // 3
        if minutes < 180:
            return 190 + (minutes - 60) // 3
        return min(380, 280 + (minutes - 180) // 6)

    def check_times(self):
        if self.ends_next_day and self.start_time <= self.end_time:
            raise ValidationError("A block that ends the next day must end earlier in the day than it starts.")
        if not self.ends_next_day and self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time. If it ends after midnight, turn on 'Ends next day'.")

    def overlaps(self, other, day_offset=0):
        """day_offset: how many days after this block's day the other block is."""
        shift = day_offset * MINUTES_IN_DAY
        return other.start_minutes + shift < self.end_minutes and other.end_minutes + shift > self.start_minutes


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

            # One INSERT for all blocks. They come from a valid day, so no extra checks needed.
            TemplateBlock.objects.bulk_create([
                TemplateBlock(
                    template=new_template,
                    action_id=block.action_id,
                    title=block.title,
                    description=block.description,
                    start_time=block.start_time,
                    end_time=block.end_time,
                    ends_next_day=block.ends_next_day,
                    order=index,
                    block_type=block.block_type
                )
                for index, block in enumerate(self.blocks.all())
            ])

            return new_template

class ScheduleBlock(BlockTimes, models.Model):
    class BlockType(models.TextChoices):
        FIXED = 'fixed', 'Fixed'
        FLEXIBLE = 'flexible', 'Flexible'
        
    schedule = models.ForeignKey(
        DaySchedule,
        on_delete=models.CASCADE,
        related_name='blocks'
    )
    action = models.ForeignKey(Action, on_delete=models.RESTRICT, null=True, blank=True)

    
    title = models.CharField(max_length=200, help_text="Specific title for this session")
    description = models.TextField(blank=True, null=True)
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    ends_next_day = models.BooleanField(default=False)
    
    block_type = models.CharField(
        max_length=20,
        choices=BlockType.choices,
        default=BlockType.FIXED
    )

    def clean(self):
        if self.start_time and self.end_time:
            self.check_times()

            if self.schedule_id:
                # the days around this one count too, a block can run across midnight
                day = self.schedule.date
                nearby = ScheduleBlock.objects.filter(
                    schedule__user_id=self.schedule.user_id,
                    schedule__date__range=(day - datetime.timedelta(days=1), day + datetime.timedelta(days=1)),
                ).select_related('schedule')
                if self.pk:
                    nearby = nearby.exclude(pk=self.pk)

                for other in nearby:
                    if self.overlaps(other, (other.schedule.date - day).days):
                        raise ValidationError(
                            f"Overlaps with existing block: '{other.title}' "
                            f"({other.start_time} - {other.end_time})"
                        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['start_time']
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_next_day=False, end_time__gt=F('start_time'))
                | Q(ends_next_day=True, end_time__lt=F('start_time')),
                name='check_block_time_valid'
            ),
        ]

class BlockSession(models.Model):
    """One finished Pomodoro focus session, optionally tied to a schedule block."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='focus_sessions')
    block = models.ForeignKey(
        ScheduleBlock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions'
    )
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    focused_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-start_time']

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def __str__(self):
        return f"{self.user} {self.start_time:%Y-%m-%d %H:%M} ({self.focused_seconds // 60} min)"


class DayTemplate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def apply_to_date_merge(self, target_date):
        """Copy this template's blocks into target_date, skipping any that overlap.
        Returns (applied_count, skipped_count)."""
        with transaction.atomic():
            schedule, _ = DaySchedule.objects.get_or_create(user=self.user, date=target_date)

            # everything around that day as (start, end) minutes from its midnight, loaded once
            taken = []
            for date, start, end, next_day in ScheduleBlock.objects.filter(
                schedule__user=self.user,
                schedule__date__range=(target_date - datetime.timedelta(days=1),
                                       target_date + datetime.timedelta(days=1)),
            ).values_list('schedule__date', 'start_time', 'end_time', 'ends_next_day'):
                shift = (date - target_date).days * MINUTES_IN_DAY
                start_m = start.hour * 60 + start.minute + shift
                end_m = end.hour * 60 + end.minute + shift + (MINUTES_IN_DAY if next_day else 0)
                taken.append((start_m, end_m))
            new_blocks = []
            skipped_count = 0

            for t_block in self.template_blocks.all():
                start, end = t_block.start_minutes, t_block.end_minutes
                overlaps = any(start < t_end and end > t_start for t_start, t_end in taken)
                if start >= end or overlaps:
                    skipped_count += 1
                    continue
                taken.append((start, end))
                new_blocks.append(ScheduleBlock(
                    schedule=schedule,
                    action_id=t_block.action_id,
                    title=t_block.title,
                    description=t_block.description,
                    start_time=t_block.start_time,
                    end_time=t_block.end_time,
                    ends_next_day=t_block.ends_next_day,
                    block_type=t_block.block_type
                ))

            ScheduleBlock.objects.bulk_create(new_blocks)
            return len(new_blocks), skipped_count

    def __str__(self):
        return self.name



class TemplateBlock(BlockTimes, models.Model):
    template = models.ForeignKey(
        DayTemplate, 
        on_delete=models.CASCADE, 
        related_name="template_blocks" 
    )
    action = models.ForeignKey(Action, on_delete=models.RESTRICT, related_name='template_blocks', null=True, blank=True)
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    ends_next_day = models.BooleanField(default=False)
    
    # ADD THIS FIELD so it matches ScheduleBlock:
    block_type = models.CharField(max_length=20, default='fixed')
    
    order = models.PositiveSmallIntegerField(default=0)

    def clean(self):
        # Same rules as ScheduleBlock: end after start, no overlaps inside one template
        if self.start_time and self.end_time:
            self.check_times()

            if self.template_id:
                others = TemplateBlock.objects.filter(template=self.template)
                if self.pk:
                    others = others.exclude(pk=self.pk)

                for other in others:
                    if self.overlaps(other):
                        raise ValidationError(
                            f"Overlaps with existing block: '{other.title}' "
                            f"({other.start_time} - {other.end_time})"
                        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['order', 'start_time']
