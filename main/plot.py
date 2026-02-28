from gdpc import Editor, Block
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from gdpc.geometry import Rect, Box
import math
import random

######### STORAGE #########
MAX_WATER_FRACTION = 0.10 # percentage of water allowed to fill to make the best flat patch
VEGETATION_KEYWORDS = (
    "leaves",
    "log"
    # "grass",
    # "fern",
    # "flower",
    # "bush",
    # "vine",
    # "sapling"
)

######### init #########
editor = Editor(buffering=True)
build_area = editor.getBuildArea()
x0, y0, z0 = build_area.begin
x1, y1, z1 = build_area.end
rect = build_area.toRect()
world_slice = editor.loadWorldSlice(rect)
height_map = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"] # to get a better estimate of the ground excluding vegetation
width, depth = height_map.shape

########## Support Funcs #########

def is_water(block_id):
    return "water" in block_id

def is_vegetation(block_id):
    return any(k in block_id for k in VEGETATION_KEYWORDS)

def distance_to_nearest_water(water_positions, px, pz):
    if not water_positions:
        return 999.0
    return min(((px - wx) ** 2 + (pz - wz) ** 2) ** 0.5 for wx, wz in water_positions)

def _block_id(block):
    bid = getattr(block, "id", None) or ""
    return bid.replace("minecraft:", "", 1)

def place_if_different(pos, block):
    """Place block only if different from current (faster re-runs and less HTTP)."""
    try:
        cur = editor.getBlock(pos)
        if _block_id(cur) == _block_id(block):
            return
    except Exception:
        pass
    editor.placeBlock(pos, block)

def compute_surface_maps():
    xs, zs = height_map.shape
    water_map = np.zeros((xs, zs), dtype=np.uint8)
    vegetation_map = np.zeros((xs, zs), dtype=np.uint8)

    for x in range(xs):
        for z in range(zs):
            y = height_map[x, z] - 1
            block_id = world_slice.getBlock((x, y, z)).id

            if block_id.endswith("water"):
                water_map[x, z] = 1
            elif is_vegetation(block_id):
                vegetation_map[x, z] = 1

    return water_map, vegetation_map

def patch_cost(patch_height, patch_water, patch_veg, a, b, c):
    h_variance = np.var(patch_height)  # how flat the patch is [web:17]
    water_count = np.sum(patch_water)
    veg_count = np.sum(patch_veg)

    return (
        a * h_variance +
        b * water_count +
        c * veg_count
    ), h_variance, water_count, veg_count

water_map, vegetation_map = compute_surface_maps()

######### Finding Best Location to build our Castle #########

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

######### Lets plot it! #########
plot_height_map(height_map)

