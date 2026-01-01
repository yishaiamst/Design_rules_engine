#!/usr/bin/env python3
"""
analyze_olt_subscriber_density.py
-------------------------------------------------------------------------------
Analyze how many subscribers (ONTs) each OLT is serving.
This helps refine R16 OLT placement strategy.
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


def analyze_olt_subscriber_counts(paths: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze how many ONTs each OLT serves."""
    print("\nAnalyzing OLT subscriber counts...")
    
    # Group ONTs by OLT
    olt_onts = defaultdict(set)  # Use set to avoid duplicates
    olt_paths = defaultdict(list)
    olt_complete_paths = defaultdict(list)
    
    for path in paths:
        ont_id = path.get("ont_id")
        olt_id = path.get("olt_id")
        is_complete = path.get("complete", False)
        total_length = path.get("total_length_m", 0)
        
        if olt_id:
            olt_onts[olt_id].add(ont_id)
            olt_paths[olt_id].append(path)
            if is_complete:
                olt_complete_paths[olt_id].append(path)
    
    # Calculate statistics per OLT
    olt_stats = {}
    subscriber_counts = []
    
    for olt_id in sorted(olt_onts.keys()):
        ont_count = len(olt_onts[olt_id])
        total_paths = len(olt_paths[olt_id])
        complete_paths = len(olt_complete_paths[olt_id])
        
        # Calculate distance statistics for this OLT
        path_lengths = [p.get("total_length_m", 0) for p in olt_complete_paths[olt_id] if p.get("total_length_m", 0) > 0]
        
        olt_stats[olt_id] = {
            "ont_count": ont_count,
            "total_paths": total_paths,
            "complete_paths": complete_paths,
            "completion_rate": (complete_paths / total_paths * 100) if total_paths > 0 else 0,
            "distance_stats": {
                "mean_km": round(statistics.mean(path_lengths) / 1000, 2) if path_lengths else 0,
                "median_km": round(statistics.median(path_lengths) / 1000, 2) if path_lengths else 0,
                "min_km": round(min(path_lengths) / 1000, 2) if path_lengths else 0,
                "max_km": round(max(path_lengths) / 1000, 2) if path_lengths else 0,
                "p95_km": round(statistics.quantiles(path_lengths, n=20)[18] / 1000, 2) if len(path_lengths) >= 20 else 0
            }
        }
        
        subscriber_counts.append(ont_count)
    
    # Overall statistics
    overall_stats = {
        "total_olts": len(olt_stats),
        "total_onts": sum(olt_stats[olt]["ont_count"] for olt in olt_stats),
        "subscriber_distribution": {
            "mean": round(statistics.mean(subscriber_counts), 2) if subscriber_counts else 0,
            "median": round(statistics.median(subscriber_counts), 2) if subscriber_counts else 0,
            "min": min(subscriber_counts) if subscriber_counts else 0,
            "max": max(subscriber_counts) if subscriber_counts else 0,
            "p25": round(statistics.quantiles(subscriber_counts, n=4)[0], 2) if len(subscriber_counts) >= 4 else 0,
            "p75": round(statistics.quantiles(subscriber_counts, n=4)[2], 2) if len(subscriber_counts) >= 4 else 0,
            "p90": round(statistics.quantiles(subscriber_counts, n=10)[8], 2) if len(subscriber_counts) >= 10 else 0,
            "p95": round(statistics.quantiles(subscriber_counts, n=20)[18], 2) if len(subscriber_counts) >= 20 else 0
        }
    }
    
    # Categorize OLTs by subscriber count
    categories = {
        "small": {"min": 0, "max": 500, "count": 0, "olts": []},
        "medium": {"min": 500, "max": 1000, "count": 0, "olts": []},
        "large": {"min": 1000, "max": 2000, "count": 0, "olts": []},
        "very_large": {"min": 2000, "max": float('inf'), "count": 0, "olts": []}
    }
    
    for olt_id, stats in olt_stats.items():
        count = stats["ont_count"]
        for cat_name, cat_data in categories.items():
            if cat_data["min"] <= count < cat_data["max"]:
                cat_data["count"] += 1
                cat_data["olts"].append({
                    "olt_id": olt_id,
                    "ont_count": count,
                    "mean_distance_km": stats["distance_stats"]["mean_km"],
                    "max_distance_km": stats["distance_stats"]["max_km"]
                })
                break
    
    # Sort OLTs by subscriber count for detailed view
    sorted_olts = sorted(
        [(olt_id, stats) for olt_id, stats in olt_stats.items()],
        key=lambda x: x[1]["ont_count"],
        reverse=True
    )
    
    return {
        "overall_statistics": overall_stats,
        "olt_statistics": {olt_id: stats for olt_id, stats in sorted_olts},
        "categories": categories,
        "recommendations": generate_recommendations(overall_stats, categories)
    }


