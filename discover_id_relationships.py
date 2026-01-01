#!/usr/bin/env python3
"""
discover_id_relationships.py
-------------------------------------------------------------------------------
ID Relationship Discovery Module
-------------------------------------------------------------------------------
Automatically finds and maps relationships between design layers using shared
or similar IDs, without relying on fixed From_ID / To_ID fields.

Inputs:
- All design layer GeoJSON files (ONT, Terminal, FOSC, FDH, OLT, cables)
- Optional: design_rules_reference.json (to enrich with known rule tags)

Outputs:
- discovered_relationships.json (list of node-to-node links with confidence)
- relationship_summary.txt (overview of matches per layer)
-------------------------------------------------------------------------------
"""

import json
import re
import os
from collections import defaultdict
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime


# ============================================================================
# DATA LOADING
# ============================================================================

def load_geojson(filepath: str) -> List[Dict[str, Any]]:
    """Load GeoJSON file and normalize property names to lowercase."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features", [])
        normalized = []
        for f in features:
            props = {k.lower(): v for k, v in f.get("properties", {}).items()}
            normalized.append(props)
        return normalized
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"  ⚠ Error loading {filepath}: {e}")
        return []


def load_all_layers() -> Dict[str, List[Dict[str, Any]]]:
    """Load all design layer GeoJSON files."""
    print("Loading design layer files...")
    
    layers = {}
    layer_files = {
        "ont": "ONT.geojson",
        "terminal": "terminal.geojson",
        "fosc": "splice closure.geojson",
        "fdh": "fdh.geojson",
        "olt": "OLT.geojson",
        "fiber_cable": "fiber cable.geojson",
        "stub_cable": "stub cable.geojson",
        "drop_cable": "drop cable.geojson"
    }
    
    for layer_name, filename in layer_files.items():
        data = load_geojson(filename)
        layers[layer_name] = data
        print(f"  ✓ {layer_name}: {len(data)} features")
    
    return layers


# ============================================================================
# SCHEMA DISCOVERY
# ============================================================================

def discover_id_fields(layer_data: List[Dict[str, Any]]) -> List[str]:
    """Discover ID-like fields in a layer."""
    id_patterns = [
        r'id$',           # ends with 'id'
        r'^id$',          # exactly 'id'
        r'_id$',          # ends with '_id'
        r'code$',         # ends with 'code'
        r'identifier$',   # ends with 'identifier'
    ]
    
    if not layer_data:
        return []
    
    # Get all field names from first few records
    all_fields = set()
    for record in layer_data[:100]:  # Sample first 100
        all_fields.update(record.keys())
    
    id_fields = []
    for field in all_fields:
        field_lower = field.lower()
        for pattern in id_patterns:
            if re.search(pattern, field_lower):
                id_fields.append(field)
                break
    
    return sorted(id_fields)


def extract_all_ids(layer_data: List[Dict[str, Any]], 
                   layer_name: str) -> Dict[str, Dict[str, Any]]:
    """Extract all ID values from a layer."""
    id_fields = discover_id_fields(layer_data)
    
    if not id_fields:
        # Try common defaults
        id_fields = ["id", "id_field", f"{layer_name}_id"]
    
    all_ids = {}
    
    for record in layer_data:
        record_ids = {}
        
        # Extract primary ID
        primary_id = None
        for field in id_fields:
            value = record.get(field)
            if value and str(value).strip():
                primary_id = str(value).strip()
                record_ids["primary_id"] = primary_id
                record_ids["primary_id_field"] = field
                break
        
        # Extract all ID-like values (for cross-referencing)
        for key, value in record.items():
            if value and isinstance(value, str):
                # Check if value looks like an ID
                if re.match(r'^[A-Z]?\d+', value) or re.match(r'^[A-Z]{2,}\d+', value):
                    if key not in record_ids:
                        record_ids[key] = value
        
        # Also check for comma-separated ID lists
        for key, value in record.items():
            if value and isinstance(value, str) and ',' in value:
                # Might be a list of IDs
                parts = [p.strip() for p in value.split(',')]
                if all(re.match(r'^[A-Z]?\d+', p) or re.match(r'^[A-Z]{2,}\d+', p) for p in parts):
                    record_ids[f"{key}_list"] = parts
        
        if primary_id:
            all_ids[primary_id] = {
                "layer": layer_name,
                "record": record,
                "all_ids": record_ids
            }
    
    return all_ids


# ============================================================================
# PREFIX GROUPING
# ============================================================================

def classify_id_prefix(id_value: str) -> Optional[str]:
    """Classify ID by prefix pattern."""
    if not id_value:
        return None
    
    # Common patterns
    patterns = {
        r'^O\d+': 'ONT',           # O1004701
        r'^T\d+': 'Terminal',       # T1001411
        r'^F\d+': 'FOSC',           # F1000338
        r'^FDH\d+': 'FDH',          # FDH103009
        r'^\d+FOC/': 'FiberCable',  # 96FOC/F1000143/F1000144
        r'^\d+F/': 'StubCable',     # 6F/F1000338/T1001411
        r'^\d+FOC/': 'DropCable',   # 1FOC/T1001411/O1004701
        r'^\d+$': 'OLT',            # 103 (just numbers)
        r'^TRUNK': 'Trunk',         # TRUNK* (if exists)
    }
    
    for pattern, prefix_type in patterns.items():
        if re.match(pattern, id_value, re.IGNORECASE):
            return prefix_type
    
    return 'Unknown'


# ============================================================================
# CROSS-LAYER MATCHING
# ============================================================================

def check_field_reference(id1: str, data1: Dict[str, Any], 
                         id2: str, data2: Dict[str, Any],
                         target_layer: str) -> Tuple[Optional[Dict[str, Any]], float]:
    """Check if id1 appears in data2's fields or vice versa."""
    id1_upper = str(id1).upper()
    id2_upper = str(id2).upper()
    
    # Check if id1 appears in data2's record fields
    record2 = data2.get("record", {})
    for field, value in record2.items():
        if not value or not isinstance(value, str):
            continue
        
        # Only check ID-like fields
        if not any(x in field.lower() for x in ["id", "code", "identifier", "ref"]):
            continue
        
        # Check exact match
        if value.upper() == id1_upper:
            return {
                "match_type": "field_reference",
                "description": f"{id1} referenced in {field} field",
                "reference_field": field
            }, calculate_confidence("field_reference", field_match=True)
        
        # Check list fields (comma-separated)
        if ',' in value:
            parts = [p.strip().upper() for p in value.split(',')]
            if id1_upper in parts:
                return {
                    "match_type": "field_reference",
                    "description": f"{id1} referenced in {field} list",
                    "reference_field": field
                }, calculate_confidence("field_reference", field_match=True)
    
    # Check if id2 appears in data1's fields
    record1 = data1.get("record", {})
    for field, value in record1.items():
        if not value or not isinstance(value, str):
            continue
        
        if not any(x in field.lower() for x in ["id", "code", "identifier", "ref"]):
            continue
        
        if value.upper() == id2_upper:
            return {
                "match_type": "field_reference",
                "description": f"{id2} referenced in {field} field",
                "reference_field": field
            }, calculate_confidence("field_reference", field_match=True)
        
        if ',' in value:
            parts = [p.strip().upper() for p in value.split(',')]
            if id2_upper in parts:
                return {
                    "match_type": "field_reference",
                    "description": f"{id2} referenced in {field} list",
                    "reference_field": field
                }, calculate_confidence("field_reference", field_match=True)
    
    return None, 0.0


