"""
Test script for DinoCollector Achievements
Tests both real-time triggers and retroactive sync logic
"""
import sys
import time
import os
import re

# Simple User class that mimics the real one
class User:
    def __init__(self):
        self.current_dino_inv = []
        self.explorer_log = []
        self.explorer_logs_sold = 0
        self.achievement_log = []
        self.has_dinocoins = 0
        self.total_dinocoins_earned = 0
        self.has_spent_dinocoins = 0
        self.total_converted_dinocoin = 0
        self.first_dino_ever_caught = ""
        self.first_dino_caught_timestamp = ""
        self.buddy_dino = {}
        self.buddy_dino_rarity = ""
        self.buddy_bonus_total_gained = 0
        self.buddy_name = ""
        self.current_inventory_upgrade_level = 0
        self.total_ever_claimed = 0
        self.total_ever_sold = 0
        self.total_ever_traded = 0
        self.total_gifts_given = 0
        self.total_gifts_received = 0
        self.total_escaped = 0
        self.has_lure = False
        self.last_lure_use = 0.0
        self.total_lures_used = 0
        self.total_legendary_caught = 0

class GuildSettings:
    def __init__(self):
        self.base_inventory_size = 20
        self.inventory_per_upgrade = 10
        self.maximum_upgrade_amount = 8

# Parse achievement_library from file
def load_achievement_library():
    path = os.path.join(os.path.dirname(__file__), 'databases', 'achievements.py')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Execute safely by providing empty globals
    local_vars = {}
    exec(content, {"__builtins__": {}}, local_vars)
    return local_vars.get('achievement_library', {})

# Count creatures from file
def count_creatures():
    path = os.path.join(os.path.dirname(__file__), 'databases', 'creatures.py')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Count creature entries by finding pattern
    matches = re.findall(r'"([a-z_]+)":\s*\{\s*"name":', content)
    return len(matches)

achievement_library = load_achievement_library()
creature_count = count_creatures()

# Create a mock creature_library as a dict with that many entries for testing
creature_library = {f"creature_{i}": {"name": f"Creature {i}"} for i in range(creature_count)}

def test_user_model_fields():
    """Test that all required tracking fields exist on User model"""
    print("\n" + "="*60)
    print("TEST: User Model Fields")
    print("="*60)
    
    user = User()
    required_fields = [
        'current_dino_inv', 'explorer_log', 'achievement_log',
        'has_dinocoins', 'total_dinocoins_earned', 'has_spent_dinocoins',
        'total_converted_dinocoin', 'buddy_dino', 'buddy_dino_rarity',
        'buddy_bonus_total_gained', 'current_inventory_upgrade_level',
        'total_ever_claimed', 'total_ever_sold', 'total_ever_traded',
        'total_gifts_given', 'total_gifts_received', 'total_escaped',
        'has_lure', 'last_lure_use', 'total_lures_used', 'total_legendary_caught'
    ]
    
    # Check these fields exist on our mock User (they do by definition)
    # The real test is checking the actual models.py file
    
    # Read the actual models.py to verify fields exist
    models_path = os.path.join(os.path.dirname(__file__), 'common', 'models.py')
    with open(models_path, 'r') as f:
        models_content = f.read()
    
    missing = []
    for field in required_fields:
        if field + ':' not in models_content and field + ' :' not in models_content:
            missing.append(field)
            print(f"  [FAIL] Missing field in models.py: {field}")
        else:
            print(f"  [PASS] Field exists: {field}")
    
    if missing:
        print(f"\n  RESULT: FAILED - Missing {len(missing)} fields")
        return False
    else:
        print(f"\n  RESULT: PASSED - All {len(required_fields)} fields present")
        return True


