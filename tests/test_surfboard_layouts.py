"""Portable scope layouts are presentation, never execution permissions."""
from copy import deepcopy
import unittest

from server.surfboards import (SurfboardError, catalog, compile_board, compile_layouts,
                              validate_pages, diff_summary, layout_catalog, template, validate, validate_layout)


class SurfboardLayoutsTests(unittest.TestCase):
    def test_legacy_boards_derive_independent_scope_defaults(self):
        board = template('research')
        self.assertNotIn('layouts', validate(board))
        layouts = compile_layouts(board)
        project = {row['id']: row for row in layouts['project']}
        item = {row['id']: row for row in layouts['item']}
        self.assertEqual('main', project['compute']['placement'])
        self.assertEqual('hidden', project['runs']['placement'])
        self.assertEqual('main', item['runs']['placement'])
        self.assertEqual('main', item['results']['placement'])
        self.assertNotIn('compute', item)
        self.assertEqual('right', project['chat']['placement'])
        self.assertEqual('right', item['chat']['placement'])
        self.assertEqual(['results', 'visualizer', 'wandb'], item['results']['node_ids'])

    def test_project_and_item_are_independent_and_omissions_hidden(self):
        board = template('research')
        board['layouts'] = {'project': [{'id': 'chat', 'placement': 'main'}],
                            'item': [{'id': 'results', 'placement': 'right', 'order': 3}]}
        normalized = validate(board)
        self.assertEqual([{'id': 'chat', 'placement': 'main', 'order': 0}], normalized['layouts']['project'])
        compiled = compile_board(normalized)['layouts']
        self.assertEqual(['chat'], [r['id'] for r in compiled['project'] if r['placement'] != 'hidden'])
        self.assertEqual(['results'], [r['id'] for r in compiled['item'] if r['placement'] != 'hidden'])
        self.assertEqual('results', compiled['item'][0]['node_id'])
        self.assertEqual(2, sum('views' in line for line in diff_summary(template('research'), normalized)))

    def test_empty_layout_is_valid_without_disabling_agents_or_tools(self):
        board = template('research')
        before = compile_board(board)
        board['layouts'] = {'item': [], 'project': []}
        after = compile_board(board)
        self.assertTrue(all(r['placement'] == 'hidden' for rows in after['layouts'].values() for r in rows))
        for key in ('tools_by_role', 'requirements', 'actions', 'data_sources', 'timers', 'recovery'):
            self.assertEqual(before[key], after[key])

    def test_per_item_override_uses_same_validator_without_mutating_board(self):
        board = template('software')
        original = deepcopy(board)
        result = validate_layout([{'id': 'editor', 'placement': 'main', 'order': 10},
                                  {'id': 'chat', 'placement': 'right', 'order': 0}], board)
        self.assertEqual(['chat', 'editor'], [r['id'] for r in result])
        self.assertEqual(original, board)
        self.assertNotIn('compute', {row['id'] for row in layout_catalog(board, 'project')})

    def test_unsupported_or_duplicate_layouts_fail_closed(self):
        board = template('research')
        cases = [None, {}, 'main', [{'id': 'editor', 'placement': 'main'}],
                 [{'id': 'compute', 'placement': 'main'}],
                 [{'id': 'chat', 'placement': 'floating'}],
                 [{'id': 'chat', 'placement': 'right', 'order': True}],
                 [{'id': 'chat', 'placement': 'right', 'order': 1001}],
                 [{'id': 'chat', 'placement': 'right', 'node_id': 'manager'}],
                 [{'id': 'chat', 'placement': 'main'}, {'id': 'chat', 'placement': 'right'}]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(SurfboardError):
                validate_layout(rows, board)
        with self.assertRaises(SurfboardError):
            validate({**board, 'layouts': {'workspace': []}})
        with self.assertRaises(SurfboardError):
            validate_layout([], board, 'workspace')

    def test_editor_is_a_view_without_action_or_extra_permissions(self):
        for workflow in ('software', 'web'):
            board = template(workflow)
            editor = next(n for n in board['nodes'] if n['kind'] == 'editor')
            compiled = compile_board(board)
            self.assertNotIn(editor['id'], compiled['actions'])
            self.assertEqual('main', next(r for r in compiled['layouts']['item'] if r['id'] == 'editor')['placement'])
            original_tools = deepcopy(compiled['tools_by_role'])
            board['nodes'] = [n for n in board['nodes'] if n['id'] != editor['id']]
            board['edges'] = [e for e in board['edges'] if editor['id'] not in (e['source'], e['target'])]
            self.assertEqual(original_tools, compile_board(board)['tools_by_role'])
        block = next(c for c in catalog() if c['kind'] == 'editor')
        self.assertEqual(['supersurfer-code-editor'], block['skills'])
        self.assertNotIn('argv', block['config_fields'])
        self.assertNotIn('editor', {r['id'] for r in layout_catalog(template('research'))})

    def test_layout_editor_can_enable_detached_view_without_granting_capabilities(self):
        board = template('research')
        before = compile_board(board)
        board['nodes'].append({'id': 'edit', 'kind': 'editor', 'label': 'Editor', 'x': 0, 'y': 0, 'config': {}})
        board['layouts'] = {'project': [{'id': 'editor', 'placement': 'main', 'order': 0}]}
        after = compile_board(board)
        self.assertEqual(before['tools_by_role'], after['tools_by_role'])
        self.assertEqual('edit', after['layouts']['project'][0]['node_id'])
        self.assertEqual('main', after['layouts']['project'][0]['placement'])

    def test_legacy_right_placement_survives_until_scope_explicitly_arranged(self):
        board = template('research')
        next(n for n in board['nodes'] if n['id'] == 'results')['config'] = {'placement': 'right', 'order': 5}
        for rows in compile_layouts(board).values():
            self.assertEqual('right', next(r for r in rows if r['id'] == 'results')['placement'])
        board['layouts'] = {'item': [{'id': 'results', 'placement': 'main', 'order': 10}]}
        layouts = compile_layouts(board)
        self.assertEqual('right', next(r for r in layouts['project'] if r['id'] == 'results')['placement'])
        self.assertEqual('main', next(r for r in layouts['item'] if r['id'] == 'results')['placement'])


if __name__ == '__main__':
    unittest.main()

class WindowGeometryTests(unittest.TestCase):
    def test_window_geometry_and_small_pdf_are_preserved(self):
        board=template('writing')
        pages=[{'id':'writing','title':'Writing','arrangement':'windows','tiles':[{'id':'pdf','kind':'pdf','height':220,'bounds':{'x':75,'y':40,'width':900,'height':220}}]}]
        normalized=validate_pages(pages,board,'item')
        self.assertEqual('windows',normalized[0]['arrangement'])
        self.assertEqual(pages[0]['tiles'][0]['bounds'],normalized[0]['tiles'][0]['bounds'])
        self.assertEqual(220,normalized[0]['tiles'][0]['height'])

    def test_invalid_geometry_cannot_become_styles_or_unbounded_windows(self):
        board=template('writing')
        for field,value in [('x',-1),('y',float('nan')),('width',True),('width',100),('height',5001),('x','1; color:red')]:
            bounds={'x':0,'y':0,'width':600,'height':500};bounds[field]=value
            with self.assertRaises(SurfboardError):validate_pages([{'id':'writing','title':'Writing','tiles':[{'id':'pdf','kind':'pdf','bounds':bounds}]}],board,'item')
        with self.assertRaises(SurfboardError):validate_pages([{'id':'writing','title':'Writing','arrangement':'execute','tiles':[]}],board,'item')


class NestedDockTests(unittest.TestCase):
    def test_mixed_splits_with_empty_space_preserve_all_panels(self):
        page={'id':'desk','title':'Desk','tiles':[{'id':'code','kind':'editor'},{'id':'pdf','kind':'pdf'}], 'layout':{'axis':'x','ratio':.6,'first':{'axis':'y','ratio':.7,'first':{'tile':'code'},'second':{'empty':True}},'second':{'tile':'pdf'}}}
        result=validate_pages([page],template('writing'),'item')[0]
        self.assertEqual(page['layout'],result['layout'])
        for tree in ({'tile':'code'},{'tile':'missing'},{'axis':'x','ratio':True,'first':{'tile':'code'},'second':{'tile':'pdf'}},{'axis':'x','ratio':.99,'first':{'tile':'code'},'second':{'tile':'pdf'}},{'axis':'x','ratio':.5,'first':{'tile':'code'},'second':{'tile':'code'}},{'empty':False}):
            with self.subTest(tree=tree), self.assertRaises(SurfboardError):
                validate_pages([{**page,'layout':tree}],template('writing'),'item')
    def test_sidebar_tiles_are_not_dock_leaves_and_depth_is_bounded(self):
        page={'id':'desk','title':'Desk','tiles':[{'id':'code','kind':'editor','placement':'left'}]}
        self.assertEqual({'empty':True},validate_pages([{**page,'layout':{'empty':True}}],template('writing'),'item')[0]['layout'])
        with self.assertRaises(SurfboardError):validate_pages([{**page,'layout':{'tile':'code'}}],template('writing'),'item')
        tree={'empty':True}
        for _ in range(17):tree={'axis':'y','ratio':.5,'first':tree,'second':{'empty':True}}
        with self.assertRaises(SurfboardError):validate_pages([{**page,'layout':tree}],template('writing'),'item')
