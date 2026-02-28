import random
import math
from gdpc import Editor, Block

import plot
import entrance
import garden
import corridor
import common_room
import tower

RNG_SEED = None

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
    
    # 1. SCOUT PLOT (NO MORE OVERALL LEVELING!)
    PLOT_SIZE = 100 
    print(f"Scouting terrain for the {PLOT_SIZE}x{PLOT_SIZE} building plot...")
    best_patch, is_ideal = plot.find_best_location(PLOT_SIZE)
    print("Clearing trees to reveal natural terrain...")
    plot.clear_trees_from_plot(best_patch, PLOT_SIZE)
    editor.flushBuffer() 
    
    # 2. RELOAD WORLD DATA & CALCULATE ELEVATION
    build_area = editor.getBuildArea()
    world_slice = editor.loadWorldSlice(build_area.toRect()) 
    
    start_x = plot.x0 + best_patch[0]
    start_z = plot.z0 + best_patch[1]
    
    # Collect all heights to find the 80th percentile (guarantees mostly elevated corridors)
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
    print("Preparing dynamic foundations and arched supports...")
    
    # Entrance footprint (Left Tower, Right Tower, and Walkway)
    construct_cylinder_foundation(editor, world_slice, build_area, left_tower_x, base_y, ent_cz, radius_e)
    construct_cylinder_foundation(editor, world_slice, build_area, right_tower_x, base_y, ent_cz, radius_e)
    # The entrance archway path is 12 blocks wide (-6 to +6) and spans South to North (+24 to -7 locally)
    construct_rect_foundation(editor, world_slice, build_area, ent_cx - 6, ent_cz - 7, ent_cx + 6, ent_cz + 24, base_y)
    
    # Outer Towers
    construct_cylinder_foundation(editor, world_slice, build_area, lib_cx, base_y, lib_cz, radius_lib)
    construct_cylinder_foundation(editor, world_slice, build_area, cr_cx, base_y, cr_cz, radius_cr)
    
    # Arched supports beneath corridors & Great Hall
    build_corridor_supports(editor, world_slice, build_area, gh_cx, base_y, gh_cz, "e-w", gh_width, gh_length)
    build_corridor_supports(editor, world_slice, build_area, lib_cx, base_y, lc_cz, "n-s", corr_width, lc_len)
    build_corridor_supports(editor, world_slice, build_area, tc_cx, base_y, lib_cz, "e-w", corr_width, tc_len)
    build_corridor_supports(editor, world_slice, build_area, cr_cx, base_y, rc_cz, "n-s", corr_width, rc_len)

    # Foundation for central garden fountain
    construct_cylinder_foundation(editor, world_slice, build_area, gard_cx, base_y, gard_cz, 5)

    editor.flushBuffer()

    # ==========================================
    # PHASE 2: EXECUTE CONSTRUCTION
    # ==========================================
    print("1/7 Constructing Entrance...")
    entrance.build_twin_tower_entrance(editor, ent_cx, base_y, ent_cz, small_roof_h_e, radius_e, height_e, facing="S")

    print("2/7 Constructing Great Hall...")
    corridor.build_dynamic_hogwarts_corridor(editor, gh_cx, base_y, gh_cz, "e-w", True, gh_width, gh_length, gh_height)

    print("3/7 Constructing Common Room...")
    common_room.build_common_room_tower(editor, cr_cx, base_y, cr_cz, radius_cr, ground_height_cr, dorm_height_cr, roof_height_cr)

    print("4/7 Constructing Bibliotheek...")
    tower.build_tower(editor, lib_cx, base_y, lib_cz, radius_lib, height_lib)

    print("5/7 Constructing Connecting Corridors...")
    corridor.build_dynamic_hogwarts_corridor(editor, lib_cx, base_y, lc_cz, "n-s", False, corr_width, lc_len, lc_height) 
    corridor.build_dynamic_hogwarts_corridor(editor, tc_cx, base_y, lib_cz, "e-w", False, corr_width, tc_len, tc_height) 
    corridor.build_dynamic_hogwarts_corridor(editor, cr_cx, base_y, rc_cz, "n-s", False, corr_width, rc_len, rc_height)  

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