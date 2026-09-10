"""Read-only browser for Jamie Engineering Extraction Schema 1.1."""
import hashlib
import json
from pathlib import Path

import graphviz
import pandas as pd
import streamlit as st
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
COLLECTIONS = ['parts', 'attributes', 'relationships', 'requirements', 'issues',
               'document_references', 'expected_information_check']


def load_model(raw):
    """Validate before rendering; never modify the source model."""
    data = json.loads(raw.decode('utf-8-sig'))
    schema = json.loads((ROOT / 'schema.json').read_text(encoding='utf-8'))
    errors = [f"{'/'.join(map(str, e.absolute_path)) or '/'}: {e.message}"
              for e in Draft202012Validator(schema).iter_errors(data)]
    if errors:
        raise ValueError('\n'.join(errors[:30]))
    records = [r for k in COLLECTIONS for r in data[k] if 'id' in r]
    index = {r['id']: r for r in records}
    warnings = []
    if len(index) != len(records):
        warnings.append('Duplicate IDs exist; linked record lookup is ambiguous.')
    parts = {p['id'] for p in data['parts']}
    for r in records:
        for field in ('owner_id', 'parent_id', 'from_id', 'to_id'):
            if r.get(field) and r[field] not in parts:
                warnings.append(f"{r['id']}: {field} does not reference a part.")
        for field in ('related_ids', 'applies_to_ids'):
            for target in r.get(field, []):
                if target not in (parts if field == 'applies_to_ids' else index):
                    warnings.append(f"{r['id']}: unresolved {field}: {target}")
    for p in data['parts']:
        seen = {p['id']}
        parent = p['parent_id']
        while parent in parts:
            if parent in seen:
                warnings.append(f"Containment cycle involving {p['id']}.")
                break
            seen.add(parent)
            parent = index[parent]['parent_id']
    for r in data['expected_information_check']:
        a = index.get(r['attribute_id'])
        if r['attribute_id'] and (not a or a.get('owner_id') != r['owner_id'] or a.get('name') != r['attribute_name']):
            warnings.append(f"Checklist link mismatch: {r['attribute_name']}")
        if r['issue_id'] and r['issue_id'] not in index:
            warnings.append(f"Missing checklist issue: {r['issue_id']}")
    return data, index, list(dict.fromkeys(warnings))


def value_text(r):
    if r.get('value_status') == 'unknown':
        return 'Unknown'
    if r.get('value_role') == 'range':
        v = f"{r.get('lower_bound') if r.get('lower_bound') is not None else '?'} to {r.get('upper_bound') if r.get('upper_bound') is not None else '?'}"
    else:
        v = str(r.get('value')) if r.get('value') is not None else 'Not specified'
    return v + (' ' + r['unit'] if r.get('unit') else '')


def scope_ids(data, selected, descendants):
    ids = {selected} if selected else set()
    if descendants and selected:
        while True:
            expanded = ids | {p['id'] for p in data['parts'] if p['parent_id'] in ids}
            if expanded == ids:
                break
            ids = expanded
    return ids


def scoped(data, kind, ids):
    if not ids:
        return data[kind]
    linked = ids | {a['id'] for a in data['attributes'] if a['owner_id'] in ids}
    linked |= {r['id'] for r in data['requirements'] if set(r['applies_to_ids']) & ids}
    linked |= {r['id'] for r in data['relationships'] if r['from_id'] in ids or r['to_id'] in ids}
    if kind == 'parts':
        return [r for r in data[kind] if r['id'] in ids]
    if kind in ('attributes', 'expected_information_check'):
        return [r for r in data[kind] if r['owner_id'] in ids]
    if kind == 'requirements':
        return [r for r in data[kind] if set(r['applies_to_ids']) & ids]
    if kind == 'relationships':
        return [r for r in data[kind] if r['from_id'] in ids or r['to_id'] in ids]
    if kind == 'issues':
        return [r for r in data[kind] if set(r['related_ids']) & linked]
    return data[kind]


def evidence(sources):
    if not sources:
        st.caption('No source evidence recorded.')
    for i, s in enumerate(sources, 1):
        st.text(f"{i}. {s['document']} | section {s['section'] or 'unspecified'} | PDF page {s['page'] or 'unspecified'}")
        if s['quote']:
            st.text(s['quote'])
        else:
            st.caption('No text quotation; source may be graphical.')


