import unittest
import pandas as pd
from src.Release.distance import Find_materials

class TestFindMaterials(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.find_materials = Find_materials()

    def test_init(self):
        self.assertIsInstance(self.find_materials.all_materials, pd.DataFrame)
        self.assertIsInstance(self.find_materials.otgruzki, pd.DataFrame)
        self.assertIsInstance(self.find_materials.method2, pd.DataFrame)
        self.assertIsInstance(self.find_materials.saves, pd.DataFrame)

    def test_jaccard_distance(self):
        str1 = "material"
        str2 = "materiel"
        distance = self.find_materials.jaccard_distance(str1, str2)
        self.assertGreaterEqual(distance, 0)
        self.assertLessEqual(distance, 1)

    def test_choose_based_on_similarity(self):
        text = "example material"
        first_ierar = "example hierarchy"
        ress = [0, 1, 2, 3, 4]
        result = self.find_materials.choose_based_on_similarity(text, first_ierar, ress)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 5)

    def test_find_top_materials_advanced(self):
        query = "example query"
        materials_df = pd.DataFrame({
            "Материал": [1, 2, 3, 4, 5],
            "Полное наименование материала": ["material1", "material2", "material3", "material4", "material5"]
        })
        result = self.find_materials.find_top_materials_advanced(query, materials_df)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), 5)

    def test_new_mat_prep(self):
        new_mat = "example material"
        result = self.find_materials.new_mat_prep(new_mat)
        self.assertIsInstance(result, str)

    def test_find_ei(self):
        new_mat = "example material"
        val_ei = "10"
        ei = "kg"
        result = self.find_materials.find_ei(new_mat, val_ei, ei)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)

    def test_paralell_rows(self):
        rows = [("example material", "10", "kg")]
        result = self.find_materials.paralell_rows(rows)
        self.assertIsInstance(result, str)

    def test_find_mats(self):
        row = "example material"
        val_ei = "10"
        ei = "kg"
        idx = 0
        self.find_materials.find_mats(row, val_ei, ei, idx)
        self.assertIn('material1_id', self.find_materials.poss[idx])

if __name__ == '__main__':
    unittest.main()