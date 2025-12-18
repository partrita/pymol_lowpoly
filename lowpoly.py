import math
import os
import tempfile
import random
from pymol import cmd, cgo

def lowpoly(selection="all", factor=7.5, color=None, cartoon_style=True, name=None, outline_color="black", rounding=1):
    """
    DESCRIPTION
    
    Transforms a molecular surface into a Low-Poly (faceted) aesthetic.
    
    USAGE
    
    lowpoly [selection], [factor], [color], [cartoon_style], [name], [outline_color], [rounding]
    
    ARGUMENTS
    
    selection = string: atom selection (default: all)
    factor = float: simplification intensity (grid size in Angstroms). Default 7.5.
    color = string: 
        - Single color (e.g. 'red') -> Apply to everything
        - Space separated list (e.g. 'red blue green') -> Cycle through chains
        - 'none' -> Do not bake colors (allows using 'color' command later)
        - None -> Use default pastel palette
    cartoon_style = boolean: apply matte/outlined rendering settings and high quality defaults (default: True)
    name = string: output object name.
    outline_color = string: color of the ray-traced outline (default: black)
    rounding = int: iterations of smoothing to soften the mesh (default: 1)
    """
    
    # 1. Input Validation
    try:
        factor = float(factor)
        rounding = int(rounding)
    except (ValueError, TypeError):
        print(f"Error: factor/rounding parameters must be numbers.")
        return
    
    if factor <= 0.1: factor = 0.5 # Safety clamp
    
    # Color Logic
    custom_palette = None
    bake_colors = True
    
    if color:
        if isinstance(color, str):
            clean_color = color.strip()
            if clean_color.lower() == 'none':
                bake_colors = False
            elif len(clean_color.split()) > 1:
                # Custom palette provided as "col1 col2 col3"
                custom_palette = clean_color.split()
            else:
                # Single color
                color = clean_color
        # If passed as list from Python API
        elif isinstance(color, (list, tuple)):
            custom_palette = color

    # Default Pastel Palette
    pastel_colors = [
        (0.60, 0.75, 0.90), # Blue
        (0.60, 0.90, 0.60), # Green
        (0.90, 0.60, 0.60), # Red
        (0.90, 0.90, 0.60), # Yellow
        (0.80, 0.60, 0.90), # Purple
        (0.60, 0.90, 0.90), # Cyan
        (0.90, 0.80, 0.60), # Orange
        (0.70, 0.70, 0.70), # Grey
    ]

    # 2. Output Name Handling
    if name is None:
        obj_list = cmd.get_object_list(selection)
        base = obj_list[0] if obj_list else "lowpoly"
        name = f"{base}_lowpoly"

    print(f"Generating Low-Poly: {name} (Factor={factor}, Rounding={rounding})")

    # 3. Create Temp Object for Surface Extraction
    temp_obj = f"tmp_lp_{random.randint(10000,99999)}"
    cmd.create(temp_obj, selection)
    
    # Optimize input surface quality for better extraction
    cmd.set("surface_quality", 1, temp_obj) 
    
    cmd.hide("everything", temp_obj)
    cmd.show("surface", temp_obj)
    
    # 4. Process Chains
    stored = set()
    try:
        cmd.iterate(temp_obj, "stored.add(chain)", space={'stored': stored})
    except Exception as e:
        print(f"Warning: Could not iterate chains: {e}")
        stored.add('')
        
    chains = sorted(list(stored))
    if not chains: chains = ['']
    
    full_cgo = []
    
    try:
        for idx, chain in enumerate(chains):
            if chain:
                sub_sel = f"{temp_obj} and chain \"{chain}\""
            else:
                sub_sel = temp_obj
            
            if cmd.count_atoms(sub_sel) == 0:
                continue

            # 4b. Extract OBJ
            fd, temp_path = tempfile.mkstemp(suffix=".obj")
            os.close(fd)
            
            try:
                cmd.save(temp_path, sub_sel)
                vertices, faces = parse_obj(temp_path)
            except Exception as e:
                continue
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            if not vertices:
                continue
                
            # 4c. Decimate
            flat_verts = []
            for face in faces:
                v_face = [vertices[i] for i in face]
                for i in range(1, len(v_face)-1):
                    flat_verts.append(v_face[0])
                    flat_verts.append(v_face[i])
                    flat_verts.append(v_face[i+1])
            
            if not flat_verts: continue
            
            simp_verts, simp_faces = vertex_clustering(flat_verts, factor)
            
            # Smoothing (Round off sharp corners)
            if rounding > 0:
                print(f"  - Smoothing chain {chain} ({rounding} iterations)...")
                simp_verts = laplacian_smooth(simp_verts, simp_faces, rounding)
            
            # 4d. Determine Color for this chain
            rgb = None
            if bake_colors:
                try:
                    if custom_palette:
                        c_name = custom_palette[idx % len(custom_palette)]
                        rgb = cmd.get_color_tuple(c_name)
                    elif color and not custom_palette:
                        rgb = cmd.get_color_tuple(color)
                    else:
                        rgb = pastel_colors[idx % len(pastel_colors)]
                except Exception as e:
                    print(f"Color Warning: {e}. Using default.")
                    rgb = (0.8, 0.8, 0.8)
                
            # 4e. Append CGO
            full_cgo.extend([cgo.BEGIN, cgo.TRIANGLES])
            if rgb:
                full_cgo.extend([cgo.COLOR, *rgb])
            
            for f in simp_faces:
                v1 = simp_verts[f[0]]
                v2 = simp_verts[f[1]]
                v3 = simp_verts[f[2]]
                
                norm = calculate_normal(v1, v2, v3)
                
                full_cgo.extend([cgo.NORMAL, *norm])
                full_cgo.extend([cgo.VERTEX, *v1])
                full_cgo.extend([cgo.VERTEX, *v2])
                full_cgo.extend([cgo.VERTEX, *v3])
                
            full_cgo.append(cgo.END)
            
    finally:
        cmd.delete(temp_obj)
        
    # 5. Load Final Object
    if not full_cgo:
        print("Error: Low-poly generation resulted in empty mesh. Try a smaller factor.")
        return
        
    cmd.load_cgo(full_cgo, name)
    print(f"Success: Created '{name}'.")
    
    # 6. Apply Pretty Settings (Defaults)
    if cartoon_style:
        cmd.set("specular", 0.0)
        cmd.set("shininess", 0.0)
        cmd.set("light_count", 2)
        cmd.set("ambient", 0.9)
        cmd.set("ray_trace_mode", 1) # Outline
        cmd.set("ray_trace_color", outline_color) # Outline Color
        cmd.set("antialias", 6)
        cmd.set("ray_shadow", 1)
        cmd.set("ray_texture", 4) # Texture effect
        
        # User requested per-chain discrete colors and high quality defaults
        cmd.set("cartoon_discrete_colors", 1)
        # surface_quality/cartoon_sampling apply to representations, 
        # but we act on CGO. Setting them globally helps other objects.
        cmd.set("surface_quality", 1)
        cmd.set("cartoon_sampling", 14)
        
        print(f"Applied 'Pretty' rendering settings (Ambient=0.9, Outline={outline_color}, DiscreteColors=On).")

