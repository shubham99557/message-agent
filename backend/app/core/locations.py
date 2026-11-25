"""
Canonical Nationwide Location Directory for Indian Business Discovery.
Covers all 28 States and 8 Union Territories with standard regions, ISO codes,
major commercial/technology cities, and preserved target presets.
"""
from typing import List, Dict, Any, Optional

INDIAN_STATES_AND_UTS = [
    {"name": "Andhra Pradesh", "code": "AP", "region": "Southern"},
    {"name": "Arunachal Pradesh", "code": "AR", "region": "North-Eastern"},
    {"name": "Assam", "code": "AS", "region": "North-Eastern"},
    {"name": "Bihar", "code": "BR", "region": "Eastern"},
    {"name": "Chhattisgarh", "code": "CG", "region": "Central"},
    {"name": "Goa", "code": "GA", "region": "Western"},
    {"name": "Gujarat", "code": "GJ", "region": "Western"},
    {"name": "Haryana", "code": "HR", "region": "Northern"},
    {"name": "Himachal Pradesh", "code": "HP", "region": "Northern"},
    {"name": "Jharkhand", "code": "JH", "region": "Eastern"},
    {"name": "Karnataka", "code": "KA", "region": "Southern"},
    {"name": "Kerala", "code": "KL", "region": "Southern"},
    {"name": "Madhya Pradesh", "code": "MP", "region": "Central"},
    {"name": "Maharashtra", "code": "MH", "region": "Western"},
    {"name": "Manipur", "code": "MN", "region": "North-Eastern"},
    {"name": "Meghalaya", "code": "ML", "region": "North-Eastern"},
    {"name": "Mizoram", "code": "MZ", "region": "North-Eastern"},
    {"name": "Nagaland", "code": "NL", "region": "North-Eastern"},
    {"name": "Odisha", "code": "OR", "region": "Eastern"},
    {"name": "Punjab", "code": "PB", "region": "Northern"},
    {"name": "Rajasthan", "code": "RJ", "region": "Northern"},
    {"name": "Sikkim", "code": "SK", "region": "North-Eastern"},
    {"name": "Tamil Nadu", "code": "TN", "region": "Southern"},
    {"name": "Telangana", "code": "TG", "region": "Southern"},
    {"name": "Tripura", "code": "TR", "region": "North-Eastern"},
    {"name": "Uttar Pradesh", "code": "UP", "region": "Northern"},
    {"name": "Uttarakhand", "code": "UK", "region": "Northern"},
    {"name": "West Bengal", "code": "WB", "region": "Eastern"},
    # Union Territories
    {"name": "Andaman and Nicobar Islands", "code": "AN", "region": "Eastern"},
    {"name": "Chandigarh", "code": "CH", "region": "Northern"},
    {"name": "Dadra and Nagar Haveli and Daman and Diu", "code": "DH", "region": "Western"},
    {"name": "Delhi", "code": "DL", "region": "Northern"},
    {"name": "Jammu and Kashmir", "code": "JK", "region": "Northern"},
    {"name": "Ladakh", "code": "LA", "region": "Northern"},
    {"name": "Lakshadweep", "code": "LD", "region": "Southern"},
    {"name": "Puducherry", "code": "PY", "region": "Southern"},
]

REGIONS = [
    {"name": "Northern", "description": "Delhi NCR, Punjab, Haryana, Rajasthan, UP, Himachal, J&K, Uttarakhand"},
    {"name": "Southern", "description": "Karnataka, Tamil Nadu, Telangana, Andhra Pradesh, Kerala"},
    {"name": "Eastern", "description": "West Bengal, Bihar, Jharkhand, Odisha"},
    {"name": "Western", "description": "Maharashtra, Gujarat, Goa"},
    {"name": "Central", "description": "Madhya Pradesh, Chhattisgarh"},
    {"name": "North-Eastern", "description": "Sikkim, Assam, Meghalaya, Manipur, Mizoram, Nagaland, Tripura, Arunachal Pradesh"},
]

