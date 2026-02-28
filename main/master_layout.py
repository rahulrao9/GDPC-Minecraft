import random
from gdpc import Editor, Block

import plot
import entrance
import garden
import corridor
import common_room
import tower

RNG_SEED = None

# ==========================================
# DOORWAY CARVER
# ==========================================
# ==========================================
# DOORWAY CARVER
# ==========================================
def build_entrance(editor, cx, base_y, cz, radius, facing, depth_in=-2, depth_out=3):
    """Punches a 4x4 hole with a banner on the wall to connect rooms."""
    directions = {
        "north": (0, -1),
        "south": (0, 1),
        "east":  (1, 0),
        "west":  (-1, 0),
    }

    fx, fz = directions[facing]
    px, pz = -fz, fx  # Perpendicular vectors for left/right

    # Wall center
    wall_x = cx + fx * int(radius)
    wall_z = cz + fz * int(radius)

    # ---- 4x4 Opening (Customizable depth!) ----
    for depth in range(depth_in, depth_out):     
        for side in range(-1, 3):          # width = 4
            for height in range(4):        # height = 4
                # Add the forward/backward (depth) offset to the X and Z coordinates
                x = wall_x + px * side + fx * depth
                z = wall_z + pz * side + fz * depth
                y = base_y + 1 + height
                editor.placeBlock((x, y, z), Block("air"))

    # ---- Banner on right side ----
    banner_colors = [
        "white","orange","magenta","light_blue","yellow",
        "lime","pink","gray","light_gray","cyan",
        "purple","blue","brown","green","red","black"
    ]
    banner_color = random.choice(banner_colors)
    banner_block = Block(f"{banner_color}_banner")
    
    right_side = 2
    # The banner will stand on the floor at the exact wall boundary (depth = 0)
    x = wall_x + px * right_side
    z = wall_z + pz * right_side
    y = base_y + 1
    editor.placeBlock((x, y, z), banner_block)

