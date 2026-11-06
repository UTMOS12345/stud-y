import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def fill_user_and_seconds(apps, schema_editor):
    BlockSession = apps.get_model('schedule', 'BlockSession')
    for session in BlockSession.objects.select_related('block__schedule'):
        session.user_id = session.block.schedule.user_id
        if session.end_time:
            session.focused_seconds = max(0, int((session.end_time - session.start_time).total_seconds()))
        session.save(update_fields=['user', 'focused_seconds'])


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0003_daytemplate_user_required'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='blocksession',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='focus_sessions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='blocksession',
            name='focused_seconds',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(fill_user_and_seconds, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='blocksession',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='focus_sessions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='blocksession',
            name='block',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='sessions', to='schedule.scheduleblock'),
        ),
        migrations.AlterModelOptions(
            name='blocksession',
            options={'ordering': ['-start_time']},
        ),
    ]
