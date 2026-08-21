"""RMW Insights supplier inventory, targeting and respondent adapter."""

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from django.db import transaction
from django.utils import timezone

from surveys.mappings import sync_survey_mappings
from surveys.models import Survey, SurveyQuota, TargetingQuestion
from vendors.credentials import resolve_integration_token

from .base import (
    NormalizedSurvey,
    ProviderConfigurationError,
    ProviderError,
    SurveyProvider,
)


COUNTRY_CODES = {
    "argentina": "AR", "australia": "AU", "austria": "AT", "belgium": "BE",
    "brazil": "BR", "canada": "CA", "chile": "CL", "china": "CN",
    "colombia": "CO", "croatia": "HR", "denmark": "DK", "finland": "FI",
    "france": "FR", "germany": "DE", "hong kong": "HK", "india": "IN",
    "indonesia": "ID", "ireland": "IE", "israel": "IL", "italy": "IT",
    "japan": "JP", "kenya": "KE", "luxembourg": "LU", "malaysia": "MY",
    "mexico": "MX", "netherlands": "NL", "new zealand": "NZ", "norway": "NO",
    "philippines": "PH", "poland": "PL", "republic of korea": "KR",
    "south korea": "KR", "romania": "RO", "saudi arabia": "SA",
    "singapore": "SG", "south africa": "ZA", "spain": "ES", "sweden": "SE",
    "switzerland": "CH", "taiwan": "TW", "thailand": "TH", "turkey": "TR",
    "united arab emirates": "AE", "united kingdom": "GB", "united states": "US",
}


