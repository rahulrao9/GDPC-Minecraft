from gdpc import Editor, Block
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
import math
from collections import Counter
import random

######### STORAGE #########
MAX_WATER_FRACTION = 0.10 # percentage of water allowed to fill to make the best flat patch
VEGETATION_KEYWORDS = ("leaves","log")
FLOOR_BLOCK = Block("spruce_planks")
STAIR_BLOCK = Block("spruce_slab")
TORCH_BLOCK = Block("wall_torch")    
AMETHYST_CLUSTER = Block("amethyst_cluster")
SEA_LANTERN = Block("sea_lantern") 
CHISELED_STONE = Block("chiseled_stone_bricks")
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
HOUSES = {
    "Gryffindor": {"color": "red", "wood": "mangrove", "angle_center": math.pi / 4},        # Quadrant 1
    "Ravenclaw":  {"color": "light_blue", "wood": "birch", "angle_center": 3 * math.pi / 4}, # Quadrant 2
    "Slytherin":  {"color": "green", "wood": "dark_oak", "angle_center": 5 * math.pi / 4},   # Quadrant 3
    "Hufflepuff": {"color": "yellow", "wood": "oak", "angle_center": 7 * math.pi / 4}        # Quadrant 4
}
TELESCOPE_BASE = Block("cut_copper")
TELESCOPE_TUBE = Block("copper_block")
TELESCOPE_LENS = Block("glass")
LANTERN_BLOCK = Block("soul_torch")

PLOT_SIZE = 100
RNG_SEED = None 

######### init #########

# ==========================================
# UTILITY FUNCTIONS
# ==========================================


# 1. Plot

def _is_vegetation(block_id):
    return any(k in block_id for k in VEGETATION_KEYWORDS)

def _compute_surface_maps(height_map, world_slice):
    xs, zs = height_map.shape
    water_map = np.zeros((xs, zs), dtype=np.uint8)
    vegetation_map = np.zeros((xs, zs), dtype=np.uint8)

    for x in range(xs):
        for z in range(zs):
            y = height_map[x, z] - 1
            block_id = world_slice.getBlock((x, y, z)).id

            if block_id.endswith("water"):
                water_map[x, z] = 1
            elif _is_vegetation(block_id):
                vegetation_map[x, z] = 1

    return water_map, vegetation_map

def _patch_cost(patch_height, patch_water, patch_veg, a, b, c):
    h_variance = np.var(patch_height)  # how flat the patch is
    water_count = np.sum(patch_water)
    veg_count = np.sum(patch_veg)

    return (
        a * h_variance +
        b * water_count +
        c * veg_count
    ), h_variance, water_count, veg_count


# 2.Entrance

def circle_points_1(cx, cz, radius):
    points = set()
    steps = max(32, int(2 * math.pi * radius * 2))
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        x = int(round(cx + radius * math.cos(angle)))
        z = int(round(cz + radius * math.sin(angle)))
        points.add((x, z))
    return list(points)

def build_circular_wall_1(editor, cx, y_start, cz, radius, height, block):
    wall_ring = circle_points_1(cx, cz, radius)
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

def build_cone_roof_1(editor, cx, base_y, cz, base_radius, height, roof_block, has_snow=False):
    for i in range(height):
        t = i / (height - 1) if height > 1 else 1.0
        radius_f = base_radius * (1.0 - t * t)
        r = max(1, int(round(radius_f)))
        y = base_y + i
        for (x, z) in circle_points_1(cx, cz, r):
            editor.placeBlock((x, y, z), roof_block)
            if has_snow:
                editor.placeBlock((x, y + 1, z), Block("snow"))
                
    # Top spire peaks
    editor.placeBlock((cx, base_y + height, cz), roof_block)
    editor.placeBlock((cx, base_y + height + 1, cz), roof_block)
    if has_snow:
        editor.placeBlock((cx, base_y + height + 2, cz), Block("snow"))

# 2.1 TOWER INTERIOR FEATURES

