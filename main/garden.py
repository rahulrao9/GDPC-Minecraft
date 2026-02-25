from gdpc import Editor, Block
import math
import random

# ==========================================
# DYNAMIC PALETTES (Changes every run!)
# ==========================================
ARCH_THEMES = [
    {
        "name": "Classic Stone",
        "pillar": "stone_bricks",
        "base": "stone_brick_stairs",
        "slab": "stone_brick_slab",
        "pyramid": "stone_brick_stairs",
        "tub": "chiseled_stone_bricks"
    },
    {
        "name": "Desert Sandstone",
        "pillar": "smooth_sandstone",
        "base": "sandstone_stairs",
        "slab": "sandstone_slab",
        "pyramid": "sandstone_stairs",
        "tub": "cut_sandstone"
    },
    {
        "name": "Gothic Deepslate",
        "pillar": "polished_deepslate",
        "base": "cobbled_deepslate_stairs",
        "slab": "polished_deepslate_slab",
        "pyramid": "cobbled_deepslate_stairs",
        "tub": "deepslate_tiles"
    },
    {
        "name": "Pristine Quartz",
        "pillar": "quartz_pillar",
        "base": "quartz_stairs",
        "slab": "quartz_slab",
        "pyramid": "quartz_stairs",
        "tub": "chiseled_quartz_block"
    }
]

PATH_BLOCKS = ["gravel", "cobblestone", "mossy_cobblestone", "andesite", "bricks"]
FLORA_LEAVES = ["oak_leaves", "spruce_leaves", "birch_leaves", "azalea_leaves", "flowering_azalea_leaves"]
FLORA_LOGS = ["oak_log", "spruce_log", "birch_log"]

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def circle_points(cx, cz, radius):
    points = set()
    steps = max(32, int(2 * math.pi * radius * 2))
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        x = int(round(cx + radius * math.cos(angle)))
        z = int(round(cz + radius * math.sin(angle)))
        points.add((x, z))
    return list(points)

def fill_cuboid(editor, x1, y1, z1, x2, y2, z2, block):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for z in range(min(z1, z2), max(z1, z2) + 1):
                editor.placeBlock((x, y, z), block)

def build_mini_tree(editor, tx, ty, tz, log_block, leaf_block):
    """Builds a small, decorative custom tree for the quadrants."""
    height = random.randint(3, 5)
    for y in range(height):
        editor.placeBlock((tx, ty + y, tz), Block(log_block))
    
    # Leaves
    leaf_y = ty + height - 2
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            for dy in range(3):
                if abs(dx) + abs(dz) + dy <= 3: # Diamond shape canopy
                    if editor.getBlock((tx + dx, leaf_y + dy, tz + dz)).id == "minecraft:air":
                        editor.placeBlock((tx + dx, leaf_y + dy, tz + dz), Block(leaf_block))

def scan_for_max_garden_radius(editor, cx, base_y, cz, max_search=25):
    
    # Safe blocks that don't count as "walls"
    safe_blocks = ["minecraft:air", "minecraft:cave_air", "minecraft:grass", 
                   "minecraft:tall_grass", "minecraft:fern", "minecraft:snow",
                   "minecraft:poppy", "minecraft:dandelion", "minecraft:water"]

    for r in range(2, max_search + 1):
        # 1. Check North & South edges of the expanding square
        for x in range(cx - r, cx + r + 1):
            for z in [cz - r, cz + r]:
                block_id = editor.getBlock((x, base_y + 1, z)).id
                if block_id not in safe_blocks and "leaves" not in block_id:
                    return r - 1 # We hit a wall! Return the previous safe radius.

        # 2. Check East & West edges of the expanding square
        for z in range(cz - r + 1, cz + r): # Avoid double-checking corners
            for x in [cx - r, cx + r]:
                block_id = editor.getBlock((x, base_y + 1, z)).id
                if block_id not in safe_blocks and "leaves" not in block_id:
                    return r - 1

    return max_search # If no walls are hit, return the maximum allowed size


