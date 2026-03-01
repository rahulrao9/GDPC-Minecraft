from gdpc import Editor, Block
import math
import random

# ==========================================
# DEFAULTS & PALETTES
# ==========================================
RNG_SEED = None 
FLOOR_BLOCK = Block("spruce_planks")

CHAIN = Block("oxidized_copper_chain")
LANTERN = Block("lantern")
SMALL_TORCH = Block("torch")

HOUSES = {
    "Gryffindor": {"color": "red", "wood": "mangrove", "angle_center": math.pi / 4},        # Quadrant 1
    "Ravenclaw":  {"color": "light_blue", "wood": "birch", "angle_center": 3 * math.pi / 4}, # Quadrant 2
    "Slytherin":  {"color": "green", "wood": "dark_oak", "angle_center": 5 * math.pi / 4},   # Quadrant 3
    "Hufflepuff": {"color": "yellow", "wood": "oak", "angle_center": 7 * math.pi / 4}        # Quadrant 4
}

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def fill_cuboid(editor, x1, y1, z1, x2, y2, z2, block):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for z in range(min(z1, z2), max(z1, z2) + 1):
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

def build_floor_disc(editor, cx, y, cz, radius, block):
    for x in range(cx - radius, cx + radius + 1):
        for z in range(cz - radius, cz + radius + 1):
            if (x - cx) ** 2 + (z - cz) ** 2 <= radius ** 2:
                editor.placeBlock((x, y, z), block)

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
    ring = circle_points(cx, cz, radius)
    for x, z in ring:
        editor.placeBlock((x, chand_y, z), CHAIN)
        editor.placeBlock((x, chand_y - 1, z), LANTERN)
    
    editor.placeBlock((cx, chand_y, cz), Block("dark_oak_fence"))
    editor.placeBlock((cx, chand_y - 1, cz), SMALL_TORCH)

def build_entrance(editor, cx, base_y, cz, radius, facing="south"):
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

# ==========================================
# GENERATOR LOGIC
# ==========================================
def build_common_room_tower(editor, cx, base_y, cz, radius, ground_height, dorm_height, roof_height, wall_block, roof_block, has_snow):
    wall_height = ground_height + dorm_height
    print(f"Building Massive Colored Common Room Tower (Radius: {radius}) at {cx}, {cz}...")

    # 1. Base Floors & Cylinder Shell
    build_floor_disc(editor, cx, base_y, cz, radius, FLOOR_BLOCK)                  
    build_floor_disc(editor, cx, base_y + ground_height, cz, radius, FLOOR_BLOCK)  
    
    # Outer Stone Wall
    for y in range(base_y + 1, base_y + wall_height + 1):
        for (wx, wz) in circle_points(cx, cz, radius):
            editor.placeBlock((wx, y, wz), wall_block)

    # Inner Wall Lining (House Colored Wool!)
    for y in range(base_y + 1, base_y + ground_height):
        for (iwx, iwz) in circle_points(cx, cz, radius - 1):
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
        shelf_ring = circle_points(cx, cz, radius - 2)
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
    print("Spawning magical creatures and villagers...")
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
        for (rx, rz) in circle_points(cx, cz, r):
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
        
    # # 9. PUNCH THE ENTRANCE HOLE
    # build_entrance(editor, cx, base_y, cz, radius, facing=entrance_facing)

def main():
    if RNG_SEED is not None:
        random.seed(RNG_SEED)

    WALL_BLOCK = Block("waxed_exposed_copper")
    ROOF_BLOCK = Block("waxed_weathered_copper")
    
    # Toggle this to test the snow feature!
    HAS_SNOW = True 
    
    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()

    cx = build_area.begin.x + 190
    cz = build_area.begin.z + 60
    base_y = -61 

    radius, ground_height, dorm_height, roof_height = 23, 16, 12, 38

    try:
        # Added the missing arguments from your original call: "south", WALL_BLOCK, ROOF_BLOCK, and HAS_SNOW
        build_common_room_tower(editor, cx, base_y, cz, radius, ground_height, dorm_height, roof_height, "south", WALL_BLOCK, ROOF_BLOCK, HAS_SNOW)
        
        editor.flushBuffer()
        print("Colored Grand Common Room Tower complete!")
    except Exception as e:
        print(f"Generation Failed: {e}")

if __name__ == "__main__":
    main()