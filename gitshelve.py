#!/usr/bin/env python
# coding: utf-8

# gitshelve.py, version 1.0
#
# by John Wiegley <johnw@newartisans.com>
#
# This file implements a Python shelve object that uses a branch within the
# current Git repository to store its data, plus a history of all changes to
# that data.  The usage is identical to shelve, with the exception that a
# branchname must be specified, and that writeback=True is assumed.
#
# Example:
#
#   import gitshelve
#
#   data = gitshelve.open(branch = 'mydata')
#
#   data['foo/bar/git.c'] = "This is some sample data."
#
#   data.commit("Changes")
#   data.sync()                  # same as data.commit()
#
#   print data['foo/bar/git.c']
#
#   data.close()
#
# If you checkout the 'mydata' branch now, you'll see the file 'git.c' in the
# directory 'foo/bar'.  Running 'git log' will show the change you made.

import re
import string
import os.path

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO

from subprocess import Popen, PIPE

######################################################################

verbose = False

######################################################################

# Utility function for calling out to Git (this script does not try to
# be a Git library, just an interface to the underlying commands).  It
# supports a 'restart' keyword, which will cause a Python function to
# be called on failure.  If that function returns True, the same
# command will be attempted again.  This can avoid costly checks to
# make sure a branch exists, for example, by simply failing on the
# first attempt to use it and then allowing the restart function to
# create it.

class GitError(Exception):
    def __init__(self, cmd, args, kwargs, stderr = None):
        self.cmd = cmd
        self.args = args
        self.kwargs = kwargs
        self.stderr = stderr

    def __str__(self):
        if stderr:
             return "Git command failed: git-%s %s: %s" % (cmd, args, stderr)
        else:
             return "Git command failed: git-%s %s" % (cmd, args)

def git(cmd, *args, **kwargs):
    restart = True
    while restart:
        stdin_mode = None
        if kwargs.has_key('input'):
            stdin_mode = PIPE

        if verbose:
            print "Command: git-%s %s" % (cmd, string.join(args, ' '))
            if kwargs.has_key('input'):
                print "Input: <<EOF"
                print kwargs['input'],
                print "EOF"

        proc = Popen(('git-' + cmd,) + args, stdin = stdin_mode,
                     stdout = PIPE, stderr = PIPE)

        if kwargs.has_key('input'):
            proc.stdin.write(kwargs['input'])
            proc.stdin.close()

        returncode = proc.wait()
        restart = False
        if returncode != 0:
            if kwargs.has_key('restart'):
                if kwargs['restart'](cmd, args, kwargs):
                    restart = True
            else:
                raise GitError(cmd, args, kwargs, proc.stderr.read())

    if not kwargs.has_key('ignore_output'):
        if kwargs.has_key('keep_newline'):
            return proc.stdout.read()
        else:
            return proc.stdout.read()[:-1]


class gitbook:
    """Abstracts a reference to a data file within a Git repository.  It also
    maintains knowledge of whether the object has been modified or not."""
    def __init__(self, shelf, path, hash = None):
        self.shelf = shelf
        self.path  = path
        self.hash  = hash
        self.data  = None
        self.dirty = False

    def get_data(self):
        if self.data is None:
            assert self.hash is not None
            self.data = self.deserialize_data(self.shelf.get_blob(self.hash))
        return self.data
        
    def set_data(self, data):
        if data != self.data:
            self.hash  = None
            self.data  = data
            self.dirty = True

    def serialize_data(self):
        return self.data

    def deserialize_data(self, data):
        return data

    def change_comment(self):
        return None

    def __getstate__(self):
        odict = self.__dict__.copy() # copy the dict since we change it
        del odict['dirty']           # remove dirty flag
        return odict

    def __setstate__(self,dict):
        self.__dict__.update(dict)   # update attributes
        self.dirty = False


