"""Selected-pair batch plans do not rerun frozen baseline-vs-baseline games."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.core.sandbox import ROOT
from arena.tournament import run_tournament, selected_pairings


class LadderPairingTests(unittest.TestCase):
    def test_pair_selection_is_canonical_and_retains_self_play(self):
        self.assertEqual(selected_pairings(4, [(3,1),(0,0),(2,0)]), [(0,0),(0,2),(1,3)])

    def test_duplicates_and_invalid_indices_are_rejected(self):
        for pairs in ([], [(0,1),(1,0)], [(0,2)], [(0,True)], [(0,-1)], [(0,1,2)], '0,1'):
            with self.subTest(pairs=pairs), self.assertRaises(ValueError): selected_pairings(2,pairs)

    def test_manifest_has_only_selected_pairs_and_resume_cannot_change_them(self):
        root=ROOT/'runs/development/ladder-pairing-tests'/uuid4().hex
        sources=[ROOT/'sdk/python/example',ROOT/'sdk/cpp/example',ROOT/'bots/public/Z-idle']
        maps=[ROOT/'maps/scrimmage/open-01.map']
        with patch('arena.tournament.run_benchmark',side_effect=AssertionError('planning must not run bots')):
            run_tournament(sources,maps,root,jobs=1,max_tasks=0,freeze_timing=True,pairings=[(0,2),(0,0)])
            m=json.loads((root/'manifest.json').read_text())
            self.assertEqual(m['request']['pairs'],[[0,0],[0,2]])
            self.assertEqual(len(m['tasks']),4)
            self.assertEqual({tuple(t['players']) for t in m['tasks']},{(0,0),(0,2),(2,0)})
            run_tournament(sources,maps,root,jobs=1,max_tasks=0,freeze_timing=True,pairings=[(2,0),(0,0)],resume=True)
            with self.assertRaisesRegex(ValueError,'changed'):
                run_tournament(sources,maps,root,jobs=1,max_tasks=0,freeze_timing=True,pairings=[(0,1)],resume=True)

    def test_ambiguous_selectors_and_identical_self_seeds_fail_before_output(self):
        root=ROOT/'runs/development/ladder-pairing-tests'/uuid4().hex
        args=([ROOT/'sdk/python/example',ROOT/'sdk/cpp/example'],[ROOT/'maps/scrimmage/open-01.map'],root)
        for options in ({'focus':0,'pairings':[(0,1)]}, {'include_self':['example#0'],'pairings':[(0,1)]},
                        {'seeds':(17,17),'pairings':[(0,0)]}):
            with self.assertRaises(ValueError): run_tournament(*args,jobs=1,max_tasks=0,**options)
            self.assertFalse(root.exists())


if __name__ == '__main__': unittest.main()