CANONICAL_CITIES: List[Dict[str, Any]] = [
    # Initial Target Cities (Preserved as Primary Presets)
    {"city": "Siliguri", "state": "West Bengal", "region": "Eastern", "tier": "Tier 2", "pincode_prefix": "734", "is_target_preset": True},
    {"city": "Gangtok", "state": "Sikkim", "region": "North-Eastern", "tier": "Tier 2", "pincode_prefix": "737", "is_target_preset": True},
    {"city": "Patna", "state": "Bihar", "region": "Eastern", "tier": "Tier 2", "pincode_prefix": "800", "is_target_preset": True},
    {"city": "Bhagalpur", "state": "Bihar", "region": "Eastern", "tier": "Tier 3", "pincode_prefix": "812", "is_target_preset": True},
    
    # Tier 1 Metros & Major Technology Hubs
    {"city": "Bengaluru", "state": "Karnataka", "region": "Southern", "tier": "Tier 1", "pincode_prefix": "560", "is_target_preset": False},
    {"city": "Hyderabad", "state": "Telangana", "region": "Southern", "tier": "Tier 1", "pincode_prefix": "500", "is_target_preset": False},
    {"city": "Pune", "state": "Maharashtra", "region": "Western", "tier": "Tier 1", "pincode_prefix": "411", "is_target_preset": False},
    {"city": "Mumbai", "state": "Maharashtra", "region": "Western", "tier": "Tier 1", "pincode_prefix": "400", "is_target_preset": False},
    {"city": "Delhi", "state": "Delhi", "region": "Northern", "tier": "Tier 1", "pincode_prefix": "110", "is_target_preset": False},
    {"city": "Noida", "state": "Uttar Pradesh", "region": "Northern", "tier": "Tier 1", "pincode_prefix": "201", "is_target_preset": False},
    {"city": "Gurugram", "state": "Haryana", "region": "Northern", "tier": "Tier 1", "pincode_prefix": "122", "is_target_preset": False},
    {"city": "Chennai", "state": "Tamil Nadu", "region": "Southern", "tier": "Tier 1", "pincode_prefix": "600", "is_target_preset": False},
    {"city": "Kolkata", "state": "West Bengal", "region": "Eastern", "tier": "Tier 1", "pincode_prefix": "700", "is_target_preset": False},
    {"city": "Ahmedabad", "state": "Gujarat", "region": "Western", "tier": "Tier 1", "pincode_prefix": "380", "is_target_preset": False},

    # Additional Emerging Technology & Industrial Centers (Tier 2 / Tier 3)
    {"city": "Jaipur", "state": "Rajasthan", "region": "Northern", "tier": "Tier 2", "pincode_prefix": "302", "is_target_preset": False},
    {"city": "Indore", "state": "Madhya Pradesh", "region": "Central", "tier": "Tier 2", "pincode_prefix": "452", "is_target_preset": False},
    {"city": "Kochi", "state": "Kerala", "region": "Southern", "tier": "Tier 2", "pincode_prefix": "682", "is_target_preset": False},
    {"city": "Thiruvananthapuram", "state": "Kerala", "region": "Southern", "tier": "Tier 2", "pincode_prefix": "695", "is_target_preset": False},
    {"city": "Bhubaneswar", "state": "Odisha", "region": "Eastern", "tier": "Tier 2", "pincode_prefix": "751", "is_target_preset": False},
    {"city": "Chandigarh", "state": "Chandigarh", "region": "Northern", "tier": "Tier 2", "pincode_prefix": "160", "is_target_preset": False},
    {"city": "Lucknow", "state": "Uttar Pradesh", "region": "Northern", "tier": "Tier 2", "pincode_prefix": "226", "is_target_preset": False},
    {"city": "Coimbatore", "state": "Tamil Nadu", "region": "Southern", "tier": "Tier 2", "pincode_prefix": "641", "is_target_preset": False},
    {"city": "Surat", "state": "Gujarat", "region": "Western", "tier": "Tier 2", "pincode_prefix": "395", "is_target_preset": False},
    {"city": "Nagpur", "state": "Maharashtra", "region": "Western", "tier": "Tier 2", "pincode_prefix": "440", "is_target_preset": False},
    {"city": "Vadodara", "state": "Gujarat", "region": "Western", "tier": "Tier 2", "pincode_prefix": "390", "is_target_preset": False},
    {"city": "Guwahati", "state": "Assam", "region": "North-Eastern", "tier": "Tier 2", "pincode_prefix": "781", "is_target_preset": False},
    {"city": "Ranchi", "state": "Jharkhand", "region": "Eastern", "tier": "Tier 2", "pincode_prefix": "834", "is_target_preset": False},
    {"city": "Jamshedpur", "state": "Jharkhand", "region": "Eastern", "tier": "Tier 2", "pincode_prefix": "831", "is_target_preset": False},
    {"city": "Durgapur", "state": "West Bengal", "region": "Eastern", "tier": "Tier 2", "pincode_prefix": "713", "is_target_preset": False},
    {"city": "Asansol", "state": "West Bengal", "region": "Eastern", "tier": "Tier 2", "pincode_prefix": "713", "is_target_preset": False},
    {"city": "Muzaffarpur", "state": "Bihar", "region": "Eastern", "tier": "Tier 3", "pincode_prefix": "842", "is_target_preset": False},
    {"city": "Gaya", "state": "Bihar", "region": "Eastern", "tier": "Tier 3", "pincode_prefix": "823", "is_target_preset": False},
    {"city": "Mangaluru", "state": "Karnataka", "region": "Southern", "tier": "Tier 2", "pincode_prefix": "575", "is_target_preset": False},
    {"city": "Mysuru", "state": "Karnataka", "region": "Southern", "tier": "Tier 2", "pincode_prefix": "570", "is_target_preset": False},
    {"city": "Visakhapatnam", "state": "Andhra Pradesh", "region": "Southern", "tier": "Tier 2", "pincode_prefix": "530", "is_target_preset": False},
    {"city": "Vijayawada", "state": "Andhra Pradesh", "region": "Southern", "tier": "Tier 2", "pincode_prefix": "520", "is_target_preset": False},
    {"city": "Bhopal", "state": "Madhya Pradesh", "region": "Central", "tier": "Tier 2", "pincode_prefix": "462", "is_target_preset": False},
    {"city": "Dehradun", "state": "Uttarakhand", "region": "Northern", "tier": "Tier 2", "pincode_prefix": "248", "is_target_preset": False},
    {"city": "Shimla", "state": "Himachal Pradesh", "region": "Northern", "tier": "Tier 3", "pincode_prefix": "171", "is_target_preset": False},
    {"city": "Raipur", "state": "Chhattisgarh", "region": "Central", "tier": "Tier 2", "pincode_prefix": "492", "is_target_preset": False},
    {"city": "Panaji", "state": "Goa", "region": "Western", "tier": "Tier 3", "pincode_prefix": "403", "is_target_preset": False},
    {"city": "Shillong", "state": "Meghalaya", "region": "North-Eastern", "tier": "Tier 3", "pincode_prefix": "793", "is_target_preset": False},
    {"city": "Agartala", "state": "Tripura", "region": "North-Eastern", "tier": "Tier 3", "pincode_prefix": "799", "is_target_preset": False},
]

