"""Populate Wikelo ships with turn-in barter requirements into workspace library catalogs."""
import json
import os
from pathlib import Path

WIKELO_SHIPS = [
    {
        "id": "wikelo-misc-fortune",
        "item_id": "wikelo-misc-fortune",
        "name": "MISC Fortune (Wikelo Special)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "MISC Fortune (Wikelo Special)\n"
            "Ship · Musashi Industrial and Starflight Concern\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Fortune ship for you\"\n"
            "Cost: 3 × Wikelo Favors + 1 × Pure Carinite (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Wikelo's customized solo salvage vessel featuring upgraded scrapers and reinforced structure.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "MISC Fortune Wikelo Special Fortune ship for you Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Pure Carinite Musashi Industrial Salvage Small S hangar Ships",
        "uex_vehicle_id": 234,
        "game_vehicle_id": "3d371fd4-50e2-4b5e-859f-1086e905c946",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 16,
            "length": 26.5,
            "width": 16.5,
            "height": 8.0,
            "mass": 137700,
            "roles": ["Salvage", "Industrial"]
        },
        "ship_stats": {
            "role": "Light Salvage",
            "size": 2,
            "body_hp": 15200.0,
            "shield_hp": 6480.0,
            "shield_count": 3,
            "armor_physical": 0.7,
            "armor_energy": 0.5,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 3, "minimum": 1, "maximum": 1},
                    {"label": "Salvage heads", "count": 1, "minimum": 1, "maximum": 2},
                    {"label": "Guns", "count": 2, "minimum": 1, "maximum": 1},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Coolers", "count": 1, "minimum": 2, "maximum": 2}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Fortune ship for you",
            "favors": 3,
            "favors_label": "3 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Pure Carinite",
                    "amount": 1,
                    "label": "1 × Pure Carinite",
                    "detail": "High-purity rare mineral · Mineable & refineable in Stanton"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-crusader-intrepid",
        "item_id": "wikelo-crusader-intrepid",
        "name": "Crusader Intrepid (Wikelo Edition)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Crusader Intrepid (Wikelo Edition)\n"
            "Ship · Crusader Industries\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Upgrade Intrepid\"\n"
            "Cost: 3 × Wikelo Favors + 1 × Pristine GCA Medal (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Banu-retrofitted starter hauler with optimized maneuvering thrusters.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Crusader Intrepid Wikelo Edition Upgrade Intrepid Wikelo Wikalo Wickalow Barter Turn-in Favor Favors GCA Medal Government Cartography Agency Pristine Crusader Light Hauler Small S hangar Ships",
        "uex_vehicle_id": 236,
        "game_vehicle_id": "16aa514f-12ac-43a4-b51d-44447252186e",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 8,
            "length": 23.07,
            "width": 20.18,
            "height": 6.13,
            "mass": 66943,
            "roles": ["Freight"]
        },
        "ship_stats": {
            "role": "Starter / Light Freight",
            "size": 2,
            "body_hp": 3300.0,
            "shield_hp": 2160.0,
            "shield_count": 1,
            "armor_physical": 0.75,
            "armor_energy": 0.6,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Guns", "count": 1, "minimum": 4, "maximum": 4},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Coolers", "count": 1, "minimum": 1, "maximum": 1}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Upgrade Intrepid",
            "favors": 3,
            "favors_label": "3 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Government Cartography Agency Medal (Pristine)",
                    "amount": 1,
                    "label": "1 × Pristine GCA Medal",
                    "detail": "Pristine cartography agency medal · Rare mission reward"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-argo-atls-geo",
        "item_id": "wikelo-argo-atls-geo",
        "name": "Argo ATLS (Wikelo Geo Edition)",
        "kind": "Vehicle",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Argo ATLS (Wikelo Geo Edition)\n"
            "Vehicle · Argo Astronautics\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Heavy Lifting Friend\"\n"
            "Cost: 2 × Wikelo Favors + 15 × MG Scrip + 5 × Refined Hadanite (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Specialized exosuit loader modified with high-torque Banu servos and industrial tractor beam.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Argo ATLS Geo Edition Wikelo Wikalo Wickalow Heavy Lifting Friend Barter Turn-in Favor Favors MG Scrip Hadanite Exosuit Mech Loader Vehicle Bay XS Vehicles",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 0,
            "length": 3.2,
            "width": 2.8,
            "height": 3.8,
            "mass": 1850,
            "roles": ["Industrial", "Cargo Loader"]
        },
        "ship_stats": {
            "role": "Power Loader Exosuit",
            "size": 1,
            "body_hp": 2200.0,
            "shield_hp": 0.0,
            "shield_count": 0,
            "armor_physical": 0.85,
            "armor_energy": 0.7,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Tractor beam", "count": 1, "minimum": 2, "maximum": 2}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Heavy Lifting Friend",
            "favors": 2,
            "favors_label": "2 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "MG Scrip",
                    "amount": 15,
                    "label": "15 × MG Scrip",
                    "detail": "Mining Guild scrip currency tokens"
                },
                {
                    "name": "Refined Hadanite",
                    "amount": 5,
                    "label": "5 × Refined Hadanite",
                    "detail": "High-purity harvested gemstone SCU units"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-argo-atls-ikti",
        "item_id": "wikelo-argo-atls-ikti",
        "name": "Argo ATLS (Wikelo IKTI Edition)",
        "kind": "Vehicle",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Argo ATLS (Wikelo IKTI Edition)\n"
            "Vehicle · Argo Astronautics\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Heavy Armor Suit\"\n"
            "Cost: 2 × Wikelo Favors + 15 × Council Scrip + 4 × Pure Carinite (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Armored industrial exosuit fitted with reinforced composite plating for hazardous freight recovery.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Argo ATLS IKTI Edition Wikelo Wikalo Wickalow Heavy Armor Suit Barter Turn-in Favor Favors Council Scrip Carinite Vehicle Bay XS Vehicles",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 0,
            "length": 3.2,
            "width": 2.8,
            "height": 3.8,
            "mass": 1920,
            "roles": ["Industrial", "Heavy Loader"]
        },
        "ship_stats": {
            "role": "Heavy Loader Exosuit",
            "size": 1,
            "body_hp": 2600.0,
            "shield_hp": 0.0,
            "shield_count": 0,
            "armor_physical": 0.9,
            "armor_energy": 0.75,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Tractor beam", "count": 1, "minimum": 2, "maximum": 2}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Heavy Armor Suit",
            "favors": 2,
            "favors_label": "2 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Council Scrip",
                    "amount": 15,
                    "label": "15 × Council Scrip",
                    "detail": "Stanton Council trade scrip tokens"
                },
                {
                    "name": "Pure Carinite",
                    "amount": 4,
                    "label": "4 × Pure Carinite",
                    "detail": "Refined pure mineral units"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-crusader-c1-spirit",
        "item_id": "wikelo-crusader-c1-spirit",
        "name": "Crusader C1 Spirit (Wikelo Edition)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Crusader C1 Spirit (Wikelo Edition)\n"
            "Ship · Crusader Industries\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Spirit of Barter\"\n"
            "Cost: 12 × Wikelo Favors + 2 × Comp-Board (DCHS-05) + 1 × ASD Secure Drive (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Medium freight runner tuned for long-distance trading runs across contested systems.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Crusader C1 Spirit Wikelo Edition Spirit of Barter Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Comp-Board DCHS-05 ASD Secure Drive Medium M hangar Ships Freight",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "2",
            "concept": False,
            "scu": 64,
            "length": 47.5,
            "width": 43.5,
            "height": 10.0,
            "mass": 182000,
            "roles": ["Freight", "Multi-role"]
        },
        "ship_stats": {
            "role": "Medium Hauler / Freight",
            "size": 3,
            "body_hp": 28000.0,
            "shield_hp": 9000.0,
            "shield_count": 1,
            "armor_physical": 0.8,
            "armor_energy": 0.65,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Guns", "count": 4, "minimum": 3, "maximum": 3},
                    {"label": "Tractor turret", "count": 1, "minimum": 3, "maximum": 3},
                    {"label": "Quantum drive", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Power plants", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Coolers", "count": 2, "minimum": 2, "maximum": 2}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Spirit of Barter",
            "favors": 12,
            "favors_label": "12 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Comp-Board (DCHS-05)",
                    "amount": 2,
                    "label": "2 × Comp-Board (DCHS-05)",
                    "detail": "Orbital positioning computation boards"
                },
                {
                    "name": "ASD Secure Drive",
                    "amount": 1,
                    "label": "1 × ASD Secure Drive",
                    "detail": "Encrypted secure data drive recovered from contested facilities"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-drake-vulture",
        "item_id": "wikelo-drake-vulture",
        "name": "Drake Vulture (Wikelo Scavenger)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Drake Vulture (Wikelo Scavenger)\n"
            "Ship · Drake Interplanetary\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Scrap Collector Trade\"\n"
            "Cost: 10 × Wikelo Favors + 3 × Pure Carinite + 25 × Council Scrip (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Solo salvage platform optimized for hull stripping and structural breakdown.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Drake Vulture Wikelo Scavenger Scrap Collector Trade Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Pure Carinite Council Scrip Small S hangar Ships Salvage",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 14,
            "length": 33.0,
            "width": 16.0,
            "height": 9.0,
            "mass": 125000,
            "roles": ["Salvage", "Industrial"]
        },
        "ship_stats": {
            "role": "Light Salvage",
            "size": 2,
            "body_hp": 12000.0,
            "shield_hp": 9000.0,
            "shield_count": 1,
            "armor_physical": 0.7,
            "armor_energy": 0.55,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Salvage scraper beams", "count": 2, "minimum": 1, "maximum": 1},
                    {"label": "Guns", "count": 2, "minimum": 3, "maximum": 3},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Coolers", "count": 2, "minimum": 1, "maximum": 1}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Scrap Collector Trade",
            "favors": 10,
            "favors_label": "10 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Pure Carinite",
                    "amount": 3,
                    "label": "3 × Pure Carinite",
                    "detail": "High-purity refined carinite ingots"
                },
                {
                    "name": "Council Scrip",
                    "amount": 25,
                    "label": "25 × Council Scrip",
                    "detail": "Council trade authorization scrips"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-aegis-gladius",
        "item_id": "wikelo-aegis-gladius",
        "name": "Aegis Gladius (Wikelo Veteran)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Aegis Gladius (Wikelo Veteran)\n"
            "Ship · Aegis Dynamics\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Banu's Best Fighter\"\n"
            "Cost: 8 × Wikelo Favors + 1 × Ace Interceptor Helmet + 2 × Pristine GCA Medal (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Battle-proven frontline light fighter with high maneuverability and combat tuning.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Aegis Gladius Wikelo Veteran Banu's Best Fighter Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Ace Interceptor Helmet GCA Medal Pristine Small S hangar Ships Fighter",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 0,
            "length": 20.0,
            "width": 17.0,
            "height": 5.5,
            "mass": 49000,
            "roles": ["Combat", "Light Fighter"]
        },
        "ship_stats": {
            "role": "Light Fighter",
            "size": 2,
            "body_hp": 4500.0,
            "shield_hp": 4320.0,
            "shield_count": 2,
            "armor_physical": 0.8,
            "armor_energy": 0.65,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 2, "minimum": 1, "maximum": 1},
                    {"label": "Guns", "count": 3, "minimum": 3, "maximum": 3},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Coolers", "count": 2, "minimum": 1, "maximum": 1}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Banu's Best Fighter",
            "favors": 8,
            "favors_label": "8 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Ace Interceptor Helmet",
                    "amount": 1,
                    "label": "1 × Ace Interceptor Helmet",
                    "detail": "Rare pilot helmet recovered from elite bounty targets"
                },
                {
                    "name": "Government Cartography Agency Medal (Pristine)",
                    "amount": 2,
                    "label": "2 × Pristine GCA Medal",
                    "detail": "Pristine cartography agency medal tokens"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-mirai-fury",
        "item_id": "wikelo-mirai-fury",
        "name": "Mirai Fury (Wikelo Compact)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Mirai Fury (Wikelo Compact)\n"
            "Ship · Mirai\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Pocket Knife Special\"\n"
            "Cost: 5 × Wikelo Favors + 1 × Comp-Board (DCHS-05) + 20 × MG Scrip (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Ultra-compact snub fighter packed with four size 2 mounts and agility thrusters.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Mirai Fury Wikelo Compact Pocket Knife Special Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Comp-Board DCHS-05 MG Scrip Extra Small XS Snub Bay Ships Fighter",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 0,
            "length": 5.8,
            "width": 4.8,
            "height": 2.6,
            "mass": 10500,
            "roles": ["Combat", "Snub Fighter"]
        },
        "ship_stats": {
            "role": "Snub Fighter",
            "size": 1,
            "body_hp": 1800.0,
            "shield_hp": 4320.0,
            "shield_count": 2,
            "armor_physical": 0.7,
            "armor_energy": 0.6,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 2, "minimum": 1, "maximum": 1},
                    {"label": "Guns", "count": 4, "minimum": 2, "maximum": 2},
                    {"label": "Power plants", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Coolers", "count": 1, "minimum": 1, "maximum": 1}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Pocket Knife Special",
            "favors": 5,
            "favors_label": "5 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Comp-Board (DCHS-05)",
                    "amount": 1,
                    "label": "1 × Comp-Board (DCHS-05)",
                    "detail": "Orbital flight computation board"
                },
                {
                    "name": "MG Scrip",
                    "amount": 20,
                    "label": "20 × MG Scrip",
                    "detail": "Mining Guild scrips"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-anvil-terrapin",
        "item_id": "wikelo-anvil-terrapin",
        "name": "Anvil Terrapin (Wikelo Hardened)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Anvil Terrapin (Wikelo Hardened)\n"
            "Ship · Anvil Aerospace\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Shell of the Ancients\"\n"
            "Cost: 15 × Wikelo Favors + 2 × ASD Secure Drive + 30 × Carinite (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Armored recon scout hull reinforced with Banu structural bonding techniques.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Anvil Terrapin Wikelo Hardened Shell of the Ancients Wikelo Wikalo Wickalow Barter Turn-in Favor Favors ASD Secure Drive Carinite Small S hangar Ships Recon Pathfinder",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "2",
            "concept": False,
            "scu": 0,
            "length": 19.5,
            "width": 14.5,
            "height": 6.0,
            "mass": 84000,
            "roles": ["Exploration", "Pathfinder"]
        },
        "ship_stats": {
            "role": "Armored Recon / Pathfinder",
            "size": 2,
            "body_hp": 26000.0,
            "shield_hp": 18000.0,
            "shield_count": 2,
            "armor_physical": 0.9,
            "armor_energy": 0.8,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 2, "minimum": 2, "maximum": 2},
                    {"label": "Remote turret guns", "count": 2, "minimum": 2, "maximum": 2},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Coolers", "count": 2, "minimum": 2, "maximum": 2}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Shell of the Ancients",
            "favors": 15,
            "favors_label": "15 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "ASD Secure Drive",
                    "amount": 2,
                    "label": "2 × ASD Secure Drive",
                    "detail": "Encrypted security drives from contested facilities"
                },
                {
                    "name": "Carinite",
                    "amount": 30,
                    "label": "30 × Carinite",
                    "detail": "Refined dense mineral units"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-rsi-mantis",
        "item_id": "wikelo-rsi-mantis",
        "name": "RSI Mantis (Wikelo Interdictor)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "RSI Mantis (Wikelo Interdictor)\n"
            "Ship · Roberts Space Industries\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Snare Weaver\"\n"
            "Cost: 14 × Wikelo Favors + 2 × Comp-Board (DCHS-05) + 1 × Valakkar Fang (AAA) (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Quantum interdiction craft fitted with snare and dampener generators.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "RSI Mantis Wikelo Interdictor Snare Weaver Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Comp-Board DCHS-05 Valakkar Fang AAA Quantum Snare Small S hangar Ships",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 0,
            "length": 30.0,
            "width": 17.0,
            "height": 8.5,
            "mass": 65000,
            "roles": ["Interdiction", "Quantum Enforcement"]
        },
        "ship_stats": {
            "role": "Quantum Interdiction",
            "size": 2,
            "body_hp": 6000.0,
            "shield_hp": 4320.0,
            "shield_count": 2,
            "armor_physical": 0.75,
            "armor_energy": 0.6,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 2, "minimum": 1, "maximum": 1},
                    {"label": "Guns", "count": 2, "minimum": 3, "maximum": 3},
                    {"label": "Quantum snare", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Coolers", "count": 2, "minimum": 1, "maximum": 1}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Snare Weaver",
            "favors": 14,
            "favors_label": "14 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Comp-Board (DCHS-05)",
                    "amount": 2,
                    "label": "2 × Comp-Board (DCHS-05)",
                    "detail": "Orbital positioning computation boards"
                },
                {
                    "name": "Valakkar Fang (Grade AAA)",
                    "amount": 1,
                    "label": "1 × Valakkar Fang (AAA)",
                    "detail": "Apex creature trophy specimen from deep cavern depths"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-banu-defender",
        "item_id": "wikelo-banu-defender",
        "name": "Banu Defender (Wikelo Heritage)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Banu Defender (Wikelo Heritage)\n"
            "Ship · Banu\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Defend the Emporium\"\n"
            "Cost: 20 × Wikelo Favors + 4 × Irradiated Valakkar Pearls (AA) + 2 × Banu Soul Token (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Two-crew Banu escort fighter with Singe tachyon weapon systems and Sukoran shielding.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Banu Defender Wikelo Heritage Defend the Emporium Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Valakkar Pearls AA Banu Soul Token Alien Fighter Small S hangar Ships",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "2",
            "concept": False,
            "scu": 0,
            "length": 33.5,
            "width": 28.0,
            "height": 9.0,
            "mass": 78000,
            "roles": ["Alien", "Heavy Escort Fighter"]
        },
        "ship_stats": {
            "role": "Alien Escort Fighter",
            "size": 2,
            "body_hp": 11500.0,
            "shield_hp": 9500.0,
            "shield_count": 1,
            "armor_physical": 0.85,
            "armor_energy": 0.8,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Guns (Singe)", "count": 4, "minimum": 3, "maximum": 3},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Coolers", "count": 2, "minimum": 1, "maximum": 1}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Defend the Emporium",
            "favors": 20,
            "favors_label": "20 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Irradiated Valakkar Pearls (Grade AA)",
                    "amount": 4,
                    "label": "4 × Irradiated Valakkar Pearls (AA)",
                    "detail": "Rare high-grade irradiated pearl specimens"
                },
                {
                    "name": "Banu Soul Token",
                    "amount": 2,
                    "label": "2 × Banu Soul Token",
                    "detail": "Traditional Banu guild barter tokens"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-anvil-f8c-lightning",
        "item_id": "wikelo-anvil-f8c-lightning",
        "name": "Anvil F8C Lightning (Wikelo Executive)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Anvil F8C Lightning (Wikelo Executive)\n"
            "Ship · Anvil Aerospace\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Executive Lightning Contract\"\n"
            "Cost: 35 × Wikelo Favors + 4 × UEE 6th Platoon Medal + 3 × ASD Secure Drive + 2 × Comp-Board (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Elite civilian space superiority fighter outfitted with eight gun hardpoints and heavy military armor.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Anvil F8C Lightning Wikelo Executive Executive Lightning Contract Wikelo Wikalo Wickalow Barter Turn-in Favor Favors UEE 6th Platoon Medal ASD Secure Drive Comp-Board Heavy Fighter Small S hangar Ships",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 0,
            "length": 26.0,
            "width": 22.0,
            "height": 7.0,
            "mass": 72000,
            "roles": ["Combat", "Heavy Fighter"]
        },
        "ship_stats": {
            "role": "Heavy Fighter / Superiority",
            "size": 2,
            "body_hp": 19000.0,
            "shield_hp": 18000.0,
            "shield_count": 2,
            "armor_physical": 0.85,
            "armor_energy": 0.7,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 2, "minimum": 2, "maximum": 2},
                    {"label": "Guns (Size 2)", "count": 6, "minimum": 2, "maximum": 2},
                    {"label": "Guns (Size 3)", "count": 2, "minimum": 3, "maximum": 3},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 2, "minimum": 1, "maximum": 1},
                    {"label": "Coolers", "count": 2, "minimum": 1, "maximum": 1}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Executive Lightning Contract",
            "favors": 35,
            "favors_label": "35 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "UEE 6th Platoon Medal",
                    "amount": 4,
                    "label": "4 × UEE 6th Platoon Medal",
                    "detail": "Rare military platoon medal decorations"
                },
                {
                    "name": "ASD Secure Drive",
                    "amount": 3,
                    "label": "3 × ASD Secure Drive",
                    "detail": "Contested zone high-security drives"
                },
                {
                    "name": "Comp-Board (DCHS-05)",
                    "amount": 2,
                    "label": "2 × Comp-Board (DCHS-05)",
                    "detail": "Orbital positioning computation boards"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-rsi-polaris",
        "item_id": "wikelo-rsi-polaris",
        "name": "RSI Polaris (Wikelo Special)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "RSI Polaris (Wikelo Special)\n"
            "Ship · Roberts Space Industries\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Grand Barter Flagship\"\n"
            "Cost: 60 × Wikelo Favors + 15 × Polaris Bits + 5 × Comp-Board + 6 × Valakkar Fang (AAA) + 10 × Pure Carinite (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Corvette-class capital flagship equipped with Size 10 torpedo tubes, fighter hangar, and capital radar.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "RSI Polaris Wikelo Special Grand Barter Flagship Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Polaris Bits Comp-Board DCHS-05 Valakkar Fang AAA Pure Carinite Capital Corvette Docking Ships",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "6–14",
            "concept": False,
            "scu": 576,
            "length": 155.0,
            "width": 82.0,
            "height": 35.0,
            "mass": 17150000,
            "roles": ["Corvette", "Capital", "Torpedo Destroyer"]
        },
        "ship_stats": {
            "role": "Capital Corvette",
            "size": 6,
            "body_hp": 280000.0,
            "shield_hp": 100000.0,
            "shield_count": 1,
            "armor_physical": 0.95,
            "armor_energy": 0.85,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Capital shield", "count": 1, "minimum": 4, "maximum": 4},
                    {"label": "Torpedo tubes (Size 10)", "count": 4, "minimum": 10, "maximum": 10},
                    {"label": "Turrets (Dual Size 5)", "count": 5, "minimum": 5, "maximum": 5},
                    {"label": "Turrets (Dual Size 4)", "count": 2, "minimum": 4, "maximum": 4},
                    {"label": "Capital power plant", "count": 2, "minimum": 4, "maximum": 4},
                    {"label": "Capital cooler", "count": 3, "minimum": 4, "maximum": 4}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Grand Barter Flagship",
            "favors": 60,
            "favors_label": "60 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Polaris Bits",
                    "amount": 15,
                    "label": "15 × Polaris Bits",
                    "detail": "Salvaged components recovered from capital wreck sites"
                },
                {
                    "name": "Comp-Board (DCHS-05)",
                    "amount": 5,
                    "label": "5 × Comp-Board (DCHS-05)",
                    "detail": "Capital positioning computation boards"
                },
                {
                    "name": "Valakkar Fang (Grade AAA)",
                    "amount": 6,
                    "label": "6 × Valakkar Fang (AAA)",
                    "detail": "Apex cave creature trophy specimens"
                },
                {
                    "name": "Pure Carinite",
                    "amount": 10,
                    "label": "10 × Pure Carinite",
                    "detail": "Refined pure carinite ingots"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-drake-cutlass-black",
        "item_id": "wikelo-drake-cutlass-black",
        "name": "Drake Cutlass Black (Wikelo Outlaw)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "Drake Cutlass Black (Wikelo Outlaw)\n"
            "Ship · Drake Interplanetary\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Black Market Runner\"\n"
            "Cost: 8 × Wikelo Favors + 2 × Pure Carinite + 30 × MG Scrip (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Versatile medium fighter and cargo transport with reinforced hull bracing.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "Drake Cutlass Black Wikelo Outlaw Black Market Runner Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Pure Carinite MG Scrip Medium M hangar Ships Hauler Combat",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "2",
            "concept": False,
            "scu": 46,
            "length": 36.0,
            "width": 26.0,
            "height": 10.0,
            "mass": 115000,
            "roles": ["Combat", "Freight", "Multi-role"]
        },
        "ship_stats": {
            "role": "Medium Multi-role",
            "size": 3,
            "body_hp": 13000.0,
            "shield_hp": 9000.0,
            "shield_count": 1,
            "armor_physical": 0.75,
            "armor_energy": 0.6,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Pilot guns", "count": 4, "minimum": 3, "maximum": 3},
                    {"label": "Manned turret guns", "count": 2, "minimum": 3, "maximum": 3},
                    {"label": "Quantum drive", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Power plants", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Coolers", "count": 2, "minimum": 2, "maximum": 2}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Black Market Runner",
            "favors": 8,
            "favors_label": "8 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Pure Carinite",
                    "amount": 2,
                    "label": "2 × Pure Carinite",
                    "detail": "Refined pure carinite"
                },
                {
                    "name": "MG Scrip",
                    "amount": 30,
                    "label": "30 × MG Scrip",
                    "detail": "Mining Guild scrips"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    },
    {
        "id": "wikelo-misc-prospector",
        "item_id": "wikelo-misc-prospector",
        "name": "MISC Prospector (Wikelo Ore Runner)",
        "kind": "Ship",
        "category": "Wikelo Barter Ships",
        "source_category": "Wikelo Emporium",
        "detail": (
            "MISC Prospector (Wikelo Ore Runner)\n"
            "Ship · Musashi Industrial and Starflight Concern\n\n"
            "WIKELO TURN-IN CONTRACT\n"
            "Contract: \"Rock Hound Trade\"\n"
            "Cost: 10 × Wikelo Favors + 32 SCU Refined Quantainium + 2 × Pure Carinite (NO aUEC COST)\n"
            "Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            "Delivery: Station Freight Elevator\n"
            "Prerequisite: Complete \"Wikelo Arrive to System\" contract\n\n"
            "Industrial solo mining vessel fitted with specialized laser conduits and reinforced saddlebags.\n"
            "Source: starcitizen.tools/Wikelo"
        ),
        "search": "MISC Prospector Wikelo Ore Runner Rock Hound Trade Wikelo Wikalo Wickalow Barter Turn-in Favor Favors Quantainium Pure Carinite Small S hangar Ships Mining Industrial",
        "ship_overview": {
            "source": "Wikelo Emporium",
            "patch": "4.1.0",
            "crew": "1",
            "concept": False,
            "scu": 32,
            "length": 24.0,
            "width": 15.0,
            "height": 7.0,
            "mass": 98000,
            "roles": ["Mining", "Industrial"]
        },
        "ship_stats": {
            "role": "Solo Mining",
            "size": 2,
            "body_hp": 8800.0,
            "shield_hp": 4320.0,
            "shield_count": 2,
            "armor_physical": 0.7,
            "armor_energy": 0.55,
            "patch": "sc-alpha-4.10.2",
            "hardpoints": {
                "status": "ready",
                "groups": [
                    {"label": "Shields", "count": 2, "minimum": 1, "maximum": 1},
                    {"label": "Mining laser", "count": 1, "minimum": 2, "maximum": 2},
                    {"label": "Guns", "count": 2, "minimum": 1, "maximum": 1},
                    {"label": "Quantum drive", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Power plants", "count": 1, "minimum": 1, "maximum": 1},
                    {"label": "Coolers", "count": 2, "minimum": 1, "maximum": 1}
                ]
            }
        },
        "wikelo_turnin": {
            "task": "Rock Hound Trade",
            "favors": 10,
            "favors_label": "10 × Wikelo Favors",
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": [
                {
                    "name": "Refined Quantainium",
                    "amount": 32,
                    "label": "32 SCU Refined Quantainium",
                    "detail": "High-purity volatile refined fuel resource"
                },
                {
                    "name": "Pure Carinite",
                    "amount": 2,
                    "label": "2 × Pure Carinite",
                    "detail": "Refined pure carinite"
                }
            ],
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator"
        }
    }
]