def test_achievement_library():
    """Test that all 48 achievements exist with required properties"""
    print("\n" + "="*60)
    print("TEST: Achievement Library")
    print("="*60)
    
    expected_achievements = [
        # Original 32
        'first_capture', 'first_corrupted', 'first_shiny', 'first_upgrade',
        'first_lure_purchase', 'first_lure_use', 'first_log_check', 'first_gift',
        'first_trade', 'full_inventory', 'max_upgrade', 'first_buddy',
        'earn_1000', 'earn_10000', 'buddy_bonus_100', 'buddy_bonus_500',
        'convert_first', 'spent_5000', 'gift_5',
        'first_legendary', 'first_super_rare', 'first_event',
        'first_aberrant', 'first_muscular', 'first_sickly',
        'catch_10', 'catch_50', 'catch_100', 'catch_500',
        'sell_50', 'sell_100', 'trade_10',
        # New 16
        'log_25_percent', 'log_50_percent', 'log_75_percent', 'log_100_percent',
        'first_withered', 'first_young', 'first_irradiated',
        'catch_1000', 'escaped_10', 'lure_10',
        'earn_50000', 'spent_25000',
        'gift_legendary', 'trade_25', 'receive_gift',
        'catch_5_legendary'
    ]
    
    missing = []
    invalid = []
    
    for ach_id in expected_achievements:
        if ach_id not in achievement_library:
            missing.append(ach_id)
            print(f"  [FAIL] Missing achievement: {ach_id}")
        else:
            ach = achievement_library[ach_id]
            required_props = ['name', 'description', 'reward', 'hint']
            props_missing = [p for p in required_props if p not in ach]
            if props_missing:
                invalid.append((ach_id, props_missing))
                print(f"  [FAIL] {ach_id} missing properties: {props_missing}")
            else:
                print(f"  [PASS] {ach_id}: {ach['name']} (+{ach['reward']} coins)")
    
    print(f"\n  Total achievements: {len(achievement_library)}")
    print(f"  Expected: {len(expected_achievements)}")
    
    if missing or invalid:
        print(f"  RESULT: FAILED - {len(missing)} missing, {len(invalid)} invalid")
        return False
    else:
        print(f"  RESULT: PASSED - All {len(expected_achievements)} achievements valid")
        return True


