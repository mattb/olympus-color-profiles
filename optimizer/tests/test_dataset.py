import unittest
from omfit.dataset import source_pairs
class DatasetTests(unittest.TestCase):
    def row(self,i,camera='PEN-F',role='train',group='one',orientation=1):
        return dict(id=str(i),raw='/fixture/'+str(i)+'.ORF',sha256='hash',camera=camera,role=role,
            scene_group=group,initial=[53,0,0,0],metadata=dict(CropWidth=5184,CropHeight=3888,Orientation=orientation))
    def test_primary_representative_and_splits_preserved(self):
        sample=dict(selected=[self.row(0),self.row(1),self.row(2,role='dev'),self.row(3,camera='E-M10MarkII')])
        pairs=source_pairs(sample)
        self.assertEqual([p['primary_train']for p in pairs],[True,False,False,True])
        self.assertEqual([p['role']for p in pairs],['train','train','dev','train'])
        self.assertTrue(pairs[1]['diagnostic_only'])
        self.assertFalse(pairs[2]['diagnostic_only'])
    def test_rotation_and_full_crop_geometry(self):
        p=source_pairs(dict(selected=[self.row(0,orientation=8)]))[0]
        self.assertEqual(p['rotate'],270);self.assertEqual(p['developed_size'],[3888,5184]);self.assertEqual(p['resize'],[600,800])
    def test_controlled_scene_policy_rejected_if_changed(self):
        row=self.row(0);row['initial']=[54,0,0,0]
        with self.assertRaises(ValueError):source_pairs(dict(selected=[row]))
    def test_no_duplicate_ids(self):
        with self.assertRaises(ValueError):source_pairs(dict(selected=[self.row(0),self.row(0)]))

class AsShotDatasetTests(unittest.TestCase):
    row=DatasetTests.row
    def test_as_shot_omits_unused_WB_overrides(self):
        from omfit.model import Layout
        p=source_pairs(dict(selected=[self.row(0)]),scene_wb_anchor='as_shot')[0]
        self.assertEqual(p['scene_wb_anchor'],'as_shot')
        self.assertFalse(p['free_wb_ablation_compatible'])
        settings=Layout('stock').settings(p,Layout('stock').start(p['initial']),'gpu',full=True)
        self.assertNotIn('white_balance_mode',settings['raw_overrides'])
        self.assertNotIn('custom_wb2',settings['raw_overrides'])
        self.assertEqual(settings['raw_overrides']['exposure_bias'],[0,3])
    def test_as_shot_WB_placeholder_unused_but_exposure_explicit(self):
        row=self.row(0);row['initial']=[74,4,-2,0]
        p=source_pairs(dict(selected=[row]),scene_wb_anchor='as_shot')[0]
        self.assertIn('unused placeholders',p['initial_wb_policy'])
        row['initial'][3]=1
        with self.assertRaises(ValueError):source_pairs(dict(selected=[row]),scene_wb_anchor='as_shot')
    def test_unknown_anchor_rejected(self):
        with self.assertRaises(ValueError):source_pairs(dict(selected=[self.row(0)]),scene_wb_anchor='auto_guess')

if __name__=='__main__':unittest.main()
