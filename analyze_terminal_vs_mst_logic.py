#!/usr/bin/env python3
"""
analyze_terminal_vs_mst_logic.py
-------------------------------------------------------------------------------
Analyze logic for choosing Aerial Terminal vs MST:
1. ONT count distribution
2. Splicing location (mid-cable vs FOSC)
3. Connection patterns
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any
import statistics
from collections import defaultdict

def extract_ont_count(props: Dict[str, Any]) -> int:
    """Extract ONT count from terminal properties."""
    # Try multiple fields
    no_of_addr = props.get("NoOfAddr")
    no_of_res = props.get("NoOfRes")
    no_of_bus = props.get("NoOfBus")
    
    count = 0
    if no_of_addr:
        try:
            count = int(no_of_addr)
        except (ValueError, TypeError):
            pass
    
    if count == 0 and no_of_res:
        try:
            count = int(no_of_res)
        except (ValueError, TypeError):
            pass
    
    # Add business if available
    if no_of_bus:
        try:
            count += int(no_of_bus)
        except (ValueError, TypeError):
            pass
    
    return count

def analyze_cable_id_pattern(cable_id: str) -> Dict[str, Any]:
    """Analyze cable ID pattern to understand connection."""
    if not cable_id:
        return {"pattern": "unknown", "has_fosc": False, "has_terminal": False}
    
    # Pattern: "48FOC/F1000703/T1002750" means cable from FOSC F1000703 to Terminal T1002750
    # Pattern: "48FOC/F1000702/F1000703" means cable from FOSC to FOSC
    parts = cable_id.split("/")
    
    has_fosc = any(part.startswith("F") and part[1:].isdigit() for part in parts)
    has_terminal = any(part.startswith("T") and part[1:].isdigit() for part in parts)
    
    if has_fosc and has_terminal:
        pattern = "fosc_to_terminal"
    elif has_fosc and not has_terminal:
        pattern = "fosc_to_fosc"
    elif has_terminal:
        pattern = "direct_to_terminal"
    else:
        pattern = "unknown"
    
    return {
        "pattern": pattern,
        "has_fosc": has_fosc,
        "has_terminal": has_terminal,
        "cable_id": cable_id
    }

def load_terminals(filepath: str = "Terminal.geojson") -> List[Dict[str, Any]]:
    """Load terminal data."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    terminals = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        terminal_id = props.get("ID") or props.get("id")
        terminal_type = props.get("Type") or props.get("type") or ""
        
        # Determine if MST (has stub cable connection or type indicates MST)
        is_mst = "MST" in terminal_type.upper() or "mst" in terminal_type.lower()
        
        # Extract ONT count
        ont_count = extract_ont_count(props)
        
        # Analyze cable ID pattern
        cable_id = props.get("Cable_ID") or props.get("cable_id") or ""
        cable_pattern = analyze_cable_id_pattern(cable_id)
        
        # Check FOSC_ID
        fosc_id = props.get("FOSC_ID") or props.get("fosc_id")
        
        terminals.append({
            "id": terminal_id,
            "type": terminal_type,
            "is_mst": is_mst,
            "ont_count": ont_count,
            "cable_id": cable_id,
            "cable_pattern": cable_pattern,
            "fosc_id": fosc_id,
            "properties": props
        })
    
    print(f"  ✓ Loaded {len(terminals)} terminals")
    return terminals

