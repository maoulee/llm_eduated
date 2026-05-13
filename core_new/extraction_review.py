# core_new/extraction_review.py

"""
Multi-stage review system for extraction pipeline results.

Stages:
  P5a: RuleChecker        — code-based schema, answer, and link validation
  P5b: DomainCritic        — adversarial LLM reviewer (optional thinking mode)
  P5c: ReadinessAggregator — rule-based readiness status aggregation

Usage:
    from core_new.extraction_review import RuleChecker, DomainCritic, ReadinessAggregator

    rule_result = RuleChecker.validate(extraction_result)
    domain_result = await DomainCritic(provider).review(extraction_result, rule_result)
    readiness = ReadinessAggregator.aggregate(rule_result, domain_result)
"""

import json
import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from .extraction_prompts import PASS5_DOMAIN_CRITIC, ORPHAN_RESOLVER

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# P5a: RuleChecker
# ---------------------------------------------------------------------------

VALID_QUESTION_TYPES = {"单选题", "多选题", "判断题", "填空题", "综合题", "计算题", "简答题"}
VALID_TARGET_TYPES = {"knowledge", "mechanism", "reasoning_pattern"}
VALID_READINESS_STATUSES = {"candidate", "verified", "rejected", "needs_human_check"}
FUZZY_MATCH_THRESHOLD = 0.6


def _fuzzy_exists(name: str, known: List[str]) -> bool:
    if not name:
        return False
    for k in known:
        if name == k or name in k or k in name:
            return True
        if SequenceMatcher(None, name, k).ratio() >= FUZZY_MATCH_THRESHOLD:
            return True
    return False


def _collect_known_names(ku: Dict, pattern: Dict) -> List[str]:
    names: List[str] = []
    for k in ku.get("knowledge_units", []):
        names.append(k.get("name", ""))
    for m in ku.get("mechanisms", []):
        names.append(m.get("name", ""))
    if pattern.get("pattern_name"):
        names.append(pattern["pattern_name"])
    return [n for n in names if n]


def _collect_known_by_type(ku: Dict, pattern: Dict) -> Dict[str, set]:
    """Build name sets indexed by entity type for cross-type validation."""
    result: Dict[str, set] = {
        "knowledge": set(),
        "mechanism": set(),
        "reasoning_pattern": set(),
    }
    for k in ku.get("knowledge_units", []):
        if k.get("name"):
            result["knowledge"].add(k["name"])
    for m in ku.get("mechanisms", []):
        if m.get("name"):
            result["mechanism"].add(m["name"])
    if pattern.get("pattern_name"):
        result["reasoning_pattern"].add(pattern["pattern_name"])
    return result


