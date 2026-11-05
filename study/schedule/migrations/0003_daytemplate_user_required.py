import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def delete_templates_without_user(apps, schema_editor):
    # Nobody can open a template without a user, so they are only dead rows
    DayTemplate = apps.get_model('schedule', 'DayTemplate')
    DayTemplate.objects.filter(user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0002_template_block_action_optional'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(delete_templates_without_user, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='daytemplate',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='templates', to=settings.AUTH_USER_MODEL),
        ),
    ]
