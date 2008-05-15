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
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz.c'] = text

        self.assertEqual(text, shelf['foo/bar/baz.c'])

        def foo1(shelf):
            return shelf['foo/bar']
        self.assertRaises(exceptions.KeyError, foo1, shelf)

        del shelf
 
    def testBasicDeletion(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
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
        text = "Hello, this is a test\n"
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

        self.assertEqual("""tree ca37be3e31987d8ece35001301c0b8f1fccbb888
  tree 95b790693f3b5934c63d10b8b007e4758f6134a9: foo
    tree c03cdd65fa74c272bed2e9a48e3ed19402576e19: bar
      blob ea93d5cc5f34e13d2a55a5866b75e2c58993d253: baz.c
""", buffer.getvalue())

        hash3 = shelf.current_head()
        self.assertEqual(hash1, hash3)

        commit = gitshelve.git('cat-file', 'commit', 'test',
                               keep_newline = True)
        self.assert_(re.search('first\n$', commit))

        data = gitshelve.git('cat-file', 'blob', 'test:foo/bar/baz.c',
                             keep_newline = True)
        self.assertEqual(text, data)

        del shelf
        shelf = gitshelve.open('test')
        
        self.assertEqual("""tree ca37be3e31987d8ece35001301c0b8f1fccbb888
  tree 95b790693f3b5934c63d10b8b007e4758f6134a9: foo
    tree c03cdd65fa74c272bed2e9a48e3ed19402576e19: bar
      blob ea93d5cc5f34e13d2a55a5866b75e2c58993d253: baz.c
""", buffer.getvalue())

        self.assertEqual(text, shelf['foo/bar/baz.c'])
        del shelf


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(t_gitshelve)

if __name__ == '__main__':
    unittest.main()