def detail(r, index):
    st.subheader(r.get('id', r.get('attribute_name', 'Record')))
    for field in ('value_status', 'value_role', 'applicability', 'kind', 'status'):
        if field in r:
            st.text(f"{field.replace('_', ' ').title()}: {r[field]}")
    if 'value' in r:
        st.metric('Recorded value', value_text(r))
    for field in ('conditions', 'text', 'description', 'information_needed', 'expected_because'):
        if r.get(field):
            st.markdown(f"**{field.replace('_', ' ').title()}**")
            st.text(r[field])
    if r.get('verification_methods'):
        st.write('Verification methods:', r['verification_methods'])
    with st.expander('Source evidence', expanded=True):
        evidence(r.get('sources', []))
    links = []
    for field in ('owner_id', 'parent_id', 'from_id', 'to_id', 'attribute_id', 'issue_id'):
        if r.get(field):
            links.append(r[field])
    links += r.get('related_ids', []) + r.get('applies_to_ids', [])
    if links:
        with st.expander('Linked records'):
            for target in dict.fromkeys(links):
                st.text(target)
                if target in index:
                    st.json(index[target], expanded=False)
                else:
                    st.warning('Referenced record was not found.')
    with st.expander('Complete record JSON'):
        st.json(r)


def table_browser(records, kind, index, token):
    status_field = {'attributes': 'value_status', 'requirements': 'applicability',
                    'issues': 'kind', 'expected_information_check': 'status',
                    'document_references': 'availability', 'parts': 'boundary_role',
                    'relationships': 'domain'}[kind]
    options = sorted({r.get(status_field) or '(none)' for r in records})
    selected = st.multiselect(status_field.replace('_', ' ').title(), options, key=f'{token}_{kind}_status')
    if selected:
        records = [r for r in records if (r.get(status_field) or '(none)') in selected]
    st.caption(f'{len(records):,} matching records. Select a row to inspect its complete details.')
    if not records:
        st.info('No matching entries. Try another part or clear the filters.')
        return
    rows = []
    for r in records:
        row = {k: (', '.join(map(str, v)) if isinstance(v, list) else v)
               for k, v in r.items() if k not in ('sources', 'value', 'lower_bound', 'upper_bound', 'unit')}
        if 'value' in r:
            row['display_value'] = value_text(r)
        row['source_documents'] = '; '.join(dict.fromkeys(s['document'] for s in r['sources']))
        rows.append(row)
    frame = pd.DataFrame(rows)
    preferred = ['id', 'attribute_name', 'name', 'display_value', status_field, 'conditions', 'description', 'text']
    cols = list(dict.fromkeys(c for c in preferred if c in frame.columns))
    cols += [c for c in frame.columns if c not in cols]
    fingerprint = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[:10]
    event = st.dataframe(frame[cols], hide_index=True, width="stretch",
                         on_select='rerun', selection_mode='single-row', height=350,
                         key=f'{token}_{kind}_{fingerprint}')
    st.download_button('Download matching records (JSON)', json.dumps(records, indent=2, ensure_ascii=False),
                       file_name=f'{kind}_filtered.json', mime='application/json', key=f'{token}_{kind}_download')
    selection = event.selection.rows
    # The dropdown also permits keyboard navigation without table selection.
    which = st.selectbox('Inspect record', range(len(records)),
                         index=selection[0] if selection else 0,
                         format_func=lambda i: records[i].get('id', records[i].get('attribute_name', str(i))),
                         key=f'{token}_{kind}_{fingerprint}_{selection}_inspect')
    detail(records[which], index)