def generate_recommendations(overall_stats: Dict, categories: Dict) -> Dict[str, Any]:
    """Generate recommendations for OLT placement thresholds."""
    total_olts = overall_stats["total_olts"]
    dist = overall_stats["subscriber_distribution"]
    
    small_count = categories["small"]["count"]
    medium_count = categories["medium"]["count"]
    large_count = categories["large"]["count"]
    very_large_count = categories["very_large"]["count"]
    
    recommendations = {
        "current_threshold_analysis": {
            "threshold_2000": {
                "olts_above": very_large_count,
                "percentage": round(very_large_count / total_olts * 100, 2) if total_olts > 0 else 0,
                "description": "OLTs serving ≥2000 subscribers"
            },
            "threshold_1000": {
                "olts_above": large_count + very_large_count,
                "percentage": round((large_count + very_large_count) / total_olts * 100, 2) if total_olts > 0 else 0,
                "description": "OLTs serving ≥1000 subscribers"
            },
            "threshold_500": {
                "olts_above": medium_count + large_count + very_large_count,
                "percentage": round((medium_count + large_count + very_large_count) / total_olts * 100, 2) if total_olts > 0 else 0,
                "description": "OLTs serving ≥500 subscribers"
            }
        },
        "suggested_thresholds": {
            "large_community": {
                "threshold": 2000,
                "rationale": "Very large communities requiring dedicated OLT",
                "current_count": very_large_count
            },
            "medium_community": {
                "threshold": 1000,
                "rationale": "Large communities that may benefit from dedicated OLT",
                "current_count": large_count + very_large_count
            },
            "small_community": {
                "threshold": 500,
                "rationale": "Small communities that may still warrant OLT placement if isolated or far from other OLTs",
                "current_count": medium_count + large_count + very_large_count
            }
        },
        "refined_rule_suggestion": {
            "primary_threshold": 2000,
            "secondary_threshold": 500,
            "rule_text": "Place OLT at community center if: (1) Community has ≥2000 subscribers, OR (2) Community has ≥500 subscribers AND is >15km from nearest existing OLT",
            "rationale": f"Current data shows {small_count} OLTs serving <500 subscribers, suggesting smaller communities may also warrant OLT placement under certain conditions"
        }
    }
    
    return recommendations


def main():
    """Main execution."""
    print("=" * 80)
    print("OLT SUBSCRIBER DENSITY ANALYSIS")
    print("=" * 80)
    
    # Load paths
    paths = load_ont_paths()
    
    # Analyze
    analysis = analyze_olt_subscriber_counts(paths)
    
    # Save results
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    
    with open("olt_subscriber_density_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)
    print("  ✓ Saved olt_subscriber_density_analysis.json")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    overall = analysis["overall_statistics"]
    dist = overall["subscriber_distribution"]
    categories = analysis["categories"]
    
    print(f"\nTotal OLTs: {overall['total_olts']}")
    print(f"Total ONTs: {overall['total_onts']}")
    print(f"\nSubscriber Count Distribution:")
    print(f"  Mean: {dist['mean']:.0f} ONTs per OLT")
    print(f"  Median: {dist['median']:.0f} ONTs per OLT")
    print(f"  Min: {dist['min']:.0f} ONTs")
    print(f"  Max: {dist['max']:.0f} ONTs")
    print(f"  25th percentile: {dist['p25']:.0f} ONTs")
    print(f"  75th percentile: {dist['p75']:.0f} ONTs")
    print(f"  90th percentile: {dist['p90']:.0f} ONTs")
    print(f"  95th percentile: {dist['p95']:.0f} ONTs")
    
    print(f"\nOLT Categories by Subscriber Count:")
    print(f"  Small (<500): {categories['small']['count']} OLTs ({categories['small']['count']/overall['total_olts']*100:.1f}%)")
    print(f"  Medium (500-1000): {categories['medium']['count']} OLTs ({categories['medium']['count']/overall['total_olts']*100:.1f}%)")
    print(f"  Large (1000-2000): {categories['large']['count']} OLTs ({categories['large']['count']/overall['total_olts']*100:.1f}%)")
    print(f"  Very Large (≥2000): {categories['very_large']['count']} OLTs ({categories['very_large']['count']/overall['total_olts']*100:.1f}%)")
    
    print(f"\nTop 10 OLTs by Subscriber Count:")
    sorted_olts = sorted(
        analysis["olt_statistics"].items(),
        key=lambda x: x[1]["ont_count"],
        reverse=True
    )[:10]
    
    for i, (olt_id, stats) in enumerate(sorted_olts, 1):
        print(f"  {i}. OLT {olt_id}: {stats['ont_count']} ONTs (mean distance: {stats['distance_stats']['mean_km']:.2f} km, max: {stats['distance_stats']['max_km']:.2f} km)")
    
    print(f"\nSmallest 10 OLTs by Subscriber Count:")
    sorted_olts_small = sorted(
        analysis["olt_statistics"].items(),
        key=lambda x: x[1]["ont_count"],
        reverse=False
    )[:10]
    
    for i, (olt_id, stats) in enumerate(sorted_olts_small, 1):
        print(f"  {i}. OLT {olt_id}: {stats['ont_count']} ONTs (mean distance: {stats['distance_stats']['mean_km']:.2f} km, max: {stats['distance_stats']['max_km']:.2f} km)")
    
    # Recommendations
    recs = analysis["recommendations"]
    print(f"\n" + "=" * 80)
    print("RECOMMENDATIONS FOR R16 REFINEMENT")
    print("=" * 80)
    
    print(f"\nCurrent Threshold Analysis:")
    for threshold_name, threshold_data in recs["current_threshold_analysis"].items():
        print(f"  {threshold_data['description']}: {threshold_data['olts_above']} OLTs ({threshold_data['percentage']:.1f}%)")
    
    print(f"\nSuggested Refined Rule:")
    print(f"  {recs['refined_rule_suggestion']['rule_text']}")
    print(f"\n  Rationale: {recs['refined_rule_suggestion']['rationale']}")
    
    print(f"\n✅ Analysis complete. See olt_subscriber_density_analysis.json for details.")


if __name__ == "__main__":
    main()