class gitshelve(dict):
    """This class implements a Python "shelf" using a branch within a Git
    repository.  There is no "writeback" argument, meaning changes are only
    written upon calling close or sync.

    This implementation uses a dictionary of gitbook objects, since we don't
    really want to use Pickling within a Git repository (it's not friendly to
    other Git users, nor does it support merging)."""
    ls_tree_pat = re.compile('(040000 tree|100644 blob) ([0-9a-f]{40})\t(start|(.+))$')

    def __init__(self, branch, book_type = gitbook):
        self.branch    = branch
        self.book_type = book_type
        self.init_data()

    def init_data(self):
        self.head      = None
        self.dirty     = False
        self.objects   = {}

    def current_head(self):
        return git('rev-parse', self.branch)

    def update_head(self, new_head):
        if self.head:
            git('update-ref', 'refs/heads/%s' % self.branch, new_head, self.head)
        else:
            git('update-ref', 'refs/heads/%s' % self.branch, new_head)
        self.head = new_head

    def read_repository(self):
        self.init_data()
        try:
            self.head = self.current_head()
        except:
            self.head = None

        if not self.head:
            return

        ls_tree = string.split(git('ls-tree', '-r', '-t', '-z', self.head),
                               '\0')
        for line in ls_tree:
            match = self.ls_tree_pat.match(line)
            assert match

            treep = match.group(1) == "040000 tree"
            hash  = match.group(2)
            path  = match.group(3)

            parts = string.split(path, os.sep)
            dict  = self.objects
            for part in parts:
                if not dict.has_key(part):
                    dict[part] = {}
                dict = dict[part]

            if treep:
                dict['__root__'] = hash
            else:
                dict['__book__'] = self.book_type(self, path, hash)

    def open(cls, branch, book_type = gitbook):
        shelf = gitshelve(branch, book_type)
        shelf.read_repository()
        return shelf

    open = classmethod(open)

    def get_blob(self, hash):
        return git('cat-file', 'blob', hash, keep_newline = True)

    def make_blob(self, data):
        return git('hash-object', '-w', '--stdin', input = data)

    def make_tree(self, objects, comment_accumulator = None):
        buffer = StringIO()

        root = None
        if objects.has_key('__root__'):
            root = objects['__root__']

        for path in objects.keys():
            if path == '__root__': continue

            object = objects[path]
            assert isinstance(object, dict)

            if len(object.keys()) == 1 and object.has_key('__book__'):
                book = object['__book__']
                if book.dirty:
                    if comment_accumulator:
                        comment = book.change_comment()
                        if comment:
                            comment_accumulator.write(comment)

                    book.hash  = self.make_blob(book.serialize_data())
                    book.dirty = False
                    root = None

                buffer.write("100644 blob %s\t%s\0" % (book.hash, path))

            else:
                tree_root = None
                if object.has_key('__root__'):
                    tree_root = object['__root__']

                tree_hash = self.make_tree(object, comment_accumulator)
                if tree_hash != tree_root:
                    root = None

                buffer.write("040000 tree %s\t%s\0" % (tree_hash, path))

        if root is None:
            hash = git('mktree', '-z', input = buffer.getvalue())
            objects['__root__'] = hash
            return hash
        else:
            return root

    def make_commit(self, tree_hash, comment):
        if not comment: comment = ""
        if self.head:
            hash = git('commit-tree', tree_hash, '-p', self.head,
                       input = comment)
        else:
            hash = git('commit-tree', tree_hash, input = comment)

        self.update_head(hash)
        return hash

    def commit(self, comment = None):
        if not self.dirty:
            return self.head

        accumulator = None
        if comment is None:
            accumulator = StringIO()
        
        # Walk the objects now, creating and nesting trees until we end up
        # with a top-level tree.  We then create a commit out of this tree.
        tree = self.make_tree(self.objects, accumulator)
        if accumulator:
            comment = accumulator.getvalue()
        hash = self.make_commit(tree, comment)

        self.dirty = False
        return hash

    def sync(self):
        self.commit()

    def close(self):
        if self.dirty:
            self.sync()
        del self.objects        # free it up right away

    def dump_objects(self, fd, indent = 0, objects = None):
        if objects is None:
            objects = self.objects

        if objects.has_key('__root__') and indent == 0:
            fd.write('%stree %s\n' % (" " * indent, objects['__root__']))
            indent += 2

        keys = objects.keys()
        keys.sort()
        for key in keys:
            if key == '__root__': continue
            assert isinstance(objects[key], dict)

            if objects[key].has_key('__book__'):
                book = objects[key]['__book__']
                if book.hash:
                    kind = 'blob ' + book.hash
                else:
                    kind = 'blob'
            else:
                if objects[key].has_key('__root__'):
                    kind = 'tree ' + objects[key]['__root__']
                else:
                    kind = 'tree'

            fd.write('%s%s: %s\n' % (" " * indent, kind, key))

            if kind[:4] == 'tree':
                self.dump_objects(fd, indent + 2, objects[key])

    def get_tree(self, path, make_dirs = False):
        parts = string.split(path, os.sep)
        dict  = self.objects
        for part in parts:
            if make_dirs and not dict.has_key(part):
                dict[part] = {}
            dict = dict[part]
        return dict

    def __getitem__(self, path):
        try:
            dict = self.get_tree(path)
        except KeyError:
            raise KeyError(path)

        if len(dict.keys()) == 1:
            return dict['__book__'].get_data()
        raise KeyError(path)

    def __setitem__(self, path, data):
        try:
            dict = self.get_tree(path, make_dirs = True)
        except KeyError:
            raise KeyError(path)
        if len(dict.keys()) == 0:
            dict['__book__'] = self.book_type(self, path)
        dict['__book__'].set_data(data)
        self.dirty = True

    def prune_tree(self, objects, paths):
        if len(paths) > 1:
            self.prune_tree(objects[paths[0]], paths[1:])
        del objects[paths[0]]

    def __delitem__(self, path):
        try:
            self.prune_tree(self.objects, string.split(path, os.sep))
        except KeyError:
            raise KeyError(path)

    def __contains__(self, path):
        dict = self.get_tree(path)
        return len(dict.keys()) == 1 and dict.has_key('__book__')

    def walker(self, kind, objects, path = ''):
        for item in objects.items():
            if item[0] == '__root__': continue
            assert isinstance(item[1], dict)

            if path:
                key = string.join((path, item[0]), os.sep)
            else:
                key = item[0]

            if len(item[1].keys()) == 1 and item[1].has_key('__book__'):
                value = item[1]['__book__']
                if kind == 'keys':
                    yield key
                elif kind == 'values':
                    yield value
                else:
                    assert kind == 'items'
                    yield (key, value)
            else:
                for object in self.walker(kind, item[1], key):
                    yield object

        raise StopIteration

    def __iter__(self):
        return self.iterkeys()
    
    def iteritems(self):
        return self.walker('items', self.objects)

    def keys(self):
        k = []
        for key in self.iterkeys():
            k.append(key)
        return k

    def iterkeys(self):
        return self.walker('keys', self.objects)

    def itervalues(self):
        return self.walker('values', self.objects)

    def __getstate__(self):
        self.sync()                  # synchronize before persisting
        odict = self.__dict__.copy() # copy the dict since we change it
        del odict['dirty']           # remove dirty flag
        return odict

    def __setstate__(self,dict):
        self.__dict__.update(dict)   # update attributes
        self.dirty = False

        # If the HEAD reference is out of date, throw away all data and
        # rebuild it.
        if not self.head or self.head != self.current_head():
            self.read_repository()


def open(branch, book_type = gitbook):
    return gitshelve.open(branch, book_type)

# gitshelve.py ends here