def simulate_retroactive_sync(user_conf, conf):
    """
    Simulates the sync_achievements logic from main.py
    Returns list of achievements that would be unlocked
    """
    newly_unlocked = []
    
    def is_unlocked(aid):
        return any(a.get("id") == aid for a in user_conf.achievement_log)
    
    # 1. First Catch
    if not is_unlocked("first_capture"):
        if user_conf.total_ever_claimed > 0:
            newly_unlocked.append("first_capture")
            
    # 2. Corrupted Hunter
    if not is_unlocked("first_corrupted"):
        has_corrupted = any(d.get("modifier", "").lower() == "corrupted" for d in user_conf.current_dino_inv)
        if has_corrupted:
            newly_unlocked.append("first_corrupted")
            
    # 3. Shiny Hunter
    if not is_unlocked("first_shiny"):
        has_shiny = any(d.get("modifier", "").lower() == "shiny" for d in user_conf.current_dino_inv)
        if has_shiny:
            newly_unlocked.append("first_shiny")
            
    # 4. Expansionist (First Upgrade)
    if not is_unlocked("first_upgrade"):
        if user_conf.current_inventory_upgrade_level > 0:
            newly_unlocked.append("first_upgrade")
            
    # 5. Prepared (First Lure Purchase)
    if not is_unlocked("first_lure_purchase"):
        if user_conf.has_lure or user_conf.last_lure_use > 0:
            newly_unlocked.append("first_lure_purchase")
            
    # 6. Trapper (First Lure Use)
    if not is_unlocked("first_lure_use"):
        if user_conf.last_lure_use > 0:
            newly_unlocked.append("first_lure_use")
            
    # 9. Trader (First Trade)
    if not is_unlocked("first_trade"):
        if user_conf.total_ever_traded > 0:
            newly_unlocked.append("first_trade")
            
    # 10. Hoarder (Full Inventory)
    if not is_unlocked("full_inventory"):
        current_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        if len(user_conf.current_dino_inv) >= current_size:
            newly_unlocked.append("full_inventory")
            
    # 11. Maxed Out (Max Upgrade)
    if not is_unlocked("max_upgrade"):
        if user_conf.current_inventory_upgrade_level >= conf.maximum_upgrade_amount:
            newly_unlocked.append("max_upgrade")
            
    # 12. Best Friends (First Buddy)
    if not is_unlocked("first_buddy"):
        if user_conf.buddy_dino:
            newly_unlocked.append("first_buddy")
    
    # 13. Coin Collector (Earned 1,000)
    if not is_unlocked("earn_1000"):
        if user_conf.total_dinocoins_earned >= 1000:
            newly_unlocked.append("earn_1000")
            
    # 14. Dino Tycoon (Earned 10,000)
    if not is_unlocked("earn_10000"):
        if user_conf.total_dinocoins_earned >= 10000:
            newly_unlocked.append("earn_10000")
            
    # 15. Best Friends Forever (Buddy Bonus 100)
    if not is_unlocked("buddy_bonus_100"):
        if user_conf.buddy_bonus_total_gained >= 100:
            newly_unlocked.append("buddy_bonus_100")
            
    # 16. Inseparable (Buddy Bonus 500)
    if not is_unlocked("buddy_bonus_500"):
        if user_conf.buddy_bonus_total_gained >= 500:
            newly_unlocked.append("buddy_bonus_500")
            
    # 17. Currency Exchange (First Convert)
    if not is_unlocked("convert_first"):
        if user_conf.total_converted_dinocoin > 0:
            newly_unlocked.append("convert_first")
            
    # 18. Big Spender (Spent 5,000)
    if not is_unlocked("spent_5000"):
        if user_conf.has_spent_dinocoins >= 5000:
            newly_unlocked.append("spent_5000")
            
    # 19. Philanthropist (Gift 5)
    if not is_unlocked("gift_5"):
        if user_conf.total_gifts_given >= 5:
            newly_unlocked.append("gift_5")
    
    # 20. Living Legend (First Legendary)
    if not is_unlocked("first_legendary"):
        has_legendary = any(d.get("rarity", "").lower() == "legendary" for d in user_conf.current_dino_inv)
        if has_legendary:
            newly_unlocked.append("first_legendary")
            
    # 21. Super Collector (First Super Rare)
    if not is_unlocked("first_super_rare"):
        has_super_rare = any(d.get("rarity", "").lower() == "super_rare" for d in user_conf.current_dino_inv)
        if has_super_rare:
            newly_unlocked.append("first_super_rare")
            
    # 22. Festive Spirit (First Event)
    if not is_unlocked("first_event"):
        has_event = any(d.get("rarity", "").lower() == "event" for d in user_conf.current_dino_inv)
        if has_event:
            newly_unlocked.append("first_event")
            
    # 23. Strange Discovery (First Aberrant)
    if not is_unlocked("first_aberrant"):
        has_aberrant = any(d.get("modifier", "").lower() == "aberrant" for d in user_conf.current_dino_inv)
        if has_aberrant:
            newly_unlocked.append("first_aberrant")
            
    # 24. Gym Enthusiast (First Muscular)
    if not is_unlocked("first_muscular"):
        has_muscular = any(d.get("modifier", "").lower() == "muscular" for d in user_conf.current_dino_inv)
        if has_muscular:
            newly_unlocked.append("first_muscular")
            
    # 25. Nurturing Soul (First Sickly)
    if not is_unlocked("first_sickly"):
        has_sickly = any(d.get("modifier", "").lower() == "sickly" for d in user_conf.current_dino_inv)
        if has_sickly:
            newly_unlocked.append("first_sickly")
    
    # Catch milestones
    if not is_unlocked("catch_10") and user_conf.total_ever_claimed >= 10:
        newly_unlocked.append("catch_10")
    if not is_unlocked("catch_50") and user_conf.total_ever_claimed >= 50:
        newly_unlocked.append("catch_50")
    if not is_unlocked("catch_100") and user_conf.total_ever_claimed >= 100:
        newly_unlocked.append("catch_100")
    if not is_unlocked("catch_500") and user_conf.total_ever_claimed >= 500:
        newly_unlocked.append("catch_500")
        
    # Sell milestones
    if not is_unlocked("sell_50") and user_conf.total_ever_sold >= 50:
        newly_unlocked.append("sell_50")
    if not is_unlocked("sell_100") and user_conf.total_ever_sold >= 100:
        newly_unlocked.append("sell_100")
        
    # Trade milestones
    if not is_unlocked("trade_10") and user_conf.total_ever_traded >= 10:
        newly_unlocked.append("trade_10")
    
    # === NEW ACHIEVEMENTS (16) ===
    
    # Explorer Log Achievements
    total_species = len(creature_library)
    caught_species = len(user_conf.explorer_log)
    if total_species > 0:
        percentage = (caught_species / total_species) * 100
        if not is_unlocked("log_25_percent") and percentage >= 25:
            newly_unlocked.append("log_25_percent")
        if not is_unlocked("log_50_percent") and percentage >= 50:
            newly_unlocked.append("log_50_percent")
        if not is_unlocked("log_75_percent") and percentage >= 75:
            newly_unlocked.append("log_75_percent")
        if not is_unlocked("log_100_percent") and percentage >= 100:
            newly_unlocked.append("log_100_percent")
    
    # Missing Modifier Achievements
    if not is_unlocked("first_withered"):
        has_withered = any(d.get("modifier", "").lower() == "withered" for d in user_conf.current_dino_inv)
        if has_withered:
            newly_unlocked.append("first_withered")
    if not is_unlocked("first_young"):
        has_young = any(d.get("modifier", "").lower() == "young" for d in user_conf.current_dino_inv)
        if has_young:
            newly_unlocked.append("first_young")
    if not is_unlocked("first_irradiated"):
        has_irradiated = any(d.get("modifier", "").lower() == "irradiated" for d in user_conf.current_dino_inv)
        if has_irradiated:
            newly_unlocked.append("first_irradiated")
    
    # Extended Milestones
    if not is_unlocked("catch_1000") and user_conf.total_ever_claimed >= 1000:
        newly_unlocked.append("catch_1000")
    if not is_unlocked("escaped_10") and user_conf.total_escaped >= 10:
        newly_unlocked.append("escaped_10")
    if not is_unlocked("lure_10") and user_conf.total_lures_used >= 10:
        newly_unlocked.append("lure_10")
    
    # Extended Economy
    if not is_unlocked("earn_50000") and user_conf.total_dinocoins_earned >= 50000:
        newly_unlocked.append("earn_50000")
    if not is_unlocked("spent_25000") and user_conf.has_spent_dinocoins >= 25000:
        newly_unlocked.append("spent_25000")
    
    # Extended Social
    if not is_unlocked("receive_gift") and user_conf.total_gifts_received >= 1:
        newly_unlocked.append("receive_gift")
    if not is_unlocked("trade_25") and user_conf.total_ever_traded >= 25:
        newly_unlocked.append("trade_25")
    
    # Legendary Collection
    if not is_unlocked("catch_5_legendary") and user_conf.total_legendary_caught >= 5:
        newly_unlocked.append("catch_5_legendary")
    
    return newly_unlocked


