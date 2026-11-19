import copy
import unittest
from wednesday_stale_week_gate import check, GateError

class TestGate(unittest.TestCase):
    def setUp(self):
        self.target = dict(operation='WEDNESDAY_FREEZE', season=2026, week=11, cutoff_at='2026-11-18T16:00:00Z')
        self.schedule = dict(season=2026, updatedAt='2026-11-18T15:00:00Z', weeks=[dict(week=11,games=[dict(id='101',date='2026-11-19T20:00:00Z',home='H',away='A')])])
        self.draft = dict(season=2026,week=11,generatedAt='2026-11-18T15:30:00Z',games=copy.deepcopy(self.schedule['weeks'][0]['games']))
        self.shadow = dict(self.draft,status='EXPERIMENTAL_SHADOW_ONLY')
    def reject(self, code):
        with self.assertRaises(GateError) as ctx:
            check(self.target,self.schedule,self.draft,self.shadow)
        self.assertEqual(ctx.exception.code,code)
    def test_matching(self): self.assertEqual(check(self.target,self.schedule,self.draft,self.shadow),('101',))
    def test_both_stale(self):
        self.draft['week']=self.shadow['week']=8
        self.reject('STALE_WEEK_INPUT')
    def test_one_stale(self):
        self.shadow['week']=8
        self.reject('STALE_WEEK_INPUT')
    def test_game_id_mismatch(self):
        self.shadow['games'][0]['id']='102'
        self.reject('GAME_ID_MISMATCH')
    def test_game_metadata_mismatch(self):
        self.shadow['games'][0]['home']='OTHER'
        self.reject('GAME_METADATA_MISMATCH')
    def test_post_cutoff_schedule(self):
        self.schedule['updatedAt']='2026-11-18T18:57:31Z'
        self.reject('POST_CUTOFF_SCHEDULE')
    def test_post_cutoff_input(self):
        self.draft['generatedAt']='2026-11-18T16:01:00Z'
        self.reject('POST_CUTOFF_INPUT')
    def test_missing_week(self):
        self.target['week']=12
        self.reject('TARGET_WEEK_MISSING')
    def test_duplicate_ids(self):
        self.schedule['weeks'][0]['games'].append(copy.deepcopy(self.schedule['weeks'][0]['games'][0]))
        self.reject('INVALID_SCHEDULE_IDS')
    def test_wrong_operation(self):
        self.target['operation']='GRADE'
        self.reject('INVALID_OPERATION')
    def test_invalid_shadow_status(self):
        self.shadow['status']='OFFICIAL'
        self.reject('INVALID_SHADOW_STATUS')
    def test_target_season_mismatch(self):
        self.target['season']=2025
        self.reject('TARGET_SCHEDULE_MISMATCH')

if __name__=='__main__': unittest.main()