def parse_obj(path):
    verts = []
    faces = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('v '):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('f '):
                # OBJ 1-indexed
                indices = [int(p.split('/')[0])-1 for p in line.split()[1:]]
                faces.append(indices)
    return verts, faces

def vertex_clustering(vertices, cell_size):
    # Grid hashing
    grid = {}
    for v in vertices:
        key = (
            int(math.floor(v[0]/cell_size)),
            int(math.floor(v[1]/cell_size)),
            int(math.floor(v[2]/cell_size))
        )
        if key not in grid: grid[key] = []
        grid[key].append(v)
    
    # Representative
    unique_verts = []
    cluster_map = {}
    
    for k, points in grid.items():
        # Average
        center = [sum(axis)/len(points) for axis in zip(*points)]
        cluster_map[k] = len(unique_verts)
        unique_verts.append(center)
        
    # Reconstruct Faces
    new_faces = []
    # Original 'vertices' list is a sequence of triangles (v0,v1,v2), (v3,v4,v5)...
    for i in range(0, len(vertices), 3):
        v1, v2, v3 = vertices[i], vertices[i+1], vertices[i+2]
        
        k1 = (int(math.floor(v1[0]/cell_size)), int(math.floor(v1[1]/cell_size)), int(math.floor(v1[2]/cell_size)))
        k2 = (int(math.floor(v2[0]/cell_size)), int(math.floor(v2[1]/cell_size)), int(math.floor(v2[2]/cell_size)))
        k3 = (int(math.floor(v3[0]/cell_size)), int(math.floor(v3[1]/cell_size)), int(math.floor(v3[2]/cell_size)))
        
        idx1, idx2, idx3 = cluster_map[k1], cluster_map[k2], cluster_map[k3]
        
        # Debounce (remove degenerate)
        if idx1 != idx2 and idx2 != idx3 and idx1 != idx3:
            new_faces.append((idx1, idx2, idx3))
            
    return unique_verts, new_faces

def laplacian_smooth(vertices, faces, iterations, lambda_factor=0.5):
    """
    Smooths the mesh by moving vertices towards the average of their neighbors.
    vertices: list of [x, y, z]
    faces: list of [i1, i2, i3]
    """
    # Build Adjacency
    adjacency = {i: set() for i in range(len(vertices))}
    for f in faces:
        adjacency[f[0]].add(f[1]); adjacency[f[0]].add(f[2])
        adjacency[f[1]].add(f[0]); adjacency[f[1]].add(f[2])
        adjacency[f[2]].add(f[0]); adjacency[f[2]].add(f[1])
        
    smoothed_verts = [list(v) for v in vertices]
    
    for _ in range(iterations):
        new_verts = []
        for i, v in enumerate(smoothed_verts):
            neighbors = list(adjacency[i])
            if not neighbors:
                new_verts.append(v)
                continue
            
            # Average neighbor position
            avg_x = sum(smoothed_verts[n][0] for n in neighbors) / len(neighbors)
            avg_y = sum(smoothed_verts[n][1] for n in neighbors) / len(neighbors)
            avg_z = sum(smoothed_verts[n][2] for n in neighbors) / len(neighbors)
            
            # Move towards average
            dx = (avg_x - v[0]) * lambda_factor
            dy = (avg_y - v[1]) * lambda_factor
            dz = (avg_z - v[2]) * lambda_factor
            
            new_verts.append([v[0]+dx, v[1]+dy, v[2]+dz])
        smoothed_verts = new_verts
        
    return smoothed_verts

def calculate_normal(v1, v2, v3):
    u = (v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2])
    v = (v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2])
    nx = u[1]*v[2] - u[2]*v[1]
    ny = u[2]*v[0] - u[0]*v[2]
    nz = u[0]*v[1] - u[1]*v[0]
    l = math.sqrt(nx*nx + ny*ny + nz*nz)
    if l == 0: return (0,0,1)
    return (nx/l, ny/l, nz/l)

# Register
cmd.extend("lowpoly", lowpoly)
