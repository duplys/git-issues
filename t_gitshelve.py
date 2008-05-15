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

    def testIterator(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz1.c'] = text
        shelf['alpha/beta/baz2.c'] = text
        shelf['apple/orange/baz3.c'] = text

        buffer = StringIO()
        keys = shelf.keys()
        keys.sort()
        for path in keys:
            buffer.write("path: (%s)\n" % path)
        self.assertEqual("""path: (alpha/beta/baz2.c)
path: (apple/orange/baz3.c)
path: (foo/bar/baz1.c)
""", buffer.getvalue())

    def testVersioning(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz1.c'] = text
        shelf.sync()

        buffer = StringIO()
        shelf.dump_objects(buffer)
        self.assertEqual("""tree 073629aeb0ef56a50a6cfcaf56da9b8393604b56
  tree ce9d91f2da4ab3aa920cd5763be48b9aef76f999: foo
    tree 2e626f2ae629ea77618e84e79e1bfae1c473452e: bar
      blob ea93d5cc5f34e13d2a55a5866b75e2c58993d253: baz1.c
""", buffer.getvalue())

        text = "Hello, this is a change\n"
        shelf['foo/bar/baz1.c'] = text
        shelf['foo/bar/baz2.c'] = text
        shelf.sync()

        buffer = StringIO()
        shelf.dump_objects(buffer)
        self.assertEqual("""tree c7c6fd4368460c645d0953349d5577d32f46115a
  tree 3936ea8daffe9eef0451b43205d6530374f8ffa3: foo
    tree 8f7bfca3bc33c93fb1a878bc79c2bb93d8f41730: bar
      blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz1.c
      blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz2.c
""", buffer.getvalue())

        del shelf

        shelf = gitshelve.open('test')

        buffer = StringIO()
        shelf.dump_objects(buffer)
        self.assertEqual("""tree 3936ea8daffe9eef0451b43205d6530374f8ffa3: foo
  tree 8f7bfca3bc33c93fb1a878bc79c2bb93d8f41730: bar
    blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz1.c
    blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz2.c
""", buffer.getvalue())

        self.assertEqual(text, shelf['foo/bar/baz1.c'])
        self.assertEqual(text, shelf['foo/bar/baz2.c'])

        log = gitshelve.git('log', 'test', keep_newline = True)

        self.assert_(re.match("""commit [0-9a-f]{40}
Author: .+
Date:   .+

commit [0-9a-f]{40}
Author: .+
Date:   .+
""", log))

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(t_gitshelve)

if __name__ == '__main__':
    unittest.main()
