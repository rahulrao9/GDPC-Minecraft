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
# VEGETATION CLEARER
# ==========================================
def clear_all_trees_in_plot(editor, start_x, start_z, size, base_y):
    print(f"Using /fill commands to nuke vegetation in the {size}x{size} plot...")
    y1, y2 = base_y - 3, base_y + 40 
    step = 25
    targets = ["#minecraft:logs", "#minecraft:leaves", "red_mushroom_block", "brown_mushroom_block", "mushroom_stem"]
    
    for dx in range(0, size, step):
        for dz in range(0, size, step):
            x1, z1 = start_x + dx, start_z + dz
            x2, z2 = min(x1 + step - 1, start_x + size - 1), min(z1 + step - 1, start_z + size - 1)
            for target in targets:
                try: editor.runCommand(f"fill {x1} {y1} {z1} {x2} {y2} {z2} air replace {target}")
                except Exception: pass

# ==========================================
# TERRAIN ANALYSIS & ROTATION ENGINE
# ==========================================
def calculate_downhill_direction(world_slice, build_area, start_x, start_z, size):
    """
    Samples the 4 edges of the plot to find the lowest elevation.
    Returns 'N', 'S', 'E', or 'W' indicating the downhill slope.
    """
    north_h, south_h, east_h, west_h = [], [], [], []
    
    for i in range(size):
        # Local coordinate conversion
        lx_n = (start_x + i) - build_area.begin.x
        lz_n = start_z - build_area.begin.z
        
        lx_s = (start_x + i) - build_area.begin.x
        lz_s = (start_z + size - 1) - build_area.begin.z
        
        lx_e = (start_x + size - 1) - build_area.begin.x
        lz_e = (start_z + i) - build_area.begin.z
        
        lx_w = start_x - build_area.begin.x
        lz_w = (start_z + i) - build_area.begin.z

        # Safely get heights (checking bounds)
        try: north_h.append(world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][lx_n][lz_n])
        except IndexError: pass
        
        try: south_h.append(world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][lx_s][lz_s])
        except IndexError: pass
        
        try: east_h.append(world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][lx_e][lz_e])
        except IndexError: pass
        
        try: west_h.append(world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][lx_w][lz_w])
        except IndexError: pass

    # Average the edge heights
    avg_n = sum(north_h) / len(north_h) if north_h else 999
    avg_s = sum(south_h) / len(south_h) if south_h else 999
    avg_e = sum(east_h) / len(east_h) if east_h else 999
    avg_w = sum(west_h) / len(west_h) if west_h else 999

    # Find the lowest average height
    min_avg = min(avg_n, avg_s, avg_e, avg_w)
    
    if min_avg == avg_n: return "N"
    elif min_avg == avg_s: return "S"
    elif min_avg == avg_e: return "E"
    else: return "W"

def rotate_point(cx, cz, map_center_x, map_center_z, facing):
    """Rotates a single coordinate point around the 50,50 center of the map."""
    # Move point to origin (0,0) based on map center
    x = cx - map_center_x
    z = cz - map_center_z
    
    # Standard orientation is facing South (Entrance at bottom)
    if facing == "S":
        rx, rz = x, z
    elif facing == "N": # Rotate 180
        rx, rz = -x, -z
    elif facing == "E": # Rotate -90
        rx, rz = z, -x
    elif facing == "W": # Rotate 90
        rx, rz = -z, x
        
    return rx + map_center_x, rz + map_center_z

def rotate_direction(direction, facing):
    """Rotates an axis ('n-s' or 'e-w')."""
    if facing in ["E", "W"]:
        return "e-w" if direction == "n-s" else "n-s"
    return direction

def rotate_facing(dir_string, facing):
    """Rotates a cardinal direction string ('north', 'south', etc)."""
    dirs = ['north', 'east', 'south', 'west']
    if dir_string not in dirs: return dir_string
    idx = dirs.index(dir_string)
    
    offset = {"S": 0, "W": 1, "N": 2, "E": 3}[facing]
    return dirs[(idx + offset) % 4]

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

