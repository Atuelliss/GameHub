"""
Pet Shop database containing all clothing and accessories for pets.
Prices (value) can be set later. Rarity: "common", "uncommon", "rare", "legendary"
category_restricted: empty list = all species can wear
species_restricted: empty list = universal item
"""

from typing import Dict, List, Optional

# =============================================================================
# PET SHOP DATABASE
# =============================================================================

SHOP_DATABASE: Dict[str, dict] = {
    
    # -------------------------------------------------------------------------
    # ONESIES
    # -------------------------------------------------------------------------
    "onesie_black_white_stripe": {
        "name": "Black & White Striped Onesie",
        "emoji": "👕",
        "category": "onesie",
        "description": "A classic jailbird look for your mischievous pet.",
        "value": 18,
        "rarity": "common",
    },
    "onesie_rainbow": {
        "name": "Rainbow Onesie",
        "emoji": "🌈",
        "category": "onesie",
        "description": "All the colors of the rainbow in one cozy outfit.",
        "value": 52,
        "rarity": "uncommon",
    },
    "onesie_banana": {
        "name": "Banana Costume Onesie",
        "emoji": "🍌",
        "category": "onesie",
        "description": "Turn your pet into an adorable banana. Potassium included.",
        "value": 135,
        "rarity": "rare",
    },
    "onesie_shark": {
        "name": "Baby Shark Onesie",
        "emoji": "🦈",
        "category": "onesie",
        "description": "Doo doo doo doo doo doo. You know the song.",
        "value": 118,
        "rarity": "rare",
    },
    "onesie_bee": {
        "name": "Bumble Bee Onesie",
        "emoji": "🐝",
        "category": "onesie",
        "description": "Yellow and black stripes with tiny wings. Buzz buzz!",
        "value": 45,
        "rarity": "uncommon",
    },
    "onesie_dinosaur": {
        "name": "Dinosaur Onesie",
        "emoji": "🦖",
        "category": "onesie",
        "description": "Green with spiky back plates. RAWR means I love you!",
        "value": 142,
        "rarity": "rare",
    },
    "onesie_unicorn": {
        "name": "Unicorn Onesie",
        "emoji": "🦄",
        "category": "onesie",
        "description": "Sparkly white with a magical horn. Dreams do come true!",
        "value": 375,
        "rarity": "legendary",
    },
    "onesie_tuxedo": {
        "name": "Tuxedo Onesie",
        "emoji": "🤵",
        "category": "onesie",
        "description": "Black and white formal wear. Ready for the red carpet!",
        "value": 58,
        "rarity": "uncommon",
    },
    "onesie_hotdog": {
        "name": "Hot Dog Costume",
        "emoji": "🌭",
        "category": "onesie",
        "description": "Your pet is now a delicious hot dog. No mustard included.",
        "value": 127,
        "rarity": "rare",
        "category_restricted": ["dogs"],
    },
    "onesie_astronaut": {
        "name": "Astronaut Suit",
        "emoji": "🚀",
        "category": "onesie",
        "description": "One small step for pet, one giant leap for pet-kind.",
        "value": 350,
        "rarity": "legendary",
    },
    "onesie_pajamas_stars": {
        "name": "Starry Night Pajamas",
        "emoji": "⭐",
        "category": "onesie",
        "description": "Navy blue with golden stars. Sweet dreams guaranteed!",
        "value": 22,
        "rarity": "common",
    },

    # -------------------------------------------------------------------------
    # HATS
    # -------------------------------------------------------------------------
    "hat_pirate": {
        "name": "Pirate Captain Hat",
        "emoji": "🏴‍☠️",
        "category": "hat",
        "description": "Ahoy matey! Complete with skull and crossbones.",
        "value": 48,
        "rarity": "uncommon",
    },
    "hat_wizard": {
        "name": "Wizard Hat",
        "emoji": "🧙",
        "category": "hat",
        "description": "Tall and purple with silver stars. Magic not included.",
        "value": 138,
        "rarity": "rare",
    },
    "hat_cowboy": {
        "name": "Cowboy Hat",
        "emoji": "🤠",
        "category": "hat",
        "description": "Yeehaw! Brown leather with a fancy band.",
        "value": 20,
        "rarity": "common",
    },
    "hat_top_hat": {
        "name": "Top Hat",
        "emoji": "🎩",
        "category": "hat",
        "description": "Fancy and sophisticated. Monocle sold separately.",
        "value": 55,
        "rarity": "uncommon",
    },
    "hat_party": {
        "name": "Party Hat",
        "emoji": "🎉",
        "category": "hat",
        "description": "Colorful cone hat with a pom-pom. It's always party time!",
        "value": 15,
        "rarity": "common",
    },
    "hat_crown_gold": {
        "name": "Golden Crown",
        "emoji": "👑",
        "category": "hat",
        "description": "A majestic golden crown for your royal pet.",
        "value": 400,
        "rarity": "legendary",
    },
    "hat_crown_princess": {
        "name": "Princess Tiara",
        "emoji": "👸",
        "category": "hat",
        "description": "Delicate silver tiara with pink gems.",
        "value": 145,
        "rarity": "rare",
    },
    "hat_beanie_red": {
        "name": "Red Beanie",
        "emoji": "🧢",
        "category": "hat",
        "description": "Cozy red knit beanie for cold days.",
        "value": 17,
        "rarity": "common",
    },
    "hat_chef": {
        "name": "Chef Hat",
        "emoji": "👨‍🍳",
        "category": "hat",
        "description": "Tall white toque. Master chef in training!",
        "value": 42,
        "rarity": "uncommon",
    },
    "hat_propeller": {
        "name": "Propeller Beanie",
        "emoji": "🚁",
        "category": "hat",
        "description": "Colorful cap with a spinning propeller on top. Wheee!",
        "value": 112,
        "rarity": "rare",
    },
    "hat_viking": {
        "name": "Viking Helmet",
        "emoji": "⚔️",
        "category": "hat",
        "description": "Metal helmet with horns. Prepare for battle!",
        "value": 130,
        "rarity": "rare",
    },
    "hat_sombrero": {
        "name": "Mini Sombrero",
        "emoji": "🪇",
        "category": "hat",
        "description": "Colorful Mexican hat. Fiesta time!",
        "value": 47,
        "rarity": "uncommon",
    },
    "hat_graduation": {
        "name": "Graduation Cap",
        "emoji": "🎓",
        "category": "hat",
        "description": "Black mortarboard. Your pet is officially smart!",
        "value": 60,
        "rarity": "uncommon",
    },
    "hat_flower_crown": {
        "name": "Flower Crown",
        "emoji": "💐",
        "category": "hat",
        "description": "Woven crown of colorful flowers. Nature's beauty!",
        "value": 19,
        "rarity": "common",
    },

    # -------------------------------------------------------------------------
    # HEADBANDS
    # -------------------------------------------------------------------------
    "headband_cat_ears": {
        "name": "Cat Ears Headband",
        "emoji": "😺",
        "category": "headband",
        "description": "Pointy black cat ears. Meow!",
        "value": 16,
        "rarity": "common",
    },
    "headband_alien_antenna": {
        "name": "Alien Antennae",
        "emoji": "👽",
        "category": "headband",
        "description": "Bouncy green antennae with glowing tips. Take me to your leader!",
        "value": 125,
        "rarity": "rare",
    },
    "headband_unicorn_horn": {
        "name": "Unicorn Horn Headband",
        "emoji": "🦄",
        "category": "headband",
        "description": "Sparkly rainbow horn. Magical transformation!",
        "value": 140,
        "rarity": "rare",
    },
    "headband_bear_ears": {
        "name": "Bear Ears Headband",
        "emoji": "🐻",
        "category": "headband",
        "description": "Round fuzzy brown bear ears. Rawr!",
        "value": 21,
        "rarity": "common",
    },
    "headband_mouse_ears": {
        "name": "Mouse Ears Headband",
        "emoji": "🐭",
        "category": "headband",
        "description": "Classic round black mouse ears. Theme park ready!",
        "value": 24,
        "rarity": "common",
    },
    "headband_flower_bow": {
        "name": "Flower Bow Headband",
        "emoji": "🌸",
        "category": "headband",
        "description": "Big pink flower bow. Adorable!",
        "value": 18,
        "rarity": "common",
    },

    # -------------------------------------------------------------------------
    # COLLARS
    # -------------------------------------------------------------------------
    "collar_red_classic": {
        "name": "Classic Red Collar",
        "emoji": "🔴",
        "category": "collar",
        "description": "Traditional red leather collar with silver buckle.",
        "value": 15,
        "rarity": "common",
    },
    "collar_studded_black": {
        "name": "Studded Punk Collar",
        "emoji": "🖤",
        "category": "collar",
        "description": "Black leather with silver studs. Punk rock pet!",
        "value": 53,
        "rarity": "uncommon",
    },
    "collar_diamond": {
        "name": "Diamond Collar",
        "emoji": "💎",
        "category": "collar",
        "description": "Sparkling with rhinestones. Fancy and fabulous!",
        "value": 385,
        "rarity": "legendary",
    },
    "collar_bandana_red": {
        "name": "Red Bandana Collar",
        "emoji": "🔺",
        "category": "collar",
        "description": "Classic red paisley bandana.",
        "value": 17,
        "rarity": "common",
    },
    "collar_bandana_blue": {
        "name": "Blue Bandana Collar",
        "emoji": "🔷",
        "category": "collar",
        "description": "Cool blue paisley bandana.",
        "value": 17,
        "rarity": "common",
    },
    "collar_bowtie_black": {
        "name": "Black Bowtie Collar",
        "emoji": "🎀",
        "category": "collar",
        "description": "Sophisticated black bowtie. Dressed to impress!",
        "value": 44,
        "rarity": "uncommon",
    },
    "collar_bowtie_rainbow": {
        "name": "Rainbow Bowtie Collar",
        "emoji": "🏳️‍🌈",
        "category": "collar",
        "description": "Colorful rainbow bowtie. Pride and joy!",
        "value": 50,
        "rarity": "uncommon",
    },
    "collar_bell": {
        "name": "Jingle Bell Collar",
        "emoji": "🔔",
        "category": "collar",
        "description": "Collar with a tinkling bell. Jingle all the way!",
        "value": 20,
        "rarity": "common",
    },
    "collar_glow_green": {
        "name": "Glow-in-Dark Collar",
        "emoji": "💚",
        "category": "collar",
        "description": "Glows neon green in the dark. Safety first!",
        "value": 115,
        "rarity": "rare",
    },
    "collar_hawaiian": {
        "name": "Hawaiian Lei Collar",
        "emoji": "🌺",
        "category": "collar",
        "description": "Tropical flower lei. Aloha vibes!",
        "value": 46,
        "rarity": "uncommon",
    },

    # -------------------------------------------------------------------------
    # EYEPATCHES & GLASSES
    # -------------------------------------------------------------------------
    "eyepatch_left": {
        "name": "Left Eye Eyepatch",
        "emoji": "🏴‍☠️",
        "category": "eyepatch",
        "description": "Black eyepatch for the left eye. Arrr!",
        "value": 16,
        "rarity": "common",
    },
    "eyepatch_right": {
        "name": "Right Eye Eyepatch",
        "emoji": "☠️",
        "category": "eyepatch",
        "description": "Black eyepatch for the right eye. Shiver me timbers!",
        "value": 16,
        "rarity": "common",
    },
    "eyepatch_heart": {
        "name": "Heart Eyepatch",
        "emoji": "❤️",
        "category": "eyepatch",
        "description": "Pink heart-shaped eyepatch. Love is blind!",
        "value": 41,
        "rarity": "uncommon",
    },
    "glasses_sunglasses_black": {
        "name": "Cool Shades",
        "emoji": "😎",
        "category": "glasses",
        "description": "Classic black sunglasses. Deal with it!",
        "value": 22,
        "rarity": "common",
    },
    "glasses_nerd": {
        "name": "Nerd Glasses",
        "emoji": "🤓",
        "category": "glasses",
        "description": "Thick black frames. Intellectual pet!",
        "value": 19,
        "rarity": "common",
    },
    "glasses_star_shaped": {
        "name": "Star Sunglasses",
        "emoji": "⭐",
        "category": "glasses",
        "description": "Gold star-shaped frames. Superstar!",
        "value": 108,
        "rarity": "rare",
    },
    "monocle": {
        "name": "Fancy Monocle",
        "emoji": "🧐",
        "category": "glasses",
        "description": "A single lens monocle with gold chain. Quite distinguished!",
        "value": 132,
        "rarity": "rare",
    },

    # -------------------------------------------------------------------------
    # SOCKS & BOOTIES
    # -------------------------------------------------------------------------
    "socks_striped_rainbow": {
        "name": "Rainbow Striped Socks",
        "emoji": "🧦",
        "category": "socks",
        "description": "Colorful rainbow stripes for all four paws!",
        "value": 23,
        "rarity": "common",
    },
    "socks_polka_dot": {
        "name": "Polka Dot Socks",
        "emoji": "⚪",
        "category": "socks",
        "description": "White socks with colorful polka dots.",
        "value": 18,
        "rarity": "common",
    },
    "booties_rain": {
        "name": "Rain Booties",
        "emoji": "🌧️",
        "category": "booties",
        "description": "Yellow rubber booties. Puddles beware!",
        "value": 43,
        "rarity": "uncommon",
    },
    "booties_snow": {
        "name": "Snow Boots",
        "emoji": "❄️",
        "category": "booties",
        "description": "Warm fuzzy boots for snowy adventures.",
        "value": 49,
        "rarity": "uncommon",
    },
    "booties_sparkly_red": {
        "name": "Ruby Slippers",
        "emoji": "👠",
        "category": "booties",
        "description": "Sparkly red booties. There's no place like home!",
        "value": 148,
        "rarity": "rare",
    },
    "booties_cowboy": {
        "name": "Cowboy Boots",
        "emoji": "🤠",
        "category": "booties",
        "description": "Tiny leather cowboy boots. Giddy up!",
        "value": 56,
        "rarity": "uncommon",
    },
    "booties_sneakers": {
        "name": "Mini Sneakers",
        "emoji": "👟",
        "category": "booties",
        "description": "Athletic sneakers for the sporty pet.",
        "value": 21,
        "rarity": "common",
    },
    "socks_fuzzy_pink": {
        "name": "Fuzzy Pink Socks",
        "emoji": "🩷",
        "category": "socks",
        "description": "Soft and fluffy pink socks. So cozy!",
        "value": 19,
        "rarity": "common",
    },
    "booties_formal": {
        "name": "Formal Dress Shoes",
        "emoji": "👞",
        "category": "booties",
        "description": "Shiny black shoes for formal occasions.",
        "value": 54,
        "rarity": "uncommon",
    },

    # -------------------------------------------------------------------------
    # TAIL ACCESSORIES
    # -------------------------------------------------------------------------
    "tail_bow_pink": {
        "name": "Pink Tail Bow",
        "emoji": "🎀",
        "category": "tail",
        "description": "Cute pink bow for the tail tip.",
        "value": 15,
        "rarity": "common",
    },
    "tail_bow_blue": {
        "name": "Blue Tail Bow",
        "emoji": "💙",
        "category": "tail",
        "description": "Pretty blue bow for the tail tip.",
        "value": 15,
        "rarity": "common",
    },
    "tail_rings_gold": {
        "name": "Golden Tail Rings",
        "emoji": "💫",
        "category": "tail",
        "description": "Elegant gold rings that wrap around the tail.",
        "value": 136,
        "rarity": "rare",
    },
    "tail_pom_pom": {
        "name": "Fluffy Pom Pom",
        "emoji": "⚪",
        "category": "tail",
        "description": "Bouncy fluffy pom pom for the tail end.",
        "value": 17,
        "rarity": "common",
    },
    "tail_jingle_bells": {
        "name": "Jingle Bell Tail Charm",
        "emoji": "🔔",
        "category": "tail",
        "description": "Tiny bells that jingle with every wag!",
        "value": 40,
        "rarity": "uncommon",
    },
    "tail_ribbon_rainbow": {
        "name": "Rainbow Tail Ribbon",
        "emoji": "🌈",
        "category": "tail",
        "description": "Colorful ribbon streaming from the tail.",
        "value": 51,
        "rarity": "uncommon",
    },
    "tail_feather": {
        "name": "Peacock Feather Tail",
        "emoji": "🦚",
        "category": "tail",
        "description": "Majestic peacock feather attachment.",
        "value": 122,
        "rarity": "rare",
    },
    "tail_glow_tip": {
        "name": "Glow-in-Dark Tail Tip",
        "emoji": "✨",
        "category": "tail",
        "description": "The tail tip glows in the dark!",
        "value": 105,
        "rarity": "rare",
    },

    # -------------------------------------------------------------------------
    # EARRINGS
    # -------------------------------------------------------------------------
    "earring_stud_diamond": {
        "name": "Diamond Stud Earring",
        "emoji": "💎",
        "category": "earring",
        "description": "Sparkling clip-on diamond stud.",
        "value": 143,
        "rarity": "rare",
    },
    "earring_hoop_gold": {
        "name": "Gold Hoop Earring",
        "emoji": "⭕",
        "category": "earring",
        "description": "Classic gold hoop clip-on earring.",
        "value": 47,
        "rarity": "uncommon",
    },
    "earring_pearl": {
        "name": "Pearl Drop Earring",
        "emoji": "🤍",
        "category": "earring",
        "description": "Elegant pearl clip-on earring.",
        "value": 52,
        "rarity": "uncommon",
    },
    "earring_star": {
        "name": "Star Dangle Earring",
        "emoji": "⭐",
        "category": "earring",
        "description": "Dangling star-shaped clip-on earring.",
        "value": 20,
        "rarity": "common",
    },
    "earring_feather": {
        "name": "Feather Earring",
        "emoji": "🪶",
        "category": "earring",
        "description": "Bohemian feather clip-on earring.",
        "value": 45,
        "rarity": "uncommon",
    },
    "earring_cross": {
        "name": "Cross Earring",
        "emoji": "✝️",
        "category": "earring",
        "description": "Silver cross clip-on earring.",
        "value": 18,
        "rarity": "common",
    },

    # -------------------------------------------------------------------------
    # CAPES & COSTUMES
    # -------------------------------------------------------------------------
    "cape_superhero_red": {
        "name": "Superhero Cape",
        "emoji": "🦸",
        "category": "cape",
        "description": "Red cape with a golden star. Up, up, and away!",
        "value": 57,
        "rarity": "uncommon",
    },
    "cape_royal_purple": {
        "name": "Royal Purple Cape",
        "emoji": "👑",
        "category": "cape",
        "description": "Majestic purple cape with gold trim.",
        "value": 128,
        "rarity": "rare",
    },
    "wings_devil": {
        "name": "Devil Wings",
        "emoji": "😈",
        "category": "costume",
        "description": "Little red bat-like devil wings.",
        "value": 117,
        "rarity": "rare",
        "holiday": "halloween",
    },
    "wings_butterfly": {
        "name": "Butterfly Wings",
        "emoji": "🦋",
        "category": "costume",
        "description": "Colorful monarch butterfly wings.",
        "value": 320,
        "rarity": "legendary",
    },
    "wings_fairy": {
        "name": "Fairy Wings",
        "emoji": "🧚",
        "category": "costume",
        "description": "Sparkly translucent fairy wings.",
        "value": 365,
        "rarity": "legendary",
    },
    "costume_mermaid_tail": {
        "name": "Mermaid Tail",
        "emoji": "🧜",
        "category": "costume",
        "description": "Shimmering mermaid tail costume piece.",
        "value": 340,
        "rarity": "legendary",
        "category_restricted": ["aquatic"],
    },
    "costume_lion_mane": {
        "name": "Lion Mane",
        "emoji": "🦁",
        "category": "costume",
        "description": "Fluffy lion mane headpiece. Roar!",
        "value": 110,
        "rarity": "rare",
        "category_restricted": ["dogs", "cats"],
    },
    "backpack_tiny": {
        "name": "Tiny Backpack",
        "emoji": "🎒",
        "category": "costume",
        "description": "Adorable miniature backpack. Ready for adventure!",
        "value": 48,
        "rarity": "uncommon",
    },

    # -------------------------------------------------------------------------
    # SPECIAL & SPECIES-SPECIFIC
    # -------------------------------------------------------------------------
    "scarf_winter": {
        "name": "Cozy Winter Scarf",
        "emoji": "🧣",
        "category": "costume",
        "description": "Warm knitted scarf in festive colors.",
        "value": 23,
        "rarity": "common",
    },
    "tutu_pink": {
        "name": "Pink Tutu",
        "emoji": "🩰",
        "category": "costume",
        "description": "Fluffy pink ballet tutu. Twirl!",
        "value": 42,
        "rarity": "uncommon",
    },
    "fish_bowl_hat": {
        "name": "Fish Bowl Helmet",
        "emoji": "🐠",
        "category": "hat",
        "description": "A fish bowl worn as a space helmet!",
        "value": 290,
        "rarity": "legendary",
        "category_restricted": ["aquatic"],
    },
    "saddle_tiny": {
        "name": "Tiny Saddle",
        "emoji": "🐴",
        "category": "costume",
        "description": "A miniature saddle. Onward, noble steed!",
        "value": 133,
        "rarity": "rare",
        "category_restricted": ["dogs", "cats", "exotic"],
    },
    "shell_decorated": {
        "name": "Decorated Shell",
        "emoji": "🐢",
        "category": "costume",
        "description": "Sparkly gems and stickers for shell decoration.",
        "value": 55,
        "rarity": "uncommon",
        "species_restricted": ["tortoise", "box_turtle"],
    },
    "sweater_knit_red": {
        "name": "Red Knit Sweater",
        "emoji": "🧶",
        "category": "costume",
        "description": "Cozy hand-knitted red sweater.",
        "value": 24,
        "rarity": "common",
    },
    "harness_wings": {
        "name": "Wing Harness",
        "emoji": "🪽",
        "category": "costume",
        "description": "Decorative harness with colorful wings attached.",
        "value": 120,
        "rarity": "rare",
        "category_restricted": ["reptiles", "small_mammals"],
    },

    # =========================================================================
    # HOLIDAY ITEMS
    # =========================================================================

    # -------------------------------------------------------------------------
    # CHRISTMAS
    # -------------------------------------------------------------------------
    "onesie_christmas": {
        "name": "Christmas Onesie",
        "emoji": "🎄",
        "category": "onesie",
        "description": "Red and green with candy cane stripes. Ho ho ho!",
        "value": 59,
        "rarity": "uncommon",
        "holiday": "christmas",
    },
    "hat_santa": {
        "name": "Santa Hat",
        "emoji": "🎅",
        "category": "hat",
        "description": "Red with white fluffy trim. Ho ho ho!",
        "value": 25,
        "rarity": "common",
        "holiday": "christmas",
    },
    "headband_antlers": {
        "name": "Reindeer Antlers",
        "emoji": "🦌",
        "category": "headband",
        "description": "Brown fuzzy antlers with jingle bells.",
        "value": 22,
        "rarity": "common",
        "holiday": "christmas",
    },
    "socks_christmas": {
        "name": "Christmas Stockings",
        "emoji": "🧦",
        "category": "socks",
        "description": "Red and white striped holiday socks.",
        "value": 18,
        "rarity": "common",
        "holiday": "christmas",
    },
    "sweater_ugly_christmas": {
        "name": "Ugly Christmas Sweater",
        "emoji": "🎄",
        "category": "costume",
        "description": "Gloriously tacky holiday sweater!",
        "value": 58,
        "rarity": "uncommon",
        "holiday": "christmas",
    },

    # -------------------------------------------------------------------------
    # HALLOWEEN
    # -------------------------------------------------------------------------
    "onesie_black_skulls": {
        "name": "Skull Print Onesie",
        "emoji": "💀",
        "category": "onesie",
        "description": "Black onesie with adorable white skulls. Spooky cute!",
        "value": 46,
        "rarity": "uncommon",
        "holiday": "halloween",
    },
    "onesie_pumpkin": {
        "name": "Pumpkin Onesie",
        "emoji": "🎃",
        "category": "onesie",
        "description": "Orange and round for Halloween festivities!",
        "value": 50,
        "rarity": "uncommon",
        "holiday": "halloween",
    },
    "headband_devil_horns": {
        "name": "Devil Horns",
        "emoji": "😈",
        "category": "headband",
        "description": "Little red devil horns. Mischief managed!",
        "value": 44,
        "rarity": "uncommon",
        "holiday": "halloween",
    },
    "cape_vampire": {
        "name": "Vampire Cape",
        "emoji": "🧛",
        "category": "cape",
        "description": "Black cape with red lining. Bleh bleh bleh!",
        "value": 53,
        "rarity": "uncommon",
        "holiday": "halloween",
    },

    # -------------------------------------------------------------------------
    # EASTER
    # -------------------------------------------------------------------------
    "headband_bunny_ears": {
        "name": "Bunny Ears Headband",
        "emoji": "🐰",
        "category": "headband",
        "description": "Floppy white bunny ears. Hippity hoppity!",
        "value": 20,
        "rarity": "common",
        "holiday": "easter",
    },
    "headband_angel_halo": {
        "name": "Angel Halo",
        "emoji": "😇",
        "category": "headband",
        "description": "Golden floating halo. Your pet is angelic!",
        "value": 55,
        "rarity": "uncommon",
        "holiday": "easter",
    },
    "wings_angel": {
        "name": "Angel Wings",
        "emoji": "👼",
        "category": "costume",
        "description": "Fluffy white angel wings.",
        "value": 138,
        "rarity": "rare",
        "holiday": "easter",
    },

    # -------------------------------------------------------------------------
    # VALENTINE'S DAY
    # -------------------------------------------------------------------------
    "onesie_pink_hearts": {
        "name": "Pink Hearts Onesie",
        "emoji": "💕",
        "category": "onesie",
        "description": "Soft pink with floating hearts. Pure love!",
        "value": 21,
        "rarity": "common",
        "holiday": "valentines",
    },
    "glasses_heart_shaped": {
        "name": "Heart Sunglasses",
        "emoji": "💕",
        "category": "glasses",
        "description": "Pink heart-shaped sunglasses. Love at first sight!",
        "value": 48,
        "rarity": "uncommon",
        "holiday": "valentines",
    },
}