# ==========================================
# MAIN GENERATOR
# ==========================================
def build_dynamic_fountain_garden(editor, cx, base_y, cz, garden_radius=15):
    # 1. Select Random Themes for this specific run
    theme = random.choice(ARCH_THEMES)
    path_block = Block(random.choice(PATH_BLOCKS))
    grass_block = Block("grass_block")
    log_block = random.choice(FLORA_LOGS)
    leaf_block = random.choice(FLORA_LEAVES)
    
    print(f"Building Fountain Garden. Theme: {theme['name']}, Path: {path_block.id}")

    fountain_radius = 4
    pillar_dist = fountain_radius + 2 # Pillars sit just outside the walkway
    walkway_width = 2 # 2 blocks out from center means a 5-block wide path total (-2 to +2)
    pillar_height = random.randint(6, 9)

    # 2. Layout the Ground: Paths vs Quadrants (Skipping the air-clearing phase!)
    for x in range(cx - garden_radius, cx + garden_radius + 1):
        for z in range(cz - garden_radius, cz + garden_radius + 1):
            dist_to_center = math.hypot(x - cx, z - cz)
            
            # Cross Pathways and Circular Walkway around the fountain
            is_path = (abs(x - cx) <= walkway_width) or \
                      (abs(z - cz) <= walkway_width) or \
                      (fountain_radius < dist_to_center <= fountain_radius + 2)

            if is_path:
                editor.placeBlock((x, base_y, z), path_block)
            else:
                editor.placeBlock((x, base_y, z), grass_block)
                
                # Quadrant Decorations (Trees, bushes, pumpkins, lamps)
                if dist_to_center > fountain_radius + 3:
                    rand_val = random.random()
                    if rand_val < 0.01:
                        build_mini_tree(editor, x, base_y + 1, z, log_block, leaf_block)
                    elif rand_val < 0.04:
                        editor.placeBlock((x, base_y + 1, z), Block(leaf_block))
                    elif rand_val < 0.06:
                        editor.placeBlock((x, base_y + 1, z), Block("pumpkin"))
                    elif rand_val < 0.08:
                        editor.placeBlock((x, base_y + 1, z), Block("dark_oak_fence"))
                        editor.placeBlock((x, base_y + 2, z), Block("lantern"))
                    elif rand_val < 0.20:
                        editor.placeBlock((x, base_y + 1, z), Block(random.choice(["tall_grass", "fern"])))

    # 3. Circular Tub Fountain
    TUB = Block(theme["tub"])
    WATER = Block("water")
    
    # Fountain floor
    fill_cuboid(editor, cx - fountain_radius, base_y, cz - fountain_radius, 
                        cx + fountain_radius, base_y, cz + fountain_radius, TUB)
    
    # Fountain walls
    for x, z in circle_points(cx, cz, fountain_radius):
        editor.placeBlock((x, base_y + 1, z), TUB)
        # Small decorative slab on top of the rim
        editor.placeBlock((x, base_y + 2, z), Block(theme["slab"], {"type": "bottom"}))
        
    # Fill water inside the tub
    for x in range(cx - fountain_radius + 1, cx + fountain_radius):
        for z in range(cz - fountain_radius + 1, cz + fountain_radius):
            if math.hypot(x - cx, z - cz) <= fountain_radius - 0.5:
                editor.placeBlock((x, base_y + 1, z), WATER)

    # Central Spout
    editor.placeBlock((cx, base_y + 1, cz), TUB)
    editor.placeBlock((cx, base_y + 2, cz), TUB)
    editor.placeBlock((cx, base_y + 3, cz), Block("water")) # Water flows down from here

    # 5. Four Pillars with Strong Bases ("Good Foot")
    PILLAR = Block(theme["pillar"])
    BASE = theme["base"]
    
    pillar_coords = [
        (cx + pillar_dist, cz + pillar_dist),
        (cx - pillar_dist, cz + pillar_dist),
        (cx + pillar_dist, cz - pillar_dist),
        (cx - pillar_dist, cz - pillar_dist)
    ]

    roof_y = base_y + pillar_height

    for px, pz in pillar_coords:
        # The pillar itself
        fill_cuboid(editor, px, base_y + 1, pz, px, roof_y, pz, PILLAR)
        
        # The "Good Foot" (Stairs wrapping around the base)
        editor.placeBlock((px + 1, base_y + 1, pz), Block(BASE, {"facing": "west"}))
        editor.placeBlock((px - 1, base_y + 1, pz), Block(BASE, {"facing": "east"}))
        editor.placeBlock((px, base_y + 1, pz + 1), Block(BASE, {"facing": "north"}))
        editor.placeBlock((px, base_y + 1, pz - 1), Block(BASE, {"facing": "south"}))
        
        # Corner blocks for the foot to make it fully square
        editor.placeBlock((px + 1, base_y + 1, pz + 1), Block(theme["slab"], {"type": "bottom"}))
        editor.placeBlock((px - 1, base_y + 1, pz + 1), Block(theme["slab"], {"type": "bottom"}))
        editor.placeBlock((px + 1, base_y + 1, pz - 1), Block(theme["slab"], {"type": "bottom"}))
        editor.placeBlock((px - 1, base_y + 1, pz - 1), Block(theme["slab"], {"type": "bottom"}))

    # 6. Flat Slab Roof extending over the pillars
    roof_span = pillar_dist + 1
    SLAB = Block(theme["slab"], {"type": "bottom"})
    fill_cuboid(editor, cx - roof_span, roof_y + 1, cz - roof_span, 
                        cx + roof_span, roof_y + 1, cz + roof_span, SLAB)

    # 7. The Pyramid Top
    PYRAMID_STAIR = theme["pyramid"]
    pyramid_y = roof_y + 2
    
    # We step inwards layer by layer to build the pyramid
    for step in range(roof_span + 1):
        curr_span = roof_span - step
        if curr_span <= 0:
            # Top cap
            editor.placeBlock((cx, pyramid_y + step, cz), Block(theme["tub"]))
            # Decorative lantern on the absolute peak
            editor.placeBlock((cx, pyramid_y + step + 1, cz), Block("lantern"))
            break
            
        # Place the square ring of stairs for this layer
        for i in range(-curr_span, curr_span + 1):
            # North and South edges
            editor.placeBlock((cx + i, pyramid_y + step, cz - curr_span), Block(PYRAMID_STAIR, {"facing": "south"}))
            editor.placeBlock((cx + i, pyramid_y + step, cz + curr_span), Block(PYRAMID_STAIR, {"facing": "north"}))
            # East and West edges
            editor.placeBlock((cx - curr_span, pyramid_y + step, cz + i), Block(PYRAMID_STAIR, {"facing": "east"}))
            editor.placeBlock((cx + curr_span, pyramid_y + step, cz + i), Block(PYRAMID_STAIR, {"facing": "west"}))
            
        # Fill the core of the pyramid so it isn't hollow and weird-looking from underneath
        if curr_span > 1:
            fill_cuboid(editor, cx - curr_span + 1, pyramid_y + step, cz - curr_span + 1,
                                cx + curr_span - 1, pyramid_y + step, cz + curr_span - 1, Block(theme["pillar"]))

def main():
    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()

    cx = build_area.begin.x + 80
    cz = build_area.begin.z + 0
    base_y = -61 

    try:
        build_dynamic_fountain_garden(editor, cx, base_y, cz, garden_radius=20)
        editor.flushBuffer()
        print("Dynamic Fountain Garden complete!")
    except Exception as e:
        print(f"Generation Failed: {e}")

if __name__ == "__main__":
    main()