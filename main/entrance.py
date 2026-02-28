from gdpc import Editor, Block
import math
import random

# Base defaults
WALL_BLOCK = Block("waxed_exposed_copper")
FLOOR_BLOCK = Block("spruce_planks")
STAIR_BLOCK = Block("spruce_slab")
WINDOW_BLOCK = Block("glass_pane")  
TORCH_BLOCK = Block("wall_torch")    
CHAIN_BLOCK = Block("oxidized_copper_chain")
LANTERN_BLOCK = Block("soul_torch")
AMETHYST_CLUSTER = Block("amethyst_cluster")
SEA_LANTERN = Block("sea_lantern") 
CHISELED_STONE = Block("chiseled_stone_bricks")
ROOF_BLOCK = Block("waxed_weathered_copper")

RNG_SEED = None 

# ==========================================
# 1. UTILITY FUNCTIONS
# ==========================================
def fill_cuboid(editor, x1, y1, z1, x2, y2, z2, block):
    """Safe manual cuboid fill to avoid GDPC version errors."""
    min_x, max_x = min(x1, x2), max(x1, x2)
    min_y, max_y = min(y1, y2), max(y1, y2)
    min_z, max_z = min(z1, z2), max(z1, z2)
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            for z in range(min_z, max_z + 1):
                editor.placeBlock((x, y, z), block)

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

def build_cone_roof(editor, cx, base_y, cz, base_radius, height, roof_block=ROOF_BLOCK):
    for i in range(height):
        t = i / (height - 1) if height > 1 else 1.0
        radius_f = base_radius * (1.0 - t * t)
        r = max(1, int(round(radius_f)))
        y = base_y + i
        for (x, z) in circle_points(cx, cz, r):
            editor.placeBlock((x, y, z), roof_block)
    editor.placeBlock((cx, base_y + height, cz), roof_block)
    editor.placeBlock((cx, base_y + height + 1, cz), roof_block)

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
        ["", "Expelliarmus", "your", "worries!"],
        ["", "You're", "broom-tiful.", ""],
        ["", "Slayin' like", "a Slytherin.", ""],
        ["", "You're my", "chosen one.", ""],
        ["100%", "certified", "Muggle", "magnet."],
        ["You're totally", "Dumble-", "adore-able!", ""]
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
def build_fully_featured_tower(editor, cx, base_y, cz, radius, height, small_roof_h):
    """Builds a single 3D wizard tower with full interior and 4 corner turrets."""
    build_floor_disc(editor, cx, base_y, cz, radius, WALL_BLOCK)
    build_circular_wall(editor, cx, base_y + 1, cz, radius, height, WALL_BLOCK)

    small_r = 4
    small_wall_h = height
    corner_offset = radius - 0 
    
    for dx in [-corner_offset, corner_offset]:
        for dz in [-corner_offset, corner_offset]:
            small_cx, small_cz = cx + dx, cz + dz
            build_solid_cylinder(editor, small_cx, base_y, small_cz, small_r, small_wall_h, WALL_BLOCK)
            build_cone_roof(editor, small_cx, base_y + small_wall_h, small_cz, small_r, small_roof_h)

    windows = sample_wall_window_slots(cx, cz, radius, height, base_y)
    build_wall_windows(editor, windows, cx, cz)
    build_spiral_stairs(editor, cx, base_y, cz, height - 2, radius, windows)

    roof_base_y = base_y + height
    build_floor_disc(editor, cx, roof_base_y, cz, radius + 1, WALL_BLOCK)
    build_chandelier(editor, cx, roof_base_y - 1, cz)
    build_cone_roof(editor, cx, roof_base_y, cz, radius, int(1.4 * height))