# =============================================================================
# SHOP TREATS DATABASE
# =============================================================================
# Treats that can be purchased and used to boost pet stats
# All treats also add +5 bond when used
# Tiers: low (+5 stat, 10 cost), medium (+10 stat, 25 cost), high (+20 stat, 50 cost)

SHOP_TREATS: Dict[str, dict] = {
    # HUNGER TREATS
    "hunger_low": {
        "name": "Light Snack",
        "emoji": "🍪",
        "stat": "hunger",
        "tier": "low",
        "effect": 5,
        "cost": 10,
        "description": "A tasty little nibble to take the edge off hunger.",
    },
    "hunger_medium": {
        "name": "Hearty Meal",
        "emoji": "🍗",
        "stat": "hunger",
        "tier": "medium",
        "effect": 10,
        "cost": 25,
        "description": "A satisfying meal that fills the belly.",
    },
    "hunger_high": {
        "name": "Gourmet Feast",
        "emoji": "🍽️",
        "stat": "hunger",
        "tier": "high",
        "effect": 20,
        "cost": 50,
        "description": "A luxurious spread fit for royalty.",
    },
    
    # HAPPINESS TREATS
    "happiness_low": {
        "name": "Squeaky Toy",
        "emoji": "🧸",
        "stat": "happiness",
        "tier": "low",
        "effect": 5,
        "cost": 10,
        "description": "A fun little toy that brings a smile.",
    },
    "happiness_medium": {
        "name": "Play Bundle",
        "emoji": "🎁",
        "stat": "happiness",
        "tier": "medium",
        "effect": 10,
        "cost": 25,
        "description": "A collection of toys and games for hours of fun.",
    },
    "happiness_high": {
        "name": "Adventure Kit",
        "emoji": "🎪",
        "stat": "happiness",
        "tier": "high",
        "effect": 20,
        "cost": 50,
        "description": "Everything needed for an unforgettable adventure!",
    },
    
    # CLEANLINESS TREATS
    "cleanliness_low": {
        "name": "Quick Wipe",
        "emoji": "🧴",
        "stat": "cleanliness",
        "tier": "low",
        "effect": 5,
        "cost": 10,
        "description": "A quick freshen-up wipe for minor messes.",
    },
    "cleanliness_medium": {
        "name": "Grooming Kit",
        "emoji": "🧹",
        "stat": "cleanliness",
        "tier": "medium",
        "effect": 10,
        "cost": 25,
        "description": "Brushes, combs, and sprays for a thorough clean.",
    },
    "cleanliness_high": {
        "name": "Spa Package",
        "emoji": "🛁",
        "stat": "cleanliness",
        "tier": "high",
        "effect": 20,
        "cost": 50,
        "description": "A full spa treatment with bath, dry, and pamper.",
    },
    
    # ENERGY TREATS
    "energy_low": {
        "name": "Catnap Pillow",
        "emoji": "😴",
        "stat": "energy",
        "tier": "low",
        "effect": 5,
        "cost": 10,
        "description": "A soft pillow for a quick power nap.",
    },
    "energy_medium": {
        "name": "Cozy Blanket",
        "emoji": "🛏️",
        "stat": "energy",
        "tier": "medium",
        "effect": 10,
        "cost": 25,
        "description": "A warm blanket for restful sleep.",
    },
    "energy_high": {
        "name": "Luxury Bed",
        "emoji": "🌙",
        "stat": "energy",
        "tier": "high",
        "effect": 20,
        "cost": 50,
        "description": "A premium bed for the deepest, most restorative sleep.",
    },
    
    # HEALTH TREATS (more expensive for balance)
    "health_low": {
        "name": "Small Bandage",
        "emoji": "🩹",
        "stat": "health",
        "tier": "low",
        "effect": 5,
        "cost": 15,
        "description": "A small bandage to help with minor scrapes.",
    },
    "health_medium": {
        "name": "Health Tonic",
        "emoji": "🧪",
        "stat": "health",
        "tier": "medium",
        "effect": 10,
        "cost": 35,
        "description": "A restorative tonic that promotes healing.",
    },
    "health_high": {
        "name": "Wellness Elixir",
        "emoji": "💖",
        "stat": "health",
        "tier": "high",
        "effect": 20,
        "cost": 75,
        "description": "A powerful elixir that rapidly restores vitality.",
    },

    # IMMORTALITY TREATS
    "golden_ambrosia": {
        "name": "Golden Ambrosia",
        "emoji": "🍯",
        "treat_type": "immortality",  # signals special handling
        "cost": 2500,                 # very expensive — legendary tier
        "rarity": "legendary",
        "description": "Feed to a graduated home pet to grant them Immortality — they will never die of old age.",
    },
}