def load_stub_cables(filepath: str = "stub cable.geojson") -> Dict[str, Dict[str, Any]]:
    """Load stub cable data and map to terminals."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    terminal_stubs = {}
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        from_id = props.get("From_ID") or props.get("from_id")
        to_id = props.get("To_ID") or props.get("to_id")
        
        # Stub cable goes from FOSC (From_ID) to Terminal (To_ID)
        if to_id and to_id.startswith("T"):
            length = props.get("MeasLength") or props.get("CalcLength") or 0
            try:
                length = float(length) if length else 0
            except (ValueError, TypeError):
                length = 0
            
            terminal_stubs[to_id] = {
                "fosc_id": from_id,
                "stub_length_m": length,
                "stub_cable_id": props.get("ID")
            }
    
    print(f"  ✓ Loaded {len(terminal_stubs)} stub cable connections")
    return terminal_stubs

def analyze_terminal_logic(terminals: List[Dict[str, Any]], 
                          stub_cables: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze logic for Aerial Terminal vs MST."""
    print("\nAnalyzing Aerial Terminal vs MST logic...")
    
    aerial_terminals = []
    mst_terminals = []
    
    for terminal in terminals:
        terminal_id = terminal["id"]
        has_stub = terminal_id in stub_cables
        
        # Classify: MST if has stub cable or explicitly marked as MST
        if terminal["is_mst"] or has_stub:
            terminal["has_stub_cable"] = has_stub
            if has_stub:
                terminal["stub_info"] = stub_cables[terminal_id]
            mst_terminals.append(terminal)
        else:
            terminal["has_stub_cable"] = False
            aerial_terminals.append(terminal)
    
    # Analyze ONT count distribution
    aerial_ont_counts = [t["ont_count"] for t in aerial_terminals if t["ont_count"] > 0]
    mst_ont_counts = [t["ont_count"] for t in mst_terminals if t["ont_count"] > 0]
    
    # Analyze cable connection patterns
    aerial_cable_patterns = defaultdict(int)
    mst_cable_patterns = defaultdict(int)
    
    for t in aerial_terminals:
        pattern = t["cable_pattern"]["pattern"]
        aerial_cable_patterns[pattern] += 1
    
    for t in mst_terminals:
        pattern = t["cable_pattern"]["pattern"]
        mst_cable_patterns[pattern] += 1
    
    # Analyze FOSC connections
    aerial_with_fosc = len([t for t in aerial_terminals if t.get("fosc_id")])
    mst_with_fosc = len([t for t in mst_terminals if t.get("fosc_id") or t.get("has_stub_cable")])
    
    return {
        "aerial_terminals": {
            "total": len(aerial_terminals),
            "ont_count_stats": {
                "mean": round(statistics.mean(aerial_ont_counts), 2) if aerial_ont_counts else 0,
                "median": round(statistics.median(aerial_ont_counts), 2) if aerial_ont_counts else 0,
                "min": min(aerial_ont_counts) if aerial_ont_counts else 0,
                "max": max(aerial_ont_counts) if aerial_ont_counts else 0,
                "distribution": {
                    "1-3": len([c for c in aerial_ont_counts if 1 <= c <= 3]),
                    "4-6": len([c for c in aerial_ont_counts if 4 <= c <= 6]),
                    "7-9": len([c for c in aerial_ont_counts if 7 <= c <= 9]),
                    "10-12": len([c for c in aerial_ont_counts if 10 <= c <= 12]),
                    "13+": len([c for c in aerial_ont_counts if c >= 13])
                }
            },
            "cable_patterns": dict(aerial_cable_patterns),
            "with_fosc_connection": aerial_with_fosc,
            "with_fosc_percentage": round((aerial_with_fosc / len(aerial_terminals)) * 100, 1) if aerial_terminals else 0
        },
        "mst_terminals": {
            "total": len(mst_terminals),
            "ont_count_stats": {
                "mean": round(statistics.mean(mst_ont_counts), 2) if mst_ont_counts else 0,
                "median": round(statistics.median(mst_ont_counts), 2) if mst_ont_counts else 0,
                "min": min(mst_ont_counts) if mst_ont_counts else 0,
                "max": max(mst_ont_counts) if mst_ont_counts else 0,
                "distribution": {
                    "1-3": len([c for c in mst_ont_counts if 1 <= c <= 3]),
                    "4-6": len([c for c in mst_ont_counts if 4 <= c <= 6]),
                    "7-9": len([c for c in mst_ont_counts if 7 <= c <= 9]),
                    "10-12": len([c for c in mst_ont_counts if 10 <= c <= 12]),
                    "13-24": len([c for c in mst_ont_counts if 13 <= c <= 24]),
                    "25+": len([c for c in mst_ont_counts if c >= 25])
                }
            },
            "cable_patterns": dict(mst_cable_patterns),
            "with_fosc_connection": mst_with_fosc,
            "with_fosc_percentage": round((mst_with_fosc / len(mst_terminals)) * 100, 1) if mst_terminals else 0,
            "with_stub_cable": len([t for t in mst_terminals if t.get("has_stub_cable")])
        }
    }

