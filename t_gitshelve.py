# -*- coding: utf-8 -*-

import sys
import re
import unittest
import gitshelve
import exceptions

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO

class t_gitshelve(unittest.TestCase):
    def setUp(self):
        try: gitshelve.git('branch', '-D', 'test')
        except: pass

    def tearDown(self):
        try: gitshelve.git('branch', '-D', 'test')
        except: pass

    def testBasicInsertion(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test"
        shelf['foo/bar/baz.c'] = text

        self.assertEqual(text, shelf['foo/bar/baz.c'])

        def foo1(shelf):
            return shelf['foo/bar']
        self.assertRaises(exceptions.KeyError, foo1, shelf)

        del shelf
 
    def testBasicDeletion(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test"
        shelf['foo/bar/baz.c'] = text
        del shelf['foo/bar/baz.c']

        def foo2(shelf):
            return shelf['foo/bar/baz.c']
        self.assertRaises(exceptions.KeyError, foo2, shelf)

        shelf['foo/bar/baz.c'] = text
        del shelf['foo/bar']

        def foo4(shelf):
            return shelf['foo/bar/baz.c']
        self.assertRaises(exceptions.KeyError, foo4, shelf)

        del shelf

    def testInsertion(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test"
        shelf['foo/bar/baz.c'] = text

        buffer = StringIO()
        shelf.dump_objects(buffer)

        self.assertEqual(buffer.getvalue(), """tree: foo
  tree: bar
    blob: baz.c
""")

        hash1 = shelf.commit('first\n')
        hash2 = shelf.commit('second\n')
        self.assertEqual(hash1, hash2)

        buffer = StringIO()
        shelf.dump_objects(buffer)

        self.assertEqual(buffer.getvalue(), """tree e2c77cb8d1351b3b8598a48b35e907c6ef4ab1ee
  tree fc1242cafda37c67d3b314babb72b20483ddbfe5: foo
    tree 3578116a80d4802f4ec428b6c974a70834ecdc5a: bar
      blob f10da7954a47a56b9bef92d0c538d40b6344c20a: baz.c
""")

        hash3 = shelf.current_head()
        self.assertEqual(hash1, hash3)

        commit = gitshelve.git('cat-file', 'commit', 'test')
        self.assert_(re.search('first$', commit))

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(t_gitshelve)

if __name__ == '__main__':
    unittest.main()