SAVED_LOCATION_PRESETS = [
    {
        "id": "target_east_northeast",
        "name": "ActTrident Core Regional Focus",
        "description": "Original four focus cities: Siliguri, Gangtok, Patna, and Bhagalpur",
        "cities": ["Siliguri", "Gangtok", "Patna", "Bhagalpur"],
    },
    {
        "id": "tier1_tech_metros",
        "name": "Tier 1 Tech Metros",
        "description": "Major Indian technology capitals (Bengaluru, Hyderabad, Pune, Mumbai, Delhi NCR, Chennai)",
        "cities": ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "Gurugram", "Noida", "Chennai"],
    },
    {
        "id": "east_india_hubs",
        "name": "Eastern India Commercial Hubs",
        "description": "Kolkata, Patna, Bhubaneswar, Ranchi, Siliguri, Bhagalpur",
        "cities": ["Kolkata", "Patna", "Bhubaneswar", "Ranchi", "Siliguri", "Bhagalpur"],
    },
    {
        "id": "northeast_corridor",
        "name": "North-Eastern Economic Corridor",
        "description": "Gangtok, Guwahati, Shillong, Siliguri, Agartala",
        "cities": ["Gangtok", "Guwahati", "Shillong", "Siliguri", "Agartala"],
    },
]

DISCOVERY_INDUSTRIES = [
    {"id": "software_dev", "name": "Software Development & SaaS", "keywords": "software development, web apps, SaaS, mobile applications"},
    {"id": "it_services", "name": "IT Services & Cloud Hosting", "keywords": "IT infrastructure, cloud management, hosting, devops, networks"},
    {"id": "digital_marketing", "name": "Digital Marketing & Web Design", "keywords": "SEO, performance marketing, digital marketing, creative agency, web design"},
    {"id": "bpo_kpo", "name": "BPO, KPO & Call Centres", "keywords": "customer support, back office, BPO, KPO, telecalling, outsourced operations"},
    {"id": "it_consulting", "name": "IT Consulting & System Integration", "keywords": "technology consulting, ERP integration, cybersecurity, enterprise solutions"},
    {"id": "education", "name": "Educational Institutions & Universities", "keywords": "colleges, universities, private schools, academic institutions"},
    {"id": "computer_training", "name": "Computer Training & Skill Development Centers", "keywords": "coding bootcamp, IT training, computer academy, certification centers"},
    {"id": "healthcare", "name": "Hospitals & Healthcare Organisations", "keywords": "hospitals, diagnostic clinics, medical research labs, healthcare centers"},
    {"id": "fintech_bfsi", "name": "Financial Services, FinTech & Banking", "keywords": "NBFC, microfinance, fintech, accounting firms, wealth management"},
    {"id": "manufacturing", "name": "Manufacturing & Industrial Enterprises", "keywords": "factories, engineering works, packaging, production units, textiles"},
    {"id": "corporate_offices", "name": "Corporate & Regional Enterprise Offices", "keywords": "corporate headquarters, regional business offices, executive centers"},
    {"id": "ecommerce_retail", "name": "E-Commerce & Retail Technology", "keywords": "online retail, D2C brands, warehouse operations, logistics technology"},
]


