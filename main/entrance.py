from gdpc import Editor, Block
import math
import random

# Base defaults

FLOOR_BLOCK = Block("spruce_planks")
STAIR_BLOCK = Block("spruce_slab")
WINDOW_BLOCK = Block("glass_pane")  
TORCH_BLOCK = Block("wall_torch")    
CHAIN_BLOCK = Block("oxidized_copper_chain")
LANTERN_BLOCK = Block("soul_torch")
AMETHYST_CLUSTER = Block("amethyst_cluster")
SEA_LANTERN = Block("sea_lantern") 
CHISELED_STONE = Block("chiseled_stone_bricks")
RNG_SEED = None 

# ==========================================
# 1. UTILITY FUNCTIONS
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

def build_circular_wall(editor, cx, y_start, cz, radius, height, block):
    wall_ring = circle_points(cx, cz, radius)
    for y in range(y_start, y_start + height):
        for (x, z) in wall_ring:
            editor.placeBlock((x, y, z), block)

def build_floor_disc(editor, cx, y, cz, radius, block):
    for x in range(cx - radius, cx + radius + 1):
        for z in range(cz - radius, cz + radius + 1):
            if (x - cx) ** 2 + (z - cz) ** 2 <= radius ** 2:
                editor.placeBlock((x, y, z), block)

def build_solid_cylinder(editor, cx, base_y, cz, radius, height, block):
    for y in range(base_y, base_y + height):
        build_floor_disc(editor, cx, y, cz, radius, block)

def build_cone_roof(editor, cx, base_y, cz, base_radius, height, roof_block, has_snow=False):
    for i in range(height):
        t = i / (height - 1) if height > 1 else 1.0
        radius_f = base_radius * (1.0 - t * t)
        r = max(1, int(round(radius_f)))
        y = base_y + i
        for (x, z) in circle_points(cx, cz, r):
            editor.placeBlock((x, y, z), roof_block)
            if has_snow:
                editor.placeBlock((x, y + 1, z), Block("snow"))
                
    # Top spire peaks
    editor.placeBlock((cx, base_y + height, cz), roof_block)
    editor.placeBlock((cx, base_y + height + 1, cz), roof_block)
    if has_snow:
        editor.placeBlock((cx, base_y + height + 2, cz), Block("snow"))

