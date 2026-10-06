"""Policy evaluation engine implementing deterministic rule evaluation with precedence."""

import uuid
from typing import List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.policy import EnforcementMode, Policy, PolicyStatus
from app.db.models.policy_version import PolicyVersion, PolicyVersionStatus
from app.engines.policy.conditions import evaluate_condition
from app.schemas.policy import (
    ActionContext,
    MatchedRuleInfo,
    PolicyDecision,
    PolicyEvaluationResult,
    RuleEffect,
)


class PolicyEngine:
    """Core engine evaluating organization security policies against runtime action contexts."""

    @classmethod
    async def evaluate(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        context: ActionContext,
    ) -> PolicyEvaluationResult:
        """Evaluate action context across all active policies and published versions for an organization.

        Precedence: DENY > REQUIRE_APPROVAL > ALLOW > NO_MATCH.
        Policies in audit mode record matches but do NOT influence the final enforceable decision.
        """
        # 1. Fetch all active policies for the organization with their published versions
        query = (
            select(Policy, PolicyVersion)
            .join(
                PolicyVersion,
                (PolicyVersion.policy_id == Policy.id)
                & (PolicyVersion.status == PolicyVersionStatus.published.value),
            )
            .where(
                Policy.organization_id == organization_id,
                Policy.status == PolicyStatus.active.value,
            )
            .order_by(Policy.created_at.asc())
        )

        result = await session.execute(query)
        pairs: List[Tuple[Policy, PolicyVersion]] = result.all()  # type: ignore[assignment]

        matched_rules: List[MatchedRuleInfo] = []
        enforced_rules: List[MatchedRuleInfo] = []
        audit_rules: List[MatchedRuleInfo] = []

        # 2. Iterate through each policy and its published version rules
        for policy, version in pairs:
            raw_rules = version.rules
            if isinstance(raw_rules, dict):
                rules_list = raw_rules.get("rules", [])
            elif isinstance(raw_rules, list):
                rules_list = raw_rules
            else:
                rules_list = []

            for rule in rules_list:
                rule_name = rule.get("name", "unnamed_rule") if isinstance(rule, dict) else getattr(rule, "name", "unnamed_rule")
                rule_effect = rule.get("effect", "") if isinstance(rule, dict) else getattr(rule, "effect", "")
                conditions = rule.get("conditions", []) if isinstance(rule, dict) else getattr(rule, "conditions", [])

                if not conditions:
                    continue

                # All conditions in a rule must evaluate to True (AND logic)
                all_matched = all(evaluate_condition(cond, context) for cond in conditions)

                if all_matched:
                    match_info = MatchedRuleInfo(
                        policy_id=policy.id,
                        policy_name=policy.name,
                        policy_version=version.version,
                        rule_name=rule_name,
                        effect=str(rule_effect),
                        enforcement_mode=str(policy.enforcement_mode),
                        policy_version_id=version.id,
                    )
                    matched_rules.append(match_info)

                    if policy.enforcement_mode == EnforcementMode.enforce.value:
                        enforced_rules.append(match_info)
                    else:
                        audit_rules.append(match_info)

        # 3. Decision resolution among enforced rules: DENY > REQUIRE_APPROVAL > ALLOW > NO_MATCH
        deny_match = next((r for r in enforced_rules if r.effect == RuleEffect.deny.value), None)
        if deny_match:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY.value,
                reason=f"Action denied by policy rule: '{deny_match.rule_name}' in policy '{deny_match.policy_name}'",
                matched_rules=matched_rules,
                enforced_rules=enforced_rules,
                audit_rules=audit_rules,
            )

        require_approval_match = next(
            (r for r in enforced_rules if r.effect == RuleEffect.require_approval.value), None
        )
        if require_approval_match:
            return PolicyEvaluationResult(
                decision=PolicyDecision.REQUIRE_APPROVAL.value,
                reason=(
                    f"Action requires approval by policy rule: '{require_approval_match.rule_name}' "
                    f"in policy '{require_approval_match.policy_name}'"
                ),
                matched_rules=matched_rules,
                enforced_rules=enforced_rules,
                audit_rules=audit_rules,
            )

        allow_match = next((r for r in enforced_rules if r.effect == RuleEffect.allow.value), None)
        if allow_match:
            return PolicyEvaluationResult(
                decision=PolicyDecision.ALLOW.value,
                reason=f"Action allowed by policy rule: '{allow_match.rule_name}' in policy '{allow_match.policy_name}'",
                matched_rules=matched_rules,
                enforced_rules=enforced_rules,
                audit_rules=audit_rules,
            )

        # 4. No enforced rules matched
        return PolicyEvaluationResult(
            decision=PolicyDecision.NO_MATCH.value,
            reason="No matching enforced policy rules found",
            matched_rules=matched_rules,
            enforced_rules=enforced_rules,
            audit_rules=audit_rules,
        )
