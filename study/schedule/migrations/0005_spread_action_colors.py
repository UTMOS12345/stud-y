from django.db import migrations

ACTION_COLORS = [
    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899',
    '#06B6D4', '#84CC16', '#F97316', '#14B8A6', '#6366F1', '#EAB308',
]
DEFAULT = '#3B82F6'


def spread_colors(apps, schema_editor):
    """Actions that all kept the old default blue get different colors.
    The first one stays blue, colors someone picked themselves are left alone."""
    Action = apps.get_model('schedule', 'Action')
    user_ids = Action.objects.filter(color__iexact=DEFAULT).values_list('user_id', flat=True).distinct()
    for user_id in user_ids:
        actions = list(Action.objects.filter(user_id=user_id).order_by('id'))
        used = {a.color.upper() for a in actions}
        free = [c for c in ACTION_COLORS if c not in used]
        blue = [a for a in actions if a.color.upper() == DEFAULT]
        for action in blue[1:]:
            if not free:
                break
            action.color = free.pop(0)
            action.save(update_fields=['color'])


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0004_blocksession_user_focused_seconds'),
    ]

    operations = [
        migrations.RunPython(spread_colors, migrations.RunPython.noop),
    ]
