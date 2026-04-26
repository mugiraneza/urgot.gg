import time
from typing import Dict, List

from api.models import TrackedSummoner
from api.services.riot_importer import run_match_import

DEFAULT_INTERVAL_MINUTES = 30.0


def register_tracked_summoner(riot_name: str, region: str) -> TrackedSummoner:
    normalized_riot_name = (riot_name or "").strip()
    normalized_region = (region or "europe").strip().lower()
    tracked_summoner, created = TrackedSummoner.objects.get_or_create(
        riot_name=normalized_riot_name,
        region=normalized_region,
        defaults={"is_active": True},
    )
    if not created and not tracked_summoner.is_active:
        tracked_summoner.is_active = True
        tracked_summoner.save(update_fields=["is_active", "updated_at"])
    return tracked_summoner


def list_tracked_riot_ids(limit: int = 8) -> List[str]:
    return list(
        TrackedSummoner.objects.filter(is_active=True)
        .order_by("-updated_at")
        .values_list("riot_name", flat=True)[:limit]
    )


def import_tracked_summoner(tracked_summoner: TrackedSummoner) -> Dict:
    tracked_summoner.mark_import_started()
    try:
        run_match_import(tracked_summoner.riot_name, tracked_summoner.region)
    except Exception as exc:
        error_message = str(exc)
        tracked_summoner.mark_import_finished("error", error_message)
        return {
            "riot_name": tracked_summoner.riot_name,
            "region": tracked_summoner.region,
            "status": "error",
            "error": error_message,
        }

    tracked_summoner.mark_import_finished("success")
    return {
        "riot_name": tracked_summoner.riot_name,
        "region": tracked_summoner.region,
        "status": "success",
    }


def import_all_tracked_summoners() -> Dict:
    tracked_summoners = list(TrackedSummoner.objects.filter(is_active=True).order_by("riot_name", "region"))
    summary = {
        "total": len(tracked_summoners),
        "success": 0,
        "error": 0,
        "details": [],
    }

    for tracked_summoner in tracked_summoners:
        result = import_tracked_summoner(tracked_summoner)
        summary["details"].append(result)
        if result["status"] == "success":
            summary["success"] += 1
        else:
            summary["error"] += 1

    return summary


def run_tracked_import_polling_service(interval_minutes: float = DEFAULT_INTERVAL_MINUTES) -> None:
    interval_seconds = max(60.0, float(interval_minutes) * 60.0)
    print(f"[INFO] Service batch actif. Import de tous les inscrits toutes les {interval_minutes:g} minute(s).")

    while True:
        summary = import_all_tracked_summoners()
        print(
            "[INFO] Batch termine. "
            f"total={summary['total']} success={summary['success']} error={summary['error']}"
        )
        time.sleep(interval_seconds)
