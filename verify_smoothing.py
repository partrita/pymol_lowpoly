from lowpoly import laplacian_smooth

def test_smoothing():
    # Simple pyramid
    # Base: (-1,-1,0), (1,-1,0), (1,1,0), (-1,1,0)
    # Peak: (0,0,1)
    # 4 faces
    
    verts = [
        [-1.0, -1.0, 0.0], # 0
        [ 1.0, -1.0, 0.0], # 1
        [ 1.0,  1.0, 0.0], # 2
        [-1.0,  1.0, 0.0], # 3
        [ 0.0,  0.0, 1.0]  # 4
    ]
    
    faces = [
        [0, 1, 4],
        [1, 2, 4],
        [2, 3, 4],
        [3, 0, 4],
        [0, 3, 2], [0, 2, 1] # Base pairs (approx)
    ]
    
    print("Original Peak:", verts[4])
    
    # Smooth
    # Peak (4) is connected to 0, 1, 2, 3.
    # Neighbors of 4 are 0,1,2,3.
    # Avg of neighbors z = 0.
    # Peak z=1.
    # New Peak z = 1 + (0 - 1)*0.5 = 0.5.
    
    smoothed = laplacian_smooth(verts, faces, iterations=1, lambda_factor=0.5)
    
    print("Smoothed Peak:", smoothed[4])
    
    if smoothed[4][2] < 1.0:
        print("Smoothing WORKED: Peak lowered.")
    else:
        print("Smoothing FAILED: Peak unchanged.")

if __name__ == "__main__":
    test_smoothing()
