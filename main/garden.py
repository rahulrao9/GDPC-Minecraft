from gdpc import Editor, Block
import math
import random

ARCH_THEMES = [
    {"name": "Classic Stone", "pillar": "stone_bricks", "base": "stone_brick_stairs", "slab": "stone_brick_slab", "pyramid": "stone_brick_stairs", "tub": "chiseled_stone_bricks"},
    {"name": "Gothic Deepslate", "pillar": "polished_deepslate", "base": "cobbled_deepslate_stairs", "slab": "polished_deepslate_slab", "pyramid": "cobbled_deepslate_stairs", "tub": "deepslate_tiles"}
]

PATH_BLOCKS = ["gravel", "cobblestone", "andesite"]
FLORA_LEAVES = ["oak_leaves", "spruce_leaves", "azalea_leaves"]
FLORA_LOGS = ["oak_log", "spruce_log"]

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
    height = random.randint(3, 5)
    for y in range(height):
        editor.placeBlock((tx, ty + y, tz), Block(log_block))
    leaf_y = ty + height - 2
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            for dy in range(3):
                if abs(dx) + abs(dz) + dy <= 3: 
                    if dx == 0 and dz == 0 and dy < 2: continue
                    editor.placeBlock((tx + dx, leaf_y + dy, tz + dz), Block(leaf_block))

def build_dynamic_fountain_garden(editor, world_slice, build_area, cx, base_y, cz, garden_radius=15):
    theme = random.choice(ARCH_THEMES)
    path_block = Block(random.choice(PATH_BLOCKS))
    grass_block = Block("grass_block")
    log_block = random.choice(FLORA_LOGS)
    leaf_block = random.choice(FLORA_LEAVES)
    
    print("Building Terrain-Adaptive Fountain Garden...")

    fountain_radius = 4
    pillar_dist = fountain_radius + 2 
    walkway_width = 2 
    pillar_height = random.randint(6, 9)

    # 1. Layout Terrain-Adaptive Ground
    for x in range(cx - garden_radius, cx + garden_radius + 1):
        for z in range(cz - garden_radius, cz + garden_radius + 1):
            dist_to_center = math.hypot(x - cx, z - cz)
            
            # Find the true natural terrain height
            local_x = x - build_area.begin.x
            local_z = z - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                ground_y = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z] - 1
            else:
                ground_y = base_y
                
            # FORCE center fountain perfectly flat at base_y!
            if dist_to_center <= fountain_radius + 3:
                target_y = base_y
            else:
                # Let the garden organically drape over the hills
                target_y = ground_y
                editor.placeBlock((x, target_y + 1, z), Block("air"))
                editor.placeBlock((x, target_y + 2, z), Block("air"))

            is_path = (abs(x - cx) <= walkway_width) or (abs(z - cz) <= walkway_width) or (fountain_radius < dist_to_center <= fountain_radius + 2)

            if is_path:
                editor.placeBlock((x, target_y, z), path_block)
            else:
                editor.placeBlock((x, target_y, z), grass_block)
                if dist_to_center > fountain_radius + 3:
                    if random.random() < 0.01:
                        build_mini_tree(editor, x, target_y + 1, z, log_block, leaf_block)
                    elif random.random() < 0.04:
                        editor.placeBlock((x, target_y + 1, z), Block("dark_oak_fence"))
                        editor.placeBlock((x, target_y + 2, z), Block("lantern"))

    # 2. Circular Tub Fountain (Always built at flat base_y)
    TUB = Block(theme["tub"])
    fill_cuboid(editor, cx - fountain_radius, base_y, cz - fountain_radius, cx + fountain_radius, base_y, cz + fountain_radius, TUB)
    for fx, fz in circle_points(cx, cz, fountain_radius):
        editor.placeBlock((fx, base_y + 1, fz), TUB)
        editor.placeBlock((fx, base_y + 2, fz), Block(theme["slab"], {"type": "bottom"}))
    for fx in range(cx - fountain_radius + 1, cx + fountain_radius):
        for fz in range(cz - fountain_radius + 1, cz + fountain_radius):
            if math.hypot(fx - cx, fz - cz) <= fountain_radius - 0.5:
                editor.placeBlock((fx, base_y + 1, fz), Block("water"))

    editor.placeBlock((cx, base_y + 1, cz), TUB)
    editor.placeBlock((cx, base_y + 2, cz), TUB)
    editor.placeBlock((cx, base_y + 3, cz), Block("water")) 

    # 3. Four Pillars
    PILLAR = Block(theme["pillar"])
    BASE = theme["base"]
    roof_y = base_y + pillar_height
    pillar_coords = [(cx+pillar_dist, cz+pillar_dist), (cx-pillar_dist, cz+pillar_dist), (cx+pillar_dist, cz-pillar_dist), (cx-pillar_dist, cz-pillar_dist)]
    for px, pz in pillar_coords:
        fill_cuboid(editor, px, base_y + 1, pz, px, roof_y, pz, PILLAR)
        editor.placeBlock((px + 1, base_y + 1, pz), Block(BASE, {"facing": "west"}))
        editor.placeBlock((px - 1, base_y + 1, pz), Block(BASE, {"facing": "east"}))
        editor.placeBlock((px, base_y + 1, pz + 1), Block(BASE, {"facing": "north"}))
        editor.placeBlock((px, base_y + 1, pz - 1), Block(BASE, {"facing": "south"}))
    
    roof_span = pillar_dist + 1
    SLAB = Block(theme["slab"], {"type": "bottom"})
    fill_cuboid(editor, cx - roof_span, roof_y + 1, cz - roof_span, cx + roof_span, roof_y + 1, cz + roof_span, SLAB)
    PYRAMID_STAIR = theme["pyramid"]
    pyramid_y = roof_y + 2
    for step in range(roof_span + 1):
        curr_span = roof_span - step
        if curr_span <= 0:
            editor.placeBlock((cx, pyramid_y + step, cz), Block(theme["tub"]))
            editor.placeBlock((cx, pyramid_y + step + 1, cz), Block("lantern"))
            break
        for i in range(-curr_span, curr_span + 1):
            editor.placeBlock((cx + i, pyramid_y + step, cz - curr_span), Block(PYRAMID_STAIR, {"facing": "south"}))
            editor.placeBlock((cx + i, pyramid_y + step, cz + curr_span), Block(PYRAMID_STAIR, {"facing": "north"}))
            editor.placeBlock((cx - curr_span, pyramid_y + step, cz + i), Block(PYRAMID_STAIR, {"facing": "east"}))
            editor.placeBlock((cx + curr_span, pyramid_y + step, cz + i), Block(PYRAMID_STAIR, {"facing": "west"}))