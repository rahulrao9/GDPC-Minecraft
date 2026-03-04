from gdpc import Editor, Block
from collections import Counter

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

def main():
    editor = Editor(buffering=True)
    build_area = editor.getBuildArea()
    print("Reloading bare terrain data...")
    world_slice = editor.loadWorldSlice(build_area.toRect(), cache=True)

    # Pass the editor into the palette function
    env_wall, env_roof, env_roof_stair, is_snowy = get_biome_palette(editor, world_slice, build_area)

if __name__ == "__main__":
    main()