class RuleChecker:
    """Code-based validation of extraction results. No LLM involved."""

    @staticmethod
    def validate(result: Dict[str, Any]) -> Dict[str, Any]:
        issues: List[str] = []
        warnings: List[str] = []

        structure = result.get("question_structure", {})
        ku = result.get("knowledge_units", {})
        tr = result.get("trigger_rules", {})
        rp = result.get("reasoning_pattern", {})

        # 1. Schema completeness
        schema_valid = True
        for required in ["question_structure", "knowledge_units", "trigger_rules", "reasoning_pattern"]:
            if not result.get(required):
                schema_valid = False
                issues.append(f"Missing required field: {required}")

        # 2. question_type validity
        q_type = structure.get("question_type", "")
        if q_type and q_type not in VALID_QUESTION_TYPES:
            warnings.append(f"Unusual question_type: {q_type}")

        # 3. Answer consistency (for choice questions)
        answer_check = RuleChecker._check_answer_consistency(structure, rp)

        # 4. Trigger target validation
        link_check = RuleChecker._check_trigger_targets(tr, ku, rp)

        # 5. Pattern required_knowledge validation
        pattern_link_check = RuleChecker._check_pattern_knowledge(rp, ku)

        all_orphan = link_check.get("orphan_targets", []) + pattern_link_check.get("orphan_targets", [])
        all_type_mismatch = link_check.get("type_mismatches", [])

        return {
            "schema_valid": schema_valid,
            "answer_consistency": answer_check,
            "link_validation": {
                "trigger_targets": link_check,
                "pattern_knowledge": pattern_link_check,
                "orphan_targets": all_orphan,
                "type_mismatches": all_type_mismatch,
            },
            "issues": issues,
            "warnings": warnings,
        }

    @staticmethod
    def _check_answer_consistency(structure: Dict, pattern: Dict) -> Dict[str, Any]:
        correct = structure.get("correct_answer", "")
        options = structure.get("options", {})
        if not correct or not options:
            return {"checked": False, "reason": "no options or correct_answer"}
        if correct not in options:
            return {
                "checked": True,
                "consistent": False,
                "raw_answer": correct,
                "reason": f"correct_answer '{correct}' not in options",
            }
        return {
            "checked": True,
            "consistent": True,
            "raw_answer": correct,
            "option_content": str(options.get(correct, "")),
        }

    @staticmethod
    def _check_trigger_targets(tr: Dict, ku: Dict, pattern: Dict) -> Dict[str, Any]:
        known_by_type = _collect_known_by_type(ku, pattern)
        orphan: List[Dict[str, str]] = []
        type_mismatch: List[Dict[str, str]] = []
        for rule in tr.get("trigger_rules", []):
            for target in rule.get("activates", {}).get("targets", []):
                name = target.get("target_name", "")
                t_type = target.get("target_type", "")
                if not name:
                    continue
                # Check target_type is valid
                if t_type and t_type not in VALID_TARGET_TYPES:
                    orphan.append({
                        "trigger": rule.get("name", ""),
                        "target_type": t_type,
                        "target_name": name,
                        "reason": f"invalid target_type '{t_type}'",
                    })
                    continue
                # Check name exists in the correct type set
                if t_type and t_type in known_by_type:
                    if _fuzzy_exists(name, list(known_by_type[t_type])):
                        continue
                    # Name not in correct type set — check if it exists in wrong type
                    found_in_wrong = False
                    for other_type, other_names in known_by_type.items():
                        if other_type != t_type and _fuzzy_exists(name, list(other_names)):
                            found_in_wrong = True
                            type_mismatch.append({
                                "trigger": rule.get("name", ""),
                                "target_type": t_type,
                                "target_name": name,
                                "actual_type": other_type,
                            })
                            break
                    if not found_in_wrong:
                        orphan.append({
                            "trigger": rule.get("name", ""),
                            "target_type": t_type,
                            "target_name": name,
                            "reason": "not found in any entity set",
                        })
                elif not t_type:
                    # No type specified, do generic fuzzy match
                    all_known = _collect_known_names(ku, pattern)
                    if not _fuzzy_exists(name, all_known):
                        orphan.append({
                            "trigger": rule.get("name", ""),
                            "target_type": "(unspecified)",
                            "target_name": name,
                            "reason": "not found",
                        })
        return {
            "orphan_targets": orphan,
            "type_mismatches": type_mismatch,
            "known_names_count": sum(len(v) for v in known_by_type.values()),
        }

    @staticmethod
    def _check_pattern_knowledge(pattern: Dict, ku: Dict) -> Dict[str, Any]:
        known = _collect_known_names(ku, {})
        orphan: List[Dict[str, str]] = []
        for step in pattern.get("steps", []):
            for req in step.get("required_knowledge", []):
                if not _fuzzy_exists(req, known):
                    orphan.append({
                        "step": step.get("order", "?"),
                        "required_knowledge": req,
                    })
        return {"orphan_targets": orphan}


# ---------------------------------------------------------------------------
# P5b: DomainCritic
# ---------------------------------------------------------------------------