# ==========================================
# MASTER GENERATOR
# ==========================================
def main():
    if RNG_SEED is not None:
        random.seed(RNG_SEED)

    editor = Editor(buffering=True)
    
    # 1. SCOUT & LEVEL THE 100x100 PLOT
    PLOT_SIZE = 100 
    print(f"Scouting terrain for the {PLOT_SIZE}x{PLOT_SIZE} building plot...")
    best_patch, is_ideal = plot.find_best_location(PLOT_SIZE)
    plot.leveling(best_patch, PLOT_SIZE)
    editor.flushBuffer() 
    
    # 2. RELOAD WORLD DATA
    build_area = editor.getBuildArea()
    world_slice = editor.loadWorldSlice(build_area.toRect()) 
    
    start_x = plot.x0 + best_patch[0]
    start_z = plot.z0 + best_patch[1]
    
    center_local_x = (start_x + 50) - build_area.begin.x
    center_local_z = (start_z + 50) - build_area.begin.z
    if 0 <= center_local_x < build_area.size.x and 0 <= center_local_z < build_area.size.z:
        base_y = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][center_local_x][center_local_z] - 1
    else:
        base_y = -61 

    print(f"Plot verified. Building Hogwarts 100x100 Blueprint at Y={base_y}...")

    # ==========================================
    # BLUEPRINT PARAMETERS
    # ==========================================
    # Entrance
    small_roof_h_e = 16
    radius_e = 5
    height_e = 30
    
    # Common Room
    radius_cr = random.randint(18, 23)
    ground_height_cr = random.randint(15, 25)
    dorm_height_cr = random.randint(13, 18)
    roof_height_cr = 38
    cr_base_h = ground_height_cr + dorm_height_cr
    
    # Library Tower
    radius_lib = random.randint(7, 13)
    height_lib = random.randint(30, 45) 
    
    # Great Hall
    gh_length = 33
    gh_width = random.randint(15, 20)
    gh_height = 25
    
    # Corridor Base Settings
    corr_width = 11

    # ==========================================
    # EXACT COORDINATE MAPPING (0-100 grid)
    # ==========================================
    # 1. Entrance (Bottom center, facing South)
    ent_cx = start_x + 40
    ent_cz = start_z + 90
    left_tower_x = ent_cx - 16  # 24
    right_tower_x = ent_cx + 16 # 51
    
    # 2. Great Hall (Horizontal, extending right)
    gh_cx = start_x + 80        # Spans X: 39 to 89
    gh_cz = ent_cz              # Z: 90
    
    # 3. Common Room (Top Right)
    # 12 blocks inward from the GH extreme right (89 - 12 = 77)
    cr_cx = start_x + 77
    cr_cz = start_z + 25        # Pushed down slightly to ensure radius_cr (23) doesn't exceed Z=0
    
    # 4. Library (Top Left)
    # Aligns strictly with the Left Entrance Tower (24) and CR Z (25)
    lib_cx = start_x + left_tower_x - start_x # 24
    lib_cz = cr_cz              # 25
    
    # 5. Garden (Fills the center void)
    gard_cx = start_x + 50
    gard_cz = start_z + 57

    # ==========================================
    # CORRIDOR CALCULATIONS (Ensuring precise connections)
    # ==========================================
    # Left Corridor (Library to Entrance Left Tower)
    lc_start = lib_cz + radius_lib
    lc_end = ent_cz - radius_e
    lc_len = lc_end - lc_start
    lc_cz = lc_start + (lc_len // 2)
    lc_height = min(height_lib, height_e) - 2 # Constrained height!

    # Top Corridor (Library to Common Room)
    tc_start = lib_cx + radius_lib
    tc_end = cr_cx - radius_cr
    tc_len = tc_end - tc_start
    tc_cx = tc_start + (tc_len // 2)
    tc_height = min(height_lib, cr_base_h) - 2 # Constrained height!

    # Right Corridor (Common Room to Great Hall)
    rc_start = cr_cz + radius_cr
    rc_end = gh_cz - (gh_width // 2)
    rc_len = rc_end - rc_start
    rc_cz = rc_start + (rc_len // 2)
    rc_height = min(cr_base_h, gh_height) - 2 # Constrained height!

    # ==========================================
    # EXECUTE CONSTRUCTION IN ORDER
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
    corridor.build_dynamic_hogwarts_corridor(editor, lib_cx, base_y, lc_cz, "n-s", False, corr_width, lc_len, lc_height) # Left
    corridor.build_dynamic_hogwarts_corridor(editor, tc_cx, base_y, lib_cz, "e-w", False, corr_width, tc_len, tc_height) # Top
    corridor.build_dynamic_hogwarts_corridor(editor, cr_cx, base_y, rc_cz, "n-s", False, corr_width, rc_len, rc_height)  # Right

    print("6/7 Constructing Central Garden...")
    garden.build_dynamic_fountain_garden(editor, gard_cx, base_y, gard_cz, garden_radius=18)
    
    # ==========================================
    # CARVE INTERNAL DOORWAYS
    # ==========================================
    print("7/7 Carving interconnected doorways...")
    
    # --- ENTRANCE TWIN TOWERS (Carved +4 blocks deeper to punch through thick archways) ---
    # Left Tower -> Left Corridor (Facing North)
    build_entrance(editor, left_tower_x, base_y, ent_cz, radius_e, "north", depth_out=7)
    # Left Tower -> Central Walkway (Facing East)
    build_entrance(editor, left_tower_x, base_y, ent_cz, radius_e, "east", depth_out=7)
    
    # Right Tower -> Central Walkway (Facing West)
    build_entrance(editor, right_tower_x, base_y, ent_cz, radius_e, "west", depth_out=7)
    # Right Tower -> Great Hall (Facing East)
    build_entrance(editor, right_tower_x, base_y, ent_cz, radius_e, "east", depth_out=7)

    # --- LIBRARY ---
    build_entrance(editor, lib_cx, base_y, lib_cz, radius_lib, "south")
    build_entrance(editor, lib_cx, base_y, lib_cz, radius_lib, "east")

    # --- COMMON ROOM ---
    build_entrance(editor, cr_cx, base_y, cr_cz, radius_cr, "west")
    build_entrance(editor, cr_cx, base_y, cr_cz, radius_cr, "south")

    # --- GREAT HALL ---
    build_entrance(editor, cr_cx, base_y, gh_cz, gh_width // 2, "north")

    print("Flushing final structural buffers to Minecraft...")
    editor.flushBuffer()
    print("Generation Complete! Perfectly balanced inside 100x100.")

if __name__ == "__main__":
    main()