def sample_wall_window_slots(cx, cz, radius, wall_height, base_y):
    total_windows = max(1, wall_height // 2)
    ring = circle_points_1(cx, cz, radius)
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
                editor.placeBlock((curr_x, wy + vertical, curr_z), WINDOW)

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

def build_chandelier_1(editor, cx, ceiling_y, cz):
    anchor_offsets = [(-3,0), (-2,1), (-2,-1), (0,3), (0,-3), (2,1), (2,-1), (3,0)]
    for dx, dz in anchor_offsets:
        for drop in range(5): 
            editor.placeBlock((cx + dx, ceiling_y - drop, cz + dz), CHAIN)
    central_y = ceiling_y - 4
    for (x, z) in circle_points_1(cx, cz, 2.5):
        editor.placeBlock((x, central_y, z), AMETHYST_CLUSTER)
        if random.random() < 0.6: 
            editor.placeBlock((x, central_y - 1, z), AMETHYST_CLUSTER)
    mid_y = ceiling_y - 6
    for r in [1.5, 3.0]:
        q = 0
        for (x, z) in circle_points_1(cx, cz, r):
            if q % 2 == 0:
                editor.placeBlock((x, mid_y, z), CHAIN)
                editor.placeBlock((x, mid_y - 1, z), LANTERN)
            q += 1
    for y in range(ceiling_y - 1, ceiling_y - 9, -1):
        if y % 2 == 0: editor.placeBlock((cx, y, cz), CHAIN)
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


# 3. Corridor

def circle_points_2(cx, cz, radius):
    pts = set()
    steps = max(16, int(2 * math.pi * radius * 2))
    for i in range(steps):
        a = 2 * math.pi * i / steps
        x = int(round(cx + radius * math.cos(a)))
        z = int(round(cz + radius * math.sin(a)))
        pts.add((x, z))
    return list(pts)

def build_circular_chandelier(editor, cx, cy, cz, radius=2):
    ring = circle_points_2(cx, cz, radius)
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


# 4. Common Room

def fill_cuboid(editor, x1, y1, z1, x2, y2, z2, block):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for z in range(min(z1, z2), max(z1, z2) + 1):
                editor.placeBlock((x, y, z), block)

def circle_points_3(cx, cz, radius):
    points = set()
    steps = max(32, int(2 * math.pi * radius * 2))
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        x = int(round(cx + radius * math.cos(angle)))
        z = int(round(cz + radius * math.sin(angle)))
        points.add((x, z))
    return list(points)

def get_quadrant_house(x, z, cx, cz):
    if x >= cx and z >= cz: return "Gryffindor"
    if x < cx and z >= cz:  return "Ravenclaw"
    if x < cx and z < cz:   return "Slytherin"
    return "Hufflepuff"

def place_wall_sign(editor, x, y, z, facing, text):
    nbt_data = f"{{front_text:{{has_glowing_text:1b, color:'white', messages:['', '{text}', '', '']}}}}"
    editor.placeBlock((x, y, z), Block("dark_oak_wall_sign", {"facing": facing}, data=nbt_data))

def build_quadrant_chandelier(editor, cx, ceiling_y, cz, radius=2, drop_length=6):
    """Updated to include drop_length for tall ceilings!"""
    for drop in range(drop_length):
        editor.placeBlock((cx, ceiling_y - drop, cz), CHAIN)
    
    chand_y = ceiling_y - drop_length
    ring = circle_points_3(cx, cz, radius)
    for x, z in ring:
        editor.placeBlock((x, chand_y, z), CHAIN)
        editor.placeBlock((x, chand_y - 1, z), LANTERN)
    
    editor.placeBlock((cx, chand_y, cz), Block("dark_oak_fence"))
    editor.placeBlock((cx, chand_y - 1, cz), SMALL_TORCH)


# 5. Tower

def build_circular_wall_2(editor, cx, y_start, cz, radius, height, block):
    wall_ring = circle_points_1(cx, cz, radius)
    for y in range(y_start, y_start + height):
        for (x, z) in wall_ring:
            editor.placeBlock((x, y, z), block)

def build_cone_roof_2(editor, cx, base_y, cz, base_radius, height, roof_block, has_snow):
    for i in range(height):
        t = i / (height - 1) if height > 1 else 1.0
        radius_f = base_radius * (1.0 - t * t)
        r = max(1, int(round(radius_f)))
        y = base_y + i
        
        # Build the outer ring of the roof
        for (x, z) in circle_points_1(cx, cz, r):
            editor.placeBlock((x, y, z), roof_block)
            
            # Add a layer of snow on top of the roof block
            if has_snow:
                editor.placeBlock((x, y + 1, z), Block("snow"))
            
        # Add torches to the inside of the roof every 5 blocks vertically
        if i > 0 and i % 5 == 0 and r > 3:
            # East Wall (Torch faces West)
            editor.placeBlock((cx + r - 1, y, cz), Block("wall_torch", {"facing": "west"}))
            # West Wall (Torch faces East)
            editor.placeBlock((cx - r + 1, y, cz), Block("wall_torch", {"facing": "east"}))
            # South Wall (Torch faces North)
            editor.placeBlock((cx, y, cz + r - 1), Block("wall_torch", {"facing": "north"}))
            # North Wall (Torch faces South)
            editor.placeBlock((cx, y, cz - r + 1), Block("wall_torch", {"facing": "south"}))

    tip_y = base_y + height
    editor.placeBlock((cx, tip_y, cz), roof_block)
    editor.placeBlock((cx, tip_y + 1, cz), roof_block)
    
    # Snow on the very tip!
    if has_snow:
        editor.placeBlock((cx, tip_y + 2, cz), Block("snow"))

def build_entrance(editor, cx, base_y, cz, radius, facing):
    directions = {
        "north": (0, -1),
        "south": (0, 1),
        "east":  (1, 0),
        "west":  (-1, 0),
    }

    fx, fz = directions[facing]
    px, pz = -fz, fx

    # Wall center
    wall_x = cx + fx * radius
    wall_z = cz + fz * radius

    # ---- 4x4 Opening ----
    for side in range(-1, 3):          # width = 4
        for height in range(4):        # height = 4
            x = wall_x + px * side
            z = wall_z + pz * side
            y = base_y + 1 + height

            editor.placeBlock((x, y, z), Block("air"))

    # ---- Banner on right side ----
    banner_colors = [
        "white","orange","magenta","light_blue","yellow",
        "lime","pink","gray","light_gray","cyan",
        "purple","blue","brown","green","red","black"
    ]

    banner_color = random.choice(banner_colors)

    banner_block = Block(
        f"{banner_color}_banner"
    )
    right_side = 2
    x = wall_x + px * right_side
    z = wall_z + pz * right_side
    y = base_y + 1
    editor.placeBlock((x, y, z), banner_block)

def build_spiral_stairs_with_interior_features(
    editor,
    cx,
    base_y,
    cz,
    stairs_height,
    wall_radius,
    wall_window_positions,
):
    windows_by_y = {}
    for wx, wz, wy in wall_window_positions:
        windows_by_y.setdefault(wy, []).append((wx, wz))

    # Increase slices to ensure no diagonal gaps at larger radii
    slices_per_circle = int(2 * math.pi * wall_radius * 1.5)
    total_steps = stairs_height * 3 + 1

    last_center_x = None
    last_center_y = None
    last_center_z = None
    last_angle = None
    
    for step in range(total_steps):
        angle = (2 * math.pi * step) / slices_per_circle
        y = base_y + 1 + (step // 3)

        # Use spruce only for final slice
        if step == total_steps - 1:
            stair_block = Block("spruce_stairs")
        else:
            stair_block = STAIR_BLOCK

        for r_offset in range(1, 4):
            current_r = wall_radius - r_offset
            x = int(round(cx + current_r * math.cos(angle)))
            z = int(round(cz + current_r * math.sin(angle)))

            editor.placeBlock((x, y, z), stair_block)
        
        if step == total_steps - 1:
            last_angle = angle
            last_center_y = y

            # middle of 3-wide (r_offset = 2)
            current_r = wall_radius - 2
            last_center_x = int(round(cx + current_r * math.cos(angle)))
            last_center_z = int(round(cz + current_r * math.sin(angle)))

        if y in windows_by_y:
            for wx, wz in windows_by_y[y]:
                place_interior_torches_for_window(editor, cx, cz, wx, wz, y)

    if last_center_x is not None:

        # Forward direction of spiral
        fx = round(math.cos(last_angle))
        fz = round(math.sin(last_angle))

        # Perpendicular direction (for 3-wide)
        px = -fz
        pz = fx

        # Determine correct stair facing
        if fx == 1:
            facing = "east"
        elif fx == -1:
            facing = "west"
        elif fz == 1:
            facing = "south"
        else:
            facing = "north"

        stair_block = Block("stone_brick_stairs", {"facing": facing})

        # Row 1 (now LOWER than before)
        for side in range(-1, 2):
            x = last_center_x + px * side + fx * 1
            z = last_center_z + pz * side + fz * 1
            editor.placeBlock((x, last_center_y, z), stair_block)

        # Row 2 (also shifted down)
        for side in range(-1, 2):
            x = last_center_x + px * side + fx * 2
            z = last_center_z + pz * side + fz * 2
            editor.placeBlock((x, last_center_y - 1, z), stair_block)

def get_stair_top_position(cx, cz, wall_radius, stairs_height):
    slices_per_circle = int(2 * math.pi * wall_radius * 1.5)
    total_steps = stairs_height * 3
    last_step = total_steps - 1
    angle = (2 * math.pi * last_step) / slices_per_circle
    stair_r = wall_radius - 1  # Outer part of 3-wide stairs
    sx = int(round(cx + stair_r * math.cos(angle)))
    sz = int(round(cz + stair_r * math.sin(angle)))
    top_y = 1 + (last_step // 3)  # Relative to base_y
    return sx, top_y, sz

def build_chandelier_2(editor, cx, ceiling_y, cz):
    anchor_offsets = [(-3,0), (-2,1), (-2,-1), (0,3), (0,-3), (2,1), (2,-1), (3,0)]
    for dx, dz in anchor_offsets:
        for drop in range(5):  # Drop 3 blocks from ceiling
            editor.placeBlock((cx + dx, ceiling_y - drop, cz + dz), CHAIN)
    central_y = ceiling_y - 4
    tier1_points = circle_points_1(cx, cz, 2.5)
    for (x, z) in tier1_points:
        editor.placeBlock((x, central_y, z), AMETHYST_CLUSTER)
        if random.random() < 0.6:  # Some get clusters
            editor.placeBlock((x, central_y - 1, z), AMETHYST_CLUSTER)
    
    # Tier 2: Mid-level chains + lanterns (y-6 level) 
    mid_y = ceiling_y - 6
    for r in [1.5, 3.0]:
        points = circle_points_1(cx, cz, r)
        q = 0
        for (x, z) in points:
            if q % 2 == 0:
                editor.placeBlock((x, mid_y, z), CHAIN)
                editor.placeBlock((x, mid_y - 1, z), LANTERN_BLOCK)
            else:
                editor.placeBlock((x, mid_y+1, z), CHAIN)
                editor.placeBlock((x, mid_y, z), LANTERN_BLOCK)
            q+=1

    bottom_y = ceiling_y - 8
    drip_offsets = [(-1,-1), (-1,1), (1,-1), (1,1)]
    for dx, dz in drip_offsets:
        for drop in range(3):
            editor.placeBlock((cx + dx, bottom_y - drop, cz + dz), CHAIN)
            if drop == 2:
                editor.placeBlock((cx + dx, bottom_y - drop - 1, cz + dz), SEA_LANTERN)

    for y in range(ceiling_y - 1, bottom_y - 1, -1):
        if y % 2 == 0:  
            editor.placeBlock((cx, y, cz), CHAIN)

def make_west_cone_base_opening(editor, cx, roof_base_y, cz, radius):
    for dx in range(0, 4): 
        for dy in range(1, 4):
            for dz in range(-1, 2):
                editor.placeBlock(
                    (cx - radius + dx,
                    roof_base_y + dy,
                    cz + dz),
                    Block("air")
                )

def build_observatory_telescope(editor, cx, roof_base_y, cz, west_opening_x):
    telescope_base_y = roof_base_y - 2
    tube_length = 3
    
    # Main tripod base (under cone floor)
    base_points = circle_points_1(cx, cz, 1.2)
    for (x, z) in base_points:
        editor.placeBlock((x, telescope_base_y, z), TELESCOPE_BASE)
    
    # Main tube - angled toward west opening
    for i in range(tube_length):
        progress = i / (tube_length - 1) if tube_length > 1 else 0
        tube_y = telescope_base_y + 1 + i
        # Tilt toward west: move X negative, slight upward angle
        tilt_x = cx - progress * 1.5  # Reach toward west opening
        tilt_z = cz + progress * 0.3   # Slight Z offset for realism
        tube_r = 0.6
        
        tube_points = circle_points_1(int(tilt_x), int(tilt_z), tube_r)
        for (x, z) in tube_points:
            editor.placeBlock((x, tube_y, z), TELESCOPE_TUBE)
    
    # Lens pointing west
    lens_x = cx - 2  # Pointed toward west opening
    lens_z = cz
    editor.placeBlock((lens_x, telescope_base_y + tube_length, lens_z), TELESCOPE_LENS)
    
    # Side detail: brass fittings
    editor.placeBlock((cx - 1, telescope_base_y + 1, cz), TELESCOPE_TUBE)

def build_tower_library(editor,cx,base_y,cz,tower_height,
                        wall_radius,entrance_facing="south",stair_clear_radius=3):

    directions = {
        "north": (0, -1),
        "south": (0, 1),
        "east":  (1, 0),
        "west":  (-1, 0),
    }

    fx, fz = directions[entrance_facing]
    px, pz = -fz, fx
    for depth in range(3):
        for side in range(-1, 3):
            for height in range(4):
                x = cx + fx * (wall_radius - depth) + px * side
                z = cz + fz * (wall_radius - depth) + pz * side
                y = base_y + 1 + height
                editor.placeBlock((x, y, z), Block("air"))
    for y in range(base_y + 1, base_y + tower_height - 1):

        for angle_step in range(int(2 * math.pi * wall_radius * 1.2)):
            angle = (2 * math.pi * angle_step) / (2 * math.pi * wall_radius * 1.2)

            if random.random() < 0.30:

                r = random.randint(wall_radius - 2, wall_radius - 1)

                x = int(round(cx + r * math.cos(angle)))
                z = int(round(cz + r * math.sin(angle)))

                # Avoid stair core
                if (x - cx) ** 2 + (z - cz) ** 2 < stair_clear_radius ** 2:
                    continue

                stack_height = random.randint(3, 6)

                for h in range(stack_height):
                    block_y = y + h
                    if block_y >= base_y + tower_height - 1:
                        break

                    block_type = (
                        "chiseled_bookshelf"
                        if random.random() < 0.4
                        else "bookshelf"
                    )

                    editor.placeBlock((x, block_y, z), Block(block_type))

    # ----- 2. Floor carpet under tables -----
    carpet_radius = 3
    for dx in range(-carpet_radius, carpet_radius + 1):
        for dz in range(-carpet_radius, carpet_radius + 1):
            editor.placeBlock((cx + dx, base_y, cz + dz), Block("red_carpet"))

    # ----- 3. Place tables and chairs on carpet -----
    table_rows = 2
    tables_per_row = 4  # fit nicely
    row_spacing = 2     # space between rows
    table_y = base_y + 1   # same level as carpet

    # Carpet area dimensions
    carpet_radius_x = 4
    carpet_radius_z = 3

    for row in range(table_rows):
        row_z = cz - row_spacing if row == 0 else cz + row_spacing
        for t in range(-tables_per_row//2, tables_per_row//2):
            t_x = cx + t  # no space between tables

            # Table block
            editor.placeBlock((t_x, table_y, row_z), Block("enchanting_table"))

            # Chairs (stairs) facing table on both sides
            # Front chair
            front_chair_z = row_z - 1
            editor.placeBlock((t_x, table_y, front_chair_z), Block("dark_oak_stairs", {"facing": "north"}))
            # Back chair
            back_chair_z = row_z + 1
            editor.placeBlock((t_x, table_y, back_chair_z), Block("dark_oak_stairs", {"facing": "south"}))

            # Random lantern on table
            if random.random() < 0.6:
                editor.placeBlock((t_x, table_y + 3, row_z), Block("soul_lantern"))


# 6. Garden

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

# 7. Generator

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

# 7.1  TERRAIN ADAPTATION BUILDERS
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
#  Components
# ==========================================

# 1. Finding Best Location to build our Hogwarts Castle

""" 
 Lets build an algo to find the best location. We need the max patch of flat landon the height map. 
 Technically the heightmap consist of variations in y as we move accross xz plane. For an optimal patch
 we search least variations in y.

 Total Cost =
    a * height_variance
  + b * water_cells
  + c * vegetation_cells
  + d * earthwork_cost

"""

def plot_height_map(heights):
    fig = plt.figure(figsize=(12, 8))

    heights = np.rot90(heights) 
    smoothed_heights = gaussian_filter(heights, sigma=2)

    # Subplot 1: 2D Top-Down Heatmap
    ax1 = fig.add_subplot(121)
    im = ax1.imshow(heights, cmap='terrain', origin='lower')
    ax1.set_title("2D Topographic View")
    fig.colorbar(im, ax=ax1, label='Y Height', shrink=0.6)

    # Subplot 2: 3D Surface Plot
    ax2 = fig.add_subplot(122, projection='3d')
    x = np.arange(heights.shape[1])
    z = np.arange(heights.shape[0])
    X, Z = np.meshgrid(x, z)

    # Smooth plot
    surf = ax2.plot_surface(X, Z, smoothed_heights, cmap='terrain', 
                            edgecolor='none', antialiased=True)

    ax2.set_title("3D Terrain Reconstruction")
    ax2.set_zlabel("Minecraft Y")
    ax2.view_init(elev=35, azim=45)

    plt.tight_layout()
    plt.show()

def find_best_location(height_map, patch_size, world_slice):

    # weights for the cost function
    a = 1.0   # variance weight (flatness)
    b = 4.0   # water penalty
    c = 0.2   # vegetation penalty

    best_pos = None
    best_cost = float("inf")

    width, depth = height_map.shape
    water_map, vegetation_map = _compute_surface_maps(height_map, world_slice)
    # First pass: only consider patches with water_count == 0
    for x in range(width - patch_size):
        for z in range(depth - patch_size):

            patch_height = height_map[x:x+patch_size, z:z+patch_size]
            patch_water  = water_map[x:x+patch_size, z:z+patch_size]
            patch_veg    = vegetation_map[x:x+patch_size, z:z+patch_size]

            cost, h_var, water_count, veg_count = _patch_cost(
                patch_height, patch_water, patch_veg, a, b, c
            )

            if water_count != 0:
                continue  # must be completely dry in the ideal phase

            if cost < best_cost:
                best_cost = cost
                best_pos = (x, z)

    if best_pos is not None:
        return best_pos, True  # ideal (0 water) patch found

    # Fallback: allow water, still use the same cost function
    best_pos = None
    best_cost = float("inf")

    for x in range(width - patch_size):
        for z in range(depth - patch_size):

            patch_height = height_map[x:x+patch_size, z:z+patch_size]
            patch_water  = water_map[x:x+patch_size, z:z+patch_size]
            patch_veg    = vegetation_map[x:x+patch_size, z:z+patch_size]

            cost, h_var, water_count, veg_count = _patch_cost(
                patch_height, patch_water, patch_veg, a, b, c
            )

            if cost < best_cost:
                best_cost = cost
                best_pos = (x, z)

    return best_pos, False

# 2. Entrance

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
    build_circular_wall_1(editor, cx, base_y + 1, cz, radius, height, wall_block)

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
            build_cone_roof_1(editor, small_cx, base_y + small_wall_h, small_cz, small_r, small_roof_h, roof_block, has_snow)
    windows = sample_wall_window_slots(cx, cz, radius, height, base_y)
    build_wall_windows(editor, windows, cx, cz)
    build_spiral_stairs(editor, cx, base_y, cz, height - 2, radius, windows)

    roof_base_y = base_y + height
    build_floor_disc(editor, cx, roof_base_y, cz, radius + 1, wall_block)
    build_chandelier_1(editor, cx, roof_base_y - 1, cz)
    build_cone_roof_1(editor, cx, roof_base_y, cz, radius, int(1.4 * height), roof_block, has_snow)

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
    build_fully_featured_tower(editor, world_slice, build_area, tcx1, base_y, tcz1, radius, height, small_roof_h, wall_block, roof_block, has_snow)
    
    tcx2, tcz2 = get_pos(right_lx, 0)
    build_fully_featured_tower(editor, world_slice, build_area, tcx2, base_y, tcz2, radius, height, small_roof_h, wall_block, roof_block, has_snow)    # =====================================
    
    # 2. THE ADAPTIVE FLOOR & ARCHWAY
    # =====================================    
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
            for (x, z) in circle_points_1(0, z_arc, 2.5):
                place_local(x, central_y, z, Block("amethyst_cluster"))
                if random.random() < 0.6: 
                    place_local(x, central_y - 1, z, Block("amethyst_cluster"))
                    
            # 3. Alternating Lantern Rings
            mid_y = peak_y - 6
            for r in [1.5, 3.0]:
                ring_points = circle_points_1(0, z_arc, r)
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

# 3. Corridor

def build_corridor(editor, map_cx, map_cz, cx, base_y, cz, direction, is_great_hall, width, length, height, facing, wall_stone, roof_block, roof_stairs, has_snow=False):      
    if direction == "n-s":
        ox, oy, oz = cx - (width // 2), base_y, cz - (length // 2)
    else:
        ox, oy, oz = cx - (length // 2), base_y, cz - (width // 2)
    carpet_color = random.choice(CARPETS)
    CARPET_BLOCK = Block(carpet_color)
    def get_pos(dw, dl, y):
        """Translates local layout into globally rotated Minecraft coordinates."""
        # Calculate where the block WOULD be in the standard unrotated South layout
        if direction == "n-s":
            ux, uz = ox + dw, oz + dl
        else: # "e-w"
            ux, uz = ox + dl, oz + dw
            
        # Matrix Math: Rotate the absolute coordinate around the map center!
        rx, rz = rotate_point(ux, uz, map_cx, map_cz, facing)
        return rx, y, rz

    # -----------------------------------------------------
    # 2. Block Facings & Axes
    # Define standard facings as normal, then rotate them!
    # -----------------------------------------------------
    if direction == "n-s":
        face_left_up = rotate_facing("east", facing)
        face_right_up = rotate_facing("west", facing)
        torch_left = rotate_facing("east", facing)
        torch_right = rotate_facing("west", facing)
        seat_left = rotate_facing("east", facing)
        seat_right = rotate_facing("west", facing)
        high_seat_facing = rotate_facing("north", facing)
    else: # "e-w"
        face_left_up = rotate_facing("south", facing)
        face_right_up = rotate_facing("north", facing)
        torch_left = rotate_facing("south", facing)
        torch_right = rotate_facing("north", facing)
        seat_left = rotate_facing("south", facing)
        seat_right = rotate_facing("north", facing)
        high_seat_facing = rotate_facing("west", facing)

    # For Logs, we need to rotate the actual structural axis (x or z)
    rot_dir = rotate_direction(direction, facing)
    beam_axis = "x" if rot_dir == "n-s" else "z"

    TORCH_LEFT = Block(f"wall_torch[facing={torch_left}]")
    TORCH_RIGHT = Block(f"wall_torch[facing={torch_right}]")
    SEAT_LEFT = Block("dark_oak_stairs", {"facing": seat_left})
    SEAT_RIGHT = Block("dark_oak_stairs", {"facing": seat_right})
    STAIR_LEFT = Block(roof_stairs.id, {"facing": face_left_up})
    STAIR_RIGHT = Block(roof_stairs.id, {"facing": face_right_up})

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
            editor.placeBlock(get_pos(0, dl, y), wall_stone)
            if random.randint(0, 11) == 0:
                editor.placeBlock(get_pos(0, dl, y), MOSSY_STONE)
        
        # RIGHT WALL (dw = width - 1)
        for y in range(oy + 1, oy + height):
            editor.placeBlock(get_pos(width - 1, dl, y), wall_stone)
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
            
            # Frost the sloped sides using carpet to bypass Minecraft's physics engine breaking the snow!
            if has_snow:
                editor.placeBlock(get_pos(left_dw, dl, y + 1), Block("white_carpet"))
                editor.placeBlock(get_pos(right_dw, dl, y + 1), Block("white_carpet"))

        # Fill the center gap if the width is an odd number
        if width % 2 != 0:
            center_dw = width // 2
            peak_y = roof_base_y + center_dw
            
            # Using prismarine bricks to match the stairs seamlessly 
            editor.placeBlock(get_pos(center_dw, dl, peak_y), roof_block)
            
            # Frost the very top peak
            if has_snow:
                editor.placeBlock(get_pos(center_dw, dl, peak_y + 1), Block("snow"))

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
        # GREAT HALL END WALL & WINDOW
        # =========================
        # 1. Build a solid stone wall to cap the end of the hall (dl = length - 1)
        far_end_dl = length - 1
        for dw in range(1, width - 1): # Between left and right walls
            for y in range(oy + 1, roof_base_y): # Floor to roof base
                editor.placeBlock(get_pos(dw, far_end_dl, y), wall_stone)
                
            # Fill the triangular gable under the roof
            local_roof_y = roof_base_y + min(dw, width - 1 - dw)
            for y in range(roof_base_y, local_roof_y):
                editor.placeBlock(get_pos(dw, far_end_dl, y), wall_stone)

        # 2. Punch the grand antique window into the center of the wall!
        def end_wall_pos(thickness, hall_width_pos, y):
            # Step 1: Calculate the BASE unrotated coordinates
            if direction == "e-w":
                ux = ox + far_end_dl + thickness
                uz = oz + hall_width_pos
            else:
                ux = ox + hall_width_pos
                uz = oz + far_end_dl + thickness
            
            # Step 2: Apply the rotation matrix before returning!
            rx, rz = rotate_point(ux, uz, map_cx, map_cz, facing)
            return (rx, y, rz)

        build_antique_window(editor, oy + 5, 0, width // 2, end_wall_pos)

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
        # Apply the rotation helper to the base direction!
        base_high_seat = "north" if direction == "n-s" else "west"
        high_seat_facing = rotate_facing(base_high_seat, facing)
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

# 4. Common Room

def build_common_room(editor, cx, base_y, cz, radius, ground_height, dorm_height, roof_height, wall_block, roof_block, has_snow):
    wall_height = ground_height + dorm_height

    # 1. Base Floors & Cylinder Shell
    build_floor_disc(editor, cx, base_y, cz, radius, FLOOR_BLOCK)                  
    build_floor_disc(editor, cx, base_y + ground_height, cz, radius, FLOOR_BLOCK)  
    
    # Outer Stone Wall
    for y in range(base_y + 1, base_y + wall_height + 1):
        for (wx, wz) in circle_points_3(cx, cz, radius):
            editor.placeBlock((wx, y, wz), wall_block)

    # Inner Wall Lining (House Colored Wool!)
    for y in range(base_y + 1, base_y + ground_height):
        for (iwx, iwz) in circle_points_3(cx, cz, radius - 1):
            house = get_quadrant_house(iwx, iwz, cx, cz)
            color = HOUSES[house]["color"]
            editor.placeBlock((iwx, y, iwz), Block(f"{color}_wool"))

    # 2. Random Windows
    for floor_base in [base_y + 2, base_y + ground_height + 2]:
        for _ in range(15):
            angle = random.uniform(0, 2 * math.pi)
            wx = int(round(cx + radius * math.cos(angle)))
            wz = int(round(cz + radius * math.sin(angle)))
            iwx = int(round(cx + (radius - 1) * math.cos(angle)))
            iwz = int(round(cz + (radius - 1) * math.sin(angle)))
            
            for dy in range(6):
                editor.placeBlock((wx, floor_base + dy, wz), Block("glass_pane"))
                # Punch through the wool lining so light comes in!
                editor.placeBlock((iwx, floor_base + dy, iwz), Block("air")) 

    # 3. Ground Floor Carpets (Fully Filled!)
    for x in range(cx - radius + 1, cx + radius):
        for z in range(cz - radius + 1, cz + radius):
            if (x - cx) ** 2 + (z - cz) ** 2 > (radius - 2) ** 2: continue
            
            # Shrunk the empty center zone to radius 4 to ensure carpet covers everything else
            if (x - cx) ** 2 + (z - cz) ** 2 <= 4 ** 2: continue

            house = get_quadrant_house(x, z, cx, cz)
            color = HOUSES[house]["color"]
            editor.placeBlock((x, base_y + 1, z), Block(f"{color}_carpet"))

    # 4. Quadrant Features 
    chimney_positions = []
    for house, data in HOUSES.items():
        angle = data["angle_center"]
        color = data["color"]
        wood = data["wood"]
        
        fx = int(round(cx + (radius - 3) * math.cos(angle)))
        fz = int(round(cz + (radius - 3) * math.sin(angle)))
        chimney_positions.append((fx, fz))

        dir_x = -1 if math.cos(angle) > 0 else 1
        dir_z = -1 if math.sin(angle) > 0 else 1

        # ==================
        # THE WIDER FIREPLACE
        # ==================
        # 7x7 Solid brick base
        fill_cuboid(editor, fx - 3, base_y + 1, fz - 3, fx + 3, base_y + 5, fz + 3, Block("bricks"))
        
        # 5x5 Hollow interior
        fill_cuboid(editor, fx - 2, base_y + 1, fz - 2, fx + 2, base_y + 4, fz + 2, Block("air"))
        
        # Carve a massive 5x5 opening facing the center of the room
        fill_cuboid(editor, fx + dir_x - 2, base_y + 1, fz + dir_z - 2, fx + dir_x*3 + 2, base_y + 4, fz + dir_z*3 + 2, Block("air"))

        # 5-block Cross Bonfire inside
        for dfx in [-1, 0, 1]:
            for dfz in [-1, 0, 1]:
                if abs(dfx) + abs(dfz) <= 1: 
                    editor.placeBlock((fx + dfx, base_y + 1, fz + dfz), Block("campfire"))
        
        for i in range(-2, 3): 
            for y_offset in [1, 2]:
                editor.placeBlock((fx + dir_x * 2, base_y + y_offset, fz + i), Block("acacia_fence"))
                editor.placeBlock((fx + i, base_y + y_offset, fz + dir_z * 2), Block("acacia_fence"))

        # House Notice Board
        facing_str = "west" if dir_x == -1 else "east"
        place_wall_sign(editor, fx + (dir_x * 4), base_y + 5, fz, facing_str, f"{house}")

        # ==================
        # SEATING & BANNERS
        # ==================
        # Move the seating anchor back to fit the massive 5x5 footprint
        seat_cx = fx + (dir_x * 6)
        seat_cz = fz + (dir_z * 6)
        
        # Calculate the Minecraft facing strings so the sofa points toward the fire
        face_z = "south" if -dir_z == 1 else "north"
        face_x = "east" if -dir_x == 1 else "west"

        # 1. The Sofa Corner
        editor.placeBlock((seat_cx, base_y + 1, seat_cz), Block(f"{wood}_stairs", {"facing": face_x}))
        editor.placeBlock((seat_cx - dir_x, base_y + 1, seat_cz - dir_z), Block(f"{wood}_slab", {"type": "bottom"}))

        # 2. The Sofa Arms (Extending 3 blocks outward towards the fire)
        for i in range(1, 6):
            # Arm 1 (Along the X-axis)
            editor.placeBlock((seat_cx - dir_x * i, base_y + 1, seat_cz), Block(f"{wood}_stairs", {"facing": face_z}))
            editor.placeBlock((seat_cx - dir_x * i, base_y + 1, seat_cz - dir_z), Block(f"{wood}_slab", {"type": "bottom"}))
            
            # Arm 2 (Along the Z-axis)
            editor.placeBlock((seat_cx, base_y + 1, seat_cz - dir_z * i), Block(f"{wood}_stairs", {"facing": face_x}))
            editor.placeBlock((seat_cx - dir_x, base_y + 1, seat_cz - dir_z * i), Block(f"{wood}_slab", {"type": "bottom"}))

        # 3. The Central Coffee Table (2x2 top slabs nested inside the L-shape)
        table_x = seat_cx - dir_x * 2
        table_z = seat_cz - dir_z * 2
        
        editor.placeBlock((table_x, base_y + 1, table_z), Block(f"{wood}_slab", {"type": "top"}))
        editor.placeBlock((table_x - dir_x, base_y + 1, table_z), Block(f"{wood}_slab", {"type": "top"}))
        editor.placeBlock((table_x, base_y + 1, table_z - dir_z), Block(f"{wood}_slab", {"type": "top"}))
        editor.placeBlock((table_x - dir_x, base_y + 1, table_z - dir_z), Block(f"{wood}_slab", {"type": "top"}))

        # 4. Snacks and Drinks on the Table!
        # Cake (with random bites taken out of it)
        editor.placeBlock((table_x, base_y + 2, table_z), Block("cake", {"bites": str(random.randint(0, 3))}))
        # Empty mug
        editor.placeBlock((table_x, base_y + 2, table_z - dir_z), Block("flower_pot")) 
        # House-colored ambiance candles
        editor.placeBlock((table_x - dir_x, base_y + 2, table_z - dir_z), Block(f"{color}_candle", {"lit": "true", "candles": "2"}))

        # 5. Standing Banners flanking the sofa
        banner_rot = str(random.randint(0, 15))
        editor.placeBlock((seat_cx - dir_z * 3, base_y + 1, seat_cz + dir_x * 3), Block(f"{color}_banner", {"rotation": banner_rot}))
        editor.placeBlock((seat_cx + dir_z * 3, base_y + 1, seat_cz - dir_x * 3), Block(f"{color}_banner", {"rotation": banner_rot}))

        # Exterior Wall Banners (On the outside of the stone tower)
        out_x = int(round(cx + radius * math.cos(angle)))
        out_z = int(round(cz + radius * math.sin(angle)))
        editor.placeBlock((out_x - dir_x, base_y + 6, out_z), Block(f"{color}_wall_banner", {"facing": "east" if -dir_x > 0 else "west"}))
        editor.placeBlock((out_x, base_y + 6, out_z - dir_z), Block(f"{color}_wall_banner", {"facing": "south" if -dir_z > 0 else "north"}))

        # ==================
        # WALL BOOKSHELVES
        # ==================
        # Calculate the ring just inside the wool wall (radius - 2)
        shelf_ring = circle_points_3(cx, cz, radius - 2)
        for bx, bz in shelf_ring:
            # Ensure we are in the correct quadrant
            if get_quadrant_house(bx, bz, cx, cz) == house:
                dist_to_fire = math.sqrt((bx - fx)**2 + (bz - fz)**2)
                
                # Keep bookshelves away from the 7x7 hearth (> 4.5) but cluster them nearby (< 11.0)
                if 4.5 < dist_to_fire < 11.0:
                    # 70% chance to place a column creates a lovely, slightly broken/organic library wall
                    if random.random() < 0.75: 
                        stack_height = random.randint(2, 8)
                        for h in range(stack_height):
                            # Mix in some chiseled bookshelves for texture
                            b_type = "chiseled_bookshelf" if random.random() < 0.3 else "bookshelf"
                            editor.placeBlock((bx, base_y + 1 + h, bz), Block(b_type))

        # Quadrant Chandelier
        quad_cx = int(round(cx + (radius / 2) * math.cos(angle)))
        quad_cz = int(round(cz + (radius / 2) * math.sin(angle)))
        build_quadrant_chandelier(editor, quad_cx, base_y + ground_height - 1, quad_cz, drop_length=6)

        # Chimney Flue straight up
        half_roof_y = base_y + wall_height + (roof_height // 3)
        fill_cuboid(editor, fx - 1, base_y + 6, fz - 1, fx + 1, half_roof_y, fz + 1, Block("bricks"))
        fill_cuboid(editor, fx, base_y + 6, fz, fx, half_roof_y, fz, Block("air")) 
        editor.placeBlock((fx, half_roof_y, fz), Block("campfire")) 

    # ==================
    # CENTRAL LIGHTING
    # ==================
    # 4 Lanterns around the center base
    editor.placeBlock((cx, base_y + 1, cz), Block("chiseled_stone_bricks")) # Center pedestal
    editor.placeBlock((cx + 1, base_y + 1, cz), LANTERN)
    editor.placeBlock((cx - 1, base_y + 1, cz), LANTERN)
    editor.placeBlock((cx, base_y + 1, cz + 1), LANTERN)
    editor.placeBlock((cx, base_y + 1, cz - 1), LANTERN)

    # ==================
    # POPULATE MOBS
    # ==================
    mobs = ["parrot", "cat", "bat", "trader_llama", "villager"]
    for mob in mobs:
        for _ in range(2):
            spawn_angle = random.uniform(0, 2 * math.pi)
            spawn_dist = random.uniform(4, radius - 4)
            mx = int(round(cx + spawn_dist * math.cos(spawn_angle)))
            mz = int(round(cz + spawn_dist * math.sin(spawn_angle)))
            
            try:
                # Trigger Minecraft's native summon command at the calculated coordinates
                editor.runCommand(f"summon minecraft:{mob} {mx} {base_y + 1} {mz}")
            except Exception:
                pass

    # 5. Central Double-Winding 2x2 Slab Stairs
    stair_radius = 3

    # 5. Central Double-Winding 2x2 Slab Stairs
    stair_radius = 3 
    total_steps = ground_height * 2

    for step in range(total_steps):
        y = base_y + 1 + (step // 2)
        slab_type = "bottom" if step % 2 == 0 else "top"
        stair_block = Block("spruce_slab", {"type": slab_type})
        
        angle1 = step * (math.pi / 8)
        angle2 = angle1 + math.pi 

        sx1 = int(round(cx + stair_radius * math.cos(angle1)))
        sz1 = int(round(cz + stair_radius * math.sin(angle1)))
        for dx in [0, 1]:
            for dz in [0, 1]:
                editor.placeBlock((sx1 + dx, y, sz1 + dz), stair_block)
        
        sx2 = int(round(cx + stair_radius * math.cos(angle2)))
        sz2 = int(round(cz + stair_radius * math.sin(angle2)))
        for dx in [0, 1]:
            for dz in [0, 1]:
                editor.placeBlock((sx2 + dx, y, sz2 + dz), stair_block)
        
    build_floor_disc(editor, cx, base_y + ground_height, cz, stair_radius + 2, Block("air"))

    # 6. Second Floor Dorms
    dorm_y = base_y + ground_height
    
    # The physical partition wall down the middle (along the X-axis)
    fill_cuboid(editor, cx - radius + 1, dorm_y + 1, cz, cx + radius - 1, dorm_y + dorm_height, cz, wall_block)
    
    # 6A. First Pass: Lay full carpets across the entire valid floor
    for x in range(cx - radius + 1, cx + radius):
        for z in range(cz - radius + 1, cz + radius):
            if (x - cx) ** 2 + (z - cz) ** 2 > (radius - 2) ** 2: continue
            if abs(z - cz) < 2: continue # Keep a clean walkway immediately next to the partition wall
            if (x - cx) ** 2 + (z - cz) ** 2 < (stair_radius + 2) ** 2: continue 
            
            house = get_quadrant_house(x, z, cx, cz)
            color = HOUSES[house]["color"]
            editor.placeBlock((x, dorm_y + 1, z), Block(f"{color}_carpet"))

    # 6B. Second Pass: Furniture, Beds, and Magical Props
    magical_props = [
        "enchanting_table", "brewing_stand", "ender_chest", 
        "cauldron", "lectern", "bookshelf", "fletching_table", "cartography_table"
    ]

    # We step by 3 on X and 4 on Z to create distinct "student station" spacing
    for x in range(cx - radius + 3, cx + radius - 2, 3):
        for z in range(cz - radius + 3, cz + radius - 2, 4):
            # Check boundaries so furniture doesn't clip into the outer curved walls
            if (x - cx) ** 2 + (z - cz) ** 2 > (radius - 4) ** 2: continue
            if abs(z - cz) < 3: continue 
            if (x - cx) ** 2 + (z - cz) ** 2 < (stair_radius + 3) ** 2: continue 

            house = get_quadrant_house(x, z, cx, cz)
            color = HOUSES[house]["color"]
            wood = HOUSES[house]["wood"]

            rand_val = random.random()

            # ~40% Chance: A Student's Bed Station
            if rand_val < 0.40: 
                # Place Foot, then Head (facing West)
                editor.placeBlock((x, dorm_y + 1, z), Block(f"{color}_bed", {"facing": "west", "part": "foot"}))
                editor.placeBlock((x - 1, dorm_y + 1, z), Block(f"{color}_bed", {"facing": "west", "part": "head"}))
                
                # Bedside table (a wood slab) with a light source
                editor.placeBlock((x + 1, dorm_y + 1, z), Block(f"{wood}_slab"))
                if random.random() < 0.5:
                    editor.placeBlock((x + 1, dorm_y + 2, z), Block("lantern"))
                else:
                    # A cluster of lit candles!
                    editor.placeBlock((x + 1, dorm_y + 2, z), Block("candle", {"lit": "true", "candles": str(random.randint(1,4))}))
                    
                # 50% chance to put a storage chest at the foot of the bed
                if random.random() < 0.5:
                    editor.placeBlock((x - 2, dorm_y + 1, z), Block("chest", {"facing": "west"}))

            # ~30% Chance: A Magical Study Corner
            elif rand_val < 0.70: 
                prop = random.choice(magical_props)
                editor.placeBlock((x, dorm_y + 1, z), Block(prop))
                
                # If the prop is a bookshelf, stack something magical on top of it!
                if prop == "bookshelf":
                    top_prop = random.choice(["lantern", "amethyst_cluster", "flower_pot", "skeleton_skull"])
                    editor.placeBlock((x, dorm_y + 2, z), Block(top_prop))

            # ~15% Chance: A Wardrobe / Double Bookshelf
            elif rand_val < 0.85: 
                editor.placeBlock((x, dorm_y + 1, z), Block("bookshelf"))
                editor.placeBlock((x, dorm_y + 2, z), Block("chiseled_bookshelf" if random.random() < 0.5 else "bookshelf"))

    # 7. Cone Roof
    roof_base_y = base_y + wall_height
    build_floor_disc(editor, cx, roof_base_y, cz, radius + 1, wall_block)
    
    for i in range(roof_height):
        r = int(round((radius + 1) * (1.0 - (i / roof_height))))
        if r < 1: r = 1
        y = roof_base_y + i
        for (rx, rz) in circle_points_3(cx, cz, r):
            editor.placeBlock((rx, y, rz), roof_block)
            
            # Add a layer of snow on top of the roof block!
            if has_snow:
                editor.placeBlock((rx, y + 1, rz), Block("snow"))
            
    # Top tip of the roof
    editor.placeBlock((cx, roof_base_y + roof_height, cz), roof_block)
    if has_snow:
        editor.placeBlock((cx, roof_base_y + roof_height + 1, cz), Block("snow"))

    # 8. Re-punch the chimneys
    half_roof_y = roof_base_y + (roof_height // 2)
    for (fx, fz) in chimney_positions:
        fill_cuboid(editor, fx - 1, roof_base_y, fz - 1, fx + 1, half_roof_y, fz + 1, Block("bricks"))
        fill_cuboid(editor, fx, roof_base_y, fz, fx, half_roof_y, fz, Block("air"))
        editor.placeBlock((fx, half_roof_y, fz), Block("campfire"))

# 5. Tower

def build_bibliotheek(editor, center_x, base_y, center_z, radius, height, entrance_facing, wall_block, roof_block, has_snow):
    wall_height = max(height - 8, 10)
    roof_height = int(1.3*height)

    # 1. Base floor & walls (unchanged)
    build_floor_disc(editor, center_x, base_y, center_z, radius, wall_block)
    build_circular_wall_2(editor, center_x, base_y + 1, center_z, radius, wall_height, wall_block)

    # 2. Windows & stairs (unchanged)  
    wall_windows = sample_wall_window_slots(center_x, center_z, radius, wall_height, base_y)
    build_wall_windows(editor, wall_windows, center_x, center_z)
    
    roof_base_y = base_y + wall_height
    stairs_height = roof_base_y - (base_y + 1)
    build_spiral_stairs_with_interior_features(editor, center_x, base_y, center_z, 
                                               stairs_height, radius, wall_windows)

    # *** 3. CONE BASE FLOOR FIRST ***
    build_floor_disc(editor, center_x, roof_base_y, center_z, radius + 1, wall_block)  # ADD THIS!
    # 4. Cone roof WITH skylight
    build_cone_roof_2(editor, center_x, roof_base_y, center_z, radius, roof_height, roof_block, has_snow)
    # 5. Stair landing position
    ceiling_y = roof_base_y
    sx, stair_top_rel_y, sz = get_stair_top_position(center_x, center_z, radius, stairs_height)
    stair_top_y = base_y + stair_top_rel_y

    # CAREFULLY cut the landing hole strictly INSIDE the tower walls
    for dx in range(-3, 4):
        for dz in range(-3, 4):
            tx = sx + dx
            tz = sz + dz
            # Mathematically force the cut to stay inward, protecting the exterior roof!
            if math.hypot(tx - center_x, tz - center_z) <= radius - 1:
                # Clear the floor block (Y=0) and 3 blocks of headroom (Y=1, 2, 3)
                for dy in range(0, 4): 
                    editor.placeBlock((tx, stair_top_y + 1 + dy, tz), Block("air"))

    # 6. West opening (NOW cone base exists)
    west_opening_x = center_x - radius
    make_west_cone_base_opening(editor, center_x, roof_base_y, center_z, radius)
    
    # 7. Features
    build_observatory_telescope(editor, center_x, roof_base_y, center_z, west_opening_x)
    build_chandelier_2(editor, center_x, ceiling_y-1, center_z)
    build_tower_library(editor,center_x,base_y,center_z,tower_height=stairs_height + 3,
                        wall_radius=radius-2,stair_clear_radius=5)
    # 8. Door
    build_entrance(editor, center_x, base_y, center_z, radius, facing=entrance_facing)

# 6. Garden
def build_garden(editor, world_slice, build_area, cx, base_y, cz, garden_radius=15, wall_block=None, roof_block=None, is_snowy=False):

    # 1. BIOME ADAPTIVE THEME ENGINE
    wall_id = wall_block.id.replace("minecraft:", "") if wall_block else "stone_bricks"
    roof_id = roof_block.id.replace("minecraft:", "") if roof_block else "oak_planks"
    # Match the fountain stone to the castle walls
    if "deepslate" in wall_id or "blackstone" in wall_id:
        theme = {"pillar": "polished_deepslate", "base": "cobbled_deepslate_stairs", "slab": "polished_deepslate_slab", "pyramid": "cobbled_deepslate_stairs", "tub": "deepslate_tiles"}
        path_block = Block("polished_basalt")
    elif "sandstone" in wall_id or "terracotta" in wall_id:
        theme = {"pillar": "smooth_sandstone", "base": "sandstone_stairs", "slab": "sandstone_slab", "pyramid": "sandstone_stairs", "tub": "cut_sandstone"}
        path_block = Block("smooth_sandstone")
    elif "quartz" in wall_id:
        theme = {"pillar": "quartz_pillar", "base": "quartz_stairs", "slab": "quartz_slab", "pyramid": "quartz_stairs", "tub": "chiseled_quartz_block"}
        path_block = Block("diorite")
    elif "mud" in wall_id:
        theme = {"pillar": "mud_bricks", "base": "mud_brick_stairs", "slab": "mud_brick_slab", "pyramid": "mud_brick_stairs", "tub": "packed_mud"}
        path_block = Block("rooted_dirt")
    elif "brick" in wall_id:
        theme = {"pillar": "bricks", "base": "brick_stairs", "slab": "brick_slab", "pyramid": "brick_stairs", "tub": "bricks"}
        path_block = Block("granite")
    else:
        theme = {"pillar": "stone_bricks", "base": "stone_brick_stairs", "slab": "stone_brick_slab", "pyramid": "stone_brick_stairs", "tub": "chiseled_stone_bricks"}
        path_block = Block("gravel")

    # Match the garden trees to the castle roofs
    if "cherry" in roof_id: log_id, leaf_id = "cherry_log", "cherry_leaves"
    elif "acacia" in roof_id: log_id, leaf_id = "acacia_log", "acacia_leaves"
    elif "warped" in roof_id: log_id, leaf_id = "warped_stem", "warped_wart_block"
    elif "crimson" in roof_id: log_id, leaf_id = "crimson_stem", "nether_wart_block"
    elif "spruce" in roof_id or is_snowy: log_id, leaf_id = "spruce_log", "spruce_leaves"
    elif "dark_oak" in roof_id: log_id, leaf_id = "dark_oak_log", "dark_oak_leaves"
    else: log_id, leaf_id = "oak_log", "azalea_leaves" # Azalea looks very magical!

    grass_block = Block("grass_block")
    fountain_radius = 4
    pillar_dist = fountain_radius + 2 
    walkway_width = 2 
    pillar_height = random.randint(6, 9)

    # 2. Layout Terrain-Adaptive Ground
    for x in range(cx - garden_radius, cx + garden_radius + 1):
        for z in range(cz - garden_radius, cz + garden_radius + 1):
            dist_to_center = math.hypot(x - cx, z - cz)
            
            local_x, local_z = x - build_area.begin.x, z - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                ground_y = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z] - 1
            else:
                ground_y = base_y
                
            if dist_to_center <= fountain_radius + 3:
                target_y = base_y
            else:
                target_y = ground_y
                editor.placeBlock((x, target_y + 1, z), Block("air"))
                editor.placeBlock((x, target_y + 2, z), Block("air"))

            is_path = (abs(x - cx) <= walkway_width) or (abs(z - cz) <= walkway_width) or (fountain_radius < dist_to_center <= fountain_radius + 2)

            if is_path:
                editor.placeBlock((x, target_y, z), path_block)
                # Dust paths with snow if winter
                if is_snowy and random.random() < 0.4:
                    editor.placeBlock((x, target_y + 1, z), Block("snow"))
            else:
                editor.placeBlock((x, target_y, z), grass_block)
                
                # Biome-aware flora generation
                if dist_to_center > fountain_radius + 3:
                    rand_val = random.random()
                    if rand_val < 0.015:
                        build_mini_tree(editor, x, target_y + 1, z, log_id, leaf_id)
                    elif rand_val < 0.04:
                        editor.placeBlock((x, target_y + 1, z), Block("dark_oak_fence"))
                        editor.placeBlock((x, target_y + 2, z), Block("lantern"))
                    elif rand_val < 0.20:
                        # Ground cover matches biome
                        if is_snowy:
                            editor.placeBlock((x, target_y + 1, z), Block("snow"))
                        elif "sand" in wall_id or "terracotta" in wall_id:
                            editor.placeBlock((x, target_y + 1, z), Block("dead_bush"))
                        elif "warped" in roof_id or "crimson" in roof_id:
                            editor.placeBlock((x, target_y + 1, z), Block(random.choice(["crimson_fungus", "warped_fungus"])))
                        else:
                            editor.placeBlock((x, target_y + 1, z), Block(random.choice(["tall_grass", "fern", "poppy", "dandelion", "azure_bluet"])))
                    elif is_snowy:
                        # Blanket remaining grass in snow
                        editor.placeBlock((x, target_y + 1, z), Block("snow"))

    # 3. Circular Tub Fountain 
    TUB = Block(theme["tub"])
    fill_cuboid(editor, cx - fountain_radius, base_y, cz - fountain_radius, cx + fountain_radius, base_y, cz + fountain_radius, TUB)
    for fx, fz in circle_points_1(cx, cz, fountain_radius):
        editor.placeBlock((fx, base_y + 1, fz), TUB)
        editor.placeBlock((fx, base_y + 2, fz), Block(theme["slab"], {"type": "bottom"}))
    for fx in range(cx - fountain_radius + 1, cx + fountain_radius):
        for fz in range(cz - fountain_radius + 1, cz + fountain_radius):
            if math.hypot(fx - cx, fz - cz) <= fountain_radius - 0.5:
                # Use ice instead of water if snowy!
                water_block = "ice" if is_snowy else "water"
                editor.placeBlock((fx, base_y + 1, fz), Block(water_block))

    editor.placeBlock((cx, base_y + 1, cz), TUB)
    editor.placeBlock((cx, base_y + 2, cz), TUB)
    editor.placeBlock((cx, base_y + 3, cz), Block("ice" if is_snowy else "water")) 

    # 4. Four Pillars
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



# ==========================================
# MASTER GENERATOR
# ==========================================
def main():
    if RNG_SEED is not None: random.seed(RNG_SEED)

    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()
    x0, y0, z0 = build_area.begin
    x1, y1, z1 = build_area.end
    rect = build_area.toRect()
    initial_world_slice = editor.loadWorldSlice(rect, cache=True)
    height_map = initial_world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"]

    print(f"Scouting terrain for the {PLOT_SIZE}x{PLOT_SIZE} building plot...")

    best_patch, is_ideal = find_best_location(height_map=height_map, patch_size=PLOT_SIZE, world_slice=initial_world_slice)
    start_x, start_z = x0 + best_patch[0], z0 + best_patch[1]

    env_wall, env_roof, env_roof_stair, is_snowy = get_biome_palette(editor, initial_world_slice, build_area)

    heights = []
    for dx in range(PLOT_SIZE):
        for dz in range(PLOT_SIZE):
            local_x, local_z = (start_x + dx) - build_area.begin.x, (start_z + dz) - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                heights.append(height_map[local_x][local_z])
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
    print(f"Aligning layout {slope_facing} and preparing foundations...")
    
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
    build_twin_tower_entrance(editor, world_slice, build_area, ent_cx, base_y, ent_cz, small_roof_h_e, radius_e, height_e, facing=slope_facing, wall_block=env_wall, roof_block=env_roof, roof_stair_block=env_roof_stair, has_snow=is_snowy)

    print("2/7 Constructing Great Hall...")
    build_corridor( editor, map_cx, map_cz, b_gh_cx, base_y, b_gh_cz, "e-w", True, gh_width, gh_length, gh_height, facing=slope_facing, wall_stone=env_wall, roof_block=env_roof, roof_stairs=env_roof_stair)
    
    print("3/7 Constructing Common Room...")
    build_common_room(editor, cr_cx, base_y, cr_cz, radius_cr, ground_height_cr, dorm_height_cr, roof_height_cr, env_wall, env_roof, is_snowy)

    print("4/7 Constructing Bibliotheek...")
    build_bibliotheek(editor, lib_cx, base_y, lib_cz, radius_lib, height_lib, rotate_facing("south", slope_facing), env_wall, env_roof, is_snowy)

    print("5/7 Constructing Connecting Corridors...")
    build_corridor(editor, map_cx, map_cz, b_lib_cx, base_y, b_lc_cz, "n-s", False, corr_width, lc_len, min(height_lib, height_e)-2, slope_facing, env_wall, env_roof, env_roof_stair) 
    build_corridor(editor, map_cx, map_cz, b_tc_cx, base_y, b_lib_cz, "e-w", False, corr_width, tc_len, min(height_lib, cr_base_h)-2, slope_facing, env_wall, env_roof, env_roof_stair) 
    build_corridor(editor, map_cx, map_cz, b_cr_cx, base_y, b_rc_cz, "n-s", False, corr_width, rc_len, min(cr_base_h, gh_height)-2, slope_facing, env_wall, env_roof, env_roof_stair)
    
    print("6/7 Constructing Central Garden...")
    build_garden(editor, world_slice, build_area, gard_cx, base_y, gard_cz, garden_radius=18, wall_block=env_wall, roof_block=env_roof, is_snowy=is_snowy)
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

    build_entrance_carver(editor, gh_cx, base_y, gh_cz, gh_width // 2, rotate_facing("north", slope_facing), depth_out=7)

    print("Flushing final structural buffers to Minecraft...")
    editor.flushBuffer()
    print("HOGWARTS Generation Complete!")

if __name__ == "__main__":
    main()    