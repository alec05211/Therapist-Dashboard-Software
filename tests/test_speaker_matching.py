import unittest

from speaker_matching import suggest_assignments


class SpeakerMatchingTests(unittest.TestCase):
    def test_swapped_roles_and_split_labels(self):
        references = {"therapist": (1, 0), "client": (0, 1)}
        clips = ([("PATIENT_0", (1, 0))] * 3
                 + [("CLINICIAN_1", (1, 0))] * 3
                 + [("CLINICIAN_0", (0, 1))] * 3)
        matches = suggest_assignments(clips, references, threshold=0.8, margin=0.12)
        self.assertEqual({label: result["profile_id"] for label, result in matches.items()},
                         {"PATIENT_0": "therapist", "CLINICIAN_1": "therapist", "CLINICIAN_0": "client"})

    def test_conflicting_and_unknown_voices_stay_unassigned(self):
        references = {"therapist": (1, 0), "client": (0, 1)}
        clips = ([("mixed", (1, 0))] * 4 + [("mixed", (0, 1))]
                 + [("unknown", (1, 1))] * 5 + [("short", (0, 1))] * 2)
        self.assertEqual(suggest_assignments(clips, references, threshold=0.8, margin=0.12), {})
