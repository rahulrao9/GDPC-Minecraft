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
    """Fills a completely solid circular tower (No interiors/windows)."""
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
    """
    Places a standing sign on the floor with specific text.
    text_lines should be a list of exactly 4 strings.
    """
    # Escape single quotes just in case!
    escaped_lines = [line.replace("'", "\\'") for line in text_lines]
    
    line0 = f'{escaped_lines[0]}'
    line1 = f'{escaped_lines[1]}'
    line2 = f'{escaped_lines[2]}'
    line3 = f'{escaped_lines[3]}'
    
    nbt_data = f"{{front_text:{{has_glowing_text:1b, color:'yellow', messages:['{line0}', '{line1}', '{line2}', '{line3}']}}}}"
    sign_block = Block(block_id, {"rotation": str(rotation)}, data=nbt_data)
    
    editor.placeBlock((x, y, z), sign_block)

def place_wizard_quote_standing_sign(editor, x, y, z, rotation, block_id="pale_oak_sign"):
    """
    Places a standing sign on the floor with a random punny wizard quote.
    Uses 'rotation' (0-15) for fine-tuned standing angles.
    """
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
    
    # 1. Escape single quotes so they don't break the NBT array format!
    escaped_lines = [line.replace("'", "\\'") for line in chosen_quote]
    
    # 2. Format them directly as raw strings (removed the {"text":...} wrapper)
    line0 = f'{escaped_lines[0]}'
    line1 = f'{escaped_lines[1]}'
    line2 = f'{escaped_lines[2]}'
    line3 = f'{escaped_lines[3]}'
    
    # Yellow glowing text so it's super visible!
    nbt_data = f"{{front_text:{{has_glowing_text:1b, color:'yellow', messages:['{line0}', '{line1}', '{line2}', '{line3}']}}}}"
    
    # Apply the rotation state and NBT
    sign_block = Block(block_id, {"rotation": str(rotation)}, data=nbt_data)
    
    editor.placeBlock((x, y, z), sign_block)


# ==========================================
# 3. MAIN GENERATOR LOGIC
# ==========================================
def build_fully_featured_tower(editor, cx, base_y, cz, radius, height):
    """Builds a single 3D wizard tower with full interior and 4 corner turrets."""
    # Base floor & walls
    build_floor_disc(editor, cx, base_y, cz, radius, WALL_BLOCK)
    build_circular_wall(editor, cx, base_y + 1, cz, radius, height, WALL_BLOCK)

    # NEW: 4 Solid Thin Corner Towers
    small_r = 4
    small_wall_h = height
    small_roof_h = 16
    corner_offset = radius - 0  # Tuck them slightly into the main cylinder
    
    for dx in [-corner_offset, corner_offset]:
        for dz in [-corner_offset, corner_offset]:
            small_cx, small_cz = cx + dx, cz + dz
            # Solid body
            build_solid_cylinder(editor, small_cx, base_y, small_cz, small_r, small_wall_h, WALL_BLOCK)
            # Pointy roofs that touch exactly where the main roof starts
            build_cone_roof(editor, small_cx, base_y + small_wall_h, small_cz, small_r, small_roof_h)

    # Windows & interior torches (Only on the main tower)
    windows = sample_wall_window_slots(cx, cz, radius, height, base_y)
    build_wall_windows(editor, windows, cx, cz)
    
    # Stairs
    build_spiral_stairs(editor, cx, base_y, cz, height - 2, radius, windows)

    # Roof base, chandelier, and main cone roof
    roof_base_y = base_y + height
    build_floor_disc(editor, cx, roof_base_y, cz, radius + 1, WALL_BLOCK)
    build_chandelier(editor, cx, roof_base_y - 1, cz)
    build_cone_roof(editor, cx, roof_base_y, cz, radius, int(1.4 * height))


