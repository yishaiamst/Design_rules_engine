#!/usr/bin/env python3
"""
config_loader.py
-------------------------------------------------------------------------------
Load and validate design engine configuration from design_config.json
-------------------------------------------------------------------------------
"""

import json
import os
from typing import Dict, Any, Optional

def load_config(config_path: str = "design_config.json") -> Dict[str, Any]:
    """
    Load design engine configuration from JSON file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    # Validate required sections
    required_sections = ["equipment", "service", "cables", "placement"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")
    
    return config

def get_equipment_config(config: Dict[str, Any], equipment_type: str, model: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific equipment model.
    
    Args:
        config: Configuration dictionary
        equipment_type: Type of equipment (mst, aerial_terminal, fosc, fdh, olt)
        model: Model name (e.g., "MST4", "AER-TRM8")
        
    Returns:
        Equipment configuration or None if not found
    """
    equipment = config.get("equipment", {})
    equipment_type_config = equipment.get(equipment_type, {})
    return equipment_type_config.get(model)

def get_service_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get service configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Service configuration dictionary
    """
    return config.get("service", {})

def get_cable_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get cable configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Cable configuration dictionary
    """
    return config.get("cables", {})

def get_placement_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get placement configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Placement configuration dictionary
    """
    return config.get("placement", {})

def get_mst_config(config: Dict[str, Any], mst_type: str) -> Optional[Dict[str, Any]]:
    """
    Get MST configuration by type.
    
    Args:
        config: Configuration dictionary
        mst_type: MST type (MST4, MST6, MST8, MST12)
        
    Returns:
        MST configuration or None if not found
    """
    return get_equipment_config(config, "mst", mst_type)

def get_olt_config(config: Dict[str, Any], olt_type: str = None) -> Dict[str, Any]:
    """
    Get OLT configuration. If olt_type not specified, uses default from service config.
    
    Args:
        config: Configuration dictionary
        olt_type: OLT type (optional)
        
    Returns:
        OLT configuration dictionary
    """
    if olt_type:
        olt_config = get_equipment_config(config, "olt", olt_type)
        if olt_config:
            return olt_config
    
    # Use default from service config
    service_config = get_service_config(config)
    return {
        "ports": 8,  # Default
        "port_capacity_gbps": service_config.get("olt_port_capacity_gbps", 1.0)
    }



