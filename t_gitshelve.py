# -*- coding: utf-8 -*-

import sys
import re
import os
import os.path
import shutil
import unittest
import gitshelve
import exceptions

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO

class t_gitshelve(unittest.TestCase):
    def setUp(self):
        if os.name == 'nt':
            self.tmpdir = os.getenv('TEMP')
        else:
            self.tmpdir = '/tmp'
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

        buf = StringIO()
        shelf.dump_objects(buf)

        self.assertEqual(buf.getvalue(), """tree: foo
  tree: bar
    blob: baz.c
""")

        hash1 = shelf.commit('first\n')
        hash2 = shelf.commit('second\n')
        self.assertEqual(hash1, hash2)

        buf = StringIO()
        shelf.dump_objects(buf)

        self.assertEqual("""tree ca37be3e31987d8ece35001301c0b8f1fccbb888
  tree 95b790693f3b5934c63d10b8b007e4758f6134a9: foo
    tree c03cdd65fa74c272bed2e9a48e3ed19402576e19: bar
      blob ea93d5cc5f34e13d2a55a5866b75e2c58993d253: baz.c
""", buf.getvalue())

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
""", buf.getvalue())

        self.assertEqual(text, shelf['foo/bar/baz.c'])
        del shelf

    def testIterator(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz1.c'] = text
        shelf['alpha/beta/baz2.c'] = text
        shelf['apple/orange/baz3.c'] = text

        buf = StringIO()
        keys = shelf.keys()
        keys.sort()
        for path in keys:
            buf.write("path: (%s)\n" % path)
        self.assertEqual("""path: (alpha/beta/baz2.c)
path: (apple/orange/baz3.c)
path: (foo/bar/baz1.c)
""", buf.getvalue())

    def testVersioning(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz1.c'] = text
        shelf.sync()

        buf = StringIO()
        shelf.dump_objects(buf)
        self.assertEqual("""tree 073629aeb0ef56a50a6cfcaf56da9b8393604b56
  tree ce9d91f2da4ab3aa920cd5763be48b9aef76f999: foo
    tree 2e626f2ae629ea77618e84e79e1bfae1c473452e: bar
      blob ea93d5cc5f34e13d2a55a5866b75e2c58993d253: baz1.c
""", buf.getvalue())

        text = "Hello, this is a change\n"
        shelf['foo/bar/baz1.c'] = text
        shelf['foo/bar/baz2.c'] = text
        shelf.sync()

        buf = StringIO()
        shelf.dump_objects(buf)
        self.assertEqual("""tree c7c6fd4368460c645d0953349d5577d32f46115a
  tree 3936ea8daffe9eef0451b43205d6530374f8ffa3: foo
    tree 8f7bfca3bc33c93fb1a878bc79c2bb93d8f41730: bar
      blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz1.c
      blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz2.c
""", buf.getvalue())

        del shelf

        shelf = gitshelve.open('test')

        buf = StringIO()
        shelf.dump_objects(buf)
        self.assertEqual("""tree 3936ea8daffe9eef0451b43205d6530374f8ffa3: foo
  tree 8f7bfca3bc33c93fb1a878bc79c2bb93d8f41730: bar
    blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz1.c
    blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz2.c
""", buf.getvalue())

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

    def testDetachedRepo(self):
        repotest = os.path.join(self.tmpdir, 'repo-test')
        repotestclone = os.path.join(self.tmpdir, 'repo-test-clone')
        shelf = gitshelve.open(repository = repotest)
        text = "Hello, world!\n"
        shelf['foo.txt'] = text

        try:
            shelf.sync()

            gitshelve.git('clone', repotest, repotestclone)

            clonedfoo = os.path.join(repotestclone, 'foo.txt')

            try:
                self.assert_(os.path.isfile(clonedfoo))

                data = open(clonedfoo)
                try:
                    self.assertEqual(text, data.read())
                finally:
                    data.close()
            finally:
                if os.path.isdir(repotestclone):
                    shutil.rmtree(repotestclone)
        finally:
            del shelf
            if os.path.isdir(repotest):
                shutil.rmtree(repotest)

    def testBlobStore(self):
        """Test use a gitshelve as a generic blob store."""
        try:
            blobpath = os.path.join(self.tmpdir, 'blobs')
            shelf = gitshelve.open(repository = blobpath, keep_history = False)
            text = "This is just some sample text.\n"
            hash = shelf.put(text)

            buf = StringIO()
            shelf.dump_objects(buf)
            self.assertEqual("""tree: ac
  blob acd291ce81136338a729a30569da2034d918e057: d291ce81136338a729a30569da2034d918e057
""", buf.getvalue())

            self.assertEqual(text, shelf.get(hash))

            shelf.sync()
            buf = StringIO()
            shelf.dump_objects(buf)
            self.assertEqual("""tree 127093ef9a92ebb1f49caa5ecee9ff7139db3a6c
  tree 6c6167149ccc5bf60892b65b84322c1943f5f7da: ac
    blob acd291ce81136338a729a30569da2034d918e057: d291ce81136338a729a30569da2034d918e057
""", buf.getvalue())
            del shelf

            shelf = gitshelve.open(repository = blobpath, keep_history = False)
            buf = StringIO()
            shelf.dump_objects(buf)
            self.assertEqual("""tree 6c6167149ccc5bf60892b65b84322c1943f5f7da: ac
  blob acd291ce81136338a729a30569da2034d918e057: d291ce81136338a729a30569da2034d918e057
""", buf.getvalue())

            self.assertEqual(text, shelf.get(hash))
            del shelf
        finally:
            if os.path.isdir(blobpath):
                shutil.rmtree(blobpath)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(t_gitshelve)

if __name__ == '__main__':
    unittest.main()