def build_twin_tower_entrance(editor, cx, base_y, cz, small_roof_h, radius, height, facing="N"):
    """
    Generates the grand twin-tower entrance, rotated intelligently to face N, S, E, or W.
    """
    tower_spread = 32 
    portal_radius = 6 
    portal_height = 8 
    curve_height = 10 
    gable_radius = portal_radius + 2 
    
    # Internal blueprint dimensions (Assuming North as default forward)
    z_front = -14  
    z_back = 7

    # ==========================================
    # LOCAL COORDINATE ROTATION HELPERS
    # ==========================================
    def get_pos(lx, lz):
        """Translates local blueprint coordinates into rotated world coordinates."""
        if facing == 'N': return cx + lx, cz + lz
        if facing == 'S': return cx - lx, cz - lz
        if facing == 'E': return cx - lz, cz + lx
        if facing == 'W': return cx + lz, cz - lx
        return cx + lx, cz + lz

    def place_local(lx, y, lz, block):
        wx, wz = get_pos(lx, lz)
        editor.placeBlock((wx, y, wz), block)
        
    def fill_cuboid_local(lx1, y1, lz1, lx2, y2, lz2, block):
        for lx in range(min(lx1, lx2), max(lx1, lx2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for lz in range(min(lz1, lz2), max(lz1, lz2) + 1):
                    place_local(lx, y, lz, block)

    def rot_facing(facing_str):
        """Rotates block facings (stairs, torches)."""
        facings = ['north', 'east', 'south', 'west']
        if facing_str not in facings: return facing_str
        idx = facings.index(facing_str)
        if facing == 'N': offset = 0
        elif facing == 'E': offset = 1
        elif facing == 'S': offset = 2
        elif facing == 'W': offset = 3
        return facings[(idx + offset) % 4]

    def rot_axis(axis_str):
        """Rotates block axes (logs)."""
        if facing in ['E', 'W']:
            if axis_str == 'x': return 'z'
            if axis_str == 'z': return 'x'
        return axis_str

    def rot_sign(rot_int):
        """Rotates signs (0-15 metadata)."""
        if facing == 'N': return rot_int
        if facing == 'E': return (rot_int + 4) % 16
        if facing == 'S': return (rot_int + 8) % 16
        if facing == 'W': return (rot_int + 12) % 16
        return rot_int

    # =====================================
    # 1. BUILD THE TOWERS (Translated)
    # =====================================
    left_lx = - (tower_spread // 2)
    right_lx = (tower_spread // 2)

    tcx1, tcz1 = get_pos(left_lx, 0)
    print(f"Building Left Fortified Tower at World({tcx1}, {tcz1})...")
    build_fully_featured_tower(editor, tcx1, base_y, tcz1, radius, height, small_roof_h)
    
    tcx2, tcz2 = get_pos(right_lx, 0)
    print(f"Building Right Fortified Tower at World({tcx2}, {tcz2})...")
    build_fully_featured_tower(editor, tcx2, base_y, tcz2, radius, height, small_roof_h)

    # =====================================
    # 2. BUILD THE GRAND PILLARED ARCHWAY
    # =====================================
    print(f"Constructing the Grand Pillared Archway (Facing: {facing})...")
    
    # Floor, Carpet, and Embedded Lighting
    fill_cuboid_local(-portal_radius, base_y, z_front, portal_radius, base_y, z_back, FLOOR_BLOCK)
    fill_cuboid_local(-2, base_y + 1, z_front, 2, base_y + 1, z_back, Block("red_carpet"))
    
    for lz in range(z_front + 2, z_back, 3):
        place_local(-3, base_y, lz, Block("glowstone"))
        place_local(3, base_y, lz, Block("glowstone"))

    # Solid Side Walls (between towers)
    wall_start_lx = left_lx + radius + 1
    wall_end_lx = right_lx - radius - 1
    fill_cuboid_local(wall_start_lx, base_y, -7, -portal_radius - 1, base_y + portal_height, 7, WALL_BLOCK)
    fill_cuboid_local(portal_radius + 1, base_y, -7, wall_end_lx, base_y + portal_height, 7, WALL_BLOCK)

    # 3. Pillars, Wooden Trusses, and Chandeliers
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
        
        # A) Bases
        fill_cuboid_local(L_X1 - 1, base_y + 1, Z1 - 1, L_X2 + 1, base_y + 2, Z2 + 1, CHISELED_STONE)
        fill_cuboid_local(R_X1 - 1, base_y + 1, Z1 - 1, R_X2 + 1, base_y + 2, Z2 + 1, CHISELED_STONE)
        
        place_local(L_X1 - 1, base_y + 3, Z1 - 1, LANTERN)
        place_local(L_X2 + 1, base_y + 3, Z1 - 1, LANTERN)
        place_local(R_X1 - 1, base_y + 3, Z1 - 1, LANTERN)
        place_local(R_X2 + 1, base_y + 3, Z1 - 1, LANTERN)

        # B) Pillars & Caps
        fill_cuboid_local(L_X1, base_y + 3, Z1, L_X2, base_y + portal_height - 1, Z2, Block("waxed_weathered_cut_copper"))
        fill_cuboid_local(R_X1, base_y + 3, Z1, R_X2, base_y + portal_height - 1, Z2, Block("waxed_weathered_copper"))
        
        fill_cuboid_local(L_X1 - 1, base_y + portal_height, Z1 - 1, L_X2 + 1, base_y + portal_height, Z2 + 1, Block("waxed_weathered_copper"))
        fill_cuboid_local(R_X1 - 1, base_y + portal_height, Z1 - 1, R_X2 + 1, base_y + portal_height, Z2 + 1, Block("waxed_weathered_copper"))

        # Torches on faces (Rotated!)
        place_local(L_X2 + 1, base_y + 5, Z1, Block("wall_torch", {"facing": rot_facing("east")}))
        place_local(R_X1 - 1, base_y + 5, Z1, Block("wall_torch", {"facing": rot_facing("west")}))
        place_local(L_X1 - 1, base_y + 5, Z1, Block("wall_torch", {"facing": rot_facing("west")}))
        place_local(R_X2 + 1, base_y + 5, Z1, Block("wall_torch", {"facing": rot_facing("east")}))

        # C) Parabolic Wooden Trusses
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

        # D) Chandeliers
        z_chand = Z1 + 3  
        if z_chand < z_back:
            chain_start_y = base_y + portal_height + curve_height - 1
            chand_y = chain_start_y - 7
            
            for dy in range(chain_start_y, chand_y - 1, -1):
                place_local(0, dy, z_chand, CHAIN)
            
            ring_radius = 2.0
            steps = 12
            for i in range(steps):
                angle = 2 * math.pi * i / steps
                cx_ring = int(round(ring_radius * math.cos(angle)))
                cz_ring = int(round(z_chand + ring_radius * math.sin(angle)))
                
                place_local(cx_ring, chand_y, cz_ring, CHAIN)
                place_local(cx_ring, chand_y - 1, cz_ring, LANTERN)
                
            place_local(0, chand_y - 1, z_chand, SMALL_TORCH)

    # 4. Continuous Curved Roof Shell
    roof_base_y = base_y + portal_height
    for lz in range(z_front, z_back + 1):
        prev_y = roof_base_y
        for lx in range(gable_radius, -1, -1):
            dy = int(curve_height * math.cos((lx / gable_radius) * (math.pi / 2)))
            y = roof_base_y + dy
            
            for fill_y in range(min(y, prev_y), max(y, prev_y) + 1):
                if fill_y < roof_base_y: continue 
                
                place_local(-lx, fill_y, lz, Block("waxed_exposed_cut_copper_stairs", {"facing": rot_facing("east")}))
                if lx != 0:
                    place_local(lx, fill_y, lz, Block("waxed_exposed_cut_copper_stairs", {"facing": rot_facing("west")}))
                
                if lx > 0:
                    place_local(-lx + 1, fill_y, lz, WALL_BLOCK)
                    place_local(lx - 1, fill_y, lz, WALL_BLOCK)
                else:
                    place_local(0, fill_y, lz, WALL_BLOCK)
            
            prev_y = y

        # Capstone and Ridge Lanterns
        place_local(0, prev_y + 1, lz, CHISELED_STONE)
        if lz % 3 == 0:
            place_local(0, prev_y + 2, lz, LANTERN)

    # Peak Hanging Lantern
    place_local(0, base_y + portal_height + curve_height, z_front - 1, CHAIN)
    place_local(0, base_y + portal_height + curve_height - 1, z_front - 1, LANTERN)

    # =====================================
    # 5. PLACE THE ENTRANCE SIGNS
    # =====================================
    sign_rot = rot_sign(8) # 8 naturally faces forward (North in blueprint terms)
    
    welcome_lx, welcome_lz = 3, z_front + 1
    wx, wz = get_pos(welcome_lx, welcome_lz)
    welcome_text = ["", "Welcome to", "Hogwarts!", ""]
    place_custom_standing_sign(editor, wx, base_y + 1, wz, sign_rot, welcome_text)

    quote_lx, quote_lz = -4, -5  
    wx, wz = get_pos(quote_lx, quote_lz)
    place_wizard_quote_standing_sign(editor, wx, base_y + 1, wz, sign_rot)

def main():
    if RNG_SEED is not None:
        random.seed(RNG_SEED)

    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()

    cx = build_area.begin.x + 300
    cz = build_area.begin.z + 00
    base_y = -61

    small_roof_h = 16
    radius = 6
    height = 30

    try:
        # Pass the newly supported 'facing' argument here! Options: 'N', 'S', 'E', 'W'
        build_twin_tower_entrance(editor, cx, base_y, cz, small_roof_h, radius, height, facing="N")
        editor.flushBuffer()
        print("Fortified Twin Tower Entrance complete! Check it out in-game.")
    except Exception as e:
        print(f"Generation Failed: {e}")

if __name__ == "__main__":
    main()