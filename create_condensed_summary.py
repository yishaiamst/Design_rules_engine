#!/usr/bin/env python3
"""
Create a condensed version of design_intent_summary.json for ChatGPT upload.
Removes verbose supporting_metrics and keeps only essential fields.
"""

import json
from collections import defaultdict

def create_condensed_summary(input_file: str = "design_intent_summary.json",
                             output_file: str = "design_intent_summary_condensed.json",
                             max_samples_per_pattern: int = 100):
    """Create condensed version of design intent summary."""
    
    print(f"Loading {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"  Original size: {len(json.dumps(data)) / 1024 / 1024:.1f} MB")
    
    # Condense each intent - keep only essential fields
    condensed_intents = []
    pattern_counts = defaultdict(int)
    
    for intent in data.get("design_intents", []):
        pattern_id = intent.get("pattern_id", "UNKNOWN")
        pattern_counts[pattern_id] += 1
        
        # Create condensed version
        condensed = {
            "node_id": intent.get("node_id"),
            "layer": intent.get("layer"),
            "pattern_id": pattern_id,
            "design_rationale": intent.get("design_rationale"),
            "textual_explanation": intent.get("textual_explanation"),
            "confidence_score": intent.get("confidence_score"),
        }
        
        # Keep only key metrics from supporting_data (not full supporting_metrics)
        supporting_data = intent.get("supporting_data", {})
        if supporting_data:
            condensed["key_metrics"] = {
                "downstream_onts": intent.get("supporting_metrics", {}).get("downstream_onts"),
                "avg_drop_length_m": intent.get("supporting_metrics", {}).get("avg_drop_length"),
                "avg_stub_length_m": intent.get("supporting_metrics", {}).get("avg_stub_length"),
                "path_length_to_olt_m": intent.get("supporting_metrics", {}).get("path_length_to_olt"),
            }
            # Add pattern-specific metrics
            if "fiber_connections" in supporting_data:
                condensed["key_metrics"]["fiber_connections"] = supporting_data.get("fiber_connections")
            if "stub_distance_m" in supporting_data:
                condensed["key_metrics"]["stub_distance_m"] = supporting_data.get("stub_distance_m")
            if "connected_fosc" in supporting_data:
                condensed["key_metrics"]["connected_fosc"] = supporting_data.get("connected_fosc")
            if "connected_fdh" in supporting_data:
                condensed["key_metrics"]["connected_fdh"] = supporting_data.get("connected_fdh")
        
        # Keep rule references (usually small)
        rule_refs = intent.get("rule_references", [])
        if rule_refs:
            condensed["rule_references"] = rule_refs
        
        condensed_intents.append(condensed)
    
    # Create condensed summary
    condensed_data = {
        "metadata": data.get("metadata", {}),
        "design_intents": condensed_intents,
        "template_clusters": data.get("template_clusters", {}),
        "template_summaries": data.get("template_summaries", {})
    }
    
    # Save condensed version
    print(f"\nSaving condensed version to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(condensed_data, f, indent=2)
    
    condensed_size = len(json.dumps(condensed_data)) / 1024 / 1024
    print(f"  Condensed size: {condensed_size:.1f} MB")
    print(f"  Reduction: {(1 - condensed_size / (len(json.dumps(data)) / 1024 / 1024)) * 100:.1f}%")
    print(f"  Total intents: {len(condensed_intents)}")
    
    # Create sample version (limited samples per pattern)
    if max_samples_per_pattern > 0:
        sample_file = output_file.replace(".json", "_sample.json")
        print(f"\nCreating sample version with max {max_samples_per_pattern} samples per pattern...")
        
        pattern_samples = defaultdict(list)
        for intent in condensed_intents:
            pattern_id = intent.get("pattern_id", "UNKNOWN")
            if len(pattern_samples[pattern_id]) < max_samples_per_pattern:
                pattern_samples[pattern_id].append(intent)
        
        sample_intents = []
        for pattern_intents in pattern_samples.values():
            sample_intents.extend(pattern_intents)
        
        sample_data = {
            "metadata": {
                **data.get("metadata", {}),
                "note": f"Sample version with max {max_samples_per_pattern} examples per pattern",
                "total_samples": len(sample_intents)
            },
            "design_intents": sample_intents,
            "template_clusters": data.get("template_clusters", {}),
            "template_summaries": data.get("template_summaries", {})
        }
        
        with open(sample_file, "w", encoding="utf-8") as f:
            json.dump(sample_data, f, indent=2)
        
        sample_size = len(json.dumps(sample_data)) / 1024 / 1024
        print(f"  Sample size: {sample_size:.1f} MB")
        print(f"  Sample intents: {len(sample_intents)}")
        print(f"  ✓ Saved {sample_file}")
    
    print(f"\n✓ Saved {output_file}")
    print(f"\nPattern distribution:")
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count}")


if __name__ == "__main__":
    create_condensed_summary()





