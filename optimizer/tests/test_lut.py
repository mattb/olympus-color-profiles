import tempfile
import os
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
from omfit.lut import load_cube,apply_cube,generate_target
from omfit.color import SRGB,rgb

class CubeTests(unittest.TestCase):
    def cube(self,folder,transform=lambda r,g,b:(r,g,b),size=2,domain=''):
        p=Path(folder)/'look.cube'
        with p.open('w') as f:
            f.write(f'TITLE "test # quoted"\nLUT_3D_SIZE {size}\n{domain}')
            for b in np.linspace(0,1,size):
                for g in np.linspace(0,1,size):
                    for r in np.linspace(0,1,size):f.write(' '.join(map(str,transform(r,g,b)))+'\n')
        return load_cube(p)
    def test_identity_and_chunk_invariance(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.cube(d);x=np.random.default_rng(42).integers(0,256,(9,11,3),dtype=np.uint8)
            a=apply_cube(x,c,chunk_rows=1);np.testing.assert_allclose(a,x/255.,atol=3e-8)
            np.testing.assert_array_equal(a,apply_cube(x,c,chunk_rows=20))
    def test_red_fastest_channel_swap_and_bias(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.cube(d,lambda r,g,b:(b+.1,r,g))
            x=np.array([[[.2,.4,.8],[1.,0.,0.]]])
            np.testing.assert_allclose(apply_cube(x,c),[[[.9,.2,.4],[.1,1.,0.]]],atol=1e-7)
    def test_interior_trilinear(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.cube(d,lambda r,g,b:(r*g,g*b,r*b),size=3)
            x=np.array([[[.23,.62,.79]]]);r,g,b=x[0,0]
            np.testing.assert_allclose(apply_cube(x,c),[[[r*g,g*b,r*b]]],atol=1e-7)
    def test_explicit_nondefault_domain_and_clamp(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.cube(d,domain='DOMAIN_MIN -1 0 1\nDOMAIN_MAX 1 2 3\n')
            np.testing.assert_allclose(apply_cube(np.array([[[0.,1.,2.],[-5.,8.,3.]]]),c),[[[.5,.5,.5],[0,1,1]]])
    def test_output_not_clipped_until_writer(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.cube(d,lambda r,g,b:(r+1,g,b-.1))
            self.assertGreater(apply_cube(np.ones((1,1,3)),c)[0,0,0],1.)
            src=Path(d)/'source.png';Image.new('RGB',(8,8),(255,255,255)).save(src,icc_profile=SRGB)
            p=Path(d)/'target.png';proof=generate_target(src,p,c)
            self.assertGreater(proof['clipped_channel_fraction'],0)
            with Image.open(p) as im:self.assertEqual(im.info['icc_profile'],SRGB)
            with self.assertRaises(FileExistsError):generate_target(src,p,c)
    def test_color_managed_tagged_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.cube(d);src=Path(d)/'source.png';Image.new('RGB',(16,16),(90,125,190)).save(src,icc_profile=SRGB)
            for ext in ('png','jpg'):
                dst=Path(d)/('out.'+ext);proof=generate_target(src,dst,c)
                with Image.open(dst) as im:self.assertEqual(im.info['icc_profile'],SRGB)
                np.testing.assert_allclose(rgb(dst),rgb(src),atol=1)
                self.assertTrue(proof['synthetic']);self.assertFalse(proof['real_film_ground_truth'])
    def test_malformed_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.cube'
            for text in ('LUT_1D_SIZE 2\n0 0 0\n','LUT_3D_SIZE 2\n0 0 0\n','LUT_3D_SIZE 2\nDOMAIN_MAX 0 1 1\n'+'0 0 0\n'*8,'LUT_3D_SIZE 2\n'+'nan 0 0\n'*8):
                p.write_text(text)
                with self.assertRaises(ValueError):load_cube(p)
    def test_nonfinite_input_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.cube(d)
            with self.assertRaises(ValueError):apply_cube(np.full((1,1,3),np.nan),c)
    def test_acquired_cube_if_available(self):
        configured = os.environ.get('OMFIT_TEST_LUT_ROOT')
        if not configured:self.skipTest('Optional acquired LUT dataset: set OMFIT_TEST_LUT_ROOT')
        root=Path(configured)
        paths=sorted(root.glob('*.cube'))
        if not paths:self.skipTest('Optional locally acquired dataset absent')
        for p in paths:
            c=load_cube(p);self.assertEqual(c.size,33)
            out=apply_cube(np.array([[[.2,.4,.6]]]),c)
            self.assertTrue(np.isfinite(out).all())

if __name__=='__main__':unittest.main()
