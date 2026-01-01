#!/usr/bin/env python3
"""
analyze_olt_distances.py
-------------------------------------------------------------------------------
Analyze OLT-to-ONT distances and establish OLT placement rules.
-------------------------------------------------------------------------------
"""

import json
from collections import defaultdict
from typing import Dict, List, Any
import statistics

def load_ont_paths(filepath: str = "olt_ont_paths.json") -> List[Dict[str, Any]]:
    """Load ONT paths."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if isinstance(data, list):
        paths = data
    else:
        paths = data.get("paths", [])
    
    print(f"  ✓ Loaded {len(paths)} paths")
    return paths


def analyze_olt_distances(paths: List[Dict[str, Any]], max_distance_km: float = 20.0) -> Dict[str, Any]:
    """Analyze OLT-to-ONT distances and identify violations."""
    print(f"\nAnalyzing OLT-to-ONT distances (max: {max_distance_km} km)...")
    
    max_distance_m = max_distance_km * 1000
    
    # Extract path lengths
    path_lengths = []
    olt_paths = defaultdict(list)
    violations = []
    
    for path in paths:
        ont_id = path.get("ont_id")
        olt_id = path.get("olt_id")
        total_length = path.get("total_length_m", 0)
        is_complete = path.get("complete", False)
        
        if is_complete and total_length > 0:
            path_lengths.append(total_length)
            olt_paths[olt_id].append({
                "ont_id": ont_id,
                "length_m": total_length,
                "path": path
            })
            
            if total_length > max_distance_m:
                violations.append({
                    "ont_id": ont_id,
                    "olt_id": olt_id,
                    "length_m": total_length,
                    "length_km": total_length / 1000,
                    "excess_km": (total_length - max_distance_m) / 1000
                })
    
    # Calculate statistics
    stats = {
        "total_paths": len(path_lengths),
        "max_distance_km": max_distance_km,
        "max_distance_m": max_distance_m,
        "violations": {
            "count": len(violations),
            "percentage": (len(violations) / len(path_lengths) * 100) if path_lengths else 0
        },
        "distance_statistics": {
            "mean_km": round(statistics.mean(path_lengths) / 1000, 2) if path_lengths else 0,
            "median_km": round(statistics.median(path_lengths) / 1000, 2) if path_lengths else 0,
            "min_km": round(min(path_lengths) / 1000, 2) if path_lengths else 0,
            "max_km": round(max(path_lengths) / 1000, 2) if path_lengths else 0,
            "p95_km": round(statistics.quantiles(path_lengths, n=20)[18] / 1000, 2) if len(path_lengths) >= 20 else 0,
            "p99_km": round(statistics.quantiles(path_lengths, n=100)[98] / 1000, 2) if len(path_lengths) >= 100 else 0
        },
        "olt_statistics": {}
    }
    
    # Analyze per-OLT
    for olt_id, olt_path_list in olt_paths.items():
        olt_lengths = [p["length_m"] for p in olt_path_list]
        olt_violations = [p for p in olt_path_list if p["length_m"] > max_distance_m]
        
        stats["olt_statistics"][olt_id] = {
            "ont_count": len(olt_path_list),
            "mean_distance_km": round(statistics.mean(olt_lengths) / 1000, 2) if olt_lengths else 0,
            "max_distance_km": round(max(olt_lengths) / 1000, 2) if olt_lengths else 0,
            "violations": len(olt_violations),
            "violation_percentage": (len(olt_violations) / len(olt_path_list) * 100) if olt_path_list else 0
        }
    
    return {
        "analysis": stats,
        "violations": violations[:100],  # Limit to first 100 for file size
        "violation_summary": {
            "total_violations": len(violations),
            "sample_count": min(100, len(violations))
        }
    }


def generate_olt_placement_rules(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate OLT placement rules based on analysis."""
    stats = analysis["analysis"]
    violations = analysis["violations"]
    
    # Calculate recommended OLT count based on violations
    # If many violations, suggest more OLTs
    violation_rate = stats["violations"]["percentage"] / 100
    
    rules = {
        "R15_OLT_MAX_DISTANCE": {
            "rule_id": "R15_OLT_MAX_DISTANCE",
            "category": "OLT Placement",
            "description": "Maximum path length from OLT to any ONT must not exceed 20 km",
            "applies_to": ["olt", "ont"],
            "validation_criteria": [
                "Path length from OLT to ONT ≤ 20,000 m",
                "All ONT paths must be complete (reach OLT)"
            ],
            "thresholds": {
                "max_distance_m": 20000,
                "max_distance_km": 20.0
            },
            "current_status": {
                "total_paths": stats["total_paths"],
                "violations": stats["violations"]["count"],
                "violation_percentage": round(stats["violations"]["percentage"], 2),
                "max_observed_km": stats["distance_statistics"]["max_km"],
                "p95_distance_km": stats["distance_statistics"]["p95_km"]
            },
            "confidence_score": 1.0,
            "source_files": ["olt_ont_paths.json"]
        },
        "R16_OLT_PLACEMENT_STRATEGY": {
            "rule_id": "R16_OLT_PLACEMENT_STRATEGY",
            "category": "OLT Placement",
            "description": "Place OLTs near large communities (≥2000 residential units) to minimize path lengths and optimize network topology",
            "applies_to": ["olt"],
            "validation_criteria": [
                "Cluster ONTs by proximity (2 km radius)",
                "If cluster ≥ 2000 ONTs → place OLT at cluster centroid",
                "If cluster < 2000 ONTs → assign to nearest OLT (within 20 km)",
                "Minimize maximum OLT-to-ONT distance"
            ],
            "thresholds": {
                "large_community_size": 2000,
                "cluster_radius_km": 2.0,
                "max_assignment_distance_km": 20.0
            },
            "recommendations": {
                "current_violation_rate": round(violation_rate, 3),
                "suggested_olt_count_increase": "Consider additional OLTs if violation rate > 5%",
                "placement_priority": "Place OLTs at centers of high-density ONT clusters"
            },
            "confidence_score": 0.9,
            "source_files": ["olt_ont_paths.json"]
        }
    }
    
    return rules


