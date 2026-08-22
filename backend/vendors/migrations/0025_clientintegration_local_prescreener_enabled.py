from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0024_remove_vendorclientallocation_client_consumed_not_above_limit_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientintegration",
            name="local_prescreener_enabled",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text=(
                    "Run the Alessar pre-screener before redirecting to this client's entry link. "
                    "Disable it when the client already provides its own pre-screener."
                ),
            ),
        ),
    ]
