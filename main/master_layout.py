import random
import math
from gdpc import Editor, Block
from collections import Counter

import plot
import entrance
import garden
import corridor
import common_room
import tower

RNG_SEED = None
# ==========================================
# DEBUG VIEW (TESTING BOUNDARIES)
# ==========================================
def build_testing_compounds(editor, world_slice, build_area, start_x, start_z, plot_size):
    """Draws a 2-block-high red boundary around the total build area and the chosen plot."""
    print("Drawing red testing boundaries...")
    RED_BLOCK = Block("red_concrete")
    
    # Helper to draw a hollow rectangle that hugs the terrain height
    def draw_rect(x1, z1, x2, z2):
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                # Only draw blocks on the exact perimeter of the rectangle
                if x == x1 or x == x2 or z == z1 or z == z2:
                    local_x = x - build_area.begin.x
                    local_z = z - build_area.begin.z
                    
                    # Ensure we don't query outside the loaded heightmap bounds
                    if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                        # Find the surface block
                        ground_y = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z]
                        
                        # Place a 2-high wall
                        editor.placeBlock((x, ground_y, z), RED_BLOCK)
                        editor.placeBlock((x, ground_y + 1, z), RED_BLOCK)
                        
    # 1. Global Build Area Boundary (The whole area you selected)
    # We shrink it by 1 block so it draws strictly inside the bounding box
    bx1, bz1 = build_area.begin.x, build_area.begin.z
    bx2, bz2 = build_area.begin.x + build_area.size.x - 1, build_area.begin.z + build_area.size.z - 1
    draw_rect(bx1, bz1, bx2, bz2)
    
    # 2. The Best Patch Boundary (Your 100x100 plot)
    px1, pz1 = start_x, start_z
    px2, pz2 = start_x + plot_size - 1, start_z + plot_size - 1
    draw_rect(px1, pz1, px2, pz2)
# ==========================================
# VEGETATION CLEARER (NATIVE COMMAND METHOD)
# ==========================================
def clear_all_trees_in_plot(editor, start_x, start_z, size, base_y):
    """Uses Minecraft's native /fill command to instantly vaporize trees in chunks."""
    print(f"Using /fill commands to nuke vegetation in the {size}x{size} plot... (Ignoring empty chunks)")
    
    # We clear from slightly below ground up into the sky
    y1 = base_y - 3
    y2 = base_y + 40 
    
    # Split the 100x100 area into 25x25 chunks to bypass the 32,768 block limit
    step = 25
    
    # Everything we want to vaporize
    targets = [
        "#minecraft:logs", 
        "#minecraft:leaves", 
        "red_mushroom_block",
        "brown_mushroom_block",
        "mushroom_stem"
    ]
    
    for dx in range(0, size, step):
        for dz in range(0, size, step):
            x1 = start_x + dx
            z1 = start_z + dz
            x2 = min(x1 + step - 1, start_x + size - 1)
            z2 = min(z1 + step - 1, start_z + size - 1)
            
            for target in targets:
                try:
                    editor.runCommand(f"fill {x1} {y1} {z1} {x2} {y2} {z2} air replace {target}")
                except Exception:
                    # If Minecraft complains that "No blocks were filled", we just silently ignore it!
                    pass
# ==========================================
# TERRAIN ADAPTATION BUILDERS
# ==========================================
def construct_cylinder_foundation(editor, world_slice, build_area, cx, base_y, cz, radius):
    """Flattens exact circular footprint. Builds up foundation or carves down."""
    for x in range(int(cx - radius - 1), int(cx + radius + 2)):
        for z in range(int(cz - radius - 1), int(cz + radius + 2)):
            if math.hypot(x - cx, z - cz) <= radius + 0.5:
                local_x = x - build_area.begin.x
                local_z = z - build_area.begin.z
                if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                    ground_y = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z]
                    
                    if ground_y > base_y:
                        for y in range(base_y, ground_y + 10):
                            editor.placeBlock((x, y, z), Block("air"))
                    elif ground_y < base_y:
                        for y in range(ground_y, base_y):
                            editor.placeBlock((x, y, z), Block("stone_bricks"))

