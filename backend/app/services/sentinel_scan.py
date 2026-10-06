"""Service layer for Sentinel scanning orchestration, persistence, and audit logging."""

import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditEventType, AuditOutcome, record_security_event
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.runtime_action import RuntimeAction
from app.db.models.security_finding import SecurityFinding
from app.db.models.security_scan import SecurityScan
from app.sentinel.adapter import sentinel_adapter
from app.sentinel.config import settings
from app.sentinel.exceptions import SentinelAdapterError, SentinelScannerExecutionError
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.runtime_action import RuntimeActionNotFoundError

logger = logging.getLogger(__name__)


class SecurityFindingNotFoundError(Exception):
    """Raised when a SecurityFinding is not found within the organization context."""
    def __init__(self, org_id: uuid.UUID, finding_id: uuid.UUID):
        super().__init__(f"SecurityFinding '{finding_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.finding_id = finding_id


async def scan_runtime_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    fail_mode: Optional[str] = None,
) -> Tuple[SecurityScan, List[SecurityFinding]]:
    """Scan a RuntimeAction's payload using Sentinel scanners and persist authoritative scan and finding records.

    Strictly preserves tenant isolation and records immutable audit events.
    """
    effective_fail_mode = fail_mode or settings.fail_mode

    # 1. Validate Organization
    org_res = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)
    if org.status != OrganizationStatus.active.value:
        raise OrganizationSuspendedError(organization_id)

    # 2. Validate RuntimeAction scoped to Organization
    action_res = await session.execute(
        select(RuntimeAction).where(
            RuntimeAction.id == runtime_action_id,
            RuntimeAction.organization_id == organization_id,
        )
    )
    action = action_res.scalar_one_or_none()
    if action is None:
        raise RuntimeActionNotFoundError(organization_id, runtime_action_id)

    # 3. Execute Sentinel Scanner via Adapter
    try:
        norm_findings, scan_meta = sentinel_adapter.scan_runtime_action_payload(
            parameters=action.parameters,
            resource=action.resource,
            action_type=action.action_type,
        )
    except Exception as exc:
        logger.error(f"Sentinel scan failed on action '{runtime_action_id}': {exc}")
        # Record failed scan record for forensic traceability
        failed_scan = SecurityScan(
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
            scanner_count=len(settings.enabled_scanners),
            findings_count=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            highest_severity="NONE",
            status="failed",
            scanners_run=settings.enabled_scanners,
            execution_time_ms=0.0,
            error_message=str(exc),
            scan_metadata={"fail_mode": effective_fail_mode},
        )
        session.add(failed_scan)
        await session.flush()

        await record_security_event(
            session=session,
            event_type=AuditEventType.SECURITY_SCAN_COMPLETED,
            action="RUN_SECURITY_SCAN",
            organization_id=organization_id,
            resource_type="SECURITY_SCAN",
            resource_id=failed_scan.id,
            outcome=AuditOutcome.FAILURE,
            metadata={
                "runtime_action_id": str(runtime_action_id),
                "error": str(exc),
                "fail_mode": effective_fail_mode,
            },
        )

        if effective_fail_mode == "fail_closed":
            raise SentinelAdapterError(f"Security scan failed in fail-closed mode: {exc}") from exc

        return failed_scan, []

    # 4. Aggregate Findings Breakdown
    critical_count = sum(1 for f in norm_findings if f.severity.value == "CRITICAL")
    high_count = sum(1 for f in norm_findings if f.severity.value == "HIGH")
    medium_count = sum(1 for f in norm_findings if f.severity.value == "MEDIUM")
    low_count = sum(1 for f in norm_findings if f.severity.value == "LOW")

    if critical_count > 0:
        highest_severity = "CRITICAL"
    elif high_count > 0:
        highest_severity = "HIGH"
    elif medium_count > 0:
        highest_severity = "MEDIUM"
    elif low_count > 0:
        highest_severity = "LOW"
    else:
        highest_severity = "NONE"

    # 5. Persist SecurityScan
    scan = SecurityScan(
        organization_id=organization_id,
        runtime_action_id=runtime_action_id,
        scanner_count=len(scan_meta.get("scanners_run", [])),
        findings_count=len(norm_findings),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        highest_severity=highest_severity,
        status="completed",
        scanners_run=scan_meta.get("scanners_run", []),
        execution_time_ms=scan_meta.get("latency_ms", 0.0),
        scan_metadata=scan_meta,
    )
    session.add(scan)
    await session.flush()
    await session.refresh(scan)

    # 6. Persist SecurityFinding records
    persisted_findings: List[SecurityFinding] = []
    for nf in norm_findings:
        finding = SecurityFinding(
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
            scan_id=scan.id,
            scanner=nf.scanner,
            category=nf.category.value,
            severity=nf.severity.value,
            confidence=nf.confidence,
            title=nf.title,
            description=nf.description,
            evidence=nf.evidence,
            remediation=nf.remediation,
            source=nf.source,
            finding_metadata=nf.metadata,
        )
        session.add(finding)
        persisted_findings.append(finding)

    if persisted_findings:
        await session.flush()
        for f in persisted_findings:
            await session.refresh(f)

    # 7. Record Security Audit Events
    audit_outcome = AuditOutcome.DENIED if critical_count > 0 else (
        AuditOutcome.FAILURE if high_count > 0 else AuditOutcome.SUCCESS
    )

    await record_security_event(
        session=session,
        event_type=AuditEventType.SECURITY_SCAN_COMPLETED,
        action="RUN_SECURITY_SCAN",
        organization_id=organization_id,
        resource_type="SECURITY_SCAN",
        resource_id=scan.id,
        outcome=audit_outcome,
        metadata={
            "runtime_action_id": str(runtime_action_id),
            "findings_count": len(persisted_findings),
            "critical_count": critical_count,
            "high_count": high_count,
            "highest_severity": highest_severity,
            "latency_ms": scan.execution_time_ms,
        },
    )

    for finding in persisted_findings:
        await record_security_event(
            session=session,
            event_type=AuditEventType.SECURITY_FINDING_CREATED,
            action="CREATE_SECURITY_FINDING",
            organization_id=organization_id,
            resource_type="SECURITY_FINDING",
            resource_id=finding.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "runtime_action_id": str(runtime_action_id),
                "scan_id": str(scan.id),
                "category": finding.category,
                "severity": finding.severity,
                "scanner": finding.scanner,
                "title": finding.title,
            },
        )

    return scan, persisted_findings