# ==========================================
# 2. TOWER INTERIOR FEATURES
# ==========================================
def sample_wall_window_slots(cx, cz, radius, wall_height, base_y):
    total_windows = max(1, wall_height // 3)
    ring = circle_points(cx, cz, radius)
    window_positions = []
    for _ in range(total_windows):
        wx, wz = random.choice(ring)
        wy = random.randint(base_y + 2, base_y + wall_height - 6)
        window_positions.append((wx, wz, wy))
    return window_positions

def build_wall_windows(editor, window_positions, cx, cz):
    for wx, wz, wy in window_positions:
        dx, dz = wx - cx, wz - cz
        side_x, side_z = (0, 1) if abs(dx) > abs(dz) else (1, 0)
        for horizontal in range(2):
            curr_x, curr_z = wx + (horizontal * side_x), wz + (horizontal * side_z)
            for vertical in range(4):
                editor.placeBlock((curr_x, wy + vertical, curr_z), Block("air"))
                editor.placeBlock((curr_x, wy + vertical, curr_z), WINDOW_BLOCK)

def place_interior_torches_for_window(editor, cx, cz, wx, wz, y):
    dx, dz = wx - cx, wz - cz
    length = math.sqrt(dx * dx + dz * dz)
    if length == 0: return
    ndx, ndz = dx / length, dz / length
    inner_x, inner_z = int(round(wx - ndx)), int(round(wz - ndz))
    left_tx, left_tz = int(round(inner_x - ndz)), int(round(inner_z + ndx))
    right_tx, right_tz = int(round(inner_x + ndz)), int(round(inner_z - ndx))
    editor.placeBlock((left_tx, y, left_tz), TORCH_BLOCK)
    editor.placeBlock((right_tx, y, right_tz), TORCH_BLOCK)

def build_spiral_stairs(editor, cx, base_y, cz, stairs_height, wall_radius, window_positions):
    windows_by_y = {}
    for wx, wz, wy in window_positions:
        windows_by_y.setdefault(wy, []).append((wx, wz))
    slices_per_circle = int(2 * math.pi * wall_radius * 1.5)
    total_steps = stairs_height * 3 + 1
    for step in range(total_steps):
        angle = (2 * math.pi * step) / slices_per_circle
        y = base_y + 1 + (step // 3)
        stair_block = Block("spruce_stairs") if step == total_steps - 1 else STAIR_BLOCK
        for r_offset in range(1, 4):
            current_r = wall_radius - r_offset
            x = int(round(cx + current_r * math.cos(angle)))
            z = int(round(cz + current_r * math.sin(angle)))
            editor.placeBlock((x, y, z), stair_block)
        if y in windows_by_y:
            for wx, wz in windows_by_y[y]:
                place_interior_torches_for_window(editor, cx, cz, wx, wz, y)

def build_chandelier(editor, cx, ceiling_y, cz):
    anchor_offsets = [(-3,0), (-2,1), (-2,-1), (0,3), (0,-3), (2,1), (2,-1), (3,0)]
    for dx, dz in anchor_offsets:
        for drop in range(5): 
            editor.placeBlock((cx + dx, ceiling_y - drop, cz + dz), CHAIN_BLOCK)
    central_y = ceiling_y - 4
    for (x, z) in circle_points(cx, cz, 2.5):
        editor.placeBlock((x, central_y, z), AMETHYST_CLUSTER)
        if random.random() < 0.6: 
            editor.placeBlock((x, central_y - 1, z), AMETHYST_CLUSTER)
    mid_y = ceiling_y - 6
    for r in [1.5, 3.0]:
        q = 0
        for (x, z) in circle_points(cx, cz, r):
            if q % 2 == 0:
                editor.placeBlock((x, mid_y, z), CHAIN_BLOCK)
                editor.placeBlock((x, mid_y - 1, z), LANTERN_BLOCK)
            q += 1
    for y in range(ceiling_y - 1, ceiling_y - 9, -1):
        if y % 2 == 0: editor.placeBlock((cx, y, cz), CHAIN_BLOCK)
    editor.placeBlock((cx, ceiling_y - 9, cz), SEA_LANTERN)

def place_custom_standing_sign(editor, x, y, z, rotation, text_lines, block_id="pale_oak_sign"):
    escaped_lines = [line.replace("'", "\\'") for line in text_lines]
    line0 = f'{escaped_lines[0]}'
    line1 = f'{escaped_lines[1]}'
    line2 = f'{escaped_lines[2]}'
    line3 = f'{escaped_lines[3]}'
    nbt_data = f"{{front_text:{{has_glowing_text:1b, color:'yellow', messages:['{line0}', '{line1}', '{line2}', '{line3}']}}}}"
    sign_block = Block(block_id, {"rotation": str(rotation)}, data=nbt_data)
    editor.placeBlock((x, y, z), sign_block)

def place_wizard_quote_standing_sign(editor, x, y, z, rotation, block_id="pale_oak_sign"):
    quotes = [
        ["I'm feeling", "Sirius-ly", "magical", "today."],
        ["", "Wingardium", "Levio-swag.", ""],
        ["", "My Patronus", "is coffee.", ""],
        ["Don't let", "the Muggles", "get you", "down."],
        ["", "Just here", "for the", "butterbeer."],
        ["", "The struggle", "is", "Riddikulus."],
        ["", "Expelliarmus", "your", "worries!"]
    ]
    chosen_quote = random.choice(quotes)
    escaped_lines = [line.replace("'", "\\'") for line in chosen_quote]
    line0, line1, line2, line3 = escaped_lines
    nbt_data = f"{{front_text:{{has_glowing_text:1b, color:'yellow', messages:['{line0}', '{line1}', '{line2}', '{line3}']}}}}"
    sign_block = Block(block_id, {"rotation": str(rotation)}, data=nbt_data)
    editor.placeBlock((x, y, z), sign_block)

# ==========================================
# 3. MAIN GENERATOR LOGIC
# ==========================================
def build_fully_featured_tower(editor, world_slice, build_area, cx, base_y, cz, radius, height, small_roof_h, wall_block, roof_block, has_snow=False):
    # 1. Adaptive Foundation for the main tower
    for x in range(cx - radius - 1, cx + radius + 2):
        for z in range(cz - radius - 1, cz + radius + 2):
            if math.hypot(x - cx, z - cz) <= radius:
                local_x = x - build_area.begin.x
                local_z = z - build_area.begin.z
                if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                    gy = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z] - 1
                    # Carve a hole if terrain is higher
                    if gy > base_y:
                        for y in range(base_y, gy + 5):
                            editor.placeBlock((x, y, z), Block("air"))
                    # Build stone foundation down if terrain is lower
                    if gy < base_y:
                        for y in range(gy, base_y):
                            editor.placeBlock((x, y, z), wall_block)

    build_floor_disc(editor, cx, base_y, cz, radius, wall_block)
    build_circular_wall(editor, cx, base_y + 1, cz, radius, height, wall_block)

    # 2. Adaptive Foundation for corner turrets
    small_r = 4
    small_wall_h = height
    corner_offset = radius - 0 
    
    for dx in [-corner_offset, corner_offset]:
        for dz in [-corner_offset, corner_offset]:
            small_cx, small_cz = cx + dx, cz + dz
            
            # Local foundation
            for x in range(small_cx - small_r, small_cx + small_r + 1):
                for z in range(small_cz - small_r, small_cz + small_r + 1):
                    if math.hypot(x - small_cx, z - small_cz) <= small_r:
                        local_x, local_z = x - build_area.begin.x, z - build_area.begin.z
                        if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                            gy = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z] - 1
                            if gy < base_y:
                                for y in range(gy, base_y):
                                    editor.placeBlock((x, y, z), wall_block)

            build_solid_cylinder(editor, small_cx, base_y, small_cz, small_r, small_wall_h, wall_block)
            build_cone_roof(editor, small_cx, base_y + small_wall_h, small_cz, small_r, small_roof_h, roof_block, has_snow)
    windows = sample_wall_window_slots(cx, cz, radius, height, base_y)
    build_wall_windows(editor, windows, cx, cz)
    build_spiral_stairs(editor, cx, base_y, cz, height - 2, radius, windows)

    roof_base_y = base_y + height
    build_floor_disc(editor, cx, roof_base_y, cz, radius + 1, wall_block)
    build_chandelier(editor, cx, roof_base_y - 1, cz)
    build_cone_roof(editor, cx, roof_base_y, cz, radius, int(1.4 * height), roof_block, has_snow)