def construct_rect_foundation(editor, world_slice, build_area, x1, z1, x2, z2, base_y):
    """Flattens exact rectangular area."""
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for z in range(min(z1, z2), max(z1, z2) + 1):
            local_x = x - build_area.begin.x
            local_z = z - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                ground_y = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z]
                if ground_y > base_y:
                    for y in range(base_y, ground_y + 10):
                        editor.placeBlock((x, y, z), Block("air"))
                elif ground_y < base_y:
                    for y in range(ground_y, base_y):
                        editor.placeBlock((x, y, z), Block("stone_bricks"))

def build_corridor_supports(editor, world_slice, build_area, cx, base_y, cz, direction, width, length):
    """Builds arched pillars down to the terrain."""
    if direction == "n-s": ox, oz = cx - (width // 2), cz - (length // 2)
    else: ox, oz = cx - (length // 2), cz - (width // 2)
        
    for dl in range(length):
        for dw in range(width):
            x = ox + dw if direction == "n-s" else ox + dl
            z = oz + dl if direction == "n-s" else oz + dw
            
            local_x = x - build_area.begin.x
            local_z = z - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                ground_y = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z]
                
                # Carve tunnel if terrain is high
                if ground_y > base_y:
                    for y in range(base_y, ground_y + 10):
                        editor.placeBlock((x, y, z), Block("air"))
                        
                # Arched supports every 6 blocks on the edges if terrain is low
                if ground_y < base_y:
                    if dl % 6 == 0 and (dw == 0 or dw == width - 1):
                        for y in range(ground_y, base_y):
                            editor.placeBlock((x, y, z), Block("stone_bricks"))
                        
                        fwd = "south" if direction == "n-s" else "east"
                        back = "north" if direction == "n-s" else "west"
                        
                        if dl + 1 < length:
                            ax = x + (0 if direction=="n-s" else 1)
                            az = z + (1 if direction=="n-s" else 0)
                            editor.placeBlock((ax, base_y - 1, az), Block("stone_brick_stairs", {"facing": fwd, "half": "top"}))
                        if dl - 1 >= 0:
                            ax = x - (0 if direction=="n-s" else 1)
                            az = z - (1 if direction=="n-s" else 0)
                            editor.placeBlock((ax, base_y - 1, az), Block("stone_brick_stairs", {"facing": back, "half": "top"}))

def get_biome_palette(world_slice, build_area):
    """
    Scans the build area to determine the dominant local terrain.
    Returns intentionally CONTRASTING structural blocks that pop against
    the environment, plus a boolean indicating if the environment is snowy.
    """
    surface_blocks = Counter()
    has_snow = False
    
    # Sample the terrain
    step = 4 
    for x in range(0, build_area.size.x, step):
        for z in range(0, build_area.size.z, step):
            y = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][x][z] - 1
            hx = build_area.begin.x + x
            hz = build_area.begin.z + z
            
            # 1. The solid ground block (Dirt, Stone, Grass)
            block = world_slice.getBlock((hx, y, hz))
            block_id = block.id.replace('minecraft:', '') 
            
            # 2. NEW: The non-solid block resting directly on top of the ground!
            block_above = world_slice.getBlock((hx, y + 1, hz))
            above_id = block_above.id.replace('minecraft:', '')
            
            # Detect snow/ice on the ground OR thin snow resting on top of the grass
            if "snow" in block_id or "ice" in block_id or "snow" in above_id:
                has_snow = True
            
            # Filter out non-buildable surface clutter
            invalid_blocks = ["grass", "tall_grass", "water", "lava", "air", "leaves", "snow", "snow_block", "ice"]
            
            if not any(invalid in block_id for invalid in invalid_blocks):
                # If we hit topsoil, assume we harvest the stone/wood underneath
                if block_id in ["grass_block", "dirt", "podzol", "mycelium"]:
                    surface_blocks["stone"] += 2
                    surface_blocks["spruce_log" if "podzol" in block_id else "oak_log"] += 1
                else:
                    surface_blocks[block_id] += 1
                    
    # Get the primary material found in the biome
    if not surface_blocks:
        primary = "stone" # Failsafe
    else:
        primary = surface_blocks.most_common(1)[0][0]

    # ==========================================
    # DYNAMIC CONTRAST LOGIC
    # ==========================================
    if has_snow:
        # Snowy: Warm red bricks and bright oxidized copper to pop against white
        wall_id = "bricks"
        roof_id = "oxidized_cut_copper"
    elif "sand" in primary or "terracotta" in primary:
        # Desert/Badlands: Dark deepslate and cool cyan warped wood to contrast hot sand
        wall_id = "deepslate_bricks"
        roof_id = "warped_planks"
    elif "dark_oak" in primary or "spruce" in primary or "podzol" in primary:
        # Dark Forest/Taiga: Bright sandstone and vibrant orange acacia to pop against dark green/brown
        wall_id = "smooth_sandstone"
        roof_id = "acacia_planks"
    elif "jungle" in primary or "mangrove" in primary or "mud" in primary:
        # Jungle/Swamp: Clean quartz and dark red crimson to contrast messy bright greens
        wall_id = "quartz_bricks"
        roof_id = "crimson_planks"
    elif "stone" in primary or "andesite" in primary or "gravel" in primary:
        # Mountains/Barren: Clean mud bricks and bright prismarine roofs to contrast gray stone
        wall_id = "mud_bricks"
        roof_id = "dark_prismarine"
    else:
        # Default (Plains, Oak Forests): Striking blackstone and mangrove for a magical academy vibe
        wall_id = "polished_blackstone_bricks"
        roof_id = "mangrove_planks"

    # Automatically figure out the exact stair variant for the roof
    def make_stair(b_id):
        if b_id.endswith("_planks"): return b_id.replace("_planks", "_stairs")
        if b_id.endswith("bricks"): return b_id[:-1] + "_stairs"
        if b_id.endswith("tiles"): return b_id[:-1] + "_stairs"
        if "copper" in b_id and "cut" not in b_id: return b_id.replace("copper", "cut_copper_stairs")
        if b_id == "stone": return "stone_stairs"
        return b_id + "_stairs"

    roof_stair_id = make_stair(roof_id)

    print(f"Biome Vibes -> Primary Block: {primary} | Snowing: {has_snow}")
    print(f"Assigned Contrasting Palette -> Walls: {wall_id}, Roof: {roof_id}, Stairs: {roof_stair_id}")
    
    # Return all 4 variables
    return Block(wall_id), Block(roof_id), Block(roof_stair_id), has_snow