def main():
    st.set_page_config(page_title='Engineering JSON Browser', page_icon='🔎', layout='wide')
    st.title('Engineering JSON Browser')
    st.caption('Jamie Schema 1.1 · Trace requirements, equipment information, and source evidence')
    with st.sidebar:
        st.header('Open an extraction')
        upload = st.file_uploader('Upload JSON', type=['json'])
        use_example = st.checkbox('Use bundled firstpass.json', value=True)
    if upload is not None:
        raw = upload.getvalue()
        filename = upload.name
    elif use_example and (ROOT / 'firstpass.json').exists():
        raw = (ROOT / 'firstpass.json').read_bytes()
        filename = 'firstpass.json (bundled)'
    else:
        st.info('Upload a JSON extraction to begin.')
        return
    try:
        data, index, warnings = load_model(raw)
    except (ValueError, UnicodeError, OSError) as exc:
        st.error('This file could not be loaded as a Jamie Schema 1.1 extraction.')
        st.code(str(exc))
        return
    token = hashlib.sha256(raw).hexdigest()[:12]
    st.caption(f'Loaded: {filename} · Schema validation passed')
    st.info('Recorded constraints and requirements do not establish selected equipment ratings or compliance. Check each record’s conditions and applicability.')
    if warnings:
        with st.expander(f'{len(warnings)} reference or containment warnings', expanded=True):
            for message in warnings:
                st.warning(message)
    with st.sidebar:
        st.header('Browse')
        def part_label(pid):
            if not pid:
                return 'All parts / whole model'
            p = index[pid]; names = [p['display_name']]; visited = {pid}
            while p.get('parent_id') in index and p['parent_id'] not in visited:
                visited.add(p['parent_id']); p = index[p['parent_id']]
                names.insert(0, p.get('display_name', p['id']))
            return ' / '.join(names) + f' [{pid}]'
        chosen = st.selectbox('Part hierarchy', [''] + [p['id'] for p in data['parts']],
                              format_func=part_label, key=f'{token}_part')
        descendants = st.checkbox('Include contained parts', value=True)
        query = st.text_input('Search records and quotations', key=f'{token}_search').casefold().strip()
        docs = sorted({s['document'] for k in COLLECTIONS for r in data[k] for s in r['sources']})
        document = st.selectbox('Source document', ['All documents'] + docs, key=f'{token}_doc')
        st.caption('Part scope includes directly linked issues. Choose All parts for unallocated requirements and global issues. References always cover the whole model.')
    ids = scope_ids(data, chosen, descendants)
    metrics = st.columns(4)
    for col, k in zip(metrics, ['parts', 'attributes', 'requirements', 'issues']):
        col.metric(k.replace('_', ' ').title(), len(data[k]))
    sections = ['Overview', 'Parts', 'Attributes', 'Relationships', 'Requirements', 'Issues', 'Missing information', 'References']
    view = st.radio('View', sections, horizontal=True, key=f'{token}_view')
    if view == 'Overview':
        st.subheader('Part relationships')
        graph = graphviz.Digraph(graph_attr={'rankdir': 'TB'})
        rels = scoped(data, 'relationships', ids)
        nodes = ids | {r[k] for r in rels for k in ('from_id', 'to_id')} if ids else {p['id'] for p in data['parts']}
        for p in data['parts']:
            if p['id'] in nodes:
                graph.node(p['id'], p['display_name']+'\n'+p['boundary_role'], shape='box')
        for r in rels:
            graph.edge(r['from_id'], r['to_id'], label=r['kind']+' / '+str(r['domain'] or ''),
                       dir={'from_to': 'forward', 'bidirectional': 'both', 'unspecified': 'none'}[r['direction']])
        st.graphviz_chart(graph, width="stretch")
        st.caption('Edges show recorded relationships. Containment is shown in the sidebar hierarchy. Search and source filters apply to record views, not this overview.')
        checklist = scoped(data, 'expected_information_check', ids)
        st.subheader('Expected information in selected scope')
        st.dataframe(pd.DataFrame([{'Status': s, 'Count': sum(r['status'] == s for r in checklist)}
                                   for s in ('found', 'missing', 'conflicting')]), hide_index=True)
        st.download_button('Download complete original JSON', raw, 'extraction.json', 'application/json')
        return
    kind = {'Parts': 'parts', 'Attributes': 'attributes', 'Relationships': 'relationships',
            'Requirements': 'requirements', 'Issues': 'issues', 'Missing information': 'expected_information_check',
            'References': 'document_references'}[view]
    records = scoped(data, kind, ids)
    if query:
        records = [r for r in records if query in json.dumps(r, ensure_ascii=False).casefold()]
    if document != 'All documents':
        records = [r for r in records if any(s['document'] == document for s in r['sources'])]
    table_browser(records, kind, index, token)


if __name__ == '__main__':
    main()