class DomainCritic:
    """Adversarial LLM reviewer for domain-level semantic issues."""

    def __init__(self, llm_provider, max_tokens: int = 16384, enable_thinking: bool = True):
        self.llm = llm_provider
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking

    async def review(
        self,
        extraction_result: Dict[str, Any],
        rule_validation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        question = extraction_result.get("raw_question", {})
        stem = question.get("prompt", "")
        answer = question.get("answer", "")

        structure = json.dumps(extraction_result.get("question_structure", {}), ensure_ascii=False)
        ku = json.dumps(extraction_result.get("knowledge_units", {}), ensure_ascii=False)
        tr = json.dumps(extraction_result.get("trigger_rules", {}), ensure_ascii=False)
        rp = json.dumps(extraction_result.get("reasoning_pattern", {}), ensure_ascii=False)

        rule_context = self._build_rule_context(rule_validation) if rule_validation else "All rule checks passed."

        prompt = PASS5_DOMAIN_CRITIC.format(
            stem=stem,
            answer=answer,
            structure=structure,
            knowledge_units=ku,
            trigger_rules=tr,
            reasoning_pattern=rp,
            rule_context=rule_context,
        )

        logger.info("Running DomainCritic (thinking=%s)", self.enable_thinking)
        messages = [[{"role": "user", "content": prompt}]]

        if self.enable_thinking:
            raw = await self.llm.generate_with_think_and_parse_batch(
                messages, enable_thinking=True, max_token=self.max_tokens,
            )
            content = raw[0].get("answer", "") if raw else ""
            reasoning = raw[0].get("think", "") if raw else ""
        else:
            raw = await self.llm.generate_json_batch(
                messages, max_tokens=self.max_tokens, enable_thinking=False,
            )
            content = json.dumps(raw[0], ensure_ascii=False) if raw and raw[0] else ""
            reasoning = ""

        parsed = _parse_json(content)

        if parsed is None and self.enable_thinking:
            logger.warning("DomainCritic JSON parse failed, retrying without thinking")
            raw = await self.llm.generate_json_batch(
                messages, max_tokens=self.max_tokens, enable_thinking=False,
            )
            parsed = raw[0] if raw else None

        if parsed is None:
            return {
                "domain_review": {"major_issues": [], "minor_issues": [], "uncertain_items": []},
                "review_summary": "JSON parse failed",
                "recommended_status": "needs_human_check",
                "reviewer_reasoning": reasoning,
            }

        if reasoning and "reviewer_reasoning" not in parsed:
            parsed["reviewer_reasoning"] = reasoning

        major_count = len(parsed.get("domain_review", {}).get("major_issues", []))
        minor_count = len(parsed.get("domain_review", {}).get("minor_issues", []))
        logger.info("DomainCritic completed: %d major, %d minor issues", major_count, minor_count)
        return parsed

    @staticmethod
    def _build_rule_context(rule_validation: Dict[str, Any]) -> str:
        parts = []
        ac = rule_validation.get("answer_consistency", {})
        if ac.get("checked"):
            parts.append(
                f"rule-based answer_consistency: consistent={ac.get('consistent')}, "
                f"raw_answer={ac.get('raw_answer')}, option_content={ac.get('option_content')}"
            )
        orphan = rule_validation.get("link_validation", {}).get("orphan_targets", [])
        if orphan:
            parts.append(f"orphan references found: {json.dumps(orphan, ensure_ascii=False)}")
        issues = rule_validation.get("issues", [])
        if issues:
            parts.append(f"rule issues: {json.dumps(issues, ensure_ascii=False)}")
        return "\n".join(parts) if parts else "All rule checks passed."


# ---------------------------------------------------------------------------
# P5c: ReadinessAggregator
# ---------------------------------------------------------------------------

class ReadinessAggregator:
    """Rule-based readiness status aggregation. No LLM."""

    @staticmethod
    def aggregate(
        rule_validation: Dict[str, Any],
        domain_review: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        status = "candidate"
        reasons: List[str] = []
        requires_human = False

        # Rule: schema invalid → rejected
        if not rule_validation.get("schema_valid", True):
            return {
                "status": "rejected",
                "requires_human_or_rule_check": True,
                "reasons": ["Schema validation failed"],
            }

        # Rule: answer inconsistent → needs_human_check
        ac = rule_validation.get("answer_consistency", {})
        if ac.get("checked") and not ac.get("consistent", True):
            status = "needs_human_check"
            reasons.append(f"Answer inconsistency: {ac.get('reason', '')}")
            requires_human = True

        # Rule: orphan references → needs_human_check
        orphan = rule_validation.get("link_validation", {}).get("orphan_targets", [])
        if orphan:
            status = "needs_human_check"
            reasons.append(f"{len(orphan)} orphan reference(s) in triggers/pattern")
            requires_human = True

        # Rule: type mismatches → needs_human_check
        type_mismatches = rule_validation.get("link_validation", {}).get("type_mismatches", [])
        if type_mismatches:
            status = "needs_human_check"
            for tm in type_mismatches:
                reasons.append(
                    f"Type mismatch: '{tm.get('target_name')}' typed as {tm.get('target_type')} "
                    f"but exists as {tm.get('actual_type')}"
                )
            requires_human = True

        # Rule: domain major issues → needs_human_check
        if domain_review:
            dr = domain_review.get("domain_review", {})
            major = dr.get("major_issues", [])
            if major:
                status = "needs_human_check"
                for issue in major:
                    reasons.append(f"Domain: {issue.get('issue_type', '?')} — {issue.get('reason', '')[:100]}")
                requires_human = True
            elif dr.get("minor_issues"):
                reasons.append(f"{len(dr['minor_issues'])} minor domain issue(s)")

        # Rule issues from RuleChecker
        issues = rule_validation.get("issues", [])
        if issues:
            status = "needs_human_check"
            reasons.extend(issues)
            requires_human = True

        return {
            "status": status,
            "requires_human_or_rule_check": requires_human,
            "reasons": reasons if reasons else ["All checks passed; MVP default is candidate"],
        }


# ---------------------------------------------------------------------------
# OrphanReferenceResolver
# ---------------------------------------------------------------------------

class OrphanReferenceResolver:
    """Resolves orphan references from P4 pattern steps and P3 trigger targets.

    For each orphan, asks LLM whether it should be:
    - new_knowledge: add to P2 knowledge_units
    - new_mechanism: add to P2 mechanisms
    - map_to_existing: remap to an existing P2 node
    - uncertain: keep for human review
    """

    def __init__(self, llm_provider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    async def resolve(
        self,
        extraction_result: Dict[str, Any],
        rule_validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        orphans = rule_validation.get("link_validation", {}).get("orphan_targets", [])
        if not orphans:
            return {"resolutions": [], "suggested_p2_additions": [], "orphan_count": 0}

        question = extraction_result.get("raw_question", {})
        stem = question.get("prompt", "")
        answer = question.get("answer", "")
        ku = json.dumps(extraction_result.get("knowledge_units", {}), ensure_ascii=False)

        # Build trigger targets list for retarget detection
        trigger_targets = []
        for rule in extraction_result.get("trigger_rules", {}).get("trigger_rules", []):
            for target in rule.get("activates", {}).get("targets", []):
                trigger_targets.append({
                    "trigger_name": rule.get("name", ""),
                    "target_name": target.get("target_name", ""),
                    "target_type": target.get("target_type", ""),
                })
        trigger_targets_str = json.dumps(trigger_targets, ensure_ascii=False, indent=2)

        orphan_str = json.dumps(orphans, ensure_ascii=False, indent=2)

        prompt = ORPHAN_RESOLVER.format(
            stem=stem,
            answer=answer,
            knowledge_units=ku,
            orphan_refs=orphan_str,
            trigger_targets=trigger_targets_str,
        )

        logger.info("Running OrphanReferenceResolver for %d orphans", len(orphans))
        messages = [[{"role": "user", "content": prompt}]]

        raw = await self.llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=False,
        )
        result = raw[0] if raw else None

        if result is None:
            logger.warning("OrphanReferenceResolver JSON parse failed")
            return {
                "resolutions": [],
                "suggested_p2_additions": [],
                "orphan_count": len(orphans),
                "error": "JSON parse failed",
            }

        result["orphan_count"] = len(orphans)
        logger.info(
            "OrphanReferenceResolver: %d orphans → %d new_knowledge, %d new_mechanism, %d map_to_existing, %d uncertain",
            len(orphans),
            sum(1 for r in result.get("resolutions", []) if r.get("verdict") == "new_knowledge"),
            sum(1 for r in result.get("resolutions", []) if r.get("verdict") == "new_mechanism"),
            sum(1 for r in result.get("resolutions", []) if r.get("verdict") == "map_to_existing"),
            sum(1 for r in result.get("resolutions", []) if r.get("verdict") == "uncertain"),
        )
        return result

    @staticmethod
    def apply_resolutions(
        extraction_result: Dict[str, Any],
        resolution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply resolved nodes back into extraction_result. Returns modified copy."""
        import copy
        result = copy.deepcopy(extraction_result)
        ku = result.get("knowledge_units", {})

        for r in resolution.get("resolutions", []):
            verdict = r.get("verdict", "")
            node = r.get("candidate_node")
            if not node:
                continue

            if verdict == "new_knowledge" and "knowledge_units" in ku:
                ku["knowledge_units"].append({
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "subtype": node.get("subtype", "term"),
                    "subject": node.get("subject", ""),
                })
            elif verdict == "new_mechanism" and "mechanisms" in ku:
                ku["mechanisms"].append({
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "affects_what": "",
                    "common_misunderstanding": "",
                    "subject": node.get("subject", ""),
                })

        return result


# ---------------------------------------------------------------------------
# LinkRepairer
# ---------------------------------------------------------------------------

class LinkRepairer:
    """Rewrites P3 trigger targets and P4 pattern required_knowledge to use
    canonical names from OrphanReferenceResolver resolutions and retargets."""

    def __init__(self):
        self._repairs: List[Dict[str, str]] = []

    def repair(
        self,
        extraction_result: Dict[str, Any],
        resolution: Dict[str, Any],
    ) -> Dict[str, Any]:
        import copy
        result = copy.deepcopy(extraction_result)

        # Build rename map: orphan_name → canonical_name
        rename_map: Dict[str, str] = {}
        for r in resolution.get("resolutions", []):
            orphan_name = r.get("orphan_name", "")
            canonical = r.get("canonical_name", "")
            map_target = r.get("map_target", "")
            verdict = r.get("verdict", "")

            if verdict == "map_to_existing" and map_target:
                rename_map[orphan_name] = map_target
            elif canonical and verdict in ("new_knowledge", "new_mechanism"):
                rename_map[orphan_name] = canonical

        # Rewrite P4 pattern required_knowledge
        for step in result.get("reasoning_pattern", {}).get("steps", []):
            new_req = []
            for req in step.get("required_knowledge", []):
                if req in rename_map:
                    new_req.append(rename_map[req])
                    self._repairs.append({
                        "path": f"reasoning_pattern.steps[{step.get('order', '?')}].required_knowledge",
                        "old": req,
                        "new": rename_map[req],
                    })
                else:
                    new_req.append(req)
            step["required_knowledge"] = new_req

        # Build retarget map from resolver output
        retarget_map: Dict[str, Dict[str, str]] = {}
        for rt in resolution.get("retargets", []):
            trigger_name = rt.get("trigger_name", "")
            retarget_map[trigger_name] = {
                "new_target_name": rt.get("new_target_name", ""),
                "new_target_type": rt.get("new_target_type", "mechanism"),
                "old_target_name": rt.get("old_target_name", ""),
            }

        # Rewrite P3 trigger targets
        for rule in result.get("trigger_rules", {}).get("trigger_rules", []):
            rule_name = rule.get("name", "")

            # Apply rename_map to existing targets
            for target in rule.get("activates", {}).get("targets", []):
                old_name = target.get("target_name", "")
                if old_name in rename_map:
                    target["target_name"] = rename_map[old_name]
                    self._repairs.append({
                        "path": f"trigger_rules.{rule_name}.target",
                        "old": old_name,
                        "new": rename_map[old_name],
                    })

            # Apply retargets (change target entirely)
            if rule_name in retarget_map:
                rt = retarget_map[rule_name]
                for target in rule.get("activates", {}).get("targets", []):
                    if target.get("target_name") == rt["old_target_name"]:
                        target["target_name"] = rt["new_target_name"]
                        target["target_type"] = rt["new_target_type"]
                        self._repairs.append({
                            "path": f"trigger_rules.{rule_name}.retarget",
                            "old": rt["old_target_name"],
                            "new": rt["new_target_name"],
                        })

        return result

    def summary(self) -> Dict[str, Any]:
        return {
            "total_repairs": len(self._repairs),
            "repairs": self._repairs,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> Optional[Dict]:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        if "```json" in raw:
            clean = raw.split("```json\n", 1)[1].rsplit("```", 1)[0]
        else:
            start, end = raw.find("{"), raw.rfind("}")
            clean = raw[start:end + 1] if start != -1 and end != -1 else raw
        return json.loads(clean)
    except (json.JSONDecodeError, IndexError, TypeError):
        return None