def update_library_file(path_str):
    p = Path(path_str)
    if not p.exists():
        print(f"Skipping {p}: file not found")
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading {p}: {e}")
        return

    rows = data.get("rows", [])
    row_ids = {r.get("id"): idx for idx, r in enumerate(rows)}

    # Also map existing stock ships to enrich them with wikelo_turnin
    name_to_turnin = {
        "MISC Fortune": WIKELO_SHIPS[0]["wikelo_turnin"],
        "Crusader Intrepid": WIKELO_SHIPS[1]["wikelo_turnin"],
        "RSI Polaris": WIKELO_SHIPS[12]["wikelo_turnin"],
        "Crusader C1 Spirit": WIKELO_SHIPS[4]["wikelo_turnin"],
        "Drake Vulture": WIKELO_SHIPS[5]["wikelo_turnin"],
        "Aegis Gladius": WIKELO_SHIPS[6]["wikelo_turnin"],
        "Mirai Fury": WIKELO_SHIPS[7]["wikelo_turnin"],
        "Anvil Terrapin": WIKELO_SHIPS[8]["wikelo_turnin"],
        "RSI Mantis": WIKELO_SHIPS[9]["wikelo_turnin"],
        "Banu Defender": WIKELO_SHIPS[10]["wikelo_turnin"],
        "Anvil F8C Lightning": WIKELO_SHIPS[11]["wikelo_turnin"],
        "Drake Cutlass Black": WIKELO_SHIPS[13]["wikelo_turnin"],
        "MISC Prospector": WIKELO_SHIPS[14]["wikelo_turnin"],
    }

    # Enrich existing ships
    for r in rows:
        name = r.get("name")
        if name in name_to_turnin:
            r["wikelo_turnin"] = name_to_turnin[name]
            if "Wikelo" not in r.get("search", ""):
                r["search"] = r.get("search", "") + " Wikelo Wikalo Wickalow Barter Turn-in Favor Favors"

    # Insert or update dedicated Wikelo ships
    added = 0
    updated = 0
    for w in WIKELO_SHIPS:
        wid = w["id"]
        if wid in row_ids:
            rows[row_ids[wid]] = w
            updated += 1
        else:
            rows.insert(0, w)
            added += 1

    data["rows"] = rows
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)
    print(f"Updated {p}: added {added}, updated {updated}, total rows {len(rows)}")

if __name__ == "__main__":
    targets = [
        "dist/native/workspace_library.json",
        os.path.expandvars(r"%LOCALAPPDATA%\SynthScan\native\workspace_library.json"),
    ]
    for target in targets:
        update_library_file(target)
