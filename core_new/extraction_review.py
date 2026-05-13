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

from .extraction_prompts import PASS5_DOMAIN_CRITIC, ORPHAN_RESOLVER, DOMAIN_ISSUE_FIXER

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# P5a: RuleChecker
# ---------------------------------------------------------------------------

VALID_QUESTION_TYPES = {"单选题", "多选题", "判断题", "填空题", "综合题", "计算题", "简答题"}
VALID_TARGET_TYPES = {"knowledge", "mechanism", "reasoning_pattern"}
VALID_READINESS_STATUSES = {
    "candidate",
    "needs_content_fix",
    "needs_link_fix",
    "auto_fixed_recheck_passed",
    "auto_fixed_recheck_failed",
    "auto_fix_partial",
    "needs_human_judgment",
    "rejected",
}
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

    def __init__(self, llm_provider, max_tokens: int = 10000, enable_thinking: bool = True):
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
        fix_result: Optional[Dict[str, Any]] = None,
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

        # Rule: answer inconsistent → needs_human_judgment
        ac = rule_validation.get("answer_consistency", {})
        if ac.get("checked") and not ac.get("consistent", True):
            status = "needs_human_judgment"
            reasons.append(f"Answer inconsistency: {ac.get('reason', '')}")
            requires_human = True

        # Rule: orphan references → needs_link_fix
        orphan = rule_validation.get("link_validation", {}).get("orphan_targets", [])
        if orphan:
            status = "needs_link_fix"
            reasons.append(f"{len(orphan)} orphan reference(s) in triggers/pattern")
            requires_human = True

        # Rule: type mismatches → needs_link_fix
        type_mismatches = rule_validation.get("link_validation", {}).get("type_mismatches", [])
        if type_mismatches:
            status = "needs_link_fix"
            for tm in type_mismatches:
                reasons.append(
                    f"Type mismatch: '{tm.get('target_name')}' typed as {tm.get('target_type')} "
                    f"but exists as {tm.get('actual_type')}"
                )
            requires_human = True

        # Domain issues: classify into fixable vs human-only
        fixable_count = 0
        human_only_count = 0
        if domain_review:
            dr = domain_review.get("domain_review", {})
            all_major = list(dr.get("major_issues", [])) + list(dr.get("minor_issues", []))
            for issue in all_major:
                cat = _classify_issue_fixability(issue)
                if cat == "auto_fixable":
                    fixable_count += 1
                elif cat == "human_only":
                    human_only_count += 1
                # "reject" issues are counted but don't affect status directly

            major = dr.get("major_issues", [])
            if major:
                for issue in major:
                    reasons.append(f"Domain: {issue.get('issue_type', '?')} — {issue.get('reason', '')[:100]}")
                requires_human = True

            if dr.get("minor_issues"):
                reasons.append(f"{len(dr['minor_issues'])} minor domain issue(s)")

            uncertain = dr.get("uncertain_items", [])
            if uncertain:
                status = "needs_human_judgment"
                reasons.append(f"{len(uncertain)} uncertain item(s) require human judgment")
                requires_human = True

        # Domain fixable issues → needs_content_fix (unless already higher priority)
        if fixable_count > 0 and status == "candidate":
            status = "needs_content_fix"
            reasons.append(f"{fixable_count} fixable domain issue(s)")

        # Domain human-only issues: set needs_human_judgment only if no fixable issues
        # (fixable issues will trigger fix loop first, then recheck may resolve or escalate)
        if human_only_count > 0 and status == "candidate":
            status = "needs_human_judgment"
            requires_human = True

        # If fix was applied, determine auto_fixed_* status from recheck results
        if fix_result and fix_result.get("fix_count", 0) > 0:
            reasons.append(f"Fix applied: {fix_result['fix_count']} patch(es)")

            # Evaluate recheck domain issues (these are from the re-review of patched data)
            recheck_fixable = fixable_count  # re-classified from recheck domain_review
            recheck_human = human_only_count
            recheck_major = 0
            if domain_review:
                recheck_major = len(domain_review.get("domain_review", {}).get("major_issues", []))

            if recheck_major == 0 and recheck_human == 0:
                status = "auto_fixed_recheck_passed"
            elif recheck_major == 0 and recheck_human > 0:
                status = "auto_fix_partial"
                requires_human = True
            else:
                status = "auto_fixed_recheck_failed"
                requires_human = True

        # Rule issues from RuleChecker
        issues = rule_validation.get("issues", [])
        if issues:
            status = "needs_human_judgment"
            reasons.extend(issues)
            requires_human = True

        return {
            "status": status,
            "requires_human_or_rule_check": requires_human,
            "requires_domain_recheck": bool(domain_review and domain_review.get("stale")),
            "fixable_issue_count": fixable_count,
            "human_only_issue_count": human_only_count,
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
# DomainIssueFixer: Path helpers and constants
# ---------------------------------------------------------------------------

FIXABLE_FIELD_PREFIXES = (
    "question_structure.distractor_analysis",
    "question_structure.correct_answer_diagnosis",
    "question_structure.structure.hidden_constraints",
    "question_structure.structure.unit_constraints",
    "trigger_rules.trigger_rules",
    "trigger_rules.negative_triggers",
    "knowledge_units.knowledge_units",
    "knowledge_units.mechanisms",
    "reasoning_pattern.steps",
    "reasoning_pattern.common_breakpoints",
)

PROTECTED_FIELD_PREFIXES = (
    "question_structure.correct_answer",
    "question_structure.options",
    "question_structure.stem",
    "question_structure.question_type",
    "raw_question",
)

HUMAN_ONLY_ISSUE_TYPES = frozenset({"answer_inconsistency"})

CHINESE_PREFIX_MAP = {
    "题目结构": "question_structure",
    "触发规则": "trigger_rules",
    "知识单元": "knowledge_units",
    "推理模式": "reasoning_pattern",
}

_TOP_LEVEL_KEYS = {"question_structure", "trigger_rules", "knowledge_units", "reasoning_pattern"}


def _parse_path(path: str) -> List:
    """Parse a dot/bracket notation path into segments.

    E.g. "question_structure.distractor_analysis[1].targeted_misconception"
         → ["question_structure", "distractor_analysis", 1, "targeted_misconception"]
    """
    import re
    segments: List = []
    for part in re.split(r'\.', path):
        if not part:
            continue
        idx_match = re.match(r'^(\w+)((?:\[\d+\])*)$', part)
        if idx_match:
            segments.append(idx_match.group(1))
            for idx_str in re.findall(r'\[(\d+)\]', idx_match.group(2)):
                segments.append(int(idx_str))
        else:
            segments.append(part)
    return segments


def _normalize_path(path: str) -> str:
    """Normalize evidence_path: replace Chinese prefixes, add top-level key if missing."""
    # Replace Chinese prefixes
    for cn, en in CHINESE_PREFIX_MAP.items():
        if path.startswith(cn + ".") or path.startswith(cn + "["):
            path = en + path[len(cn):]
            break

    # Strip misleading "structure." prefix when it refers to question_structure
    # DomainCritic sometimes outputs "structure.distractor_analysis" meaning "question_structure.distractor_analysis"
    _qs_subfields = {
        "distractor_analysis", "correct_answer_diagnosis", "asked_target",
        "question_type", "stem", "options", "correct_answer",
    }
    if path.startswith("structure."):
        second = path.split(".")[1].split("[")[0]
        if second in _qs_subfields:
            path = path[len("structure."):]

    # Add top-level key prefix if missing
    first_segment = path.split(".")[0].split("[")[0]
    if first_segment in _TOP_LEVEL_KEYS:
        return path  # Already has correct prefix

    # Map bare field names to their top-level container
    bare_to_toplevel = {
        "distractor_analysis": "question_structure",
        "correct_answer_diagnosis": "question_structure",
        "structure": "question_structure",  # structure.hidden_constraints etc.
        "asked_target": "question_structure",
        "trigger_rules": "trigger_rules",
        "negative_triggers": "trigger_rules",
        "knowledge_units": "knowledge_units",
        "mechanisms": "knowledge_units",
        "steps": "reasoning_pattern",
        "common_breakpoints": "reasoning_pattern",
        "question": "question_structure",
    }
    if first_segment in bare_to_toplevel:
        path = bare_to_toplevel[first_segment] + "." + path

    return path


def _resolve_path(data: Dict, path: str):
    """Navigate nested dict/list by path. Returns (value, found)."""
    segments = _parse_path(path)
    obj = data
    for seg in segments:
        try:
            if isinstance(seg, int):
                if not isinstance(obj, list) or seg >= len(obj):
                    return None, False
                obj = obj[seg]
            elif isinstance(obj, dict):
                if seg not in obj:
                    return None, False
                obj = obj[seg]
            else:
                return None, False
        except (KeyError, IndexError, TypeError):
            return None, False
    return obj, True


def _is_fixable_path(path: str) -> bool:
    """Check if a normalized path targets a fixable field (not protected)."""
    normalized = _normalize_path(path)
    for prefix in PROTECTED_FIELD_PREFIXES:
        if normalized.startswith(prefix):
            return False
    for prefix in FIXABLE_FIELD_PREFIXES:
        if normalized.startswith(prefix):
            return True
    return False


def _classify_issue_fixability(issue: Dict) -> str:
    """Classify a domain issue as 'auto_fixable', 'human_only', or 'reject'."""
    if issue.get("suggested_action") == "reject":
        return "reject"
    if issue.get("issue_type") in HUMAN_ONLY_ISSUE_TYPES:
        return "human_only"

    path = issue.get("evidence_path", "")
    if not path:
        return "human_only"
    # Multi-path (comma-separated) → too complex
    if "," in path:
        return "human_only"

    normalized = _normalize_path(path)
    if _is_fixable_path(normalized):
        return "auto_fixable"
    return "human_only"


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


# ---------------------------------------------------------------------------
# DomainIssueFixer: LLM-based localized patch fixer
# ---------------------------------------------------------------------------

class DomainIssueFixer:
    """Fixes domain issues via localized patches (not full rewrites).

    Takes extraction_result + domain_issues, calls LLM to generate patches,
    validates each patch (field permission, path existence, old_value match),
    and applies only validated patches. Max 1 fix iteration.
    """

    def __init__(self, llm_provider, max_tokens: int = 8192):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    async def fix(
        self,
        extraction_result: Dict[str, Any],
        domain_issues: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Identify fixable issues, call LLM for patches, validate, and apply.

        Returns:
            {patches_applied, patches_rejected, patches_skipped,
             fixed_result, fix_count}
        """
        fixable = self._classify_fixable_issues(domain_issues)
        if not fixable:
            return {
                "patches_applied": [],
                "patches_rejected": [],
                "patches_skipped": [],
                "fixed_result": extraction_result,
                "fix_count": 0,
            }

        question = extraction_result.get("raw_question", {})
        stem = question.get("prompt", "")
        answer = question.get("answer", "")
        fixable_data = self._build_fixable_data(extraction_result)
        issues_json = json.dumps(fixable, ensure_ascii=False, indent=1)

        prompt = DOMAIN_ISSUE_FIXER.format(
            stem=stem,
            answer=answer,
            fixable_data=fixable_data,
            issues=issues_json,
        )

        logger.info("Running DomainIssueFixer for %d fixable issues", len(fixable))
        messages = [[{"role": "user", "content": prompt}]]
        raw = await self.llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=False,
        )
        result = raw[0] if raw else None

        if result is None:
            logger.warning("DomainIssueFixer: LLM returned no result")
            return {
                "patches_applied": [],
                "patches_rejected": [],
                "patches_skipped": [],
                "fixed_result": extraction_result,
                "fix_count": 0,
            }

        patches = result.get("patches", [])
        skipped = result.get("skipped", [])

        applied, rejected = [], []
        for patch in patches:
            valid, reason = self._validate_patch(extraction_result, patch)
            if valid:
                applied.append(patch)
            else:
                rejected.append({**patch, "rejection_reason": reason})

        fixed = self.apply_patches(extraction_result, applied) if applied else extraction_result

        logger.info(
            "DomainIssueFixer: %d applied, %d rejected, %d skipped",
            len(applied), len(rejected), len(skipped),
        )

        return {
            "patches_applied": applied,
            "patches_rejected": rejected,
            "patches_skipped": skipped,
            "fixed_result": fixed,
            "fix_count": len(applied),
        }

    def _classify_fixable_issues(self, domain_issues: Dict[str, Any]) -> List[Dict]:
        """Filter domain issues to those safe for auto-fix."""
        dr = domain_issues.get("domain_review", {})
        all_issues = list(dr.get("major_issues", [])) + list(dr.get("minor_issues", []))
        fixable = []
        for issue in all_issues:
            if not isinstance(issue, dict):
                continue
            category = _classify_issue_fixability(issue)
            if category == "auto_fixable":
                fixable.append(issue)
        return fixable

    def _build_fixable_data(self, extraction_result: Dict[str, Any]) -> str:
        """Serialize only fixable top-level fields for the LLM prompt."""
        fixable = {}
        qs = extraction_result.get("question_structure", {})
        if "distractor_analysis" in qs:
            fixable["question_structure.distractor_analysis"] = qs["distractor_analysis"]
        if "correct_answer_diagnosis" in qs:
            fixable["question_structure.correct_answer_diagnosis"] = qs["correct_answer_diagnosis"]
        struct = qs.get("structure", {})
        if "hidden_constraints" in struct:
            fixable["question_structure.structure.hidden_constraints"] = struct["hidden_constraints"]
        if "unit_constraints" in struct:
            fixable["question_structure.structure.unit_constraints"] = struct["unit_constraints"]

        tr = extraction_result.get("trigger_rules", {})
        if "trigger_rules" in tr:
            fixable["trigger_rules.trigger_rules"] = tr["trigger_rules"]
        if "negative_triggers" in tr:
            fixable["trigger_rules.negative_triggers"] = tr["negative_triggers"]

        ku = extraction_result.get("knowledge_units", {})
        if "knowledge_units" in ku:
            fixable["knowledge_units.knowledge_units"] = ku["knowledge_units"]
        if "mechanisms" in ku:
            fixable["knowledge_units.mechanisms"] = ku["mechanisms"]

        rp = extraction_result.get("reasoning_pattern", {})
        if "steps" in rp:
            fixable["reasoning_pattern.steps"] = rp["steps"]
        if "common_breakpoints" in rp:
            fixable["reasoning_pattern.common_breakpoints"] = rp["common_breakpoints"]

        return json.dumps(fixable, ensure_ascii=False, indent=1)

    def _validate_patch(
        self,
        extraction_result: Dict[str, Any],
        patch: Dict[str, Any],
    ) -> tuple:
        """Validate a single patch. Returns (is_valid, reason)."""
        path = patch.get("path", "")
        if not path:
            return False, "empty path"

        normalized = _normalize_path(path)

        # Check: field is not protected
        for prefix in PROTECTED_FIELD_PREFIXES:
            if normalized.startswith(prefix):
                return False, f"protected field: {prefix}"

        # Check: field is in fixable list
        if not _is_fixable_path(normalized):
            return False, f"not in fixable field list"

        # Check: path resolves
        current, found = _resolve_path(extraction_result, normalized)
        if not found:
            return False, f"path not found: {normalized}"

        # Check: old_value fuzzy match
        old_value = patch.get("old_value", "")
        if not old_value:
            return True, "ok (no old_value to verify)"

        if isinstance(current, str):
            old_str = str(old_value)
            if len(old_str) > 20:
                # For long strings, use substring or fuzzy match
                if old_str in current or current in old_str:
                    return True, "ok (substring match)"
                ratio = SequenceMatcher(None, old_str, current).ratio()
                if ratio >= FUZZY_MATCH_THRESHOLD:
                    return True, f"ok (fuzzy match {ratio:.2f})"
                return False, f"old_value mismatch (ratio={ratio:.2f})"
            else:
                if old_str.strip() == current.strip():
                    return True, "ok (exact match)"
                ratio = SequenceMatcher(None, old_str, current).ratio()
                if ratio >= FUZZY_MATCH_THRESHOLD:
                    return True, f"ok (fuzzy match {ratio:.2f})"
                return False, f"old_value mismatch (ratio={ratio:.2f})"

        return True, "ok (non-string field)"

    @staticmethod
    def apply_patches(
        extraction_result: Dict[str, Any],
        validated_patches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Apply validated patches to a deep copy of extraction_result."""
        import copy
        result = copy.deepcopy(extraction_result)

        for patch in validated_patches:
            path = _normalize_path(patch["path"])
            new_value = patch["new_value"]
            segments = _parse_path(path)

            if not segments:
                continue

            obj = result
            for seg in segments[:-1]:
                if isinstance(seg, int):
                    obj = obj[seg]
                else:
                    obj = obj[seg]

            final = segments[-1]
            if isinstance(final, int):
                obj[final] = new_value
            else:
                obj[final] = new_value

        return result
