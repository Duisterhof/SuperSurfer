import unittest
from server.draft_merge import plan
from server.surfboards import SurfboardError


def merged(editor, chunks):
    for chunk in reversed(chunks):
        if not chunk['conflict'] and not chunk['already_applied']:
            # Test ASCII offsets, except the dedicated UTF-16 check.
            editor=editor[:chunk['start']]+chunk['after']+editor[chunk['end']:]
    return editor


class DraftMergeTests(unittest.TestCase):
    def test_disjoint_user_and_external_edits_preserve_draft(self):
        base='first\nsecond\nthird\nfourth\n'
        editor=base.replace('first','my first')
        disk=base.replace('third','agent third')
        chunks=plan(base,editor,disk)['chunks']
        self.assertEqual(len(chunks),1);self.assertFalse(chunks[0]['conflict'])
        self.assertEqual(merged(editor,chunks),'my first\nsecond\nagent third\nfourth\n')
        self.assertEqual(chunks[0]['before'],'third\n')

    def test_overlapping_edits_keep_user_text_for_explicit_choice(self):
        base='one\ntwo\nthree\n';editor=base.replace('two','mine');disk=base.replace('two','agent')
        chunk=plan(base,editor,disk)['chunks'][0]
        self.assertTrue(chunk['conflict']);self.assertEqual(chunk['before'],'mine\n');self.assertEqual(chunk['after'],'agent\n');self.assertEqual(merged(editor,[chunk]),editor)

    def test_insertion_deletion_and_shifted_user_lines(self):
        base='one\ntwo\nthree\n';editor='my prefix\n'+base;disk=base.replace('two\n','')
        chunks=plan(base,editor,disk)['chunks'];self.assertEqual(merged(editor,chunks),'my prefix\none\nthree\n')
        chunks=plan(base,base,base+'tail\n')['chunks'];self.assertEqual(merged(base,chunks),base+'tail\n')
        chunks=plan(base,base+'mine\n',base+'agent\n')['chunks'];self.assertTrue(chunks[0]['conflict']);self.assertEqual(chunks[0]['before'],'mine\n')

    def test_clean_native_reload_still_exposes_review_chunks(self):
        base='one\ntwo\n';disk='one\nagent\n'
        chunks=plan(base,disk,disk)['chunks'];self.assertEqual(len(chunks),1);self.assertTrue(chunks[0]['already_applied']);self.assertEqual(chunks[0]['before'],'two\n')
        self.assertEqual(merged(disk,chunks),disk)

    def test_offsets_follow_native_utf16_unicode_model(self):
        chunk=plan('😀\none\n','😀\none\n','😀\nagent\n')['chunks'][0]
        self.assertEqual(chunk['start'],3);self.assertEqual(chunk['end'],7)

    def test_bounds_and_non_text_fail_without_changes(self):
        for value in (None,'x'*(2*1024*1024+1),'x\n'*20001):
            with self.assertRaises(SurfboardError):plan('base',value,'disk')

if __name__=='__main__':unittest.main()
