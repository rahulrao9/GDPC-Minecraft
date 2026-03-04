import random
import math
from gdpc import Editor, Block
from collections import Counter

import plot

def draw_debug_boundaries(editor, world_slice, build_area, plot, start_x, start_z, plot_size):
    """
    Draws a terrain-conforming 2-block high red boundary around the main build area 
    and outlines the optimal plot in green.
    """
    red_block = Block("red_concrete")
    green_block = Block("blue_concrete")

    # Helper function to get the exact surface Y for a specific X and Z
    def get_surface_y(x, z):
        local_x = x - build_area.begin.x
        local_z = z - build_area.begin.z
        
        # Ensure we are inside the loaded slice bounds to prevent errors
        if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
            return world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z]
        return 64 # Fallback if out of bounds

    # ---- 1. Red Boundary (2 blocks high) around the main plot ----
    # Draw along X-axis edges (Top and Bottom)
    for x in range(plot.x0, plot.x1 + 1):
        y_top = get_surface_y(x, plot.z0)
        y_bottom = get_surface_y(x, plot.z1)
        for y_offset in range(2):
            editor.placeBlock((x, y_top + y_offset, plot.z0), red_block)
            editor.placeBlock((x, y_bottom + y_offset, plot.z1), red_block)
            
    # Draw along Z-axis edges (Left and Right)
    for z in range(plot.z0, plot.z1 + 1):
        y_left = get_surface_y(plot.x0, z)
        y_right = get_surface_y(plot.x1, z)
        for y_offset in range(2):
            editor.placeBlock((plot.x0, y_left + y_offset, z), red_block)
            editor.placeBlock((plot.x1, y_right + y_offset, z), red_block)

    # ---- 2. Green Outline inside the optimal plot ----
    size_x = plot_size[0] if isinstance(plot_size, (list, tuple)) else plot_size
    size_z = plot_size[1] if isinstance(plot_size, (list, tuple)) else plot_size

    # Draw a 1-block high green outline that hugs the terrain
    for x in range(start_x, start_x + size_x):
        editor.placeBlock((x, get_surface_y(x, start_z), start_z), green_block)
        editor.placeBlock((x, get_surface_y(x, start_z + size_z - 1), start_z + size_z - 1), green_block)
        
    for z in range(start_z, start_z + size_z):
        editor.placeBlock((start_x, get_surface_y(start_x, z), z), green_block)
        editor.placeBlock((start_x + size_x - 1, get_surface_y(start_x + size_x - 1, z), z), green_block)
        
    # Drop a diamond block exactly in the center of the plot, on the surface
    center_x = start_x + (size_x // 2)
    center_z = start_z + (size_z // 2)
    editor.placeBlock((center_x, get_surface_y(center_x, center_z), center_z), Block("diamond_block"))


def main():
    editor = Editor(buffering=True)
    
    PLOT_SIZE = 60 
    print(f"Scouting terrain for the {PLOT_SIZE}x{PLOT_SIZE} building plot...")
    best_patch, is_ideal = plot.find_best_location(PLOT_SIZE)
    start_x, start_z = plot.x0 + best_patch[0], plot.z0 + best_patch[1]

    build_area = editor.getBuildArea()
    initial_world_slice = editor.loadWorldSlice(build_area.toRect(), cache=True)
    heights = []
    for dx in range(PLOT_SIZE):
        for dz in range(PLOT_SIZE):
            local_x, local_z = (start_x + dx) - build_area.begin.x, (start_z + dz) - build_area.begin.z
            if 0 <= local_x < build_area.size.x and 0 <= local_z < build_area.size.z:
                heights.append(initial_world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"][local_x][local_z])
    heights.sort()
    base_y = heights[int(len(heights) * 0.80)] - 1 

    # ... your existing code ...
    heights.sort()
    base_y = heights[int(len(heights) * 0.80)] - 1 

    # --- Call the terrain-hugging debug visualizer ---
    draw_debug_boundaries(editor, initial_world_slice, build_area, plot, start_x, start_z, PLOT_SIZE)

if __name__ == "__main__":
    main()