class RMWInsightsProvider(SurveyProvider):
    """Consume the authenticated supplier API exposed by RMW Insights."""

    code = "rmwinsights"
    label = "RMW Insights"
    default_base_url = "https://api.rmwinsights.com/api/v1/surveys/"
    minimum_sync_interval_seconds = 60
    credential_fields = (("token", "X-API-Key"),)

    def __init__(self, integration, *, session=None):
        super().__init__(integration, session=session or requests.Session())
        self.api_key = resolve_integration_token(integration)
        if not self.api_key:
            raise ProviderConfigurationError("Configure the RMW Insights API key.")
        self.base_url = str(integration.base_url or self.default_base_url).strip().rstrip("/")
        parts = urlsplit(self.base_url)
        if (
            parts.scheme != "https"
            or parts.hostname != "api.rmwinsights.com"
            or parts.path.rstrip("/") != "/api/v1/surveys"
            or parts.query
            or parts.fragment
        ):
            raise ProviderConfigurationError(
                "RMW Insights base URL must be https://api.rmwinsights.com/api/v1/surveys/."
            )
        config = integration.config or {}
        self.timeout = max(5, min(int(config.get("timeout_seconds", 30)), 120))
        self.page_size = max(1, min(int(config.get("page_size", 100)), 100))
        self.max_pages = max(1, min(int(config.get("max_pages", 100)), 200))

    def _get(self, url, *, params=None):
        try:
            response = self.session.get(
                url,
                params=params,
                headers={"X-API-Key": self.api_key, "Accept": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise ProviderError(f"RMW Insights request failed{suffix}.", status_code=status) from exc
        except ValueError as exc:
            raise ProviderError("RMW Insights returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderError("RMW Insights returned an invalid response object.")
        return data

    def test_connection(self):
        data = self._get(self.base_url + "/", params={"page": 1, "page_size": 1, "status": "live"})
        if not isinstance(data.get("results"), list):
            raise ProviderError("RMW Insights inventory response has no results list.")
        return {
            "provider": self.code,
            "authenticated": True,
            "available_live_surveys": max(0, self._integer(data.get("count"))),
        }

    def inventory(self):
        rows = []
        for page_number in range(1, self.max_pages + 1):
            data = self._get(
                self.base_url + "/",
                params={"page": page_number, "page_size": self.page_size, "status": "live"},
            )
            page_rows = data.get("results")
            if not isinstance(page_rows, list):
                raise ProviderError("RMW Insights inventory response has no results list.")
            rows.extend(row for row in page_rows if isinstance(row, dict) and row.get("local_id"))
            if not data.get("next"):
                return rows
        raise ProviderError(
            "RMW Insights inventory exceeded the configured pagination safety limit."
        )

    @staticmethod
    def _integer(value, default=0):
        try:
            return max(0, int(float(value))) if value not in (None, "") else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _decimal(value):
        try:
            return Decimal(str(value)) if value not in (None, "") else None
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _datetime(value):
        if value in (None, ""):
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_timezone.utc)
            return parsed.astimezone(dt_timezone.utc)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _country(payload):
        name = str(
            payload.get("country") or payload.get("country_label") or payload.get("country_code") or ""
        ).strip()
        code = str(payload.get("country_code") or "").strip().upper()
        if len(code) != 2:
            code = name.upper() if len(name) == 2 else COUNTRY_CODES.get(name.casefold(), "")
        return name, code

    @staticmethod
    def _entry_link(payload):
        value = str(
            payload.get("supplier_entry_link")
            or payload.get("start_link")
            or payload.get("entry_link")
            or ""
        ).strip()
        parts = urlsplit(value)
        if parts.scheme != "https" or parts.hostname != "api.rmwinsights.com":
            raise ProviderError("RMW Insights supplied an invalid respondent entry URL.")
        query_keys = {key.casefold() for key, _ in parse_qsl(parts.query, keep_blank_values=True)}
        if not {"key", "survey", "token", "pid"}.issubset(query_keys):
            raise ProviderError("RMW Insights respondent entry URL is missing required parameters.")
        return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))

    def normalize_inventory_item(self, payload, seen_at):
        remote_project_id = str(payload.get("local_id") or "").strip()
        if not re.fullmatch(r"\d{14}", remote_project_id):
            raise ProviderError("RMW Insights survey has an invalid remote project ID.")
        upstream_id = str(payload.get("survey_id") or payload.get("source_id") or "").strip()
        if not upstream_id or len(upstream_id) > 160:
            raise ProviderError("RMW Insights survey has no valid survey ID.")
        modified = self._datetime(payload.get("source_modified_at") or payload.get("updated_at"))
        created = self._datetime(payload.get("source_created_at") or payload.get("created_at"))
        country, country_code = self._country(payload)
        status = str(payload.get("status") or "").strip().lower()
        group_type = str(payload.get("survey_type") or payload.get("group_type") or "").strip().upper()
        raw_data = {
            **payload,
            "adapter": "rmwinsights_v1",
            "remote_project_id": remote_project_id,
        }
        return NormalizedSurvey(
            # The supplier API exposes both its own platform Project ID and
            # InnovateMR's survey ID. The project ID remains the detail/link
            # lookup key, but the Survey ID column must show the real upstream
            # survey identifier.
            source_key=upstream_id,
            numeric_source_id=int(upstream_id) if upstream_id.isdigit() else None,
            modified_at=modified,
            raw_data=raw_data,
            values={
                "company_name": str(
                    payload.get("display_company_name")
                    or payload.get("company_name")
                    or payload.get("client_name")
                    or "InnovateMR"
                ).strip(),
                "name": str(payload.get("name") or "RMW Insights Survey").strip(),
                "status": Survey.Status.LIVE if status == "live" else Survey.Status.CLOSED,
                "sample_size": self._integer(payload.get("sample_size")),
                "completes": self._integer(payload.get("completes")),
                "remaining": self._integer(payload.get("remaining")),
                "starts": self._integer(payload.get("starts")),
                "cpi": self._decimal(payload.get("cpi")),
                "loi": self._integer(payload.get("loi"), None),
                "incidence_rate": self._decimal(payload.get("incidence_rate")),
                "country": country,
                "country_code": country_code,
                "language": str(payload.get("language") or "").strip(),
                "language_code": str(payload.get("language_code") or "").strip().upper(),
                "group_type": group_type,
                "buyer_id": str(payload.get("buyer_id") or "").strip(),
                "survey_type": group_type,
                "device_type": str(payload.get("device_type") or "").strip(),
                "entry_link": self._entry_link(payload),
                "has_quota": bool(payload.get("has_quota")),
                "source_created_at": created,
                "source_modified_at": modified or created,
                "last_seen_at": seen_at,
                "detail_synced_at": None,
                "quota_synced_at": None,
                "targeting_synced_at": None,
                "raw_data": raw_data,
            },
        )

    def _details(self, remote_project_id):
        if not re.fullmatch(r"\d{14}", str(remote_project_id or "")):
            raise ProviderError("RMW Insights survey has no valid remote project ID.")
        return self._get(f"{self.base_url}/{remote_project_id}/")

    def refresh_details(self, survey):
        details = self._details((survey.raw_data or {}).get("remote_project_id") or survey.source_key)
        questions = []
        for row in details.get("targeting_questions") or []:
            if not isinstance(row, dict):
                continue
            question_id = self._integer(row.get("question_id"), None)
            if question_id is None:
                continue
            questions.append(TargetingQuestion(
                survey=survey,
                question_id=question_id,
                key=str(row.get("key") or ""),
                text=str(row.get("text") or ""),
                question_type=str(row.get("question_type") or ""),
                category=str(row.get("category") or ""),
                options=row.get("options") if isinstance(row.get("options"), list) else [],
                raw_data={**row, "provider": self.code},
            ))
        quotas = []
        for index, row in enumerate(details.get("quotas") or []):
            if not isinstance(row, dict):
                continue
            quota_id = self._integer(row.get("quota_id"), None)
            source_key = str(row.get("quota_id") or row.get("id") or f"rmw-{index}")
            quotas.append(SurveyQuota(
                survey=survey,
                source_key=source_key,
                quota_id=quota_id,
                title=str(row.get("title") or row.get("display_name") or ""),
                name=str(row.get("name") or row.get("display_name") or ""),
                sample_size=self._integer(row.get("sample_size")),
                remaining=self._integer(row.get("remaining")),
                completes=self._integer(row.get("completes")),
                clicks=self._integer(row.get("clicks")),
                status=str(row.get("status") or ""),
                targeting=row.get("targeting") if isinstance(row.get("targeting"), dict) else {},
                raw_data={**row, "provider": self.code},
            ))
        now = timezone.now()
        entry_link = self._entry_link(details)
        with transaction.atomic():
            survey.targeting_questions.all().delete()
            survey.quotas.all().delete()
            TargetingQuestion.objects.bulk_create(questions)
            SurveyQuota.objects.bulk_create(quotas)
            survey.entry_link = entry_link
            survey.has_quota = bool(quotas)
            survey.targeting_synced_at = now
            survey.quota_synced_at = now
            survey.detail_synced_at = now
            survey.save(update_fields=[
                "entry_link", "has_quota", "targeting_synced_at", "quota_synced_at",
                "detail_synced_at", "updated_at",
            ])
        sync_survey_mappings(survey)

    def build_outbound_url(self, survey, attempt, answers):
        parts = urlsplit(self._entry_link({"supplier_entry_link": survey.entry_link}))
        query = []
        found_pid = False
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.casefold() == "pid":
                query.append((key, attempt.rid))
                found_pid = True
            else:
                query.append((key, value))
        if not found_pid:
            raise ProviderError("RMW Insights respondent entry URL has no PID parameter.")
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