# ==========================================
# DOORWAY CARVER
# ==========================================
def build_entrance(editor, cx, base_y, cz, radius, facing, depth_in=-2, depth_out=3):
    directions = {"north": (0, -1), "south": (0, 1), "east":  (1, 0), "west":  (-1, 0)}
    fx, fz = directions[facing]
    px, pz = -fz, fx  

    wall_x = cx + fx * int(radius)
    wall_z = cz + fz * int(radius)

    for depth in range(depth_in, depth_out):     
        for side in range(-1, 3):          
            for height in range(4):        
                x = wall_x + px * side + fx * depth
                z = wall_z + pz * side + fz * depth
                y = base_y + 1 + height
                editor.placeBlock((x, y, z), Block("air"))

    banner_colors = ["white","orange","magenta","light_blue","yellow","lime","pink","gray","light_gray","cyan","purple","blue","brown","green","red","black"]
    banner_color = random.choice(banner_colors)
    banner_block = Block(f"{banner_color}_banner")
    
    x = wall_x + px * 2
    z = wall_z + pz * 2
    y = base_y + 1
    editor.placeBlock((x, y, z), banner_block)

# ==========================================
# MASTER GENERATOR
# ==========================================
def main():
    if RNG_SEED is not None: random.seed(RNG_SEED)
    editor = Editor(buffering=True)
    
    # 1. SCOUT PLOT
    PLOT_SIZE = 100 
    print(f"Scouting terrain for the {PLOT_SIZE}x{PLOT_SIZE} building plot...")
    best_patch, is_ideal = plot.find_best_location(PLOT_SIZE)
    
    start_x = plot.x0 + best_patch[0]
    start_z = plot.z0 + best_patch[1]

    # 2. GET INITIAL TERRAIN DATA (To calculate height)
    build_area = editor.getBuildArea()
    initial_world_slice = editor.loadWorldSlice(build_area.toRect()) 
    
    heights = []
    for dx in range(PLOT_SIZE):
        for dz in range(PLOT_SIZE):
            local_x = (start_x + dx) - build_area.begin.x
            local_z = (start_z + dz) - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                heights.append(initial_world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z])
    
    heights.sort()
    base_y = heights[int(len(heights) * 0.80)] - 1 

    # build_testing_compounds(editor, initial_world_slice
    #                         , build_area, start_x, start_z, PLOT_SIZE)
    # editor.flushBuffer() # Flush immediately so you can see it while the rest builds

    # 3. NUKE THE TREES USING COMMANDS
    clear_all_trees_in_plot(editor, start_x, start_z, PLOT_SIZE, base_y)
    editor.flushBuffer() 
    
    # 4. RELOAD BARE WORLD DATA
    # We must reload so the engine registers the trees are gone and reads the raw dirt!
    print("Reloading bare terrain data...")
    world_slice = editor.loadWorldSlice(build_area.toRect())

    print(f"Plot verified. Elevated Master Height is Y={base_y}. Building Adaptive Hogwarts Blueprint...")
    
    heights = []
    for dx in range(PLOT_SIZE):
        for dz in range(PLOT_SIZE):
            local_x = (start_x + dx) - build_area.begin.x
            local_z = (start_z + dz) - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                heights.append(world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z])
    
    heights.sort()
    base_y = heights[int(len(heights) * 0.80)] - 1 

    print(f"Plot verified. Elevated Master Height is Y={base_y}. Building Adaptive Hogwarts Blueprint...")

    # ==========================================
    # BLUEPRINT PARAMETERS
    # ==========================================
    small_roof_h_e, radius_e, height_e = 16, 5, 30
    radius_cr = random.randint(14, 17)
    ground_height_cr = random.randint(15, 25)
    dorm_height_cr = random.randint(13, 18)
    roof_height_cr = 38
    cr_base_h = ground_height_cr + dorm_height_cr
    radius_lib = random.randint(7, 13)
    height_lib = random.randint(30, 45) 
    gh_length = 40
    gh_width = random.randint(15, 20)
    gh_height = 25
    corr_width = 11

    # ==========================================
    # EXACT COORDINATE MAPPING (0-100 grid)
    # ==========================================
    ent_cx = start_x + 35
    ent_cz = start_z + 85
    left_tower_x = ent_cx - 16  
    right_tower_x = ent_cx + 16 
    
    gh_ox = right_tower_x + radius_e + 1 
    gh_cx = gh_ox + (gh_length // 2)        
    gh_cz = ent_cz              
    
    cr_cx = gh_cx
    cr_cz = start_z + 25        
    
    lib_cx = left_tower_x
    lib_cz = cr_cz              
    
    gard_cx = start_x + 48
    gard_cz = start_z + 55

    # ==========================================
    # CORRIDOR CALCULATIONS
    # ==========================================
    lc_start = lib_cz + radius_lib
    lc_end = ent_cz - radius_e
    lc_len = lc_end - lc_start
    lc_cz = lc_start + (lc_len // 2)
    lc_height = min(height_lib, height_e) - 2 

    tc_start = lib_cx + radius_lib
    tc_end = cr_cx - radius_cr
    tc_len = tc_end - tc_start
    tc_cx = tc_start + (tc_len // 2)
    tc_height = min(height_lib, cr_base_h) - 2 

    rc_start = cr_cz + radius_cr
    rc_end = gh_cz - (gh_width // 2)
    rc_len = rc_end - rc_start
    rc_cz = rc_start + (rc_len // 2)
    rc_height = min(cr_base_h, gh_height) - 2 

    # ==========================================
    # PHASE 1: PREPARE TERRAIN FOUNDATIONS
    # ==========================================
    print("Preparing dynamic foundations and grand viaducts...")
    
    construct_cylinder_foundation(editor, world_slice, build_area, left_tower_x, base_y, ent_cz, radius_e)
    construct_cylinder_foundation(editor, world_slice, build_area, right_tower_x, base_y, ent_cz, radius_e)
    construct_rect_foundation(editor, world_slice, build_area, ent_cx - 6, ent_cz - 7, ent_cx + 6, ent_cz + 24, base_y)
    
    construct_cylinder_foundation(editor, world_slice, build_area, lib_cx, base_y, lib_cz, radius_lib)
    construct_cylinder_foundation(editor, world_slice, build_area, cr_cx, base_y, cr_cz, radius_cr)
    
    build_corridor_supports(editor, world_slice, build_area, gh_cx, base_y, gh_cz, "e-w", gh_width, gh_length)
    build_corridor_supports(editor, world_slice, build_area, lib_cx, base_y, lc_cz, "n-s", corr_width, lc_len)
    build_corridor_supports(editor, world_slice, build_area, tc_cx, base_y, lib_cz, "e-w", corr_width, tc_len)
    build_corridor_supports(editor, world_slice, build_area, cr_cx, base_y, rc_cz, "n-s", corr_width, rc_len)

    construct_cylinder_foundation(editor, world_slice, build_area, gard_cx, base_y, gard_cz, 5)
    editor.flushBuffer()

    # ==========================================
    # PHASE 2: EXECUTE CONSTRUCTION
    # ==========================================
    # Harvest local materials
    env_wall, env_roof, env_roof_stair, is_snowy = get_biome_palette(world_slice, build_area)

    print("1/7 Constructing Entrance...")
    entrance.build_twin_tower_entrance(editor, world_slice, build_area, ent_cx, 
                                       base_y, ent_cz, small_roof_h_e, radius_e, height_e, 
                                       facing="S", wall_block=env_wall, roof_block=env_roof, roof_stair_block=env_roof_stair, has_snow=is_snowy)

    print("2/7 Constructing Great Hall...")
    # Fixed: Using the 'env_roof_stair' variable unpacked from the palette
    corridor.build_dynamic_hogwarts_corridor(editor, gh_cx, base_y, gh_cz, "e-w", 
                                        True, gh_width, gh_length, gh_height, wall_stone=env_wall, 
                                        roof_block=env_roof, roof_stairs=env_roof_stair)

    print("3/7 Constructing Common Room...")
    # Added: facing, wall block, roof block, and snow flag
    common_room.build_common_room_tower(editor, cr_cx, base_y, cr_cz, radius_cr, ground_height_cr, dorm_height_cr, roof_height_cr, env_wall, env_roof, is_snowy)

    print("4/7 Constructing Bibliotheek...")
    # Added: facing, wall block, roof block, and snow flag
    tower.build_tower(editor, lib_cx, base_y, lib_cz, radius_lib, height_lib, "south", env_wall, env_roof, is_snowy)

    print("5/7 Constructing Connecting Corridors...")
    # Added: wall and roof variables to the connecting corridors so they match the Great Hall
    corridor.build_dynamic_hogwarts_corridor(editor, lib_cx, base_y, lc_cz, "n-s", False, corr_width, lc_len, lc_height, wall_stone=env_wall, roof_block=env_roof, roof_stairs=env_roof_stair) 
    corridor.build_dynamic_hogwarts_corridor(editor, tc_cx, base_y, lib_cz, "e-w", False, corr_width, tc_len, tc_height, wall_stone=env_wall, roof_block=env_roof, roof_stairs=env_roof_stair) 
    corridor.build_dynamic_hogwarts_corridor(editor, cr_cx, base_y, rc_cz, "n-s", False, corr_width, rc_len, rc_height, wall_stone=env_wall, roof_block=env_roof, roof_stairs=env_roof_stair)  

    print("6/7 Constructing Central Garden...")
    garden.build_dynamic_fountain_garden(editor, world_slice, build_area, gard_cx, base_y, gard_cz, garden_radius=18)

    # ==========================================
    # PHASE 3: CARVE INTERNAL DOORWAYS
    # ==========================================
    print("7/7 Carving interconnected doorways...")
    
    build_entrance(editor, left_tower_x, base_y, ent_cz, radius_e, "north", depth_out=7)
    build_entrance(editor, left_tower_x, base_y, ent_cz, radius_e, "east", depth_out=7)
    build_entrance(editor, right_tower_x, base_y, ent_cz, radius_e, "west", depth_out=7)
    build_entrance(editor, right_tower_x, base_y, ent_cz, radius_e, "east", depth_out=7)

    build_entrance(editor, lib_cx, base_y, lib_cz, radius_lib, "south")
    build_entrance(editor, lib_cx, base_y, lib_cz, radius_lib, "east")

    build_entrance(editor, cr_cx, base_y, cr_cz, radius_cr, "west")
    build_entrance(editor, cr_cx, base_y, cr_cz, radius_cr, "south")

    build_entrance(editor, cr_cx, base_y, gh_cz, gh_width // 2, "north")

    print("Flushing final structural buffers to Minecraft...")
    editor.flushBuffer()
    print("Generation Complete! A fully terrain-adaptive castle is built.")

if __name__ == "__main__":
    main()