def build_twin_tower_entrance(editor, cx, base_y, cz):
    """Generates two fully detailed wizard towers with a grand curved connecting entrance."""
    radius = 7
    height = 30
    tower_spread = 40  # Widened to give the grand curved arch room
    
    left_cx = cx - (tower_spread // 2)
    right_cx = cx + (tower_spread // 2)

    print(f"Building Left Fortified Tower at X:{left_cx}...")
    build_fully_featured_tower(editor, left_cx, base_y, cz, radius, height)
    
    print(f"Building Right Fortified Tower at X:{right_cx}...")
    build_fully_featured_tower(editor, right_cx, base_y, cz, radius, height)

    # =====================================
    # BUILD THE GRAND PILLARED ARCHWAY
    # =====================================
    print("Constructing the Grand Pillared Archway (Illuminated!)...")
    
    arch_center = cx
    portal_radius = 6   # Width of the passage
    portal_height = 8   # Straight pillar height before the curve starts
    curve_height = 10   # The height of the curving arch/roof itself
    gable_radius = portal_radius + 2 
    
    # Protrude even further!
    z_back = cz + 7
    z_front = cz - 24  

    # 1. Floor, Carpet, and Embedded Lighting
    fill_cuboid(editor, arch_center - portal_radius, base_y, z_front, 
                        arch_center + portal_radius, base_y, z_back, FLOOR_BLOCK)
    
    # Red carpet down the middle (NOW 5 BLOCKS WIDE)
    fill_cuboid(editor, arch_center - 2, base_y + 1, z_front, 
                        arch_center + 2, base_y + 1, z_back, Block("red_carpet"))
    
    # Embedded floor lights pushed out to the new edges (offset changed from 2 to 3)
    for z_light in range(z_front + 2, z_back, 3):
        editor.placeBlock((arch_center - 3, base_y, z_light), Block("glowstone"))
        editor.placeBlock((arch_center + 3, base_y, z_light), Block("glowstone"))

    # 2. Solid Side Walls (ONLY between the towers, cz - 7 to cz + 7)
    wall_start_x = left_cx + radius + 1
    wall_end_x = right_cx - radius - 1
    fill_cuboid(editor, wall_start_x, base_y, cz - 7, arch_center - portal_radius - 1, base_y + portal_height, cz + 7, WALL_BLOCK)
    fill_cuboid(editor, arch_center + portal_radius + 1, base_y, cz - 7, wall_end_x, base_y + portal_height, cz + 7, WALL_BLOCK)

    # 3. 2x2 Pillars, Parabolic Wooden Trusses, and Chandeliers
    BEAM = Block("stripped_dark_oak_log", {"axis": "x"})
    TRACERY = Block("dark_oak_fence")
    CHAIN = Block("oxidized_copper_chain")
    LANTERN = Block("lantern")
    SMALL_TORCH = Block("torch")

    # Arch math pre-calculations
    span_left = -portal_radius + 2
    span_right = portal_radius - 2
    center_float = 0.0
    arch_peak_y = base_y + portal_height + curve_height - 2
    base_y_arch = base_y + portal_height
    a_curve = (base_y_arch - arch_peak_y) / ((span_left - center_float)**2)

    # Step by 6 blocks
    for z_rib in range(z_front, z_back + 1, 6):
        
        # Pillar Core Coordinates
        L_X1 = arch_center - portal_radius - 1
        L_X2 = arch_center - portal_radius
        R_X1 = arch_center + portal_radius
        R_X2 = arch_center + portal_radius + 1
        Z1 = z_rib
        Z2 = z_rib + 1
        
        # A) Bases (4x2x4 footprint)
        fill_cuboid(editor, L_X1 - 1, base_y + 1, Z1 - 1, L_X2 + 1, base_y + 2, Z2 + 1, CHISELED_STONE)
        fill_cuboid(editor, R_X1 - 1, base_y + 1, Z1 - 1, R_X2 + 1, base_y + 2, Z2 + 1, CHISELED_STONE)
        
        # NEW: Lanterns sitting on the ledges of the stone pedestals
        editor.placeBlock((L_X1 - 1, base_y + 3, Z1 - 1), LANTERN) # Left Outer
        editor.placeBlock((L_X2 + 1, base_y + 3, Z1 - 1), LANTERN) # Left Inner
        editor.placeBlock((R_X1 - 1, base_y + 3, Z1 - 1), LANTERN) # Right Inner
        editor.placeBlock((R_X2 + 1, base_y + 3, Z1 - 1), LANTERN) # Right Outer

        # B) 2x2 Copper Pillars
        fill_cuboid(editor, L_X1, base_y + 3, Z1, L_X2, base_y + portal_height - 1, Z2, Block("waxed_weathered_cut_copper"))
        fill_cuboid(editor, R_X1, base_y + 3, Z1, R_X2, base_y + portal_height - 1, Z2, Block("waxed_weathered_copper"))
        
        # C) 4x4 Top Capital plates holding up the roof
        fill_cuboid(editor, L_X1 - 1, base_y + portal_height, Z1 - 1, L_X2 + 1, base_y + portal_height, Z2 + 1, Block("waxed_weathered_copper"))
        fill_cuboid(editor, R_X1 - 1, base_y + portal_height, Z1 - 1, R_X2 + 1, base_y + portal_height, Z2 + 1, Block("waxed_weathered_copper"))

        # Torches on the INNER faces of the pillars
        editor.placeBlock((L_X2 + 1, base_y + 5, Z1), Block("wall_torch", {"facing": "east"}))
        editor.placeBlock((R_X1 - 1, base_y + 5, Z1), Block("wall_torch", {"facing": "west"}))
        
        # NEW: Torches on the OUTER faces of the pillars
        editor.placeBlock((L_X1 - 1, base_y + 5, Z1), Block("wall_torch", {"facing": "west"}))
        editor.placeBlock((R_X2 + 1, base_y + 5, Z1), Block("wall_torch", {"facing": "east"}))

        # D) Parabolic Wooden Trusses with Tracery
        for z_arc in [Z1, Z2]:
            prev_y = base_y_arch
            for x in range(span_left, span_right + 1):
                y_float = a_curve * (x - center_float)**2 + arch_peak_y
                y_int = int(round(y_float))

                local_roof_y = base_y + portal_height + int(curve_height * math.cos((abs(x) / gable_radius) * (math.pi / 2)))
                y_int = min(y_int, local_roof_y - 1)

                step = 1 if y_int > prev_y else -1
                if x > span_left:
                    fill_x = x - 1 if step > 0 else x
                    for filler_y in range(prev_y + step, y_int, step):
                        editor.placeBlock((arch_center + fill_x, filler_y, z_arc), BEAM)

                editor.placeBlock((arch_center + x, y_int, z_arc), BEAM)

                for fill_ceil in range(y_int + 1, local_roof_y):
                    editor.placeBlock((arch_center + x, fill_ceil, z_arc), BEAM)

                if x % 2 == 0 and x != span_left and x != span_right:
                    editor.placeBlock((arch_center + x, y_int - 1, z_arc), TRACERY)

                prev_y = y_int

        # E) Circular Chandeliers
        z_chand = Z1 + 3  
        if z_chand < z_back:
            chain_start_y = base_y + portal_height + curve_height - 1
            chand_y = chain_start_y - 7
            
            for dy in range(chain_start_y, chand_y - 1, -1):
                editor.placeBlock((arch_center, dy, z_chand), CHAIN)
            
            ring_radius = 2.0
            steps = 12
            for i in range(steps):
                angle = 2 * math.pi * i / steps
                cx_ring = int(round(arch_center + ring_radius * math.cos(angle)))
                cz_ring = int(round(z_chand + ring_radius * math.sin(angle)))
                
                editor.placeBlock((cx_ring, chand_y, cz_ring), CHAIN)
                editor.placeBlock((cx_ring, chand_y - 1, cz_ring), LANTERN)
                
            editor.placeBlock((arch_center, chand_y - 1, z_chand), SMALL_TORCH)

    # 4. Build the continuous curved hollow roof shell
    roof_base_y = base_y + portal_height
    
    for z in range(z_front, z_back + 1):
        prev_y = roof_base_y
        
        for x in range(gable_radius, -1, -1):
            dy = int(curve_height * math.cos((x / gable_radius) * (math.pi / 2)))
            y = roof_base_y + dy
            
            for fill_y in range(min(y, prev_y), max(y, prev_y) + 1):
                if fill_y < roof_base_y: continue 
                
                editor.placeBlock((arch_center - x, fill_y, z), Block("waxed_exposed_cut_copper_stairs", {"facing": "east"}))
                if x != 0:
                    editor.placeBlock((arch_center + x, fill_y, z), Block("waxed_exposed_cut_copper_stairs", {"facing": "west"}))
                
                if x > 0:
                    editor.placeBlock((arch_center - x + 1, fill_y, z), WALL_BLOCK)
                    editor.placeBlock((arch_center + x - 1, fill_y, z), WALL_BLOCK)
                else:
                    editor.placeBlock((arch_center, fill_y, z), WALL_BLOCK)
            
            prev_y = y

        # Top Capstone along the roof ridge
        editor.placeBlock((arch_center, prev_y + 1, z), CHISELED_STONE)
        
        # NEW: Roof Exterior Ridge Lanterns (every 3 blocks)
        if z % 3 == 0:
            editor.placeBlock((arch_center, prev_y + 2, z), LANTERN)

    # NEW: Front Entrance Peak Hanging Lantern
    editor.placeBlock((arch_center, base_y + portal_height + curve_height, z_front - 1), CHAIN)
    editor.placeBlock((arch_center, base_y + portal_height + curve_height - 1, z_front - 1), LANTERN)

    # =====================================
    # 5. PLACE THE ENTRANCE SIGNS
    # =====================================
    # Sign rotation "8" faces North (pointing outward towards the arriving player)
    
    # A) "Welcome to Hogwarts!" at the front entrance, on the right side
    # arch_center + 3 places it just off the edge of a 5-wide carpet!
    welcome_x = arch_center + 3 
    welcome_z = z_front + 1
    welcome_y = base_y + 1
    
    welcome_text = ["", "Welcome to", "Hogwarts!", ""]
    place_custom_standing_sign(editor, welcome_x, welcome_y, welcome_z, rotation=8, text_lines=welcome_text)

    # B) Random wizard quote at the end of the passage
    # cz - 8 places it right before the actual tower walls begin
    quote_x = arch_center - 4
    quote_z = cz - 5  
    quote_y = base_y + 1
    
    place_wizard_quote_standing_sign(editor, quote_x, quote_y, quote_z, rotation=8)

def main():
    if RNG_SEED is not None:
        random.seed(RNG_SEED)

    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()

    cx = build_area.begin.x + 200
    cz = build_area.begin.z + 00
    base_y = -61

    try:
        build_twin_tower_entrance(editor, cx, base_y, cz)
        editor.flushBuffer()
        print("Fortified Twin Tower Entrance complete! Check it out in-game.")
    except Exception as e:
        print(f"Generation Failed: {e}")

if __name__ == "__main__":
    main()