from gdpc import Editor, Block
import math
import random

# Base defaults
BASE_TOWER_HEIGHT = 30
MIN_RADIUS = 7
MAX_RADIUS = 13
MAX_EXTRA_HEIGHT = 25

FLOOR_BLOCK = Block("spruce_planks")
STAIR_BLOCK = Block("spruce_slab")
WINDOW_BLOCK = Block("glass_pane")  
DOOR_BLOCK = Block("oak_door")
TORCH_BLOCK = Block("wall_torch")    
CHAIN_BLOCK = Block("oxidized_copper_chain")

TELESCOPE_BASE = Block("cut_copper")
TELESCOPE_TUBE = Block("copper_block")
TELESCOPE_LENS = Block("glass")

LANTERN_BLOCK = Block("soul_torch")
AMETHYST_CLUSTER = Block("amethyst_cluster")
AMETHYST_BUD_LARGE = Block("large_amethyst_bud")
AMETHYST_BLOCK = Block("amethyst_block")
SEA_LANTERN = Block("sea_lantern") 

# If None → system time used, so random each run; if int → deterministic PCG run. [web:11][web:16][web:19]
RNG_SEED = None  # or None for non-deterministic runs


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

def build_cone_roof(editor, cx, base_y, cz, base_radius, height, roof_block, has_snow):
    for i in range(height):
        t = i / (height - 1) if height > 1 else 1.0
        radius_f = base_radius * (1.0 - t * t)
        r = max(1, int(round(radius_f)))
        y = base_y + i
        
        # Build the outer ring of the roof
        for (x, z) in circle_points(cx, cz, r):
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