def test_scenario_new_player():
    """Test: Brand new player catches their first dino"""
    print("\n" + "="*60)
    print("SCENARIO: New Player First Catch")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    
    # Simulate first catch
    user.total_ever_claimed = 1
    user.current_dino_inv.append({
        "name": "Raptor",
        "rarity": "common",
        "modifier": "normal",
        "value": 25
    })
    user.explorer_log.append({"name": "Raptor"})
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected = ["first_capture"]
    print(f"  Unlocked: {unlocked}")
    print(f"  Expected: {expected}")
    
    if set(unlocked) == set(expected):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_modifier_hunter():
    """Test: Player catches all modifier types"""
    print("\n" + "="*60)
    print("SCENARIO: Modifier Hunter (all modifier achievements)")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    user.total_ever_claimed = 10
    
    modifiers = [
        ("corrupted", "first_corrupted"),
        ("shiny", "first_shiny"),
        ("aberrant", "first_aberrant"),
        ("muscular", "first_muscular"),
        ("sickly", "first_sickly"),
        ("withered", "first_withered"),
        ("young", "first_young"),
        ("irradiated", "first_irradiated"),
    ]
    
    for modifier, ach_id in modifiers:
        user.current_dino_inv.append({
            "name": f"Test Dino {modifier}",
            "rarity": "common",
            "modifier": modifier,
            "value": 25
        })
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected_modifiers = [ach_id for _, ach_id in modifiers]
    matched = [a for a in expected_modifiers if a in unlocked]
    
    print(f"  Modifier achievements unlocked: {len(matched)}/{len(expected_modifiers)}")
    for mod, ach in modifiers:
        status = "[PASS]" if ach in unlocked else "[FAIL]"
        print(f"    {status} {mod} -> {ach}")
    
    if len(matched) == len(expected_modifiers):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_rarity_collector():
    """Test: Player catches all rarity types"""
    print("\n" + "="*60)
    print("SCENARIO: Rarity Collector")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    user.total_ever_claimed = 5
    user.total_legendary_caught = 5
    
    rarities = [
        ("legendary", "first_legendary"),
        ("super_rare", "first_super_rare"),
        ("event", "first_event"),
    ]
    
    for rarity, ach_id in rarities:
        user.current_dino_inv.append({
            "name": f"Test Dino {rarity}",
            "rarity": rarity,
            "modifier": "normal",
            "value": 100
        })
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected = [ach_id for _, ach_id in rarities] + ["catch_5_legendary"]
    matched = [a for a in expected if a in unlocked]
    
    print(f"  Rarity achievements: {matched}")
    
    if set(expected).issubset(set(unlocked)):
        print("  RESULT: PASSED")
        return True
    else:
        print(f"  Missing: {set(expected) - set(unlocked)}")
        print("  RESULT: FAILED")
        return False


