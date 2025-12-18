import unittest
import math
import sys
import os
import tempfile
from unittest.mock import MagicMock

# Mocking is handled in conftest.py, but we access sys.modules['pymol'] in tests

import lowpoly

class TestLowPoly(unittest.TestCase):

    def test_calculate_normal(self):
        v1 = (0, 0, 0)
        v2 = (1, 0, 0)
        v3 = (0, 1, 0)
        # Right hand rule: x cross y = z
        normal = lowpoly.calculate_normal(v1, v2, v3)
        self.assertEqual(normal, (0.0, 0.0, 1.0))
        
    def test_vertex_clustering_simple(self):
        # Create a detailed grid of vertices that should collapse
        v_detailed = [
            (0.1, 0.1, 0.1), (0.9, 0.1, 0.1), (0.1, 0.9, 0.1) 
        ]
        factor = 1.0
        verts, faces = lowpoly.vertex_clustering(v_detailed, factor)
        
        # Should be 1 vertex, 0 faces
        self.assertEqual(len(verts), 1)
        self.assertEqual(len(faces), 0)
        
        # Triangle across cells
        v_large = [
            (0.1, 0.1, 0.1), 
            (1.5, 0.1, 0.1), 
            (0.1, 1.5, 0.1) 
        ]
        
        verts, faces = lowpoly.vertex_clustering(v_large, factor)
        self.assertEqual(len(verts), 3)
        self.assertEqual(len(faces), 1)
        
    def test_parse_obj(self):
        obj_content = """
        v 0.0 0.0 0.0
        v 1.0 0.0 0.0
        v 0.0 1.0 0.0
        f 1 2 3
        """
        
        fd, path = tempfile.mkstemp(suffix=".obj")
        try:
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(obj_content)
            
            verts, faces = lowpoly.parse_obj(path)
            
            self.assertEqual(len(verts), 3)
            self.assertEqual(verts[0], [0.0, 0.0, 0.0])
            self.assertEqual(len(faces), 1)
            self.assertEqual(faces[0], [0, 1, 2])
            
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_lowpoly_string_arg(self):
        # Verify that passing a string factor works
        obj_content = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3"
        
        import sys
        pymol_mock = sys.modules['pymol']
        
        # Mocks
        pymol_mock.cmd.create = MagicMock()
        pymol_mock.cmd.delete = MagicMock()
        pymol_mock.cmd.count_atoms.return_value = 10
        pymol_mock.cmd.get_object_list.return_value = ["dummy_obj"]
        
        def side_effect_save(filename, selection):
            with open(filename, 'w') as f:
                f.write(obj_content)
        pymol_mock.cmd.save.side_effect = side_effect_save
        
        # Iterate mock
        def side_effect_iterate(selection, expression, space):
            if 'stored' in space:
                space['stored'].add('A')
        pymol_mock.cmd.iterate.side_effect = side_effect_iterate
        
        # Run
        try:
            lowpoly.lowpoly("dummy", factor="1.5")
        except TypeError:
            self.fail("lowpoly raised TypeError with string factor")
        
        # Verify
        pymol_mock.cmd.load_cgo.assert_called()

    def test_coloring_chains(self):
        import sys
        pymol_mock = sys.modules['pymol']
        
        # Mocks
        pymol_mock.cmd.create = MagicMock()
        pymol_mock.cmd.delete = MagicMock()
        pymol_mock.cmd.count_atoms.return_value = 10
        pymol_mock.cmd.get_object_list.return_value = ["dummy_obj"]
        
        # Mock iterating over 2 chains: A and B
        def side_effect_iterate(selection, expression, space):
            if 'stored' in space:
                space['stored'].add('A')
                space['stored'].add('B')
        pymol_mock.cmd.iterate.side_effect = side_effect_iterate
        
        # Mock save
        obj_content = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3"
        def side_effect_save(filename, selection):
            with open(filename, 'w') as f:
                f.write(obj_content)
        pymol_mock.cmd.save.side_effect = side_effect_save
        
        pymol_mock.cmd.load_cgo.reset_mock()
        
        # Run with small factor to ensure geometry is preserved
        lowpoly.lowpoly("dummy", factor=0.5)
        
        # Verify creation/deletion
        pymol_mock.cmd.create.assert_called()
        pymol_mock.cmd.delete.assert_called()
        
        # Check colors
        pymol_mock.cmd.load_cgo.assert_called()
        args, _ = pymol_mock.cmd.load_cgo.call_args
        cgo_list = args[0]
        
        # Opcode 6.0 is COLOR
        color_ops = [x for x in cgo_list if x == 6.0]
        self.assertGreaterEqual(len(color_ops), 2)

if __name__ == '__main__':
    unittest.main()