def main():
    """Main execution."""
    print("=" * 80)
    print("OLT DISTANCE ANALYSIS")
    print("=" * 80)
    
    # Load paths
    paths = load_ont_paths()
    
    # Analyze distances
    analysis = analyze_olt_distances(paths, max_distance_km=20.0)
    
    # Generate rules
    rules = generate_olt_placement_rules(analysis)
    
    # Save results
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    
    with open("olt_distance_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)
    print("  ✓ Saved olt_distance_analysis.json")
    
    with open("olt_placement_rules.json", "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.0",
            "generated_at": "2025-11-04",
            "rules": rules
        }, f, indent=2)
    print("  ✓ Saved olt_placement_rules.json")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    stats = analysis["analysis"]
    print(f"\nTotal Paths Analyzed: {stats['total_paths']}")
    print(f"Max Distance Limit: {stats['max_distance_km']} km")
    print(f"\nDistance Statistics:")
    dist_stats = stats["distance_statistics"]
    print(f"  Mean: {dist_stats['mean_km']} km")
    print(f"  Median: {dist_stats['median_km']} km")
    print(f"  Max: {dist_stats['max_km']} km")
    print(f"  95th percentile: {dist_stats['p95_km']} km")
    print(f"\nViolations (> {stats['max_distance_km']} km):")
    print(f"  Count: {stats['violations']['count']}")
    print(f"  Percentage: {stats['violations']['percentage']:.2f}%")
    
    print(f"\n✅ Rules R15 and R16 generated")
    print(f"   See olt_placement_rules.json for details")


if __name__ == "__main__":
    main()