def sample_wall_window_slots(cx, cz, radius, wall_height, base_y):
    # Proportional count: maybe one window for every 6 blocks of height
    total_windows = max(1, wall_height // 2)

    ring = circle_points(cx, cz, radius)
    window_positions = []

    for _ in range(total_windows):
        wx, wz = random.choice(ring)
        # wy is the BOTTOM-LEFT of the 4x2 window.
        # Adjusted range: base_y + 2 (min) to wall_height - 6 (max)
        # This prevents the 4-block tall window from hitting the roof.
        wy = random.randint(base_y + 2, base_y + wall_height - 6)
        window_positions.append((wx, wz, wy))

    return window_positions

def build_wall_windows(editor, window_positions, cx, cz):
    for wx, wz, wy in window_positions:
        dx = wx - cx
        dz = wz - cz
        if abs(dx) > abs(dz):
            side_x, side_z = 0, 1
        else:
            side_x, side_z = 1, 0

        for horizontal in range(2):
            curr_x = wx + (horizontal * side_x)
            curr_z = wz + (horizontal * side_z)
            
            for vertical in range(4):
                curr_y = wy + vertical
                editor.placeBlock((curr_x, curr_y, curr_z), Block("air"))
                editor.placeBlock((curr_x, curr_y, curr_z), WINDOW_BLOCK)

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
                place_interior_torches_for_window(editor, cx, cz, wx, wz, y, wall_radius)

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

def place_interior_torches_for_window(editor, cx, cz, wx, wz, y, wall_radius):
    """
    Given an outer wall window at (wx,wz,y), place two torches on the interior
    side walls near that window, at the same height.
    """
    # Direction from center to window
    dx = wx - cx
    dz = wz - cz
    length = math.sqrt(dx * dx + dz * dz)
    if length == 0:
        return
    ndx = dx / length
    ndz = dz / length

    inner_x = int(round(wx - ndx))  # one in from the wall
    inner_z = int(round(wz - ndz))

    sdx1, sdz1 = -ndz, ndx
    sdx2, sdz2 = ndz, -ndx

    left_tx = int(round(inner_x + sdx1))
    left_tz = int(round(inner_z + sdz1))
    right_tx = int(round(inner_x + sdx2))
    right_tz = int(round(inner_z + sdz2))

    editor.placeBlock((left_tx, y, left_tz), TORCH_BLOCK)
    editor.placeBlock((right_tx, y, right_tz), TORCH_BLOCK)

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

def build_chandelier(editor, cx, ceiling_y, cz):
    anchor_offsets = [(-3,0), (-2,1), (-2,-1), (0,3), (0,-3), (2,1), (2,-1), (3,0)]
    for dx, dz in anchor_offsets:
        for drop in range(5):  # Drop 3 blocks from ceiling
            editor.placeBlock((cx + dx, ceiling_y - drop, cz + dz), CHAIN_BLOCK)
    central_y = ceiling_y - 4
    tier1_points = circle_points(cx, cz, 2.5)
    for (x, z) in tier1_points:
        editor.placeBlock((x, central_y, z), AMETHYST_CLUSTER)
        if random.random() < 0.6:  # Some get clusters
            editor.placeBlock((x, central_y - 1, z), AMETHYST_CLUSTER)
    
    # Tier 2: Mid-level chains + lanterns (y-6 level) 
    mid_y = ceiling_y - 6
    for r in [1.5, 3.0]:
        points = circle_points(cx, cz, r)
        q = 0
        for (x, z) in points:
            if q % 2 == 0:
                editor.placeBlock((x, mid_y, z), CHAIN_BLOCK)
                editor.placeBlock((x, mid_y - 1, z), LANTERN_BLOCK)
            else:
                editor.placeBlock((x, mid_y+1, z), CHAIN_BLOCK)
                editor.placeBlock((x, mid_y, z), LANTERN_BLOCK)
            q+=1

    bottom_y = ceiling_y - 8
    drip_offsets = [(-1,-1), (-1,1), (1,-1), (1,1)]
    for dx, dz in drip_offsets:
        for drop in range(3):
            editor.placeBlock((cx + dx, bottom_y - drop, cz + dz), CHAIN_BLOCK)
            if drop == 2:
                editor.placeBlock((cx + dx, bottom_y - drop - 1, cz + dz), SEA_LANTERN)

    for y in range(ceiling_y - 1, bottom_y - 1, -1):
        if y % 2 == 0:  
            editor.placeBlock((cx, y, cz), CHAIN_BLOCK)

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
    base_points = circle_points(cx, cz, 1.2)
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
        
        tube_points = circle_points(int(tilt_x), int(tilt_z), tube_r)
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

def build_tower(editor, center_x, base_y, center_z, radius, height, entrance_facing, wall_block, roof_block, has_snow):
    wall_height = max(height - 8, 10)
    roof_height = int(1.3*height)

    # 1. Base floor & walls (unchanged)
    build_floor_disc(editor, center_x, base_y, center_z, radius, wall_block)
    build_circular_wall(editor, center_x, base_y + 1, center_z, radius, wall_height, wall_block)

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
    build_cone_roof(editor, center_x, roof_base_y, center_z, radius, roof_height, roof_block, has_snow)
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
    build_chandelier(editor, center_x, ceiling_y-1, center_z)
    build_tower_library(editor,center_x,base_y,center_z,tower_height=stairs_height + 3,
                        wall_radius=radius-2,stair_clear_radius=5)
    # 8. Door
    build_entrance(editor, center_x, base_y, center_z, radius, facing=entrance_facing)

def main():
    # Seed behavior: if RNG_SEED is None, Python uses system time; if not, PCG is deterministic. [web:11][web:16][web:19]
    if RNG_SEED is not None:
        random.seed(RNG_SEED)
    
    ROOF_BLOCK = Block("spruce_planks")
    WALL_BLOCK = Block("stone_bricks")
    
    # Toggle this to test the snow!
    HAS_SNOW = True

    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()

    cx = build_area.begin.x + 660
    cz = build_area.begin.z + 60
    base_y = -61
    radius, height = 12, 45

    # Passed HAS_SNOW and fixed "South" -> "south" to prevent dictionary crash
    build_tower(editor, cx, base_y, cz, radius, height, "south", WALL_BLOCK, ROOF_BLOCK, HAS_SNOW)

    editor.flushBuffer()