def create_relationship(id1: str, layer1_name: str, id2: str, layer2_name: str,
                       match_info: Dict[str, Any], confidence: float,
                       data1: Dict[str, Any], data2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a relationship object if confidence is sufficient."""
    if confidence < 0.5:
        return None
    
    relationship = {
        "source_id": id1,
        "source_layer": layer1_name,
        "target_id": id2,
        "target_layer": layer2_name,
        "match_type": match_info["match_type"],
        "description": match_info["description"],
        "confidence": round(confidence, 3),
        "source_prefix": classify_id_prefix(id1),
        "target_prefix": classify_id_prefix(id2)
    }
    
    if "reference_field" in match_info:
        relationship["reference_field"] = match_info["reference_field"]
    
    return relationship

def match_ids_exact(id1: str, id2: str) -> bool:
    """Check if two IDs match exactly (case-insensitive)."""
    if not id1 or not id2:
        return False
    return str(id1).strip().upper() == str(id2).strip().upper()


def match_ids_substring(id1: str, id2: str) -> bool:
    """Check if one ID contains the other as substring."""
    if not id1 or not id2:
        return False
    id1_upper = str(id1).strip().upper()
    id2_upper = str(id2).strip().upper()
    return id1_upper in id2_upper or id2_upper in id1_upper


def match_ids_prefix(id1: str, id2: str) -> bool:
    """Check if IDs share the same prefix pattern."""
    if not id1 or not id2:
        return False
    
    # Extract prefix (letters before numbers)
    prefix1 = re.match(r'^([A-Z]+)', str(id1).upper())
    prefix2 = re.match(r'^([A-Z]+)', str(id2).upper())
    
    if prefix1 and prefix2:
        return prefix1.group(1) == prefix2.group(1)
    
    return False


def match_ids_in_cable_id(cable_id: str, node_id: str) -> bool:
    """Check if node ID appears in cable ID (e.g., "96FOC/F1000143/F1000144" contains "F1000143")."""
    if not cable_id or not node_id:
        return False
    
    cable_id_upper = str(cable_id).upper()
    node_id_upper = str(node_id).upper()
    
    # Check if node ID appears in cable ID (common pattern: "SIZE/ID1/ID2")
    return node_id_upper in cable_id_upper


def calculate_confidence(match_type: str, field_match: bool = False) -> float:
    """Calculate confidence score based on match type."""
    confidences = {
        "exact": 1.0,
        "exact_field": 0.95,  # Exact match in specific field
        "substring": 0.7,
        "prefix": 0.5,
        "cable_id_contains": 0.8,
        "field_reference": 0.85  # ID appears in another field
    }
    
    base_confidence = confidences.get(match_type, 0.3)
    
    # Boost confidence if it's a field match
    if field_match:
        base_confidence = min(1.0, base_confidence + 0.1)
    
    return base_confidence


def find_relationships(all_layers_ids: Dict[str, Dict[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Find relationships between layers based on ID matching."""
    print("\nFinding relationships between layers...")
    
    relationships = []
    layer_names = list(all_layers_ids.keys())
    
    # Build index of all IDs for fast lookup
    all_ids_index = {}
    for layer_name, layer_ids in all_layers_ids.items():
        for id_value in layer_ids.keys():
            id_upper = str(id_value).upper()
            if id_upper not in all_ids_index:
                all_ids_index[id_upper] = []
            all_ids_index[id_upper].append((layer_name, id_value))
    
    # Compare each layer with every other layer (optimized)
    for i, layer1_name in enumerate(layer_names):
        for layer2_name in layer_names[i+1:]:
            layer1_ids = all_layers_ids[layer1_name]
            layer2_ids = all_layers_ids[layer2_name]
            
            # Build lookup sets for faster matching
            layer2_ids_upper = {str(id2).upper(): (id2, data2) for id2, data2 in layer2_ids.items()}
            
            # Process layer1
            processed = 0
            for id1, data1 in layer1_ids.items():
                id1_upper = str(id1).upper()
                
                # Check exact match first (fastest)
                if id1_upper in layer2_ids_upper:
                    id2, data2 = layer2_ids_upper[id1_upper]
                    match_info = {
                        "match_type": "exact",
                        "description": f"Exact ID match"
                    }
                    confidence = calculate_confidence("exact")
                    
                    relationship = create_relationship(
                        id1, layer1_name, id2, layer2_name, 
                        match_info, confidence, data1, data2
                    )
                    if relationship:
                        relationships.append(relationship)
                    processed += 1
                    if processed % 1000 == 0:
                        print(f"    Processed {processed}/{len(layer1_ids)} from {layer1_name}...")
                    continue
                
                # Check cable ID contains (for cable layers)
                if layer1_name.endswith("_cable") and not layer2_name.endswith("_cable"):
                    # Check if any node ID in layer2 appears in cable ID
                    for id2_upper, (id2, data2) in layer2_ids_upper.items():
                        if id2_upper in id1_upper and len(id2_upper) >= 3:  # Avoid very short matches
                            match_info = {
                                "match_type": "cable_id_contains",
                                "description": f"{id2} appears in cable {id1}"
                            }
                            confidence = calculate_confidence("cable_id_contains")
                            
                            relationship = create_relationship(
                                id1, layer1_name, id2, layer2_name,
                                match_info, confidence, data1, data2
                            )
                            if relationship:
                                relationships.append(relationship)
                            break  # Only need first match
                
                elif layer2_name.endswith("_cable") and not layer1_name.endswith("_cable"):
                    # Check if id1 appears in cable ID
                    for id2_upper, (id2, data2) in layer2_ids_upper.items():
                        if id1_upper in id2_upper and len(id1_upper) >= 3:
                            match_info = {
                                "match_type": "cable_id_contains",
                                "description": f"{id1} appears in cable {id2}"
                            }
                            confidence = calculate_confidence("cable_id_contains")
                            
                            relationship = create_relationship(
                                id1, layer1_name, id2, layer2_name,
                                match_info, confidence, data1, data2
                            )
                            if relationship:
                                relationships.append(relationship)
                            break
                
                # Check field references (for non-cable layers only)
                elif not layer1_name.endswith("_cable") and not layer2_name.endswith("_cable"):
                    # Check a sample of layer2 IDs (limit to avoid O(N^2))
                    sample_size = min(100, len(layer2_ids_upper))
                    sample_ids = list(layer2_ids_upper.items())[:sample_size]
                    
                    for id2_upper, (id2, data2) in sample_ids:
                        match_info, confidence = check_field_reference(
                            id1, data1, id2, data2, layer2_name
                        )
                        if match_info:
                            relationship = create_relationship(
                                id1, layer1_name, id2, layer2_name,
                                match_info, confidence, data1, data2
                            )
                            if relationship:
                                relationships.append(relationship)
                                break  # Only need first match
                
                processed += 1
                if processed % 1000 == 0:
                    print(f"    Processed {processed}/{len(layer1_ids)} from {layer1_name}...")
    
    print(f"  ✓ Found {len(relationships)} relationships")
    return relationships


# ============================================================================
# RELATIONSHIP TYPE INFERENCE
# ============================================================================

def infer_relationship_type(relationship: Dict[str, Any]) -> str:
    """Infer the type of relationship based on layers and context."""
    source_layer = relationship.get("source_layer", "")
    target_layer = relationship.get("target_layer", "")
    match_type = relationship.get("match_type", "")
    
    # Hierarchical relationships
    if source_layer == "ont" and target_layer == "terminal":
        return "ont_connects_to_terminal"
    elif source_layer == "terminal" and target_layer == "fosc":
        return "terminal_connects_to_fosc"
    elif source_layer == "fosc" and target_layer == "fdh":
        return "fosc_connects_to_fdh"
    elif source_layer == "fdh" and target_layer == "olt":
        return "fdh_connects_to_olt"
    
    # Cable relationships
    if "_cable" in source_layer or "_cable" in target_layer:
        cable_layer = source_layer if "_cable" in source_layer else target_layer
        node_layer = target_layer if "_cable" in source_layer else source_layer
        
        if "drop" in cable_layer:
            return "drop_cable_connects"
        elif "stub" in cable_layer:
            return "stub_cable_connects"
        elif "fiber" in cable_layer:
            return "fiber_cable_connects"
    
    # Field references
    if match_type == "field_reference":
        ref_field = relationship.get("reference_field", "")
        if "termnal" in ref_field.lower() or "terminal" in ref_field.lower():
            return "references_terminal"
        elif "fosc" in ref_field.lower():
            return "references_fosc"
        elif "fdh" in ref_field.lower():
            return "references_fdh"
        elif "olt" in ref_field.lower():
            return "references_olt"
    
    return "related"


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_relationships_json(relationships: List[Dict[str, Any]], 
                               output_file: str = "discovered_relationships.json") -> None:
    """Generate discovered_relationships.json."""
    print(f"\nGenerating {output_file}...")
    
    # Add inferred relationship types
    for rel in relationships:
        rel["relationship_type"] = infer_relationship_type(rel)
    
    # Sort by confidence (descending)
    relationships.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    
    output = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_relationships": len(relationships),
        "relationships": relationships
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"  ✓ Saved {output_file}")


