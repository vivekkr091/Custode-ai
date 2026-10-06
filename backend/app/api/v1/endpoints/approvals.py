"""API endpoints for Human Approval Workflows and Revalidation."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.approval import (
    ApprovalApproveRequest,
    ApprovalCancelRequest,
    ApprovalCreate,
    ApprovalListResponse,
    ApprovalRejectRequest,
    ApprovalResponse,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.approval import (
    ApprovalExpiredError,
    ApprovalNotFoundError,
    DecisionMismatchError,
    InvalidApprovalLifecycleTransitionError,
    InvalidDecisionForApprovalError,
    RevalidationFailedError,
    RevalidationStaleError,
    SelfApprovalNotAllowedError,
    UnauthorizedReviewerError,
    approve_request,
    cancel_request,
    create_approval_request,
    get_approval,
    list_approvals,
    reject_request,
)
from app.services.decision import DecisionNotFoundError
from app.services.permission import InactiveResourceError, ResourceHierarchyError
from app.services.runtime_action import RuntimeActionNotFoundError

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Approvals"],
)


def _resolve_reviewer_id(
    authorization: Optional[str],
    x_user_id: Optional[uuid.UUID],
    user_id: Optional[uuid.UUID],
) -> uuid.UUID:
    """Extract reviewer user ID from Authorization Bearer token or Header/Query fallback."""
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw_token = parts[1].strip()
            if not raw_token.startswith("cst_ag_"):
                try:
                    from app.core.security import decode_access_token
                    payload = decode_access_token(raw_token)
                    sub = payload.get("sub")
                    if sub:
                        return uuid.UUID(sub)
                except Exception:
                    pass

    resolved = x_user_id or user_id
    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reviewer identity required. Provide X-User-ID header.",
        )
    return resolved


@router.post(
    "/runtime-actions/{runtime_action_id}/approval",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or Retrieve Human Approval Request",
)
async def create_approval_request_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    payload: ApprovalCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Initiate a human governance approval request for an action requiring authorization."""
    try:
        approval = await create_approval_request(
            session=session,
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
            data=payload,
        )
        from app.audit.service import record_event, AuditEventType, AuditOutcome, AuditActorType
        await record_event(
            session=session,
            event_type=AuditEventType.APPROVAL_CREATED,
            action="CREATE_APPROVAL_REQUEST",
            organization_id=organization_id,
            actor_type=AuditActorType.AGENT,
            actor_id=str(approval.requested_by_agent_id),
            resource_type="APPROVAL_REQUEST",
            resource_id=approval.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "runtime_action_id": str(runtime_action_id),
                "decision_id": str(payload.decision_id),
                "reason": payload.reason,
            },
        )
        return ApprovalResponse.model_validate(approval)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RuntimeActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DecisionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DecisionMismatchError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvalidDecisionForApprovalError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ResourceHierarchyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InactiveResourceError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/approvals",
    response_model=ApprovalListResponse,
    summary="List Organization Approval Requests",
)
async def list_approvals_endpoint(
    organization_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by approval status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalListResponse:
    """Retrieve all approval requests scoped to an organization."""
    items, total = await list_approvals(
        session=session,
        organization_id=organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ApprovalListResponse(
        items=[ApprovalResponse.model_validate(i) for i in items],
        total=total,
    )


@router.get(
    "/approvals/{approval_id}",
    response_model=ApprovalResponse,
    summary="Retrieve Approval Request by ID",
)
async def get_approval_endpoint(
    organization_id: uuid.UUID,
    approval_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Retrieve an authoritative ApprovalRequest scoped to an organization."""
    approval = await get_approval(session, organization_id, approval_id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ApprovalRequest '{approval_id}' not found in organization '{organization_id}'",
        )
    return ApprovalResponse.model_validate(approval)


@router.post(
    "/approvals/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve Human Governance Request",
)
async def approve_request_endpoint(
    organization_id: uuid.UUID,
    approval_id: uuid.UUID,
    payload: Optional[ApprovalApproveRequest] = None,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    user_id: Optional[uuid.UUID] = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Approve a pending approval request after real-time security revalidation."""
    reviewer_id = _resolve_reviewer_id(authorization, x_user_id, user_id)
    try:
        approval = await approve_request(
            session=session,
            organization_id=organization_id,
            approval_id=approval_id,
            reviewer_user_id=reviewer_id,
            data=payload,
        )
        from app.services.audit import log_audit_event
        await log_audit_event(
            session=session,
            action="APPROVAL_APPROVED",
            organization_id=organization_id,
            user_id=reviewer_id,
            target_type="approval_request",
            target_id=str(approval_id),
            outcome="success",
            metadata={"reviewer_note": payload.reviewer_note if payload else None},
        )
        return ApprovalResponse.model_validate(approval)
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidApprovalLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ApprovalExpiredError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except UnauthorizedReviewerError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except SelfApprovalNotAllowedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RevalidationFailedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RevalidationStaleError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/approvals/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject Human Governance Request",
)
async def reject_request_endpoint(
    organization_id: uuid.UUID,
    approval_id: uuid.UUID,
    payload: ApprovalRejectRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    user_id: Optional[uuid.UUID] = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Reject a pending approval request with a mandatory reason."""
    reviewer_id = _resolve_reviewer_id(authorization, x_user_id, user_id)
    try:
        approval = await reject_request(
            session=session,
            organization_id=organization_id,
            approval_id=approval_id,
            reviewer_user_id=reviewer_id,
            data=payload,
        )
        from app.services.audit import log_audit_event
        await log_audit_event(
            session=session,
            action="APPROVAL_REJECTED",
            organization_id=organization_id,
            user_id=reviewer_id,
            target_type="approval_request",
            target_id=str(approval_id),
            outcome="success",
            metadata={"rejection_reason": payload.rejection_reason},
        )
        return ApprovalResponse.model_validate(approval)
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidApprovalLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ApprovalExpiredError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except UnauthorizedReviewerError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/approvals/{approval_id}/cancel",
    response_model=ApprovalResponse,
    summary="Cancel Human Governance Request",
)
async def cancel_request_endpoint(
    organization_id: uuid.UUID,
    approval_id: uuid.UUID,
    payload: Optional[ApprovalCancelRequest] = None,
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Cancel an active pending approval request."""
    try:
        approval = await cancel_request(
            session=session,
            organization_id=organization_id,
            approval_id=approval_id,
            data=payload,
        )
        return ApprovalResponse.model_validate(approval)
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidApprovalLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