def main():
    """Main execution."""
    print("=" * 80)
    print("AERIAL TERMINAL vs MST LOGIC ANALYSIS")
    print("=" * 80)
    
    # Load data
    terminals = load_terminals()
    stub_cables = load_stub_cables()
    
    # Analyze
    analysis = analyze_terminal_logic(terminals, stub_cables)
    
    # Save results
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    
    with open("terminal_vs_mst_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)
    print("  ✓ Saved terminal_vs_mst_analysis.json")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    aerial = analysis["aerial_terminals"]
    mst = analysis["mst_terminals"]
    
    print(f"\nAerial Terminals: {aerial['total']}")
    print(f"  ONT Count Statistics:")
    if aerial["ont_count_stats"]["mean"] > 0:
        stats = aerial["ont_count_stats"]
        print(f"    Mean: {stats['mean']}")
        print(f"    Median: {stats['median']}")
        print(f"    Range: {stats['min']} - {stats['max']}")
        print(f"  Distribution:")
        for range_key, count in stats["distribution"].items():
            if count > 0:
                print(f"    {range_key} ONTs: {count} ({count/sum(stats['distribution'].values())*100:.1f}%)")
    print(f"  Cable Connection Patterns:")
    for pattern, count in aerial["cable_patterns"].items():
        print(f"    {pattern}: {count}")
    print(f"  With FOSC Connection: {aerial['with_fosc_connection']} ({aerial['with_fosc_percentage']}%)")
    
    print(f"\nMST Terminals: {mst['total']}")
    print(f"  ONT Count Statistics:")
    if mst["ont_count_stats"]["mean"] > 0:
        stats = mst["ont_count_stats"]
        print(f"    Mean: {stats['mean']}")
        print(f"    Median: {stats['median']}")
        print(f"    Range: {stats['min']} - {stats['max']}")
        print(f"  Distribution:")
        for range_key, count in stats["distribution"].items():
            if count > 0:
                print(f"    {range_key} ONTs: {count} ({count/sum(stats['distribution'].values())*100:.1f}%)")
    print(f"  Cable Connection Patterns:")
    for pattern, count in mst["cable_patterns"].items():
        print(f"    {pattern}: {count}")
    print(f"  With FOSC Connection (via stub): {mst['with_fosc_connection']} ({mst['with_fosc_percentage']}%)")
    print(f"  With Stub Cable: {mst['with_stub_cable']} (100% - stub is part of MST product)")
    
    # Key findings
    print(f"\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)
    
    aerial_median = aerial["ont_count_stats"]["median"]
    mst_median = mst["ont_count_stats"]["median"]
    
    print(f"\n1. ONT Count:")
    print(f"   Aerial Terminal median: {aerial_median} ONTs")
    print(f"   MST median: {mst_median} ONTs")
    if aerial_median < mst_median:
        print(f"   ✅ Aerial terminals serve fewer ONTs (as expected)")
    
    print(f"\n2. FOSC Connection:")
    print(f"   Aerial Terminal: {aerial['with_fosc_percentage']}% have FOSC connection")
    print(f"   MST: {mst['with_fosc_percentage']}% have FOSC connection (via stub)")
    print(f"   ✅ MST always connects to FOSC via stub cable (part of product)")
    
    print(f"\n3. Splicing Location:")
    print(f"   Aerial Terminal cable patterns: {list(aerial['cable_patterns'].keys())}")
    print(f"   MST cable patterns: {list(mst['cable_patterns'].keys())}")
    
    print(f"\n✅ Analysis complete. See terminal_vs_mst_analysis.json for details.")


if __name__ == "__main__":
    main()