def get_biome_palette(editor, world_slice, build_area):
    """
    Scans the build area to determine the true Minecraft Biome.
    If GDPC fails to read the biome string, it falls back to a smart block analyzer.
    """
    biome_counter = Counter()
    surface_blocks = Counter()
    flora_blocks = Counter()
    has_snow = False
    step = 4 
    
    for x in range(0, build_area.size.x, step):
        for z in range(0, build_area.size.z, step):
            # GDPC uses local coordinates for heightmaps
            y_ground = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][x][z] - 1
            y_top = world_slice.heightmaps["MOTION_BLOCKING"][x][z] - 1
            
            hx, hz = build_area.begin.x + x, build_area.begin.z + z
            
            # Get the block IDs
            ground_id = world_slice.getBlock((hx, y_ground, hz)).id.replace('minecraft:', '') 
            above_ground_id = world_slice.getBlock((hx, y_ground + 1, hz)).id.replace('minecraft:', '')
            top_id = world_slice.getBlock((hx, y_top, hz)).id.replace('minecraft:', '')
            
            # Check for snow
            if "snow" in ground_id or "ice" in ground_id or "snow" in above_ground_id or "snow" in top_id:
                has_snow = True
            
            # ---> NEW: Added "void_air" to the ignore list!
            ignore_blocks = ["water", "lava", "air", "cave_air", "void_air"]
            
            # Tally blocks for fallback analysis (Ignoring air and liquids)
            if ground_id not in ignore_blocks:
                surface_blocks[ground_id] += 1
                
            # If the top block is higher than the ground, it's a tree/plant!
            if y_top > y_ground and top_id not in ignore_blocks:
                flora_blocks[top_id] += 1
            
            # Attempt GDPC native biome extraction using GLOBAL coordinates
            try:
                biome_id = editor.getBiomeGlobal((hx, y_ground, hz))
                if biome_id and "minecraft:" in biome_id:
                    biome_name = biome_id.replace("minecraft:", "")
                    biome_counter[biome_name] += 1
            except Exception:
                pass

    # ==========================================
    # DECIDE THE PRIMARY BIOME
    # ==========================================
    if biome_counter:
        primary_biome = biome_counter.most_common(1)[0][0]
        print(f"Native GDPC Biome Detected: {primary_biome}")
    else:
        # Smart Fallback Logic if GDPC returns ""
        ground = surface_blocks.most_common(1)[0][0] if surface_blocks else "grass_block"
        flora = flora_blocks.most_common(1)[0][0] if flora_blocks else "none"
        
        if has_snow: primary_biome = "snowy_plains"
        elif "sand" in ground: primary_biome = "desert"
        elif "terracotta" in ground: primary_biome = "badlands"
        elif ground == "podzol": primary_biome = "taiga"
        elif ground == "mycelium": primary_biome = "mushroom"
        elif "spruce" in flora: primary_biome = "taiga"
        elif "jungle" in flora: primary_biome = "jungle"
        elif "mangrove" in flora or "mud" in ground: primary_biome = "mangrove_swamp"
        elif "cherry" in flora: primary_biome = "cherry_grove"
        elif "dark_oak" in flora: primary_biome = "dark_forest"
        elif "acacia" in flora: primary_biome = "savanna"
        elif "stone" in ground or "gravel" in ground or "andesite" in ground: primary_biome = "mountains"
        else: primary_biome = "plains"
        
        print(f"GDPC Biome string was empty. Used Smart Block Analysis:")
        print(f" -> Dominant Ground: {ground}")
        print(f" -> Dominant Flora (Canopy): {flora}")
        print(f" -> Calculated Biome: {primary_biome}")

    # ==========================================
    # TRUE BIOME PALETTE MAPPING
    # ==========================================
    if has_snow or "ice" in primary_biome or "snow" in primary_biome or "frozen" in primary_biome:
        wall_id, roof_id = "bricks", "oxidized_cut_copper"
    elif "desert" in primary_biome or "badlands" in primary_biome or "mesa" in primary_biome:
        wall_id, roof_id = "deepslate_bricks", "warped_planks"
    elif "taiga" in primary_biome or "spruce" in primary_biome or "pine" in primary_biome or "old_growth" in primary_biome:
        wall_id, roof_id = "smooth_sandstone", "acacia_planks"
    elif "jungle" in primary_biome or "swamp" in primary_biome or "mangrove" in primary_biome:
        wall_id, roof_id = "quartz_bricks", "crimson_planks"
    elif "mountain" in primary_biome or "peaks" in primary_biome or "stony" in primary_biome:
        wall_id, roof_id = "mud_bricks", "dark_prismarine"
    elif "savanna" in primary_biome:
        wall_id, roof_id = "yellow_terracotta", "dark_oak_planks"
    elif "cherry" in primary_biome:
        wall_id, roof_id = "polished_deepslate", "cherry_planks"
    elif "dark_forest" in primary_biome:
        wall_id, roof_id = "cobbled_deepslate", "spruce_planks"
    else:
        wall_id, roof_id = "polished_blackstone_bricks", "mangrove_planks"

    def make_stair(b_id):
        if b_id.endswith("_planks"): return b_id.replace("_planks", "_stairs")
        if b_id.endswith("bricks"): return b_id[:-1] + "_stairs"
        if b_id.endswith("tiles"): return b_id[:-1] + "_stairs"
        if "copper" in b_id and "cut" not in b_id: return b_id.replace("copper", "cut_copper_stairs")
        if b_id == "stone": return "stone_stairs"
        if "terracotta" in b_id: return "granite_stairs" 
        return b_id + "_stairs"

    roof_stair_id = make_stair(roof_id)
    print(f"Assigned Contrasting Palette -> Walls: {wall_id}, Roof: {roof_id}")
    
    return Block(wall_id), Block(roof_id), Block(roof_stair_id), has_snow

