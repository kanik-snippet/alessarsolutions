"""RMW Insights supplier inventory, targeting and respondent adapter."""

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from surveys.integrations import InnovateMRClient
from surveys.models import Survey
from surveys.services import replace_survey_details
from vendors.credentials import resolve_integration_token
from vendors.models import ClientIntegration

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

    def __init__(self, integration, *, session=None, detail_client=None):
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
        self.detail_client = detail_client

    def _innovate_client(self):
        """Use the legacy direct Innovate account only for quota/targeting."""

        if self.detail_client is not None:
            return self.detail_client
        configured_id = (self.integration.config or {}).get("detail_integration_id")
        integrations = ClientIntegration.objects.filter(
            client_id=self.integration.client_id,
            provider_code="innovatemr",
        ).exclude(pk=self.integration.pk)
        if configured_id:
            integrations = integrations.filter(pk=configured_id)
        detail_integration = integrations.order_by("pk").first()
        if detail_integration is None:
            raise ProviderConfigurationError(
                "RMW Insights requires the client's legacy InnovateMR integration for live details."
            )
        self.detail_client = InnovateMRClient(integration=detail_integration)
        return self.detail_client

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

    def refresh_details(self, survey):
        # Inventory, CPI and respondent URL remain authoritative from RMW.
        # Only the derived live quota and pre-screener collections come from
        # the original InnovateMR API keyed by the actual numeric survey ID.
        replace_survey_details(self._innovate_client(), survey)
        has_quota = survey.quotas.exists()
        if survey.has_quota != has_quota:
            survey.has_quota = has_quota
            survey.save(update_fields=["has_quota", "updated_at"])

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
