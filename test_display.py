import unittest
from streamlit_app import display_frame


class DisplayTests(unittest.TestCase):
    def test_calibrated_probability_only_and_input_preserved(self):
        rows = [dict(hit_prob=.63, model_prob=.91, raw_model_prob=.98,
                     p_if_plays=.9, play_prob=.7, nested=dict(raw_model_prob=.99)),
                dict(blended_prob=.61, model_prob=.88)]
        frame = display_frame(rows)
        self.assertEqual(frame['Model %'].tolist(), [.63, .61])
        self.assertEqual(frame.columns.tolist(), ['Model %'])
        self.assertEqual(rows[0]['raw_model_prob'], .98)

    def test_no_raw_fallback(self):
        frame = display_frame([dict(model_prob=.9, raw_model_prob=.99)])
        self.assertNotIn('Model %', frame)
        self.assertEqual(frame.columns.tolist(), [])