def find_best_location(patch_size):
    # weights for the cost function
    a = 2.0   # variance weight (flatness)
    b = 3.0   # water penalty
    c = 0.2   # vegetation penalty

    best_pos = None
    best_cost = float("inf")

    # First pass: only consider patches with water_count == 0
    for x in range(width - patch_size):
        for z in range(depth - patch_size):

            patch_height = height_map[x:x+patch_size, z:z+patch_size]
            patch_water  = water_map[x:x+patch_size, z:z+patch_size]
            patch_veg    = vegetation_map[x:x+patch_size, z:z+patch_size]

            cost, h_var, water_count, veg_count = patch_cost(
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

            cost, h_var, water_count, veg_count = patch_cost(
                patch_height, patch_water, patch_veg, a, b, c
            )

            if cost < best_cost:
                best_cost = cost
                best_pos = (x, z)

    return best_pos, False


def clear_trees_from_plot(plot_pos, patch_size):
    px, pz = plot_pos
    print(f"Scanning {patch_size}x{patch_size} plot at {plot_pos} for trees...")
    
    trees_found = 0
    
    for dx in range(patch_size):
        for dz in range(patch_size):
            x = px + dx
            z = pz + dz
            
            scan_y = height_map[x, z] -1 
            block_id = world_slice.getBlock((x, scan_y, z)).id
            
            if "log" in block_id or "stem" in block_id:
                gx = x0 + x
                gz = z0 + z
                trees_found += 1
                for y in range(scan_y, scan_y + 40):
                    editor.placeBlock((gx, y, gz), Block("minecraft:air"))

### max we level to +- 2 blocks height. we clear the trees on the path and floor max 15% of the water on the patch
def leveling(plot_pos, patch_size, fill_block="minecraft:dirt"):
    px, pz = plot_pos
    editor.buffering = True

    patch = height_map[px:px+patch_size, pz:pz+patch_size]
    target_height = int(np.median(patch))

    print("Target leveling height (median):", target_height)
    total_columns = patch_size * patch_size
    water_columns = []

    for dx in range(patch_size):
        for dz in range(patch_size):
            x = px + dx
            z = pz + dz
            h = height_map[x, z]
            block_id = world_slice.getBlock((x, h - 1, z)).id
            if block_id.endswith("water"):
                water_columns.append((x, z))

    max_water_fill = int(0.15 * total_columns)
    water_filled = 0
    clear_trees_from_plot(plot_pos, patch_size)
    for dx in range(patch_size):
        for dz in range(patch_size):

            x = px + dx
            z = pz + dz

            gx = x0 + x
            gz = z0 + z

            original_height = height_map[x, z]

            for y in range(original_height, original_height + 80):
                bid = world_slice.getBlock((x, y, z)).id
                if bid != "minecraft:air":
                    editor.placeBlock((gx, y, gz), Block("minecraft:air"))

            surface_block = world_slice.getBlock((x, original_height - 1, z)).id

            if surface_block.endswith("water") and water_filled < max_water_fill:
                for depth in range(2):
                    water_y = original_height - 1 - depth
                    bid = world_slice.getBlock((x, water_y, z)).id
                    if bid.endswith("water"):
                        editor.placeBlock((gx, water_y, gz), Block(fill_block))
                water_filled += 1

            height_diff = target_height - original_height
            clamped_diff = max(-2, min(2, height_diff))
            new_height = original_height + clamped_diff

            if original_height > new_height:
                for y in range(new_height, original_height):
                    editor.placeBlock((gx, y, gz), Block("minecraft:air"))

            elif original_height < new_height:
                for y in range(original_height, new_height):
                    editor.placeBlock((gx, y, gz), Block(fill_block))

            base_block = world_slice.getBlock((x, original_height - 1, z)).id
            editor.placeBlock((gx, new_height - 1, gz), Block(base_block))
    
    print(f"Leveled with ±2 constraint and max 15% water fill at {plot_pos}")
# def leveling(plot_pos, patch_size, fill_block="minecraft:dirt"):
#     px, pz = plot_pos
#     editor.buffering = True

#     patch = height_map[px:px+patch_size, pz:pz+patch_size]
#     target_height = int(np.median(patch))
#     print("Target leveling height (median):", target_height)
    
#     total_columns = patch_size * patch_size
#     max_water_fill = int(0.15 * total_columns)
#     water_filled = 0

#     for dx in range(patch_size):
#         for dz in range(patch_size):
#             x = px + dx
#             z = pz + dz
#             gx = x0 + x
#             gz = z0 + z
#             original_height = height_map[x, z]

#             # FIXED CLEARING: Simple, reliable, works everywhere
#             for y in range(original_height, 320):  # Clears trees/structures too!
#                 editor.placeBlock((gx, y, gz), Block("minecraft:air"))

#             # Your existing water fill + height adjust logic stays EXACTLY the same...
#             surface_block = world_slice.getBlock((x, original_height - 1, z)).id
#             if surface_block.endswith("water") and water_filled < max_water_fill:
#                 for depth in range(2):
#                     water_y = original_height - 1 - depth
#                     bid = world_slice.getBlock((x, water_y, z)).id
#                     if bid.endswith("water"):
#                         editor.placeBlock((gx, water_y, gz), Block(fill_block))
#                 water_filled += 1

#             height_diff = target_height - original_height
#             clamped_diff = max(-2, min(2, height_diff))
#             new_height = original_height + clamped_diff

#             if original_height > new_height:
#                 for y in range(new_height, original_height):
#                     editor.placeBlock((gx, y, gz), Block("minecraft:air"))
#             elif original_height < new_height:
#                 for y in range(original_height, new_height):
#                     editor.placeBlock((gx, y, gz), Block(fill_block))

#             base_block = world_slice.getBlock((x, original_height - 1, z)).id
#             editor.placeBlock((gx, new_height - 1, gz), Block(base_block))

#     editor.flushBuffer()
#     print(f"Leveled {patch_size}x{patch_size} at {plot_pos}")


def main():
    patch_size = 40
    best_patch, is_ideal = find_best_location(patch_size)

    if not is_ideal:
        print("Warning: The plot is not ideal for Hogwarts to be build. Proceeding anyways...")

    leveling(best_patch, patch_size)


if __name__ == "__main__":
    main()
