from gdpc import Editor, Block
import random
import math
# ==========================================
# PRECOMPUTE ALL BLOCKS
# ==========================================
WALL = "cobbled_deepslate"
WALL_STONE = Block(WALL)
CRACKED_STONE = Block("cracked_stone_bricks")
MOSSY_STONE = Block("mossy_stone_bricks")
FLOOR_STONE = Block("polished_andesite")
WINDOW = Block("glass_pane")
WINDOW_WALL = Block("chiseled_sandstone")
CHAIN = Block("oxidized_copper_chain")
LANTERN = Block("lantern")
SMALL_TORCH = Block("torch")
TABLE = Block("dark_oak_planks")

CARPETS = [
    "white_carpet", "orange_carpet", "light_blue_carpet", "yellow_carpet", 
    "cyan_carpet","blue_carpet", "green_carpet", "red_carpet", "gray_carpet"
]

RNG_SEED = None

def circle_points(cx, cz, radius):
    pts = set()
    steps = max(16, int(2 * math.pi * radius * 2))
    for i in range(steps):
        a = 2 * math.pi * i / steps
        x = int(round(cx + radius * math.cos(a)))
        z = int(round(cz + radius * math.sin(a)))
        pts.add((x, z))
    return list(pts)

def build_circular_chandelier(editor, cx, cy, cz, radius=2):
    ring = circle_points(cx, cz, radius)
    for x, z in ring:
        editor.placeBlock((x, cy, z), CHAIN)
        editor.placeBlock((x, cy - 1, z), LANTERN)
    editor.placeBlock((cx, cy, cz), CHAIN)
    editor.placeBlock((cx, cy - 1, cz), SMALL_TORCH)

def build_antique_window(editor, oy, dw, dl_center, get_pos):
    """
    Builds the window using local coordinates (dw, dl).
    get_pos maps local coordinates to global Minecraft coordinates.
    """
    glass = WINDOW
    stone = WINDOW_WALL

    rows = 4
    section_height = 4
    vertical_gap = 1
    horizontal_gap = 1

    total_height = rows * section_height + (rows - 1) * vertical_gap

    # COLUMN WIDTHS (1 - 3 - 1)
    left_width = 1
    center_width = 3
    right_width = 1

    total_width = left_width + horizontal_gap + center_width + horizontal_gap + right_width # 7

    left_dl = dl_center - total_width // 2
    right_dl = left_dl + total_width - 1

    # Column starting positions
    left_col_dl = left_dl
    center_col_dl = left_col_dl + left_width + horizontal_gap
    right_col_dl = center_col_dl + center_width + horizontal_gap

    # BUILD GLASS COLUMNS
    for row in range(rows):
        y_start = oy + row * (section_height + vertical_gap)

        # LEFT 1x4
        for dy in range(section_height):
            editor.placeBlock(get_pos(dw, left_col_dl, y_start + dy), glass)

        # CENTER 3x4
        for ddl in range(center_width):
            for dy in range(section_height):
                editor.placeBlock(get_pos(dw, center_col_dl + ddl, y_start + dy), glass)

        # RIGHT 1x4
        for dy in range(section_height):
            editor.placeBlock(get_pos(dw, right_col_dl, y_start + dy), glass)

        # Horizontal stone separator
        if row < rows - 1:
            sep_y = y_start + section_height
            for dl in range(left_col_dl, right_col_dl + 1):
                editor.placeBlock(get_pos(dw, dl, sep_y), stone)

    # VERTICAL STONE MULLIONS
    for y in range(oy, oy + total_height):
        editor.placeBlock(get_pos(dw, left_col_dl + left_width, y), stone)
        editor.placeBlock(get_pos(dw, center_col_dl + center_width, y), stone)

    # FRAME
    frame_left = left_dl - 1
    frame_right = right_dl + 1
    arch_base_y = oy + total_height

    for y in range(oy - 1, arch_base_y + 1):
        editor.placeBlock(get_pos(dw, frame_left, y), stone)
        editor.placeBlock(get_pos(dw, frame_right, y), stone)

    for dl in range(frame_left, frame_right + 1):
        editor.placeBlock(get_pos(dw, dl, oy - 1), stone)

    # ARC BASE (STONE BEAM)
    for dl in range(left_dl, right_dl + 1):
        editor.placeBlock(get_pos(dw, dl, arch_base_y), stone)

    # SEMICIRCULAR ARCH
    radius = total_width // 2
    center = (left_dl + right_dl) // 2

    for ddl in range(-radius, radius + 1):
        dl_pos = center + ddl
        if left_dl <= dl_pos <= right_dl:
            arch_height = int(round(math.sqrt(radius**2 - ddl**2)))
            for dy in range(1, arch_height + 1):
                editor.placeBlock(get_pos(dw, dl_pos, arch_base_y + dy), glass)
            editor.placeBlock(get_pos(dw, dl_pos, arch_base_y + arch_height + 1), stone)

    # DOUBLE DEPTH FRAME (IN + OUT)
    outer_left = frame_left
    outer_right = frame_right
    bottom_y = oy - 1

    depth_layers = [dw - 1, dw + 1]

    for depth_dw in depth_layers:
        for y in range(bottom_y, arch_base_y + 1):
            editor.placeBlock(get_pos(depth_dw, outer_left, y), stone)
            editor.placeBlock(get_pos(depth_dw, outer_right, y), stone)

        for dl in range(outer_left, outer_right + 1):
            editor.placeBlock(get_pos(depth_dw, dl, bottom_y), stone)

        for dl in range(left_dl, right_dl + 1):
            editor.placeBlock(get_pos(depth_dw, dl, arch_base_y), stone)

        for ddl in range(-radius, radius + 1):
            dl_pos = center + ddl
            if left_dl <= dl_pos <= right_dl:
                arch_height = int(round(math.sqrt(radius**2 - ddl**2)))
                editor.placeBlock(get_pos(depth_dw, dl_pos, arch_base_y + arch_height + 1), stone)

        # Keystone
        editor.placeBlock(get_pos(depth_dw, center, arch_base_y + radius + 2), stone)

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