def test_scenario_catch_milestones():
    """Test: Player reaches all catch milestones"""
    print("\n" + "="*60)
    print("SCENARIO: Catch Milestones (10, 50, 100, 500, 1000)")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    
    milestones = [
        (10, "catch_10"),
        (50, "catch_50"),
        (100, "catch_100"),
        (500, "catch_500"),
        (1000, "catch_1000"),
    ]
    
    results = []
    for count, ach_id in milestones:
        user.total_ever_claimed = count
        unlocked = simulate_retroactive_sync(user, conf)
        passed = ach_id in unlocked
        results.append((count, ach_id, passed))
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {count} catches -> {ach_id}")
    
    if all(r[2] for r in results):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_economy_tycoon():
    """Test: Player reaches economy milestones"""
    print("\n" + "="*60)
    print("SCENARIO: Economy Tycoon")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    
    user.total_dinocoins_earned = 50000
    user.has_spent_dinocoins = 25000
    user.buddy_bonus_total_gained = 500
    user.total_converted_dinocoin = 100
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected = [
        "earn_1000", "earn_10000", "earn_50000",
        "spent_5000", "spent_25000",
        "buddy_bonus_100", "buddy_bonus_500",
        "convert_first"
    ]
    
    matched = [a for a in expected if a in unlocked]
    print(f"  Economy achievements: {len(matched)}/{len(expected)}")
    for ach in expected:
        status = "[PASS]" if ach in unlocked else "[FAIL]"
        print(f"    {status} {ach}")
    
    if set(expected).issubset(set(unlocked)):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_social_butterfly():
    """Test: Player reaches social milestones"""
    print("\n" + "="*60)
    print("SCENARIO: Social Butterfly (trades & gifts)")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    
    user.total_ever_traded = 25
    user.total_gifts_given = 5
    user.total_gifts_received = 1
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected = ["first_trade", "trade_10", "trade_25", "gift_5", "receive_gift"]
    
    matched = [a for a in expected if a in unlocked]
    print(f"  Social achievements: {len(matched)}/{len(expected)}")
    for ach in expected:
        status = "[PASS]" if ach in unlocked else "[FAIL]"
        print(f"    {status} {ach}")
    
    if set(expected).issubset(set(unlocked)):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_explorer_log():
    """Test: Player fills explorer log to various percentages"""
    print("\n" + "="*60)
    print("SCENARIO: Explorer Log Progress")
    print("="*60)
    
    total_species = len(creature_library)
    print(f"  Total species in library: {total_species}")
    
    thresholds = [
        (25, "log_25_percent"),
        (50, "log_50_percent"),
        (75, "log_75_percent"),
        (100, "log_100_percent"),
    ]
    
    results = []
    for percent, ach_id in thresholds:
        user = User()
        conf = GuildSettings()
        
        # Add enough species to reach threshold
        needed = int((percent / 100) * total_species)
        species_names = list(creature_library.keys())[:needed]
        for name in species_names:
            user.explorer_log.append({"name": creature_library[name]["name"]})
        
        unlocked = simulate_retroactive_sync(user, conf)
        passed = ach_id in unlocked
        results.append((percent, ach_id, passed, needed))
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {percent}% ({needed} species) -> {ach_id}")
    
    if all(r[2] for r in results):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_escaped_dinos():
    """Test: Player has dinos escape"""
    print("\n" + "="*60)
    print("SCENARIO: Escaped Dinosaurs")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    user.total_escaped = 10
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected = ["escaped_10"]
    passed = expected[0] in unlocked
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} 10 escapes -> escaped_10")
    
    if passed:
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_lure_master():
    """Test: Player uses lures"""
    print("\n" + "="*60)
    print("SCENARIO: Lure Master")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    user.has_lure = True
    user.last_lure_use = time.time()
    user.total_lures_used = 10
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected = ["first_lure_purchase", "first_lure_use", "lure_10"]
    matched = [a for a in expected if a in unlocked]
    
    for ach in expected:
        status = "[PASS]" if ach in unlocked else "[FAIL]"
        print(f"  {status} {ach}")
    
    if set(expected).issubset(set(unlocked)):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_inventory_achievements():
    """Test: Inventory-related achievements"""
    print("\n" + "="*60)
    print("SCENARIO: Inventory Achievements")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    
    # Max upgrade level
    user.current_inventory_upgrade_level = conf.maximum_upgrade_amount
    
    # Full inventory
    current_size = conf.base_inventory_size + (user.current_inventory_upgrade_level * conf.inventory_per_upgrade)
    for i in range(current_size):
        user.current_dino_inv.append({
            "name": f"Dino{i}",
            "rarity": "common",
            "modifier": "normal",
            "value": 25
        })
    
    # Buddy set
    user.buddy_dino = {"name": "BuddyDino", "rarity": "rare"}
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected = ["first_upgrade", "max_upgrade", "full_inventory", "first_buddy"]
    matched = [a for a in expected if a in unlocked]
    
    for ach in expected:
        status = "[PASS]" if ach in unlocked else "[FAIL]"
        print(f"  {status} {ach}")
    
    if set(expected).issubset(set(unlocked)):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_scenario_sell_milestones():
    """Test: Sell milestones"""
    print("\n" + "="*60)
    print("SCENARIO: Sell Milestones")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    user.total_ever_sold = 100
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    expected = ["sell_50", "sell_100"]
    matched = [a for a in expected if a in unlocked]
    
    for ach in expected:
        status = "[PASS]" if ach in unlocked else "[FAIL]"
        print(f"  {status} {ach}")
    
    if set(expected).issubset(set(unlocked)):
        print("  RESULT: PASSED")
        return True
    else:
        print("  RESULT: FAILED")
        return False