def build_twin_tower_entrance(editor, world_slice, build_area, cx, base_y, cz, small_roof_h, radius, height, facing, wall_block, roof_block,roof_stair_block, has_snow=False):
    tower_spread = 32
    portal_radius = 6 
    portal_height = 8 
    curve_height = 10 
    gable_radius = portal_radius + 2 
    
    z_front = -14  
    z_back = 14

    # ==========================================
    # LOCAL TERRAIN & ROTATION HELPERS
    # ==========================================
    def get_pos(lx, lz):
        if facing == 'N': return cx + lx, cz + lz
        if facing == 'S': return cx - lx, cz - lz
        if facing == 'E': return cx - lz, cz + lx
        if facing == 'W': return cx + lz, cz - lx
        return cx + lx, cz + lz

    def get_ground_y(wx, wz):
        """Scans the heightmap for natural terrain."""
        local_x = wx - build_area.begin.x
        local_z = wz - build_area.begin.z
        if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
            return world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z] - 1
        return base_y

    def place_local(lx, y, lz, block):
        wx, wz = get_pos(lx, lz)
        editor.placeBlock((wx, y, wz), block)

    def fill_cuboid_local(lx1, y1, lz1, lx2, y2, lz2, block):
        for lx in range(min(lx1, lx2), max(lx1, lx2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for lz in range(min(lz1, lz2), max(lz1, lz2) + 1):
                    place_local(lx, y, lz, block)

    def fill_cuboid_local_adaptive(lx1, y1, lz1, lx2, y2, lz2, block, foundation_block=None):
        """Builds a local cuboid, extending downwards if terrain is low."""
        for lx in range(min(lx1, lx2), max(lx1, lx2) + 1):
            for lz in range(min(lz1, lz2), max(lz1, lz2) + 1):
                wx, wz = get_pos(lx, lz)
                gy = get_ground_y(wx, wz)
                
                # Build down to the natural ground!
                if foundation_block and gy < y1:
                    for y in range(gy, y1):
                        editor.placeBlock((wx, y, wz), foundation_block)
                
                for y in range(y1, y2 + 1):
                    editor.placeBlock((wx, y, wz), block)

    def rot_facing(facing_str):
        facings = ['north', 'east', 'south', 'west']
        if facing_str not in facings: return facing_str
        idx = facings.index(facing_str)
        offset = {'N':0, 'E':1, 'S':2, 'W':3}[facing]
        return facings[(idx + offset) % 4]

    def rot_axis(axis_str):
        if facing in ['E', 'W']:
            if axis_str == 'x': return 'z'
            if axis_str == 'z': return 'x'
        return axis_str

    def rot_sign(rot_int):
        offset = {'N':0, 'E':4, 'S':8, 'W':12}[facing]
        return (rot_int + offset) % 16

    # =====================================
    # 1. BUILD THE TOWERS
    # =====================================
    left_lx = - (tower_spread // 2)
    right_lx = (tower_spread // 2)

    tcx1, tcz1 = get_pos(left_lx, 0)
    print(f"Building Adaptive Left Fortified Tower at World({tcx1}, {tcz1})...")
    build_fully_featured_tower(editor, world_slice, build_area, tcx1, base_y, tcz1, radius, height, small_roof_h, wall_block, roof_block, has_snow)
    
    tcx2, tcz2 = get_pos(right_lx, 0)
    print(f"Building Adaptive Right Fortified Tower at World({tcx2}, {tcz2})...")
    build_fully_featured_tower(editor, world_slice, build_area, tcx2, base_y, tcz2, radius, height, small_roof_h, wall_block, roof_block, has_snow)    # =====================================
    
    # 2. THE ADAPTIVE FLOOR & ARCHWAY
    # =====================================
    print(f"Constructing the Terrain-Adaptive Archway (Facing: {facing})...")
    
    for lz in range(z_front, z_back + 1):
        for lx in range(-portal_radius, portal_radius + 1):
            wx, wz = get_pos(lx, lz)
            gy = get_ground_y(wx, wz)
            
            # Carve terrain if it blocks the path
            if gy > base_y:
                for y in range(base_y + 1, gy + 5):
                    editor.placeBlock((wx, y, wz), Block("air"))
            # Build foundation if we are over a dip
            if gy < base_y:
                for y in range(gy, base_y):
                    editor.placeBlock((wx, y, wz), Block("stone_bricks"))
                    
            editor.placeBlock((wx, base_y, wz), FLOOR_BLOCK)
            if abs(lx) <= 2:
                editor.placeBlock((wx, base_y + 1, wz), Block("red_carpet"))
                
            # Embedded Edge Lights
            if abs(lx) == 3 and lz % 3 == 0:
                editor.placeBlock((wx, base_y, wz), Block("glowstone"))

    wall_start_lx = left_lx + radius + 1
    wall_end_lx = right_lx - radius - 1
    fill_cuboid_local_adaptive(wall_start_lx, base_y, -7, -portal_radius - 1, base_y + portal_height, 7, wall_block, foundation_block=wall_block)
    fill_cuboid_local_adaptive(portal_radius + 1, base_y, -7, wall_end_lx, base_y + portal_height, 7, wall_block, foundation_block=wall_block)
    # =====================================
    # 3. PILLARS & TRUSSES
    # =====================================
    BEAM = Block("stripped_dark_oak_log", {"axis": rot_axis("x")})
    TRACERY = Block("dark_oak_fence")
    CHAIN = Block("oxidized_copper_chain")
    LANTERN = Block("lantern")
    SMALL_TORCH = Block("torch")

    span_left = -portal_radius + 2
    span_right = portal_radius - 2
    center_float = 0.0
    arch_peak_y = base_y + portal_height + curve_height - 2
    base_y_arch = base_y + portal_height
    a_curve = (base_y_arch - arch_peak_y) / ((span_left - center_float)**2)

    for z_rib in range(z_front, z_back + 1, 6):
        L_X1, L_X2 = -portal_radius - 1, -portal_radius
        R_X1, R_X2 = portal_radius, portal_radius + 1
        Z1, Z2 = z_rib, z_rib + 1
        
        # A) Bases root themselves down to terrain!
        fill_cuboid_local_adaptive(L_X1 - 1, base_y + 1, Z1 - 1, L_X2 + 1, base_y + 2, Z2 + 1, CHISELED_STONE, foundation_block=CHISELED_STONE)
        fill_cuboid_local_adaptive(R_X1 - 1, base_y + 1, Z1 - 1, R_X2 + 1, base_y + 2, Z2 + 1, CHISELED_STONE, foundation_block=CHISELED_STONE)
        
        place_local(L_X1 - 1, base_y + 3, Z1 - 1, LANTERN)
        place_local(L_X2 + 1, base_y + 3, Z1 - 1, LANTERN)
        place_local(R_X1 - 1, base_y + 3, Z1 - 1, LANTERN)
        place_local(R_X2 + 1, base_y + 3, Z1 - 1, LANTERN)

        # B) Pillars (Sitting on the terrain-adapted bases)
        fill_cuboid_local(L_X1, base_y + 3, Z1, L_X2, base_y + portal_height - 1, Z2, Block("waxed_weathered_cut_copper"))
        fill_cuboid_local(R_X1, base_y + 3, Z1, R_X2, base_y + portal_height - 1, Z2, Block("waxed_weathered_copper"))
        
        fill_cuboid_local(L_X1 - 1, base_y + portal_height, Z1 - 1, L_X2 + 1, base_y + portal_height, Z2 + 1, Block("waxed_weathered_copper"))
        fill_cuboid_local(R_X1 - 1, base_y + portal_height, Z1 - 1, R_X2 + 1, base_y + portal_height, Z2 + 1, Block("waxed_weathered_copper"))

        # Torches
        place_local(L_X2 + 1, base_y + 5, Z1, Block("wall_torch", {"facing": rot_facing("east")}))
        place_local(R_X1 - 1, base_y + 5, Z1, Block("wall_torch", {"facing": rot_facing("west")}))
        place_local(L_X1 - 1, base_y + 5, Z1, Block("wall_torch", {"facing": rot_facing("west")}))
        place_local(R_X2 + 1, base_y + 5, Z1, Block("wall_torch", {"facing": rot_facing("east")}))

        # C) Trusses
        for z_arc in [Z1, Z2]:
            prev_y = base_y_arch
            for lx in range(span_left, span_right + 1):
                y_float = a_curve * (lx - center_float)**2 + arch_peak_y
                y_int = int(round(y_float))
                local_roof_y = base_y + portal_height + int(curve_height * math.cos((abs(lx) / gable_radius) * (math.pi / 2)))
                y_int = min(y_int, local_roof_y - 1)
                step = 1 if y_int > prev_y else -1
                if lx > span_left:
                    fill_x = lx - 1 if step > 0 else lx
                    for filler_y in range(prev_y + step, y_int, step):
                        place_local(fill_x, filler_y, z_arc, BEAM)

                place_local(lx, y_int, z_arc, BEAM)
                for fill_ceil in range(y_int + 1, local_roof_y):
                    place_local(lx, fill_ceil, z_arc, BEAM)
                if lx % 2 == 0 and lx != span_left and lx != span_right:
                    place_local(lx, y_int - 1, z_arc, TRACERY)
                prev_y = y_int

            # ==========================================
            # MASSIVE CHANDELIER
            # ==========================================
            peak_y = int(arch_peak_y)
            
            # 1. Outer Anchor Chains
            anchor_offsets = [(-3,0), (-2,1), (-2,-1), (0,3), (0,-3), (2,1), (2,-1), (3,0)]
            for dx, dz in anchor_offsets:
                for drop in range(5): 
                    place_local(dx, peak_y - drop, z_arc + dz, CHAIN)
                    
            # 2. Top Amethyst Ring
            central_y = peak_y - 4
            for (x, z) in circle_points(0, z_arc, 2.5):
                place_local(x, central_y, z, Block("amethyst_cluster"))
                if random.random() < 0.6: 
                    place_local(x, central_y - 1, z, Block("amethyst_cluster"))
                    
            # 3. Alternating Lantern Rings
            mid_y = peak_y - 6
            for r in [1.5, 3.0]:
                ring_points = circle_points(0, z_arc, r)
                # Sort points by angle so they alternate perfectly!
                ring_points.sort(key=lambda p: math.atan2(p[1] - z_arc, p[0]))
                
                for index, (x, z) in enumerate(ring_points):
                    if index % 2 == 0:
                        place_local(x, mid_y, z, CHAIN)
                        place_local(x, mid_y - 1, z, LANTERN)
                        
            # 4. Central Drop and Core Light
            for y in range(peak_y - 1, peak_y - 9, -1):
                if y % 2 == 0: 
                    place_local(0, y, z_arc, CHAIN)
                    
            place_local(0, peak_y - 9, z_arc, Block("sea_lantern"))

    roof_base_y = base_y + portal_height
    for lz in range(z_front, z_back + 1):
        prev_y = roof_base_y
        for lx in range(gable_radius, -1, -1):
            dy = int(curve_height * math.cos((lx / gable_radius) * (math.pi / 2)))
            y = roof_base_y + dy
            
            for fill_y in range(min(y, prev_y), max(y, prev_y) + 1):
                if fill_y < roof_base_y: continue 
                
                # USE THE PASSED IN STAIR BLOCK ID HERE
                place_local(-lx, fill_y, lz, Block(roof_stair_block.id, {"facing": rot_facing("east")}))
                # FIXED: Swapped 'snow' for 'white_carpet'
                if has_snow: place_local(-lx, fill_y + 1, lz, Block("white_carpet"))
                
                if lx != 0:
                    # AND HERE
                    place_local(lx, fill_y, lz, Block(roof_stair_block.id, {"facing": rot_facing("west")}))
                    # FIXED: Swapped 'snow' for 'white_carpet'
                    if has_snow: place_local(lx, fill_y + 1, lz, Block("white_carpet"))
                
                if lx > 0:
                    place_local(-lx + 1, fill_y, lz, wall_block)
                    place_local(lx - 1, fill_y, lz, wall_block)
                else:
                    place_local(0, fill_y, lz, wall_block)
            prev_y = y
        place_local(0, prev_y + 1, lz, CHISELED_STONE)
        # FIXED: Swapped 'snow' for 'white_carpet'
        if has_snow: place_local(0, prev_y + 2, lz, Block("white_carpet"))

    # =====================================
    # 5. DYNAMIC GARDEN STAIRS
    # =====================================
    print("Constructing adaptive terrain stairs into the Garden...")
    current_y = base_y
    # We step outward towards the garden (z_back is 14, we loop out to 25)
    for lz in range(z_back + 1, z_back + 12):
        wx_center, wz_center = get_pos(0, lz)
        gy = get_ground_y(wx_center, wz_center)
        
        # If we hit flat ground, finish with a neat gravel path
        if gy == current_y:
            for lx in range(-portal_radius, portal_radius + 1):
                wx, wz = get_pos(lx, lz)
                editor.placeBlock((wx, current_y, wz), Block("gravel"))
            break
            
        # Logic for determining stair direction
        if gy < current_y:
            current_y -= 1
            stair_facing = rot_facing("north") # Ascends backward toward the hall
        else:
            current_y += 1
            stair_facing = rot_facing("south") # Ascends forward into the hill
            
        for lx in range(-portal_radius, portal_radius + 1):
            wx, wz = get_pos(lx, lz)
            # Clear above head
            for clear_y in range(current_y + 1, current_y + 4):
                editor.placeBlock((wx, clear_y, wz), Block("air"))
            
            # Anchor stairs to ground to prevent floating
            local_gy = get_ground_y(wx, wz)
            if local_gy < current_y:
                for fill_y in range(local_gy, current_y):
                    editor.placeBlock((wx, fill_y, wz), Block("stone_bricks"))
                    
            editor.placeBlock((wx, current_y, wz), Block("stone_brick_stairs", {"facing": stair_facing}))

    # Signs
    sign_rot = rot_sign(8) 
    wx, wz = get_pos(3, z_front + 1)
    place_custom_standing_sign(editor, wx, base_y + 1, wz, sign_rot, ["", "Welcome to", "Hogwarts!", ""])
    wx, wz = get_pos(-4, -5)
    place_wizard_quote_standing_sign(editor, wx, base_y + 1, wz, sign_rot)

def main():
    if RNG_SEED is not None:
        random.seed(RNG_SEED)

    WALL_BLOCK = Block("waxed_exposed_copper")
    ROOF_BLOCK = Block("waxed_weathered_copper")

    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()
    world_slice = editor.loadWorldSlice(build_area.toRect())

    cx = build_area.begin.x + 300
    cz = build_area.begin.z + 00
    base_y = -61

    small_roof_h = 16
    radius = 6
    height = 30

    try:
        # Pass the world slice into the builder so it can read the terrain!
        build_twin_tower_entrance(editor, world_slice, build_area, cx, base_y, cz, small_roof_h, radius, height, facing="N", wall_block=WALL_BLOCK, roof_block=ROOF_BLOCK, has_snow=True)
        editor.flushBuffer()
        print("Terrain-Adaptive Twin Tower Entrance complete!")
    except Exception as e:
        print(f"Generation Failed: {e}")

if __name__ == "__main__":
    main()