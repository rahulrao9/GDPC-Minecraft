from gdpc import Editor, Block
import random

def build_grand_arched_entrance(editor: Editor, cx: int, base_y: int, cz: int, facing: str = "south"):
    """
    Builds a monumental arched doorway with pillars.
    Features massive 5-block-tall wooden doors "swung open" inward.
    Modular and rotatable based on the 'facing' argument.
    """
    # ==========================================
    # 1. LOCAL COORDINATE SYSTEM MATH
    # ==========================================
    # Maps the facing string to Forward (fx, fz) and Right (rx, rz) vectors
    dir_map = {
        "north": ((-1, 0), (0, -1), "north", "south", "west", "east"),
        "south": ((1, 0),  (0, 1),  "south", "north", "east", "west"),
        "east":  ((0, 1),  (1, 0),  "east",  "west",  "south", "north"),
        "west":  ((0, -1), (-1, 0), "west",  "east",  "north", "south")
    }
    
    (rx, rz), (fx, fz), face_fwd, face_back, face_right, face_left = dir_map[facing]
    
    def get_pos(r, u, f):
        """r = Right/Left, u = Up, f = Forward/Backward"""
        return (cx + r * rx + f * fx, base_y + u, cz + r * rz + f * fz)

    # ==========================================
    # 2. BLOCK PALETTE & FACINGS
    # ==========================================
    PILLAR_BASE = Block("chiseled_stone_bricks")
    PILLAR_SHAFT = Block("stone_bricks")
    PILLAR_WALL = Block("stone_brick_wall")
    
    # Stairs to create the arch curve
    # Left stair's tall side points right (towards center). Right stair points left.
    ARCH_STAIR_LEFT = Block("stone_brick_stairs", {"facing": face_right})
    ARCH_STAIR_RIGHT = Block("stone_brick_stairs", {"facing": face_left})
    ARCH_STAIR_UPSIDEDOWN = Block("stone_brick_stairs", {"facing": face_back, "half": "top"})
    
    DOOR_WOOD = Block("dark_oak_planks")
    DOOR_TRIM = Block("dark_oak_trapdoor", {"facing": face_back, "open": "true"})
    
    TORCH = Block("wall_torch", {"facing": face_fwd})
    CHAIN = Block("iron_chain")
    LANTERN = Block("lantern")
    
    # Clear the doorway area first (5 wide, 8 high, 3 deep)
    for r in range(-2, 3):
        for u in range(0, 9):
            for f in range(0, 3):
                editor.placeBlock(get_pos(r, u, f), Block("air"))

    # ==========================================
    # 3. STONE PILLARS (The frame)
    # ==========================================
    # Left Pillar (r = -3) and Right Pillar (r = 3)
    for r in [-3, 3]:
        # Base
        editor.placeBlock(get_pos(r, 0, 0), PILLAR_BASE)
        # Shaft
        for u in range(1, 6):
            editor.placeBlock(get_pos(r, u, 0), PILLAR_SHAFT)
        # Capital
        editor.placeBlock(get_pos(r, 6, 0), PILLAR_BASE)
        
        # Add a wall torch on the front face of the pillar
        editor.placeBlock(get_pos(r, 3, -1), TORCH)

    # ==========================================
    # 4. GOTHIC ARCHWAY
    # ==========================================
    # Base curve of the arch
    editor.placeBlock(get_pos(-2, 6, 0), ARCH_STAIR_LEFT)
    editor.placeBlock(get_pos(-1, 7, 0), ARCH_STAIR_LEFT)
    
    editor.placeBlock(get_pos(2, 6, 0), ARCH_STAIR_RIGHT)
    editor.placeBlock(get_pos(1, 7, 0), ARCH_STAIR_RIGHT)
    
    # Center Peak
    editor.placeBlock(get_pos(0, 8, 0), PILLAR_SHAFT)
    editor.placeBlock(get_pos(0, 7, 0), ARCH_STAIR_UPSIDEDOWN) # Corbel under the peak
    
    # Hanging Lantern in the center of the arch
    editor.placeBlock(get_pos(0, 6, 0), CHAIN)
    editor.placeBlock(get_pos(0, 5, 0), LANTERN)

    # ==========================================
    # 5. SWUNG-OPEN MASSIVE DOORS
    # ==========================================
    # Instead of actual Minecraft doors, we build huge 2-block wide, 5-block tall 
    # wooden slabs attached to the inner frame, jutting "forward" (f=1, f=2) 
    # to look like they have been thrown open to welcome students.
    
    # Left Door
    for f in [1, 2]:
        for u in range(0, 5):
            editor.placeBlock(get_pos(-2, u, f), DOOR_WOOD)
            # Add trapdoors on the edge for a heavy iron-banded/paneled look
            editor.placeBlock(get_pos(-1, u, f), DOOR_TRIM)
            
    # Right Door
    for f in [1, 2]:
        for u in range(0, 5):
            editor.placeBlock(get_pos(2, u, f), DOOR_WOOD)
            editor.placeBlock(get_pos(1, u, f), DOOR_TRIM)

RNG_SEED = None

def main():
    if RNG_SEED is not None:
        random.seed(RNG_SEED)

    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()
    editor.loadWorldSlice(cache=True)

    cx = build_area.begin.x + 630
    cz = build_area.begin.z + 320
    base_y = -61
    origin = (cx - 2, base_y, cz - 8)
    
    # Randomly pick orientation for testing
    chosen_direction = random.choice(["n-s", "e-w"])
    
    print(f"Building {chosen_direction} corridor at {origin}...")
    
    # --- TEST THE GRAND ENTRANCE ---
    # Placing it at the start coordinates of the origin so you can see it immediately
    door_facing = "south" if chosen_direction == "n-s" else "east"
    build_grand_arched_entrance(editor, origin[0], origin[1], origin[2], facing=door_facing)

    # CRITICAL: Always flush the buffer before exiting to prevent GDPC crashes!
    editor.flushBuffer()
    print("Corridor and Entrance complete!")

if __name__ == "__main__":
    main()