async def get_security_finding(
    session: AsyncSession,
    organization_id: uuid.UUID,
    finding_id: uuid.UUID,
) -> Optional[SecurityFinding]:
    """Retrieve an authoritative SecurityFinding scoped to an organization."""
    query = select(SecurityFinding).where(
        SecurityFinding.organization_id == organization_id,
        SecurityFinding.id == finding_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_security_findings(
    session: AsyncSession,
    organization_id: uuid.UUID,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    scanner: Optional[str] = None,
    runtime_action_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[SecurityFinding], int]:
    """List security findings scoped strictly to an organization with filters and pagination."""
    query = select(SecurityFinding).where(SecurityFinding.organization_id == organization_id)
    count_query = select(func.count(SecurityFinding.id)).where(SecurityFinding.organization_id == organization_id)

    if severity:
        sev_upper = severity.upper()
        query = query.where(SecurityFinding.severity == sev_upper)
        count_query = count_query.where(SecurityFinding.severity == sev_upper)

    if category:
        cat_upper = category.upper()
        query = query.where(SecurityFinding.category == cat_upper)
        count_query = count_query.where(SecurityFinding.category == cat_upper)

    if scanner:
        query = query.where(SecurityFinding.scanner == scanner)
        count_query = count_query.where(SecurityFinding.scanner == scanner)

    if runtime_action_id:
        query = query.where(SecurityFinding.runtime_action_id == runtime_action_id)
        count_query = count_query.where(SecurityFinding.runtime_action_id == runtime_action_id)

    count_res = await session.execute(count_query)
    total = count_res.scalar_one() or 0

    query = query.order_by(desc(SecurityFinding.created_at)).limit(limit).offset(offset)
    res = await session.execute(query)
    return list(res.scalars().all()), total


async def list_scans_for_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
) -> List[SecurityScan]:
    """List historical security scans for a specific action in descending order."""
    query = (
        select(SecurityScan)
        .where(
            SecurityScan.organization_id == organization_id,
            SecurityScan.runtime_action_id == runtime_action_id,
        )
        .order_by(desc(SecurityScan.created_at))
    )
    res = await session.execute(query)
    return list(res.scalars().all())


async def list_findings_for_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
) -> List[SecurityFinding]:
    """List all findings for a specific action."""
    query = (
        select(SecurityFinding)
        .where(
            SecurityFinding.organization_id == organization_id,
            SecurityFinding.runtime_action_id == runtime_action_id,
        )
        .order_by(desc(SecurityFinding.created_at))
    )
    res = await session.execute(query)
    return list(res.scalars().all())


async def get_security_metrics(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> Dict[str, Any]:
    """Calculate aggregated security scanner metrics strictly within tenant boundary."""
    # Total scans
    scans_q = select(func.count(SecurityScan.id)).where(SecurityScan.organization_id == organization_id)
    scans_res = await session.execute(scans_q)
    total_scans = scans_res.scalar_one() or 0

    # Total findings
    find_q = select(func.count(SecurityFinding.id)).where(SecurityFinding.organization_id == organization_id)
    find_res = await session.execute(find_q)
    total_findings = find_res.scalar_one() or 0

    # Severity counts
    sev_q = (
        select(SecurityFinding.severity, func.count(SecurityFinding.id))
        .where(SecurityFinding.organization_id == organization_id)
        .group_by(SecurityFinding.severity)
    )
    sev_res = await session.execute(sev_q)
    sev_map = {row[0].upper(): row[1] for row in sev_res.all()}

    # Category counts
    cat_q = (
        select(SecurityFinding.category, func.count(SecurityFinding.id))
        .where(SecurityFinding.organization_id == organization_id)
        .group_by(SecurityFinding.category)
    )
    cat_res = await session.execute(cat_q)
    cat_map = {row[0]: row[1] for row in cat_res.all()}

    # Scanner counts
    scan_counts_q = (
        select(SecurityFinding.scanner, func.count(SecurityFinding.id))
        .where(SecurityFinding.organization_id == organization_id)
        .group_by(SecurityFinding.scanner)
    )
    scan_counts_res = await session.execute(scan_counts_q)
    scanner_map = {row[0]: row[1] for row in scan_counts_res.all()}

    return {
        "total_scans": total_scans,
        "total_findings": total_findings,
        "critical_count": sev_map.get("CRITICAL", 0),
        "high_count": sev_map.get("HIGH", 0),
        "medium_count": sev_map.get("MEDIUM", 0),
        "low_count": sev_map.get("LOW", 0),
        "category_distribution": cat_map,
        "scanner_distribution": scanner_map,
    }