def build_entrance_carver(editor, cx, base_y, cz, radius, facing, depth_in=-2, depth_out=3):
    directions = {"north": (0, -1), "south": (0, 1), "east":  (1, 0), "west":  (-1, 0)}
    fx, fz = directions[facing]
    px, pz = -fz, fx  
    wall_x, wall_z = cx + fx * int(radius), cz + fz * int(radius)
    for depth in range(depth_in, depth_out):     
        for side in range(-1, 3):          
            for height in range(4):        
                editor.placeBlock((wall_x + px * side + fx * depth, base_y + 1 + height, wall_z + pz * side + fz * depth), Block("air"))
    banner_color = random.choice(["white","orange","magenta","light_blue","yellow","lime","pink","gray","light_gray","cyan","purple","blue","brown","green","red","black"])
    editor.placeBlock((wall_x + px * 2, base_y + 1, wall_z + pz * 2), Block(f"{banner_color}_banner"))

# ==========================================
# MASTER GENERATOR
# ==========================================
def main():
    if RNG_SEED is not None: random.seed(RNG_SEED)
    editor = Editor(buffering=True)
    
    PLOT_SIZE = 100 
    print(f"Scouting terrain for the {PLOT_SIZE}x{PLOT_SIZE} building plot...")
    best_patch, is_ideal = plot.find_best_location(PLOT_SIZE)
    start_x, start_z = plot.x0 + best_patch[0], plot.z0 + best_patch[1]

    build_area = editor.getBuildArea()
    initial_world_slice = editor.loadWorldSlice(build_area.toRect(), cache=True)
    env_wall, env_roof, env_roof_stair, is_snowy = get_biome_palette(editor, initial_world_slice, build_area)
    heights = []
    for dx in range(PLOT_SIZE):
        for dz in range(PLOT_SIZE):
            local_x, local_z = (start_x + dx) - build_area.begin.x, (start_z + dz) - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                heights.append(initial_world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z])
    heights.sort()
    base_y = heights[int(len(heights) * 0.80)] - 1 

    # Determine Topography Downhill Direction!
    slope_facing = calculate_downhill_direction(initial_world_slice, build_area, start_x, start_z, PLOT_SIZE)
    print(f"Terrain Analysis Complete. The valley drops off to the {slope_facing}.")

    clear_all_trees_in_plot(editor, start_x, start_z, PLOT_SIZE, base_y)
    editor.flushBuffer() 
    
    print("Reloading bare terrain data...")
    world_slice = editor.loadWorldSlice(build_area.toRect())

    # ==========================================
    # BLUEPRINT PARAMETERS
    # ==========================================
    small_roof_h_e, radius_e, height_e = 16, 5, 30
    radius_cr, ground_height_cr, dorm_height_cr, roof_height_cr = random.randint(14, 17), random.randint(15, 25), random.randint(13, 18), 38
    cr_base_h = ground_height_cr + dorm_height_cr
    radius_lib, height_lib = random.randint(7, 13), random.randint(30, 45) 
    gh_length, gh_width, gh_height = 40, random.randint(15, 20), 25
    corr_width = 11

    # Map Center for rotation calculations
    map_cx = start_x + (PLOT_SIZE // 2)
    map_cz = start_z + (PLOT_SIZE // 2)

    # Base Blueprint Coordinates
    b_ent_cx, b_ent_cz = start_x + 35, start_z + 85
    b_left_tower_x, b_right_tower_x = b_ent_cx - 16, b_ent_cx + 16 
    
    b_gh_cx, b_gh_cz = (b_right_tower_x + radius_e + 1) + (gh_length // 2), b_ent_cz              
    b_cr_cx, b_cr_cz = b_gh_cx, start_z + 25        
    b_lib_cx, b_lib_cz = b_left_tower_x, b_cr_cz              
    b_gard_cx, b_gard_cz = start_x + 48, start_z + 55

    # ROTATE ALL COORDINATES
    ent_cx, ent_cz = rotate_point(b_ent_cx, b_ent_cz, map_cx, map_cz, slope_facing)
    left_tower_x, left_tower_z = rotate_point(b_left_tower_x, b_ent_cz, map_cx, map_cz, slope_facing)
    right_tower_x, right_tower_z = rotate_point(b_right_tower_x, b_ent_cz, map_cx, map_cz, slope_facing)
    
    gh_cx, gh_cz = rotate_point(b_gh_cx, b_gh_cz, map_cx, map_cz, slope_facing)
    cr_cx, cr_cz = rotate_point(b_cr_cx, b_cr_cz, map_cx, map_cz, slope_facing)
    lib_cx, lib_cz = rotate_point(b_lib_cx, b_lib_cz, map_cx, map_cz, slope_facing)
    gard_cx, gard_cz = rotate_point(b_gard_cx, b_gard_cz, map_cx, map_cz, slope_facing)

    # CORRIDOR CALCULATIONS (Pre-rotated)
    b_lc_cz = b_lib_cz + radius_lib + ((b_ent_cz - radius_e - (b_lib_cz + radius_lib)) // 2)
    b_tc_cx = b_lib_cx + radius_lib + ((b_cr_cx - radius_cr - (b_lib_cx + radius_lib)) // 2)
    b_rc_cz = b_cr_cz + radius_cr + ((b_gh_cz - (gh_width // 2) - (b_cr_cz + radius_cr)) // 2)
    
    lc_cx, lc_cz = rotate_point(b_lib_cx, b_lc_cz, map_cx, map_cz, slope_facing)
    tc_cx, tc_cz = rotate_point(b_tc_cx, b_lib_cz, map_cx, map_cz, slope_facing)
    rc_cx, rc_cz = rotate_point(b_cr_cx, b_rc_cz, map_cx, map_cz, slope_facing)

    # Lengths stay the same, but Axis changes
    lc_len = (b_ent_cz - radius_e) - (b_lib_cz + radius_lib)
    tc_len = (b_cr_cx - radius_cr) - (b_lib_cx + radius_lib)
    rc_len = (b_gh_cz - (gh_width // 2)) - (b_cr_cz + radius_cr)
    
    axis_n_s = rotate_direction("n-s", slope_facing)
    axis_e_w = rotate_direction("e-w", slope_facing)

    # ==========================================
    # PHASE 1: PREPARE TERRAIN FOUNDATIONS
    # ==========================================
    print(f"Aligning layout {slope_facing} and preparing exact foundations...")
    
    # 1. Entrance footprint: Exact cylinders for towers
    construct_cylinder_foundation(editor, world_slice, build_area, left_tower_x, base_y, left_tower_z, radius_e)
    construct_cylinder_foundation(editor, world_slice, build_area, right_tower_x, base_y, right_tower_z, radius_e)
    
    # 2. Entrance footprint: Exact tight rectangle for the connecting archway
    if slope_facing in ["N", "S"]:
        # Towers are spread across the X axis
        min_ex, max_ex = ent_cx - 15, ent_cx + 15
        min_ez, max_ez = ent_cz, ent_cz
    else:
        # Towers are spread across the Z axis ('E' or 'W' rotation)
        min_ex, max_ex = ent_cx, ent_cx
        min_ez, max_ez = ent_cz - 15, ent_cz + 15
        
    construct_rect_foundation(editor, world_slice, build_area, min_ex, min_ez, max_ex, max_ez, base_y)
    
    # 3. Outer Towers
    construct_cylinder_foundation(editor, world_slice, build_area, lib_cx, base_y, lib_cz, radius_lib)
    construct_cylinder_foundation(editor, world_slice, build_area, cr_cx, base_y, cr_cz, radius_cr)
    
    # 4. Grand Viaducts for Corridors
    build_corridor_supports(editor, world_slice, build_area, gh_cx, base_y, gh_cz, axis_e_w, gh_width, gh_length)
    build_corridor_supports(editor, world_slice, build_area, lc_cx, base_y, lc_cz, axis_n_s, corr_width, lc_len)
    build_corridor_supports(editor, world_slice, build_area, tc_cx, base_y, tc_cz, axis_e_w, corr_width, tc_len)
    build_corridor_supports(editor, world_slice, build_area, rc_cx, base_y, rc_cz, axis_n_s, corr_width, rc_len)

    # 5. Central Garden Fountain
    construct_cylinder_foundation(editor, world_slice, build_area, gard_cx, base_y, gard_cz, 5)
    
    editor.flushBuffer()

    # ==========================================
    # PHASE 2: EXECUTE CONSTRUCTION
    # ==========================================
    print("1/7 Constructing Entrance...")
    entrance.build_twin_tower_entrance(editor, world_slice, build_area, ent_cx, base_y, ent_cz, small_roof_h_e, radius_e, height_e, facing=slope_facing, wall_block=env_wall, roof_block=env_roof, roof_stair_block=env_roof_stair, has_snow=is_snowy)

    print("2/7 Constructing Great Hall...")
    corridor.build_dynamic_hogwarts_corridor(editor, gh_cx, base_y, gh_cz, axis_e_w, True, gh_width, gh_length, gh_height, wall_stone=env_wall, roof_block=env_roof, roof_stairs=env_roof_stair)

    print("3/7 Constructing Common Room...")
    common_room.build_common_room_tower(editor, cr_cx, base_y, cr_cz, radius_cr, ground_height_cr, dorm_height_cr, roof_height_cr, env_wall, env_roof, is_snowy)

    print("4/7 Constructing Bibliotheek...")
    tower.build_tower(editor, lib_cx, base_y, lib_cz, radius_lib, height_lib, rotate_facing("south", slope_facing), env_wall, env_roof, is_snowy)

    print("5/7 Constructing Connecting Corridors...")
    corridor.build_dynamic_hogwarts_corridor(editor, lc_cx, base_y, lc_cz, axis_n_s, False, corr_width, lc_len, min(height_lib, height_e)-2, wall_stone=env_wall, roof_block=env_roof, roof_stairs=env_roof_stair) 
    corridor.build_dynamic_hogwarts_corridor(editor, tc_cx, base_y, tc_cz, axis_e_w, False, corr_width, tc_len, min(height_lib, cr_base_h)-2, wall_stone=env_wall, roof_block=env_roof, roof_stairs=env_roof_stair) 
    corridor.build_dynamic_hogwarts_corridor(editor, rc_cx, base_y, rc_cz, axis_n_s, False, corr_width, rc_len, min(cr_base_h, gh_height)-2, wall_stone=env_wall, roof_block=env_roof, roof_stairs=env_roof_stair)  

    print("6/7 Constructing Central Garden...")
    garden.build_dynamic_fountain_garden(editor, world_slice, build_area, gard_cx, base_y, gard_cz, garden_radius=18, wall_block=env_wall, roof_block=env_roof, is_snowy=is_snowy)
    # ==========================================
    # PHASE 3: CARVE INTERNAL DOORWAYS
    # ==========================================
    print("7/7 Carving interconnected doorways...")
    
    build_entrance_carver(editor, left_tower_x, base_y, left_tower_z, radius_e, rotate_facing("north", slope_facing), depth_out=7)
    build_entrance_carver(editor, left_tower_x, base_y, left_tower_z, radius_e, rotate_facing("east", slope_facing), depth_out=7)
    build_entrance_carver(editor, right_tower_x, base_y, right_tower_z, radius_e, rotate_facing("west", slope_facing), depth_out=7)
    build_entrance_carver(editor, right_tower_x, base_y, right_tower_z, radius_e, rotate_facing("east", slope_facing), depth_out=7)

    build_entrance_carver(editor, lib_cx, base_y, lib_cz, radius_lib, rotate_facing("south", slope_facing))
    build_entrance_carver(editor, lib_cx, base_y, lib_cz, radius_lib, rotate_facing("east", slope_facing))

    build_entrance_carver(editor, cr_cx, base_y, cr_cz, radius_cr, rotate_facing("west", slope_facing))
    build_entrance_carver(editor, cr_cx, base_y, cr_cz, radius_cr, rotate_facing("south", slope_facing))

    build_entrance_carver(editor, cr_cx, base_y, gh_cz, gh_width // 2, rotate_facing("north", slope_facing))

    print("Flushing final structural buffers to Minecraft...")
    editor.flushBuffer()
    print("Generation Complete! The adaptive, self-orienting castle is built.")

if __name__ == "__main__":
    main()