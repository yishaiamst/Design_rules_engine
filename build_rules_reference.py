#!/usr/bin/env python3
"""
build_rules_reference.py
-------------------------------------------------------------------------------
Consolidated Rule Reference Generator
-------------------------------------------------------------------------------
Automatically generates a consolidated rule reference from all available 
design-analysis outputs.

Input files:
- design_intent_summary_condensed.json
- design_templates.txt
- placement_rules_analysis.json
- adaptive_rules_summary.json
- mst_long_reach_comparison.json
- rules_summary.txt

Outputs:
- design_rules_reference.json (machine-readable)
- rules_summary_full.txt (human-readable)
-------------------------------------------------------------------------------
"""

import json
import re
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional, Set


# ============================================================================
# RULE PARSING FUNCTIONS
# ============================================================================

def parse_placement_rules_analysis(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parse placement_rules_analysis.json and extract rules."""
    rules = {}
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        placement_analyses = data.get("placement_analyses", [])
        
        for analysis in placement_analyses:
            rule_id = analysis.get("rule_id")
            if not rule_id:
                continue
            
            if rule_id not in rules:
                rules[rule_id] = {
                    "rule_id": rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": set(),
                    "validation_criteria": [],
                    "source_files": ["placement_rules_analysis.json"]
                }
            
            # Collect description
            desc = analysis.get("rule_description")
            if desc and desc not in rules[rule_id]["descriptions"]:
                rules[rule_id]["descriptions"].append(desc)
            
            # Collect confidence
            conf = analysis.get("confidence_score")
            if conf is not None:
                rules[rule_id]["confidence_scores"].append(conf)
            
            # Collect example node
            node_id = analysis.get("node_id")
            if node_id:
                rules[rule_id]["examples"].append(node_id)
            
            # Collect layer
            layer = analysis.get("layer")
            if layer:
                rules[rule_id]["applies_to"].add(layer)
            
            # Collect validation criteria from supporting_data
            supporting = analysis.get("supporting_data", {})
            if supporting:
                conditions = supporting.get("rule_conditions_met", [])
                for condition in conditions:
                    if condition not in rules[rule_id]["validation_criteria"]:
                        rules[rule_id]["validation_criteria"].append(condition)
    
    except FileNotFoundError:
        print(f"  ⚠ {filepath} not found")
    except Exception as e:
        print(f"  ⚠ Error parsing {filepath}: {e}")
    
    return rules


def parse_adaptive_rules_summary(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parse adaptive_rules_summary.json and extract rules."""
    rules = {}
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Extract adaptive thresholds
        thresholds = data.get("adaptive_thresholds", {})
        for rule_id_base, threshold_data in thresholds.items():
            # Create adaptive rule ID
            adaptive_rule_id = f"{rule_id_base}_ADAPTIVE"
            
            if adaptive_rule_id not in rules:
                rules[adaptive_rule_id] = {
                    "rule_id": adaptive_rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": set(),
                    "validation_criteria": [],
                    "thresholds": threshold_data,
                    "source_files": ["adaptive_rules_summary.json"]
                }
            
            # Determine layer from rule ID
            if "TERMINAL" in rule_id_base:
                rules[adaptive_rule_id]["applies_to"].add("terminal")
            elif "FOSC" in rule_id_base:
                rules[adaptive_rule_id]["applies_to"].add("splice closure")
            
            # Extract validation criteria from thresholds
            criteria = []
            if "ont_count_min" in threshold_data:
                criteria.append(f"ONT count: {threshold_data['ont_count_min']}-{threshold_data.get('ont_count_max', 'N/A')}")
            if "drop_length_max" in threshold_data:
                criteria.append(f"Max drop length: ≤{threshold_data['drop_length_max']}m")
            if "stub_length_max" in threshold_data:
                criteria.append(f"Max stub length: ≤{threshold_data['stub_length_max']}m")
            if "fiber_connections_min" in threshold_data:
                criteria.append(f"Min fiber connections: ≥{threshold_data['fiber_connections_min']}")
            if "fiber_length_threshold" in threshold_data:
                criteria.append(f"Fiber length threshold: ≥{threshold_data['fiber_length_threshold']}m")
            
            rules[adaptive_rule_id]["validation_criteria"].extend(criteria)
        
        # Extract results summary
        results = data.get("results_summary", {})
        avg_confidence = results.get("avg_confidence_by_rule", {})
        
        for rule_id, conf in avg_confidence.items():
            if rule_id not in rules:
                rules[rule_id] = {
                    "rule_id": rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": set(),
                    "validation_criteria": [],
                    "source_files": ["adaptive_rules_summary.json"]
                }
            
            if conf is not None:
                rules[rule_id]["confidence_scores"].append(conf)
        
        # Extract long-reach MST rule
        if "R11_MST_LONG_REACH" in avg_confidence:
            rule_id = "R11_MST_LONG_REACH"
            if rule_id not in rules:
                rules[rule_id] = {
                    "rule_id": rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": {"terminal"},
                    "validation_criteria": ["Stub length: 500-2500m", "ONT count: 6-48"],
                    "source_files": ["adaptive_rules_summary.json"]
                }
            if avg_confidence[rule_id] is not None:
                rules[rule_id]["confidence_scores"].append(avg_confidence[rule_id])
    
    except FileNotFoundError:
        print(f"  ⚠ {filepath} not found")
    except Exception as e:
        print(f"  ⚠ Error parsing {filepath}: {e}")
    
    return rules


def parse_mst_long_reach_comparison(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parse mst_long_reach_comparison.json and extract rules."""
    rules = {}
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Extract long-reach rule info
        after_data = data.get("after", {})
        rule_id = after_data.get("rule_id", "R11_MST_LONG_REACH")
        
        if rule_id not in rules:
            rules[rule_id] = {
                "rule_id": rule_id,
                "descriptions": [],
                "confidence_scores": [],
                "examples": [],
                "applies_to": {"terminal"},
                "validation_criteria": [],
                "source_files": ["mst_long_reach_comparison.json"]
            }
        
        # Add description
        desc = f"MST Long-Reach: Stub length 500-2500m from FOSC, serving 6-48 ONTs"
        if desc not in rules[rule_id]["descriptions"]:
            rules[rule_id]["descriptions"].append(desc)
        
        # Add confidence
        conf = after_data.get("avg_confidence")
        if conf is not None:
            rules[rule_id]["confidence_scores"].append(conf)
        
        # Add validation criteria
        stub_max = after_data.get("max_stub_threshold")
        if stub_max:
            rules[rule_id]["validation_criteria"].append(f"Max stub length: ≤{stub_max}m")
    
    except FileNotFoundError:
        print(f"  ⚠ {filepath} not found")
    except Exception as e:
        print(f"  ⚠ Error parsing {filepath}: {e}")
    
    return rules


def parse_rules_summary_txt(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parse rules_summary.txt and extract rules."""
    rules = {}
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Pattern to match rule blocks
        # Format: [RULE_ID] followed by Description, Status, Confidence
        rule_pattern = r'\[([^\]]+)\]\s*\n\s*Description:\s*([^\n]+)\s*\n\s*Status:\s*([^\n]+)\s*\n\s*Confidence:\s*([^\n]+)'
        
        matches = re.finditer(rule_pattern, content, re.MULTILINE)
        
        for match in matches:
            rule_id = match.group(1).strip()
            description = match.group(2).strip()
            status = match.group(3).strip()
            confidence_str = match.group(4).strip()
            
            # Extract confidence score
            conf_match = re.search(r'(\d+\.?\d*)', confidence_str)
            confidence = float(conf_match.group(1)) if conf_match else 0.85
            
            if rule_id not in rules:
                rules[rule_id] = {
                    "rule_id": rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": set(),
                    "validation_criteria": [],
                    "source_files": ["rules_summary.txt"]
                }
            
            if description not in rules[rule_id]["descriptions"]:
                rules[rule_id]["descriptions"].append(description)
            
            rules[rule_id]["confidence_scores"].append(confidence)
            
            # Infer layer from rule ID
            if "ONT" in rule_id or "TERMINAL" in rule_id:
                rules[rule_id]["applies_to"].add("terminal")
            if "ONT" in rule_id:
                rules[rule_id]["applies_to"].add("ont")
            if "FOSC" in rule_id or "SPLICE" in rule_id:
                rules[rule_id]["applies_to"].add("splice closure")
            if "FDH" in rule_id:
                rules[rule_id]["applies_to"].add("fdh")
            if "OLT" in rule_id:
                rules[rule_id]["applies_to"].add("olt")
        
        # Parse refined rules section (R10-R14)
        refined_pattern = r'\[([^\]]+)\]\s*\n\s*Description:\s*([^\n]+)\s*\n\s*Nodes Analyzed:\s*(\d+)\s*\n\s*Matches Criteria:\s*([^\n]+)\s*\n\s*Average Confidence:\s*([^\n]+)'
        refined_matches = re.finditer(refined_pattern, content, re.MULTILINE)
        
        for match in refined_matches:
            rule_id = match.group(1).strip()
            description = match.group(2).strip()
            nodes_analyzed = match.group(3).strip()
            matches_criteria = match.group(4).strip()
            conf_str = match.group(5).strip()
            
            conf_match = re.search(r'(\d+\.?\d*)', conf_str)
            confidence = float(conf_match.group(1)) if conf_match else 0.85
            
            if rule_id not in rules:
                rules[rule_id] = {
                    "rule_id": rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": set(),
                    "validation_criteria": [],
                    "source_files": ["rules_summary.txt"]
                }
            
            if description not in rules[rule_id]["descriptions"]:
                rules[rule_id]["descriptions"].append(description)
            
            rules[rule_id]["confidence_scores"].append(confidence)
            
            # Infer layer
            if "TERMINAL" in rule_id or "MST" in rule_id:
                rules[rule_id]["applies_to"].add("terminal")
            if "FOSC" in rule_id:
                rules[rule_id]["applies_to"].add("splice closure")
            if "FDH" in rule_id:
                rules[rule_id]["applies_to"].add("fdh")
            
            # Add validation info from description
            if "≤" in description or "≥" in description:
                rules[rule_id]["validation_criteria"].append(description)
        
        # Parse connectivity rules
        connectivity_pattern = r'\[([^\]]+)\]\s*\n\s*Description:\s*([^\n]+)\s*\n\s*Status:\s*([^\n]+)\s*\n\s*Confidence:\s*([^\n]+)'
        # Already handled above
        
    except FileNotFoundError:
        print(f"  ⚠ {filepath} not found")
    except Exception as e:
        print(f"  ⚠ Error parsing {filepath}: {e}")
    
    return rules


def parse_design_templates_txt(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parse design_templates.txt and extract pattern rules."""
    rules = {}
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Pattern to match template blocks
        # Format: [PATTERN_ID] followed by Description, Instance Count, Average Confidence
        pattern = r'\[([^\]]+)\]\s*\n\s*Description:\s*([^\n]+)\s*\n\s*Instance Count:\s*(\d+)\s*\n\s*Average Confidence:\s*([^\n]+)'
        
        matches = re.finditer(pattern, content, re.MULTILINE)
        
        for match in matches:
            pattern_id = match.group(1).strip()
            description = match.group(2).strip()
            instance_count = match.group(3).strip()
            conf_str = match.group(4).strip()
            
            conf_match = re.search(r'(\d+\.?\d*)', conf_str)
            confidence = float(conf_match.group(1)) if conf_match else 0.85
            
            # Convert pattern to rule ID
            rule_id = f"PATTERN_{pattern_id}"
            
            if rule_id not in rules:
                rules[rule_id] = {
                    "rule_id": rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": set(),
                    "validation_criteria": [],
                    "source_files": ["design_templates.txt"]
                }
            
            if description not in rules[rule_id]["descriptions"]:
                rules[rule_id]["descriptions"].append(description)
            
            rules[rule_id]["confidence_scores"].append(confidence)
            
            # Infer layer from pattern ID
            if "ONT" in pattern_id:
                rules[rule_id]["applies_to"].add("ont")
            if "TERMINAL" in pattern_id or "AERIAL" in pattern_id or "MST" in pattern_id:
                rules[rule_id]["applies_to"].add("terminal")
            if "FOSC" in pattern_id or "SPLICE" in pattern_id:
                rules[rule_id]["applies_to"].add("splice closure")
            if "FDH" in pattern_id:
                rules[rule_id]["applies_to"].add("fdh")
            if "OLT" in pattern_id:
                rules[rule_id]["applies_to"].add("olt")
    
    except FileNotFoundError:
        print(f"  ⚠ {filepath} not found")
    except Exception as e:
        print(f"  ⚠ Error parsing {filepath}: {e}")
    
    return rules


def parse_design_intent_summary(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parse design_intent_summary_condensed.json and extract rules from patterns."""
    rules = {}
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Extract rules from design intents (via pattern_id)
        design_intents = data.get("design_intents", [])
        
        for intent in design_intents:
            pattern_id = intent.get("pattern_id")
            if not pattern_id:
                continue
            
            rule_id = f"PATTERN_{pattern_id}"
            
            if rule_id not in rules:
                rules[rule_id] = {
                    "rule_id": rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": set(),
                    "validation_criteria": [],
                    "source_files": ["design_intent_summary_condensed.json"]
                }
            
            # Collect description
            rationale = intent.get("design_rationale")
            explanation = intent.get("textual_explanation")
            if rationale and rationale not in rules[rule_id]["descriptions"]:
                rules[rule_id]["descriptions"].append(rationale)
            if explanation:
                # Extract key info from explanation
                rules[rule_id]["examples"].append(intent.get("node_id"))
            
            # Collect confidence
            conf = intent.get("confidence_score")
            if conf is not None:
                rules[rule_id]["confidence_scores"].append(conf)
            
            # Collect layer
            layer = intent.get("layer")
            if layer:
                rules[rule_id]["applies_to"].add(layer)
        
        # Extract from template summaries
        template_summaries = data.get("template_summaries", {})
        for pattern_id, summary in template_summaries.items():
            rule_id = f"PATTERN_{pattern_id}"
            
            if rule_id not in rules:
                rules[rule_id] = {
                    "rule_id": rule_id,
                    "descriptions": [],
                    "confidence_scores": [],
                    "examples": [],
                    "applies_to": set(),
                    "validation_criteria": [],
                    "source_files": ["design_intent_summary_condensed.json"]
                }
            
            desc = summary.get("description")
            if desc and desc not in rules[rule_id]["descriptions"]:
                rules[rule_id]["descriptions"].append(desc)
            
            avg_conf = summary.get("average_confidence")
            if avg_conf is not None:
                rules[rule_id]["confidence_scores"].append(avg_conf)
    
    except FileNotFoundError:
        print(f"  ⚠ {filepath} not found")
    except Exception as e:
        print(f"  ⚠ Error parsing {filepath}: {e}")
    
    return rules


# ============================================================================
# RULE CONSOLIDATION
# ============================================================================

def consolidate_rules(all_rules: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Consolidate rules from all sources, merging duplicates."""
    consolidated = {}
    
    # First pass: collect all rules
    for rule_id, rule_data in all_rules.items():
        # Merge duplicates by keeping most complete entry
        if rule_id not in consolidated:
            consolidated[rule_id] = {
                "rule_id": rule_id,
                "category": infer_category(rule_id),
                "description": "",
                "applies_to": [],
                "validation_criteria": [],
                "examples": [],
                "confidence_score": None,
                "source_files": [],
                "thresholds": rule_data.get("thresholds")
            }
        
        # Merge descriptions (keep longest)
        descriptions = rule_data.get("descriptions", [])
        if descriptions:
            longest_desc = max(descriptions, key=len)
            if len(longest_desc) > len(consolidated[rule_id]["description"]):
                consolidated[rule_id]["description"] = longest_desc
        
        # Merge applies_to
        applies_to = rule_data.get("applies_to", set())
        consolidated[rule_id]["applies_to"].extend(list(applies_to))
        
        # Merge validation_criteria (deduplicate similar ones)
        criteria = rule_data.get("validation_criteria", [])
        for crit in criteria:
            # Check for similar criteria (normalize and compare)
            crit_normalized = crit.lower().strip()
            is_duplicate = False
            for existing in consolidated[rule_id]["validation_criteria"]:
                if crit_normalized == existing.lower().strip():
                    is_duplicate = True
                    break
            if not is_duplicate:
                consolidated[rule_id]["validation_criteria"].append(crit)
        
        # Merge examples (up to 3)
        examples = rule_data.get("examples", [])
        for ex in examples[:3]:
            if ex not in consolidated[rule_id]["examples"] and len(consolidated[rule_id]["examples"]) < 3:
                consolidated[rule_id]["examples"].append(ex)
        
        # Merge confidence scores (average)
        conf_scores = rule_data.get("confidence_scores", [])
        if conf_scores:
            existing_conf = consolidated[rule_id]["confidence_score"]
            if existing_conf is not None:
                conf_scores.append(existing_conf)
            consolidated[rule_id]["confidence_score"] = sum(conf_scores) / len(conf_scores)
        elif consolidated[rule_id]["confidence_score"] is None:
            consolidated[rule_id]["confidence_score"] = 0.85  # Default for text-only sources
        
        # Merge source files
        source_files = rule_data.get("source_files", [])
        for src in source_files:
            if src not in consolidated[rule_id]["source_files"]:
                consolidated[rule_id]["source_files"].append(src)
    
    # Second pass: generate descriptions for rules missing them, merge from related rules
    for rule_id, rule in consolidated.items():
        # If description is empty, try to generate from thresholds or related rules
        if not rule["description"]:
            # Try to find related rule (e.g., R10_AERIAL_TERMINAL_ADAPTIVE -> R10_AERIAL_TERMINAL_PLACEMENT)
            base_id = rule_id.replace("_ADAPTIVE", "").replace("_REFINED", "").replace("_PLACEMENT", "")
            
            # Look for related rule with description
            for other_id, other_rule in consolidated.items():
                if other_id != rule_id and base_id in other_id and other_rule.get("description"):
                    rule["description"] = other_rule["description"]
                    break
            
            # If still no description, generate from thresholds
            if not rule["description"] and rule.get("thresholds"):
                thresholds = rule["thresholds"]
                desc_parts = []
                
                if "ont_count_min" in thresholds and "ont_count_max" in thresholds:
                    desc_parts.append(f"Serves {thresholds['ont_count_min']}-{thresholds['ont_count_max']} ONTs")
                if "drop_length_max" in thresholds:
                    desc_parts.append(f"max drop length ≤{thresholds['drop_length_max']}m")
                if "stub_length_max" in thresholds:
                    desc_parts.append(f"stub length ≤{thresholds['stub_length_max']}m")
                if "fiber_connections_min" in thresholds:
                    desc_parts.append(f"≥{thresholds['fiber_connections_min']} fiber connections")
                
                if desc_parts:
                    rule["description"] = ", ".join(desc_parts)
                else:
                    rule["description"] = f"Adaptive version of {base_id}"
        
        # Limit validation criteria to avoid too many duplicates
        # Keep only unique general criteria, not specific instance values
        unique_criteria = []
        seen_patterns = set()
        for crit in rule["validation_criteria"]:
            # Extract pattern (remove specific numbers in parentheses)
            pattern = re.sub(r'\s*\([^)]+\)', '', crit)
            pattern_normalized = pattern.lower().strip()
            if pattern_normalized not in seen_patterns:
                seen_patterns.add(pattern_normalized)
                unique_criteria.append(crit)
        
        # Limit to top 10 most general criteria
        rule["validation_criteria"] = unique_criteria[:10]
    
    # Clean up applies_to (remove duplicates, sort)
    for rule in consolidated.values():
        rule["applies_to"] = sorted(list(set(rule["applies_to"])))
        # Remove thresholds from final output (not needed in reference)
        if "thresholds" in rule:
            del rule["thresholds"]
    
    # Convert to list and sort
    rule_list = list(consolidated.values())
    rule_list.sort(key=lambda x: (x["category"], x["rule_id"]))
    
    return rule_list


def infer_category(rule_id: str) -> str:
    """Infer rule category from rule ID."""
    rule_id_upper = rule_id.upper()
    
    if "CONNECTIVITY" in rule_id_upper or "HIERARCHY" in rule_id_upper:
        return "Connectivity & Hierarchy"
    elif "CABLE" in rule_id_upper or "TRANSITION" in rule_id_upper:
        return "Cable Management"
    elif "TERMINAL" in rule_id_upper or "AERIAL" in rule_id_upper or "MST" in rule_id_upper:
        return "Terminal Placement"
    elif "FOSC" in rule_id_upper or "SPLICE" in rule_id_upper:
        return "FOSC Placement"
    elif "FDH" in rule_id_upper:
        return "FDH Placement"
    elif "OLT" in rule_id_upper:
        return "OLT Placement"
    elif "PATTERN" in rule_id_upper:
        return "Design Patterns"
    elif "PLACEMENT" in rule_id_upper:
        return "Placement Logic"
    else:
        return "General Rules"


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_json_output(rules: List[Dict[str, Any]], output_file: str) -> None:
    """Generate design_rules_reference.json."""
    output = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_rules": len(rules),
        "rules": rules
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"  ✓ Saved {output_file}")


def generate_text_output(rules: List[Dict[str, Any]], output_file: str) -> None:
    """Generate rules_summary_full.txt."""
    output = "=" * 80 + "\n"
    output += "CONSOLIDATED DESIGN RULES REFERENCE\n"
    output += "=" * 80 + "\n\n"
    output += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    output += f"Total Rules: {len(rules)}\n\n"
    
    # Group by category
    by_category = defaultdict(list)
    for rule in rules:
        by_category[rule["category"]].append(rule)
    
    # Output by category
    for category in sorted(by_category.keys()):
        output += "=" * 80 + "\n"
        output += f"{category.upper()}\n"
        output += "=" * 80 + "\n\n"
        
        for rule in by_category[category]:
            output += f"[{rule['rule_id']}]\n"
            output += f"  Description: {rule['description']}\n"
            
            if rule['applies_to']:
                output += f"  Applies To: {', '.join(rule['applies_to'])}\n"
            
            if rule['validation_criteria']:
                output += f"  Validation Criteria:\n"
                for crit in rule['validation_criteria']:
                    output += f"    • {crit}\n"
            
            if rule['examples']:
                output += f"  Examples: {', '.join(rule['examples'][:3])}\n"
            
            if rule['confidence_score'] is not None:
                output += f"  Confidence: {rule['confidence_score']:.3f}\n"
            
            if rule['source_files']:
                output += f"  Sources: {', '.join(rule['source_files'])}\n"
            
            output += "\n"
    
    output += "=" * 80 + "\n"
    output += "END OF REFERENCE\n"
    output += "=" * 80 + "\n"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output)
    
    print(f"  ✓ Saved {output_file}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main execution pipeline."""
    print("=" * 80)
    print("CONSOLIDATED RULE REFERENCE GENERATOR")
    print("=" * 80)
    
    # Step 1: Parse all input files
    print("\nParsing input files...")
    all_rules = {}
    
    # Parse each source
    print("  Parsing placement_rules_analysis.json...")
    rules1 = parse_placement_rules_analysis("placement_rules_analysis.json")
    all_rules.update(rules1)
    print(f"    Found {len(rules1)} rules")
    
    print("  Parsing adaptive_rules_summary.json...")
    rules2 = parse_adaptive_rules_summary("adaptive_rules_summary.json")
    all_rules.update(rules2)
    print(f"    Found {len(rules2)} rules")
    
    print("  Parsing mst_long_reach_comparison.json...")
    rules3 = parse_mst_long_reach_comparison("mst_long_reach_comparison.json")
    all_rules.update(rules3)
    print(f"    Found {len(rules3)} rules")
    
    print("  Parsing rules_summary.txt...")
    rules4 = parse_rules_summary_txt("rules_summary.txt")
    all_rules.update(rules4)
    print(f"    Found {len(rules4)} rules")
    
    print("  Parsing design_templates.txt...")
    rules5 = parse_design_templates_txt("design_templates.txt")
    all_rules.update(rules5)
    print(f"    Found {len(rules5)} rules")
    
    print("  Parsing design_intent_summary_condensed.json...")
    rules6 = parse_design_intent_summary("design_intent_summary_condensed.json")
    all_rules.update(rules6)
    print(f"    Found {len(rules6)} rules")
    
    print(f"\n  Total unique rule IDs found: {len(all_rules)}")
    
    # Step 2: Consolidate rules
    print("\nConsolidating rules...")
    consolidated_rules = consolidate_rules(all_rules)
    print(f"  ✓ Consolidated {len(consolidated_rules)} rules")
    
    # Step 3: Generate outputs
    print("\nGenerating outputs...")
    generate_json_output(consolidated_rules, "design_rules_reference.json")
    generate_text_output(consolidated_rules, "rules_summary_full.txt")
    
    # Step 4: Print summary
    print("\n" + "=" * 80)
    print("✅ SUCCESS SUMMARY")
    print("=" * 80)
    
    # Count rules by category
    by_category = defaultdict(int)
    for rule in consolidated_rules:
        by_category[rule["category"]] += 1
    
    print(f"\n✅ {len(consolidated_rules)} rules consolidated from {6} sources")
    print("\nRules by category:")
    for cat in sorted(by_category.keys()):
        print(f"  {cat}: {by_category[cat]}")
    
    # File sizes
    import os
    json_size = os.path.getsize("design_rules_reference.json") / 1024
    txt_size = os.path.getsize("rules_summary_full.txt") / 1024
    
    print(f"\n📄 design_rules_reference.json ({json_size:.1f} KB)")
    print(f"📄 rules_summary_full.txt ({txt_size:.1f} KB)")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

