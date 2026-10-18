"""A shared presentation for measured training comparisons, authored as a small spec."""
import copy
import html
import json
import re
from pathlib import Path

from .result_data import validate_sources

TEXT = lambda maximum: {"type": "string", "minLength": 1, "maxLength": maximum}
NUMBER = {"type": "number"}
TRACE = {"type": "object", "additionalProperties": False, "required": ["source", "metric", "x", "split"], "properties": {
    "source": TEXT(64), "metric": TEXT(256), "x": TEXT(256),
    "split": {"type": "string", "enum": ["training", "validation", "test"]},
    "label": TEXT(160), "x_offset": NUMBER, "x_scale": {"type": "number", "exclusiveMinimum": 0},
    "y_scale": {"type": "number", "exclusiveMinimum": 0},
    "where": {"type": "object", "additionalProperties": False, "required": ["key", "equals"], "properties": {
        "key": TEXT(256), "equals": {"type": ["string", "number", "boolean"]}}}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["title", "sources", "plots"], "properties": {
    "result_id": TEXT(100), "expected_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
    "title": TEXT(200), "description": TEXT(1200),
    "sources": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "object", "additionalProperties": False,
        "required": ["id", "url", "label"], "properties": {"id": TEXT(64), "url": TEXT(2048), "label": TEXT(100)}}},
    "plots": {"type": "array", "minItems": 1, "maxItems": 24, "items": {"type": "object", "additionalProperties": False,
        "required": ["title", "x_label", "y_label", "traces"], "properties": {
            "title": TEXT(160), "x_label": TEXT(160), "y_label": TEXT(160), "caption": TEXT(1200),
            "secondary": {"type": "boolean"},
            "traces": {"type": "array", "minItems": 1, "maxItems": 12, "items": TRACE}}}},
    "missing_measurements": {"type": "array", "maxItems": 12, "items": TEXT(500)},
    "details_html": {"type": "string", "maxLength": 600000, "description": "Requested method schematic/domain widgets after the curves; no credentials or duplicate app UI."},
    "provenance": TEXT(4000)}}


def compile_report(fields):
    from .agent_tools import validate_arguments
    validate_arguments({"name": "publish_training_results", "inputSchema": SCHEMA}, fields)
    if fields.get("result_id") and not fields.get("expected_sha256"):
        raise ValueError("Read the current result and supply expected_sha256 when updating training Results")
    spec = copy.deepcopy(fields)
    sources = {source['id']: {**source, 'keys': [], 'sparse_metrics': []} for source in spec['sources']}
    if len(sources) != len(spec['sources']):
        raise ValueError('Use distinct source IDs for the compared runs')
    splits = set()
    for plot in spec['plots']:
        for trace in plot['traces']:
            if trace['source'] not in sources:
                raise ValueError('Every trace must reference a declared source')
            source = sources[trace['source']]
            source['keys'].extend([trace['metric'], trace['x']])
            if trace.get('where'):
                source['keys'].append(trace['where']['key'])
            splits.add(trace['split'])
            if trace['split'] != 'training':
                metric = {'key': trace['metric'], 'x_axis': trace['x']}
                if metric not in source['sparse_metrics']:
                    source['sparse_metrics'].append(metric)
    if 'training' not in splits:
        raise ValueError('Training Results must include measured training traces; use publish_result for other scientific artifacts')
    if not {'validation', 'test'} & splits and not spec.get('missing_measurements'):
        raise ValueError('Declare actual validation/test traces, or state the unavailable measurements and evidence checked in missing_measurements')
    if not any(not plot.get('secondary') and any(t['split'] == 'training' for t in plot['traces']) for plot in spec['plots']):
        raise ValueError('The primary Results view must begin with training comparisons, not hide them in details')
    # Curves with training lead even if an author supplies held-out panels first.
    spec['plots'].sort(key=lambda p: (bool(p.get('secondary')), not any(t['split'] == 'training' for t in p['traces'])))
    bindings = validate_sources([{k: list(dict.fromkeys(v)) if k == 'keys' else v for k, v in s.items() if k != 'label'} for s in sources.values()])
    # JSON remains data even when labels contain HTML or closing script tags.
    encoded = json.dumps(spec, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    root = Path(__file__).resolve().parents[1]
    template = (root / 'ui/training-results.html').read_text()
    values = {'TITLE': html.escape(spec['title']), 'DESCRIPTION': html.escape(spec.get('description', '')),
              # Plotly's old raw-trace cleanup treats UIDs as CSS selectors.
              # Escape the selector instead of changing persisted series IDs.
              'SPEC': encoded, 'PLOTLY': (root / 'ui/vendor/plotly-basic.min.js').read_text().replace(
                  'n._infolayer.select(".cb"+f).remove()', 'n._infolayer.select(".cb"+CSS.escape(f)).remove()', 1),
              'RENDERER': (root / 'ui/training-results.js').read_text(), 'DETAILS': spec.get('details_html', '')}
    document = re.sub(r'\{\{([A-Z]+)\}\}', lambda match: values[match[1]], template)
    return {**{k: fields[k] for k in ('result_id', 'expected_sha256') if k in fields},
        'title': spec['title'], 'html': document, 'wandb_sources': bindings}