def build_dynamic_hogwarts_corridor(editor, cx, base_y, cz, 
                                    direction, is_great_hall, 
                                    width, length, height) -> None:  
      
    if direction == "n-s":
        ox, oy, oz = cx - (width // 2), base_y, cz - (length // 2)
    else:
        ox, oy, oz = cx - (length // 2), base_y, cz - (width // 2)
    carpet_color = random.choice(CARPETS)
    CARPET_BLOCK = Block(carpet_color)
    # 2. Coordinate Transformer and Directional Facings
    def get_pos(dw, dl, y):
        """Translates local width (dw) and length (dl) into global X/Z."""
        if direction == "n-s":
            return (ox + dw, y, oz + dl)
        else: # "e-w"
            return (ox + dl, y, oz + dw)

    # Determine Minecraft block facings based on corridor direction
    if direction == "n-s":
        face_left_up = "east"
        face_right_up = "west"
        torch_left = "east"
        torch_right = "west"
        seat_left = "east"
        seat_right = "west"
    else: # "e-w"
        face_left_up = "south"
        face_right_up = "north"
        torch_left = "south"
        torch_right = "north"
        seat_left = "south"
        seat_right = "north"

    TORCH_LEFT = Block(f"wall_torch[facing={torch_left}]")
    TORCH_RIGHT = Block(f"wall_torch[facing={torch_right}]")
    SEAT_LEFT = Block("dark_oak_stairs", {"facing": seat_left})
    SEAT_RIGHT = Block("dark_oak_stairs", {"facing": seat_right})
    STAIR_LEFT = Block("prismarine_brick_stairs", {"facing": face_left_up})
    STAIR_RIGHT = Block("prismarine_brick_stairs", {"facing": face_right_up})

    # =========================
    # CORE STRUCTURE (Floor & Walls)
    # =========================
    walk_margin = max(2, width // 5) 

    for dl in range(length):
        # FLOOR
        for dw in range(width):
            editor.placeBlock(get_pos(dw, dl, oy), FLOOR_STONE)
            # CARPET WALKWAY
            if walk_margin <= dw <= width - walk_margin - 1:
                editor.placeBlock(get_pos(dw, dl, oy + 1), CARPET_BLOCK)

        # LEFT WALL (dw = 0)
        for y in range(oy + 1, oy + height):
            editor.placeBlock(get_pos(0, dl, y), WALL_STONE)
            if random.randint(0, 11) == 0:
                editor.placeBlock(get_pos(0, dl, y), MOSSY_STONE)
        
        # RIGHT WALL (dw = width - 1)
        for y in range(oy + 1, oy + height):
            editor.placeBlock(get_pos(width - 1, dl, y), WALL_STONE)
            if random.randint(0, 11) == 0:
                editor.placeBlock(get_pos(width - 1, dl, y), CRACKED_STONE)

    # =========================
    # TRIANGULAR ROOF
    # =========================
    roof_base_y = oy + height
    for dl in range(length):
        for i in range(width // 2):
            left_dw = i
            right_dw = width - 1 - i
            y = roof_base_y + i

            editor.placeBlock(get_pos(left_dw, dl, y), STAIR_LEFT)
            editor.placeBlock(get_pos(right_dw, dl, y), STAIR_RIGHT)

        # Fill the center gap if the width is an odd number
        if width % 2 != 0:
            center_dw = width // 2
            peak_y = roof_base_y + center_dw
            
            # Using prismarine bricks to match the stairs seamlessly 
            editor.placeBlock(get_pos(center_dw, dl, peak_y), Block("prismarine_bricks"))

    # =========================
    # ANTIQUE ARCHED BEAMS
    # =========================
    # Determine the log axis based on corridor direction so the bark faces correctly
    beam_axis = "x" if direction == "n-s" else "z"
    
    BEAM = Block("stripped_dark_oak_log", {"axis": beam_axis})
    PILLAR = Block("stripped_dark_oak_log", {"axis": "y"})
    # Re-using the seat facings for the corbels so they face inwards!
    CORBEL_LEFT = Block("dark_oak_stairs", {"facing": seat_left, "half": "top"})
    CORBEL_RIGHT = Block("dark_oak_stairs", {"facing": seat_right, "half": "top"})
    TRACERY = Block("dark_oak_fence")
    
    arch_interval = 8
    arch_drop = 5
    base_y_arch = roof_base_y - arch_drop
    
    # Arch bounds (1 block inward from the walls)
    span_left = 1
    span_right = width - 2
    center_dw_float = (span_left + span_right) / 2.0
    
    # Peak of the arch just inside the roof
    arch_peak_y = roof_base_y + (width // 2) - 1
    
    # Parabola coefficient: a = (y - k) / (x - h)^2
    a_curve = (base_y_arch - arch_peak_y) / ((span_left - center_dw_float)**2)
    
    for dl_arch in range(arch_interval, length - arch_interval, arch_interval):
        # 1. Corbels (The supports holding the arch on the wall)
        editor.placeBlock(get_pos(span_left, dl_arch, base_y_arch - 1), CORBEL_LEFT)
        editor.placeBlock(get_pos(span_right, dl_arch, base_y_arch - 1), CORBEL_RIGHT)
        
        # 2. Vertical wall pillars (Extending from corbel to roof base)
        for y in range(base_y_arch, roof_base_y):
            editor.placeBlock(get_pos(span_left, dl_arch, y), PILLAR)
            editor.placeBlock(get_pos(span_right, dl_arch, y), PILLAR)
            
        # 3. Draw the Parabolic Arch
        prev_y = base_y_arch
        for dw in range(span_left, span_right + 1):
            y_float = a_curve * (dw - center_dw_float)**2 + arch_peak_y
            y_int = int(round(y_float))
            
            # Prevent arch from poking through the actual roof slopes
            local_roof_y = roof_base_y + min(dw, width - 1 - dw)
            y_int = min(y_int, local_roof_y - 1)
            
            # Fill vertical gaps so the curve is continuous, not diagonal points
            step = 1 if y_int > prev_y else -1
            if dw > span_left:
                # If stepping up, fill the previous column. If stepping down, fill current column.
                fill_dw = dw - 1 if step > 0 else dw
                for filler_y in range(prev_y + step, y_int, step):
                    editor.placeBlock(get_pos(fill_dw, dl_arch, filler_y), BEAM)
            
            # Place the main curve block
            editor.placeBlock(get_pos(dw, dl_arch, y_int), BEAM)
            
            # Thicken the beam UPWARDS to meet the ceiling (Truss style)
            for fill_ceil in range(y_int + 1, local_roof_y):
                editor.placeBlock(get_pos(dw, dl_arch, fill_ceil), BEAM)
                
            # Cool Pattern: Tracery (hanging fences under the arch)
            # We place them on alternating blocks, leaving the center clear
            if dw % 2 == 0 and dw != span_left and dw != span_right:
                editor.placeBlock(get_pos(dw, dl_arch, y_int - 1), TRACERY)
                
            prev_y = y_int
            
        # 4. Central King Post / Lantern Drop
        center_int = width // 2
        editor.placeBlock(get_pos(center_int, dl_arch, int(arch_peak_y) - 1), CHAIN)
        editor.placeBlock(get_pos(center_int, dl_arch, int(arch_peak_y) - 2), LANTERN)

    # =========================
    # WINDOWS & TORCHES
    # =========================
    window_spacing = 13 
    window_centers = []

    for dl_offset in range(10, length - 10, window_spacing):
        window_centers.append(dl_offset)
        base_y = oy + 3
        # Left wall window
        build_antique_window(editor, base_y, 0, dl_offset, get_pos)
        # Right wall window  
        build_antique_window(editor, base_y, width - 1, dl_offset, get_pos)

    # Torches between windows
    gap_centers = [(window_centers[i] + window_centers[i + 1]) // 2 for i in range(len(window_centers) - 1)]
    torch_y = oy + 9
    for dl_gap in gap_centers:
        editor.placeBlock(get_pos(1, dl_gap, torch_y), TORCH_LEFT)
        editor.placeBlock(get_pos(width - 2, dl_gap, torch_y), TORCH_RIGHT)

    # =========================
    # CHANDELIERS
    # =========================
    chain_top_y = roof_base_y + (width // 2) - 2
    center_dw = width // 2

    for dl in range(3, length - 3, 7):
        for dy in range(15):
            editor.placeBlock(get_pos(center_dw, dl, chain_top_y - dy), CHAIN)
        
        cx, _, cz = get_pos(center_dw, dl, chain_top_y - 15)
        build_circular_chandelier(editor, cx, chain_top_y - 15, cz)
    
    if is_great_hall:
        # =========================
        # GREAT HALL SEATING (Hogwarts Style)
        # =========================
        TABLE = Block("dark_oak_planks")
        table_y = oy + 1

        # 1. Calculate equally spaced lanes for the Four House Tables
        table_centers = [
            max(2, int(width * 0.15)),
            int(width * 0.38),
            int(width * 0.62),
            min(width - 3, int(width * 0.85))
        ]

        house_table_start = 6
        house_table_end = length - 12  # Leave room at the back for the High Table

        for dl in range(house_table_start, house_table_end):
            # Create a small walking gap halfway down the hall for easier player traversal
            if dl in [length // 2, (length // 2) + 1]:
                continue

            for t_dw in table_centers:
                editor.placeBlock(get_pos(t_dw, dl, table_y), TABLE)
                editor.placeBlock(get_pos(t_dw - 1, dl, table_y), SEAT_LEFT)
                editor.placeBlock(get_pos(t_dw + 1, dl, table_y), SEAT_RIGHT)

        # =========================
        # THE HIGH TABLE (Teachers' Table)
        # =========================
        high_table_dl = length - 7
        high_table_start_dw = 2
        high_table_end_dw = width - 3

        # The teachers sit on the far side of the table, looking back at the students.
        # We flip the orientation based on the generation axis.
        high_seat_facing = "north" if direction == "n-s" else "west"
        HIGH_SEAT = Block("dark_oak_stairs", {"facing": high_seat_facing})

        # Build a raised stone platform for the High Table
        PLATFORM = FLOOR_STONE 
        for dw in range(1, width - 1):
            for dl in range(high_table_dl - 2, length - 1):
                editor.placeBlock(get_pos(dw, dl, oy + 1), PLATFORM)

        # Place the High Table, chairs, and lectern on top of the new platform (oy + 2)
        for dw in range(high_table_start_dw, high_table_end_dw + 1):
            # Leave a gap in the center of the table for the Headmaster's podium
            if dw == width // 2:
                editor.placeBlock(get_pos(dw, high_table_dl - 1, oy + 2), Block("lectern", {"facing": high_seat_facing}))
                continue
                
            editor.placeBlock(get_pos(dw, high_table_dl, oy + 2), TABLE)
            editor.placeBlock(get_pos(dw, high_table_dl + 1, oy + 2), HIGH_SEAT)
        
        # =========================
        # FLOATING CANDLES
        # =========================
        # Scale candles based on volume to keep density consistent
        candle_volume = (width * height * length)
        candle_count_target = int(candle_volume * 0.005) 
        
        min_y = oy + 4
        max_y = oy + height - 15  
        
        for _ in range(candle_count_target):
            rand_dw = random.randint(2, width - 3)
            rand_dl = random.randint(5, length - 5)
            y = int(random.triangular(min_y, max_y, (min_y + max_y) // 2))
            
            gx, gy, gz = get_pos(rand_dw, rand_dl, y)
            candles = random.randint(1, 4)
            
            editor.placeBlock((gx, gy, gz), Block("candle", {"candles": str(candles), "lit": "true"}))

    # =========================
    # ENTRANCE STANDING SIGN
    # =========================

    sign_dw = (width // 2) + 4
    sign_x, sign_y, sign_z = get_pos(sign_dw, 2, oy + 1)
    
    # Reverted to dynamic rotation so it always faces the player entering the hall
    sign_rot = "8" if direction == "n-s" else "4"
    
    place_wizard_quote_standing_sign(
        editor, 
        sign_x, sign_y, sign_z, 
        rotation=sign_rot, 
        block_id="pale_oak_sign"
    )


def main():
    if RNG_SEED is not None:
        random.seed(RNG_SEED)

    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()
    editor.loadWorldSlice(cache=True)

    cx = build_area.begin.x + 60
    cz = build_area.begin.z + 60
    base_y = -61
    origin = (cx - 2, base_y, cz - 8)

    width, length, height = 30, 40, 100

    # Randomly pick orientation for testing
    chosen_direction = random.choice(["n-s", "e-w"])

    build_dynamic_hogwarts_corridor(editor, origin, chosen_direction, True, width, length, height)
    print("Corridor complete!")
if __name__ == "__main__":
    main()