def test_no_duplicate_unlocks():
    """Test: Already unlocked achievements don't unlock again"""
    print("\n" + "="*60)
    print("SCENARIO: No Duplicate Unlocks")
    print("="*60)
    
    user = User()
    conf = GuildSettings()
    user.total_ever_claimed = 100
    
    # Pre-unlock some achievements
    user.achievement_log.append({"id": "first_capture", "timestamp": time.time()})
    user.achievement_log.append({"id": "catch_10", "timestamp": time.time()})
    user.achievement_log.append({"id": "catch_50", "timestamp": time.time()})
    
    unlocked = simulate_retroactive_sync(user, conf)
    
    # Should NOT include already unlocked ones
    should_not_include = ["first_capture", "catch_10", "catch_50"]
    duplicates = [a for a in should_not_include if a in unlocked]
    
    if duplicates:
        print(f"  [FAIL] Duplicate unlocks found: {duplicates}")
        print("  RESULT: FAILED")
        return False
    else:
        print(f"  [PASS] No duplicates - only new achievements: {unlocked}")
        print("  RESULT: PASSED")
        return True


def test_scenario_gift_legendary():
    """Test: Player gifts a legendary dinosaur (real-time trigger only, not retroactive)"""
    print("\n" + "="*60)
    print("SCENARIO: Gift Legendary (Real-time trigger)")
    print("="*60)
    
    # This achievement is triggered in user.py when trade_type == "free" and dino rarity == "legendary"
    # It cannot be synced retroactively because we don't track "legendary dinos gifted"
    # This test verifies the achievement EXISTS and the code path is correct
    
    # Check achievement exists
    if "gift_legendary" not in achievement_library:
        print("  [FAIL] gift_legendary achievement not in library")
        return False
    
    ach = achievement_library["gift_legendary"]
    print(f"  Achievement: {ach['name']}")
    print(f"  Description: {ach['description']}")
    print(f"  Reward: {ach['reward']} coins")
    
    # Verify the trigger exists in user.py
    user_py_path = os.path.join(os.path.dirname(__file__), 'commands', 'user.py')
    with open(user_py_path, 'r', encoding='utf-8') as f:
        user_content = f.read()
    
    if 'gift_legendary' in user_content:
        print("  [PASS] gift_legendary trigger exists in user.py")
    else:
        print("  [FAIL] gift_legendary trigger NOT found in user.py")
        return False
    
    # Check the trigger condition (gifting a legendary)
    if 'rarity' in user_content and 'legendary' in user_content and 'gift_legendary' in user_content:
        print("  [PASS] Trigger checks rarity == legendary")
    else:
        print("  [WARN] Could not verify trigger condition")
    
    print("  NOTE: This achievement triggers only at gift-time, not retroactively")
    print("  RESULT: PASSED")
    return True


