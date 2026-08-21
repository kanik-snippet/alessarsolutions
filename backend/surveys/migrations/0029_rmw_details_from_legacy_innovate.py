from django.db import migrations


def configure_hybrid_details(apps, schema_editor):
    if schema_editor.connection.alias != "default":
        return
    Integration = apps.get_model("vendors", "ClientIntegration")
    Survey = apps.get_model("surveys", "Survey")
    SurveyQuota = apps.get_model("surveys", "SurveyQuota")
    TargetingQuestion = apps.get_model("surveys", "TargetingQuestion")

    for integration in Integration.objects.using("default").filter(provider_code="rmwinsights"):
        detail_integration = (
            Integration.objects.using("default")
            .filter(client_id=integration.client_id, provider_code="innovatemr")
            .order_by("pk")
            .first()
        )
        config = dict(integration.config or {})
        if detail_integration is not None:
            config["detail_integration_id"] = detail_integration.pk
        Integration.objects.using("default").filter(pk=integration.pk).update(config=config)

        survey_ids = Survey.objects.using("default").filter(
            integration_id=integration.pk,
        ).values_list("pk", flat=True)
        SurveyQuota.objects.using("default").filter(survey_id__in=survey_ids).delete()
        TargetingQuestion.objects.using("default").filter(survey_id__in=survey_ids).delete()
        Survey.objects.using("default").filter(integration_id=integration.pk).update(
            detail_synced_at=None,
            quota_synced_at=None,
            targeting_synced_at=None,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("surveys", "0028_rekey_rmw_surveys_to_upstream_id"),
    ]

    operations = [
        migrations.RunPython(configure_hybrid_details, migrations.RunPython.noop),
    ]