def get_states_and_uts() -> List[Dict[str, Any]]:
    return INDIAN_STATES_AND_UTS


def get_regions() -> List[Dict[str, Any]]:
    return REGIONS


def get_presets() -> List[Dict[str, Any]]:
    return SAVED_LOCATION_PRESETS


def get_industries() -> List[Dict[str, Any]]:
    return DISCOVERY_INDUSTRIES


def search_locations(
    query: str = "",
    state: Optional[str] = None,
    region: Optional[str] = None,
    pincode: Optional[str] = None,
    limit: int = 15
) -> List[Dict[str, Any]]:
    """
    Search canonical locations with debounced autocomplete support across city,
    state, district, region, and PIN prefix.
    """
    q = (query or "").strip().lower()
    st_filter = (state or "").strip().lower()
    reg_filter = (region or "").strip().lower()
    pin_filter = (pincode or "").strip()

    matches = []
    for item in CANONICAL_CITIES:
        if st_filter and item["state"].lower() != st_filter:
            continue
        if reg_filter and item["region"].lower() != reg_filter:
            continue
        if pin_filter and not item["pincode_prefix"].startswith(pin_filter[:3]):
            continue

        if not q:
            matches.append(item)
        else:
            city_match = q in item["city"].lower()
            state_match = q in item["state"].lower()
            region_match = q in item["region"].lower()
            pin_match = q in item["pincode_prefix"]
            if city_match or state_match or region_match or pin_match:
                matches.append(item)

        if len(matches) >= limit:
            break

    return matches


def get_canonical_location(city_name: str) -> Optional[Dict[str, Any]]:
    """Retrieves canonical metadata for a specified city name."""
    if not city_name:
        return None
    target = city_name.strip().lower()
    for item in CANONICAL_CITIES:
        if item["city"].lower() == target:
            return item
    return None


def get_nationwide_search_batches(batch_size: int = 4) -> List[List[Dict[str, Any]]]:
    """
    Generates balanced geographic batches for controlled All India discovery runs.
    Ensures diverse regional coverage across Tier 1 and Tier 2 cities without overwhelming rate limits.
    """
    priority_sample = [
        # Metros
        {"city": "Bengaluru", "state": "Karnataka", "region": "Southern"},
        {"city": "Hyderabad", "state": "Telangana", "region": "Southern"},
        {"city": "Pune", "state": "Maharashtra", "region": "Western"},
        {"city": "Delhi", "state": "Delhi", "region": "Northern"},
        {"city": "Noida", "state": "Uttar Pradesh", "region": "Northern"},
        {"city": "Kolkata", "state": "West Bengal", "region": "Eastern"},
        {"city": "Chennai", "state": "Tamil Nadu", "region": "Southern"},
        {"city": "Mumbai", "state": "Maharashtra", "region": "Western"},
        # Regional Hubs (Including ActTrident Presets)
        {"city": "Siliguri", "state": "West Bengal", "region": "Eastern"},
        {"city": "Patna", "state": "Bihar", "region": "Eastern"},
        {"city": "Gangtok", "state": "Sikkim", "region": "North-Eastern"},
        {"city": "Bhagalpur", "state": "Bihar", "region": "Eastern"},
        {"city": "Indore", "state": "Madhya Pradesh", "region": "Central"},
        {"city": "Bhubaneswar", "state": "Odisha", "region": "Eastern"},
        {"city": "Kochi", "state": "Kerala", "region": "Southern"},
        {"city": "Jaipur", "state": "Rajasthan", "region": "Northern"},
    ]
    batches = []
    for i in range(0, len(priority_sample), batch_size):
        batches.append(priority_sample[i:i + batch_size])
    return batches