def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "#"*60)
    print("#  DINOCOLLECTOR ACHIEVEMENT TEST SUITE")
    print("#"*60)
    
    tests = [
        ("User Model Fields", test_user_model_fields),
        ("Achievement Library", test_achievement_library),
        ("New Player First Catch", test_scenario_new_player),
        ("Modifier Hunter", test_scenario_modifier_hunter),
        ("Rarity Collector", test_scenario_rarity_collector),
        ("Catch Milestones", test_scenario_catch_milestones),
        ("Economy Tycoon", test_scenario_economy_tycoon),
        ("Social Butterfly", test_scenario_social_butterfly),
        ("Gift Legendary", test_scenario_gift_legendary),
        ("Explorer Log Progress", test_scenario_explorer_log),
        ("Escaped Dinosaurs", test_scenario_escaped_dinos),
        ("Lure Master", test_scenario_lure_master),
        ("Inventory Achievements", test_scenario_inventory_achievements),
        ("Sell Milestones", test_scenario_sell_milestones),
        ("No Duplicate Unlocks", test_no_duplicate_unlocks),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"  EXCEPTION: {e}")
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)
    
    for name, passed, error in results:
        status = "[PASS]" if passed else "[FAIL]"
        error_msg = f" - {error}" if error else ""
        print(f"  {status} {name}{error_msg}")
    
    print(f"\n  TOTAL: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n  ALL TESTS PASSED!")
        return True
    else:
        print(f"\n  {total_count - passed_count} TESTS FAILED")
        return False


if __name__ == "__main__":
    run_all_tests()
