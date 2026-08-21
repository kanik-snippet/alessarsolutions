from django.db import migrations


def rekey_to_upstream_survey_id(apps, schema_editor):
    Survey = apps.get_model("surveys", "Survey")
    rows = Survey.objects.filter(
        integration__provider_code="rmwinsights",
    ).only("id", "source_id", "source_key", "raw_data")
    for survey in rows.iterator(chunk_size=500):
        raw = survey.raw_data if isinstance(survey.raw_data, dict) else {}
        upstream_id = str(raw.get("survey_id") or raw.get("source_id") or "").strip()
        if not upstream_id or len(upstream_id) > 160:
            continue
        numeric_id = int(upstream_id) if upstream_id.isdigit() else None
        Survey.objects.filter(pk=survey.pk).update(
            source_key=upstream_id,
            source_id=numeric_id,
        )


def rekey_to_remote_project_id(apps, schema_editor):
    Survey = apps.get_model("surveys", "Survey")
    rows = Survey.objects.filter(
        integration__provider_code="rmwinsights",
    ).only("id", "source_key", "raw_data")
    for survey in rows.iterator(chunk_size=500):
        raw = survey.raw_data if isinstance(survey.raw_data, dict) else {}
        remote_project_id = str(raw.get("remote_project_id") or raw.get("local_id") or "").strip()
        if remote_project_id:
            Survey.objects.filter(pk=survey.pk).update(source_key=remote_project_id)


class Migration(migrations.Migration):
    dependencies = [
        ("surveys", "0027_surveyattempt_supplier_respondent_id_and_more"),
    ]

    operations = [
        migrations.RunPython(
            rekey_to_upstream_survey_id,
            rekey_to_remote_project_id,
        ),
    ]