# =============================================================================
# SHOP VITAMINS DATABASE
# =============================================================================
# Vitamins that reduce player action cooldowns (not pet decay)
# Effect is time reduction in seconds
# Tiers: low (small reduction), medium (moderate), high (significant)

SHOP_VITAMINS: Dict[str, dict] = {
    # FEED VITAMINS (Base cooldown: 75 min)
    "feed_low": {
        "name": "Quick Nibble Pill",
        "emoji": "💊",
        "cooldown_type": "feed",
        "tier": "low",
        "effect": 900,  # -15 minutes
        "cost": 12,
        "description": "A small supplement that speeds up appetite recovery.",
    },
    "feed_medium": {
        "name": "Appetite Booster",
        "emoji": "🧬",
        "cooldown_type": "feed",
        "tier": "medium",
        "effect": 1800,  # -30 minutes
        "cost": 30,
        "description": "An effective formula that helps your pet get hungry faster.",
    },
    "feed_high": {
        "name": "Mega Hunger Surge",
        "emoji": "⚡",
        "cooldown_type": "feed",
        "tier": "high",
        "effect": 3600,  # -60 minutes
        "cost": 60,
        "description": "A powerful vitamin that rapidly restores feeding readiness.",
    },
    
    # PLAY VITAMINS (Base cooldown: 90 min)
    "play_low": {
        "name": "Playful Pick-Me-Up",
        "emoji": "💊",
        "cooldown_type": "play",
        "tier": "low",
        "effect": 900,  # -15 minutes
        "cost": 12,
        "description": "A light boost to get playtime going sooner.",
    },
    "play_medium": {
        "name": "Fun Fuel Capsule",
        "emoji": "🧬",
        "cooldown_type": "play",
        "tier": "medium",
        "effect": 1800,  # -30 minutes
        "cost": 30,
        "description": "Recharges your pet's playful spirit faster.",
    },
    "play_high": {
        "name": "Mega Play Surge",
        "emoji": "⚡",
        "cooldown_type": "play",
        "tier": "high",
        "effect": 3600,  # -60 minutes
        "cost": 60,
        "description": "Instant playtime readiness in a bottle!",
    },
    
    # GROOM VITAMINS (Base cooldown: 105 min)
    "groom_low": {
        "name": "Quick Freshen Tab",
        "emoji": "💊",
        "cooldown_type": "groom",
        "tier": "low",
        "effect": 900,  # -15 minutes
        "cost": 12,
        "description": "A small supplement for faster grooming recovery.",
    },
    "groom_medium": {
        "name": "Shine Booster",
        "emoji": "🧬",
        "cooldown_type": "groom",
        "tier": "medium",
        "effect": 1800,  # -30 minutes
        "cost": 30,
        "description": "Helps your pet need another grooming session sooner.",
    },
    "groom_high": {
        "name": "Mega Groom Surge",
        "emoji": "⚡",
        "cooldown_type": "groom",
        "tier": "high",
        "effect": 3600,  # -60 minutes
        "cost": 60,
        "description": "Your pet will be ready for pampering in no time!",
    },
    
    # REST VITAMINS (Base cooldown: 120 min)
    "rest_low": {
        "name": "Light Drowsy Drop",
        "emoji": "💊",
        "cooldown_type": "rest",
        "tier": "low",
        "effect": 900,  # -15 minutes
        "cost": 12,
        "description": "A gentle nudge toward sleepiness.",
    },
    "rest_medium": {
        "name": "Slumber Supplement",
        "emoji": "🧬",
        "cooldown_type": "rest",
        "tier": "medium",
        "effect": 1800,  # -30 minutes
        "cost": 30,
        "description": "Helps your pet feel ready for rest sooner.",
    },
    "rest_high": {
        "name": "Mega Rest Surge",
        "emoji": "⚡",
        "cooldown_type": "rest",
        "tier": "high",
        "effect": 3600,  # -60 minutes
        "cost": 60,
        "description": "Rapid recovery to rest readiness!",
    },
    
    # TREAT VITAMINS (Base cooldown: 24 hours)
    "treat_low": {
        "name": "Snack Craving Pill",
        "emoji": "💊",
        "cooldown_type": "treat",
        "tier": "low",
        "effect": 7200,  # -2 hours
        "cost": 20,
        "description": "Makes your pet crave treats a bit sooner.",
    },
    "treat_medium": {
        "name": "Sweet Tooth Serum",
        "emoji": "🧬",
        "cooldown_type": "treat",
        "tier": "medium",
        "effect": 14400,  # -4 hours
        "cost": 45,
        "description": "Significantly speeds up treat readiness.",
    },
    "treat_high": {
        "name": "Mega Treat Surge",
        "emoji": "⚡",
        "cooldown_type": "treat",
        "tier": "high",
        "effect": 28800,  # -8 hours
        "cost": 90,
        "description": "Your pet will be begging for treats in no time!",
    },
    
    # PET VITAMINS (Base cooldown: 30 min)
    "pet_low": {
        "name": "Cuddle Catalyst",
        "emoji": "💊",
        "cooldown_type": "pet",
        "tier": "low",
        "effect": 300,  # -5 minutes
        "cost": 8,
        "description": "A tiny boost to get those cuddles going.",
    },
    "pet_medium": {
        "name": "Affection Amplifier",
        "emoji": "🧬",
        "cooldown_type": "pet",
        "tier": "medium",
        "effect": 600,  # -10 minutes
        "cost": 18,
        "description": "Your pet craves attention sooner!",
    },
    "pet_high": {
        "name": "Mega Cuddle Surge",
        "emoji": "⚡",
        "cooldown_type": "pet",
        "tier": "high",
        "effect": 900,  # -15 minutes
        "cost": 35,
        "description": "Maximum cuddle readiness achieved!",
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_shop_item(item_id: str) -> Optional[dict]:
    """Get a shop item by ID."""
    return SHOP_DATABASE.get(item_id)


def get_items_by_category(category: str) -> List[dict]:
    """Get all items in a category."""
    return [{"id": k, **v} for k, v in SHOP_DATABASE.items() if v["category"] == category]


def get_items_by_rarity(rarity: str) -> List[dict]:
    """Get all items of a specific rarity."""
    return [{"id": k, **v} for k, v in SHOP_DATABASE.items() if v["rarity"] == rarity]


def get_items_for_species(species_id: str, species_category: str) -> List[dict]:
    """Get all items a specific species can wear."""
    valid_items = []
    for item_id, item in SHOP_DATABASE.items():
        # Check species restriction
        species_restricted = item.get("species_restricted", [])
        if species_restricted and species_id not in species_restricted:
            continue
        # Check category restriction
        category_restricted = item.get("category_restricted", [])
        if category_restricted and species_category not in category_restricted:
            continue
        valid_items.append({"id": item_id, **item})
    return valid_items


def get_all_items() -> List[dict]:
    """Get all shop items."""
    return [{"id": k, **v} for k, v in SHOP_DATABASE.items()]


def get_item_count() -> int:
    """Get total number of items in the shop."""
    return len(SHOP_DATABASE)


# =============================================================================
# TREAT HELPER FUNCTIONS
# =============================================================================

def get_treat(treat_id: str) -> Optional[dict]:
    """Get a treat by ID."""
    treat = SHOP_TREATS.get(treat_id)
    if treat:
        return {"id": treat_id, **treat}
    return None


def get_treats_by_stat(stat: str) -> List[dict]:
    """Get all treats for a specific stat."""
    return [{"id": k, **v} for k, v in SHOP_TREATS.items() if v.get("stat") == stat]


def get_all_treats() -> List[dict]:
    """Get all treats with their IDs."""
    return [{"id": k, **v} for k, v in SHOP_TREATS.items()]


def get_treats_by_tier(tier: str) -> List[dict]:
    """Get all treats of a specific tier."""
    return [{"id": k, **v} for k, v in SHOP_TREATS.items() if v["tier"] == tier]


# =============================================================================
# VITAMIN HELPER FUNCTIONS
# =============================================================================

def get_vitamin(vitamin_id: str) -> Optional[dict]:
    """Get a vitamin by ID."""
    vitamin = SHOP_VITAMINS.get(vitamin_id)
    if vitamin:
        return {"id": vitamin_id, **vitamin}
    return None


def get_vitamins_by_cooldown_type(cooldown_type: str) -> List[dict]:
    """Get all vitamins for a specific cooldown type."""
    return [{"id": k, **v} for k, v in SHOP_VITAMINS.items() if v["cooldown_type"] == cooldown_type]


def get_all_vitamins() -> List[dict]:
    """Get all vitamins with their IDs."""
    return [{"id": k, **v} for k, v in SHOP_VITAMINS.items()]


def get_vitamins_by_tier(tier: str) -> List[dict]:
    """Get all vitamins of a specific tier."""
    return [{"id": k, **v} for k, v in SHOP_VITAMINS.items() if v["tier"] == tier]
