import unittest
from embedded_window import valid_request
class DesktopRequestTests(unittest.TestCase):
    def test_owner_and_expiry(self):
        good=dict(owner_pid=12,parent=30,generation=2,at=100)
        self.assertTrue(valid_request(good,12,101))
        for key,value in [('owner_pid',13),('parent',0),('parent',True),('generation',0),('at',70),('at',102)]:
            self.assertFalse(valid_request(dict(good,**{key:value}),12,101),(key,value))
    def test_invalid_request(self):
        for value in [None,[],{},'stale']:
            self.assertFalse(valid_request(value,12,101))
if __name__=='__main__':unittest.main()
