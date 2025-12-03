import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.cache import performance_monitor, get_cache_health, cache_manager
from app.core.database import db_manager, check_database_ready
from app.core.security_enhanced import security_audit, security_monitor
from app.core.authorization import (
    get_authorization_context,
    AuthorizationContext,
    require_role,
    UserRole,
)
from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["infra"])


@router.get("/performance/metrics")
@require_role(UserRole.ADMIN)
async def get_performance_metrics(auth_context: AuthorizationContext = Depends(get_authorization_context)) -> Dict[str, Any]:
    """Return performance metrics, cache stats, and DB statistics."""
    cache_health = await get_cache_health()
    db_stats = await db_manager.get_database_statistics()
    perf_stats = performance_monitor.get_all_stats()

    return {
        "cache": cache_health,
        "database": db_stats,
        "performance": perf_stats,
    }


@router.get("/security/audit")
@require_role(UserRole.ADMIN)
async def get_security_audit(auth_context: AuthorizationContext = Depends(get_authorization_context)) -> Dict[str, Any]:
    """Return a comprehensive security audit report and threat summary."""
    report = security_audit.generate_security_report(days=7)
    summary = security_monitor.get_threat_summary()

    return {
        "report": report,
        "summary": summary,
    }


def _read_coverage_xml(path: str) -> Optional[Dict[str, Any]]:
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        # Cobertura XML: root attributes may include 'line-rate', 'branch-rate'
        line_rate = root.attrib.get("line-rate")
        branch_rate = root.attrib.get("branch-rate")
        lines_valid = 0
        lines_covered = 0
        branches_valid = 0
        branches_covered = 0
        # Aggregate metrics from packages/classes if present
        for child in root:
            if child.tag == "packages":
                for pkg in child:
                    for cls in pkg.findall("classes/class"):
                        for lines in cls.findall("lines/line"):
                            hits = int(lines.attrib.get("hits", "0"))
                            lines_valid += 1
                            if hits > 0:
                                lines_covered += 1
        return {
            "line_rate": float(line_rate) if line_rate else None,
            "branch_rate": float(branch_rate) if branch_rate else None,
            "lines_valid": lines_valid,
            "lines_covered": lines_covered,
            "branches_valid": branches_valid,
            "branches_covered": branches_covered,
        }
    except Exception:
        return None


@router.get("/test/coverage")
@require_role(UserRole.ADMIN)
async def get_test_coverage(auth_context: AuthorizationContext = Depends(get_authorization_context)) -> Dict[str, Any]:
    """Return test coverage summary if available (from coverage.xml or htmlcov)."""
    # Look for coverage.xml
    cov_xml_path = os.path.join(os.getcwd(), "coverage.xml")
    cov_html_index = os.path.join(os.getcwd(), "htmlcov", "index.html")

    summary = None
    if os.path.exists(cov_xml_path):
        summary = _read_coverage_xml(cov_xml_path)

    return {
        "available": bool(summary) or os.path.exists(cov_html_index),
        "summary": summary,
        "html_report": os.path.exists(cov_html_index),
    }


@router.get("/deployment/status")
@require_role(UserRole.ADMIN)
async def get_deployment_status(auth_context: AuthorizationContext = Depends(get_authorization_context)) -> Dict[str, Any]:
    """Report deployment readiness and environment checks."""
    settings = get_settings()

    # Database readiness
    db_ready = await check_database_ready()
    migration_status = await db_manager.check_migration_status()

    # Cache readiness
    cache_backend = "redis" if cache_manager.use_redis else "memory"
    cache_ok = True
    try:
        if cache_manager.use_redis and cache_manager.redis_cache and cache_manager.redis_cache.redis_client:
            cache_ok = await cache_manager.redis_cache.redis_client.ping()
    except Exception:
        cache_ok = False

    # CORS / Hosts
    cors_origins = getattr(settings, "CORS_ORIGINS", []) or []
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", ["*"])

    # SSL configured flag (heuristic)
    ssl_configured = bool(os.environ.get("SSL_ENABLED", "false").lower() == "true")

    # Overall readiness (simple rule set)
    readiness_ok = all([
        db_ready,
        cache_ok,
        True,  # add more checks as needed
    ])

    return {
        "environment": {
            "env": getattr(settings, "ENV", "dev"),
            "app": getattr(settings, "APP_NAME", "Sistema Boladão"),
            "version": getattr(settings, "APP_VERSION", "unknown"),
        },
        "database": {
            "ready": db_ready,
            "migration_status": migration_status,
        },
        "cache": {
            "backend": cache_backend,
            "ready": cache_ok,
        },
        "network": {
            "cors_origins": cors_origins,
            "allowed_hosts": allowed_hosts,
            "ssl_configured": ssl_configured,
        },
        "readiness": {
            "ok": readiness_ok,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        },
    }


# Test endpoint to intentionally raise an internal error for verification
@router.get("/test/raise_error")
@require_role(UserRole.ADMIN)
async def raise_internal_error(auth_context: AuthorizationContext = Depends(get_authorization_context)) -> Dict[str, Any]:
    raise RuntimeError("Simulated internal server error for logging verification")