def generate_summary_txt(relationships: List[Dict[str, Any]], 
                        all_layers_ids: Dict[str, Dict[str, Dict[str, Any]]],
                        output_file: str = "relationship_summary.txt") -> None:
    """Generate relationship_summary.txt."""
    print(f"\nGenerating {output_file}...")
    
    output = "=" * 80 + "\n"
    output += "ID RELATIONSHIP DISCOVERY SUMMARY\n"
    output += "=" * 80 + "\n\n"
    output += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    output += f"Total Relationships: {len(relationships)}\n\n"
    
    # Statistics by layer
    output += "STATISTICS BY LAYER:\n"
    output += "-" * 80 + "\n\n"
    
    for layer_name, layer_ids in all_layers_ids.items():
        output += f"{layer_name.upper()}:\n"
        output += f"  Total IDs: {len(layer_ids)}\n"
        
        # Count relationships
        source_count = sum(1 for r in relationships if r.get("source_layer") == layer_name)
        target_count = sum(1 for r in relationships if r.get("target_layer") == layer_name)
        output += f"  As source: {source_count} relationships\n"
        output += f"  As target: {target_count} relationships\n"
        output += f"  Total connections: {source_count + target_count}\n\n"
    
    # Match type distribution
    output += "=" * 80 + "\n"
    output += "MATCH TYPE DISTRIBUTION:\n"
    output += "-" * 80 + "\n\n"
    
    match_type_counts = defaultdict(int)
    for rel in relationships:
        match_type_counts[rel.get("match_type", "unknown")] += 1
    
    for match_type, count in sorted(match_type_counts.items(), key=lambda x: -x[1]):
        output += f"  {match_type}: {count} ({count/len(relationships)*100:.1f}%)\n"
    
    # Confidence distribution
    output += "\n" + "=" * 80 + "\n"
    output += "CONFIDENCE DISTRIBUTION:\n"
    output += "-" * 80 + "\n\n"
    
    confidence_ranges = {
        "0.9-1.0": 0,
        "0.8-0.9": 0,
        "0.7-0.8": 0,
        "0.5-0.7": 0
    }
    
    for rel in relationships:
        conf = rel.get("confidence", 0)
        if conf >= 0.9:
            confidence_ranges["0.9-1.0"] += 1
        elif conf >= 0.8:
            confidence_ranges["0.8-0.9"] += 1
        elif conf >= 0.7:
            confidence_ranges["0.7-0.8"] += 1
        else:
            confidence_ranges["0.5-0.7"] += 1
    
    for range_name, count in confidence_ranges.items():
        output += f"  {range_name}: {count} ({count/len(relationships)*100:.1f}%)\n"
    
    # Relationship type distribution
    output += "\n" + "=" * 80 + "\n"
    output += "RELATIONSHIP TYPE DISTRIBUTION:\n"
    output += "-" * 80 + "\n\n"
    
    rel_type_counts = defaultdict(int)
    for rel in relationships:
        rel_type = rel.get("relationship_type", "unknown")
        rel_type_counts[rel_type] += 1
    
    for rel_type, count in sorted(rel_type_counts.items(), key=lambda x: -x[1]):
        output += f"  {rel_type}: {count} ({count/len(relationships)*100:.1f}%)\n"
    
    # Sample relationships
    output += "\n" + "=" * 80 + "\n"
    output += "SAMPLE RELATIONSHIPS (High Confidence):\n"
    output += "-" * 80 + "\n\n"
    
    high_confidence = [r for r in relationships if r.get("confidence", 0) >= 0.8]
    for rel in high_confidence[:20]:
        output += f"  {rel.get('source_layer')}::{rel.get('source_id')} -> {rel.get('target_layer')}::{rel.get('target_id')}\n"
        output += f"    Type: {rel.get('relationship_type')}, Match: {rel.get('match_type')}, Confidence: {rel.get('confidence')}\n"
        output += f"    {rel.get('description')}\n\n"
    
    output += "=" * 80 + "\n"
    output += "END OF SUMMARY\n"
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
    print("ID RELATIONSHIP DISCOVERY")
    print("=" * 80)
    
    # Step 1: Load all layers
    layers = load_all_layers()
    
    # Step 2: Extract IDs from each layer
    print("\nExtracting IDs from layers...")
    all_layers_ids = {}
    
    for layer_name, layer_data in layers.items():
        ids = extract_all_ids(layer_data, layer_name)
        all_layers_ids[layer_name] = ids
        print(f"  ✓ {layer_name}: {len(ids)} unique IDs")
    
    # Step 3: Find relationships
    relationships = find_relationships(all_layers_ids)
    
    # Step 4: Generate outputs
    print("\n" + "=" * 80)
    print("GENERATING OUTPUTS")
    print("=" * 80)
    
    generate_relationships_json(relationships)
    generate_summary_txt(relationships, all_layers_ids)
    
    # Final summary
    print("\n" + "=" * 80)
    print("✅ DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"\nDiscovered {len(relationships)} relationships")
    print(f"\nGenerated files:")
    print(f"  📄 discovered_relationships.json")
    print(f"  📄 relationship_summary.txt")
    
    # Quick stats
    high_conf = sum(1 for r in relationships if r.get("confidence", 0) >= 0.8)
    print(f"\nConfidence breakdown:")
    print(f"  High confidence (≥0.8): {high_conf} ({high_conf/len(relationships)*100:.1f}%)")
    print(f"  Medium confidence (0.5-0.8): {len(relationships) - high_conf} ({(len(relationships) - high_conf)/len(relationships)*100:.1f}%)")
    print()


if __name__ == "__main__":
    main()

