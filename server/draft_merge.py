"""Three-way draft merge: keep user edits and expose external changes for review."""
import difflib
from .surfboards import SurfboardError

LIMIT=2*1024*1024


def _edits(base, other):
    a,b=base.splitlines(keepends=True),other.splitlines(keepends=True)
    offsets=[0]
    for line in a:offsets.append(offsets[-1]+len(line))
    result=[]
    for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if tag!='equal':result.append({'start':offsets[i],'end':offsets[j],'text':''.join(b[k:l])})
    return result


def _overlap(a,b):
    if a['start']==a['end'] or b['start']==b['end']:
        return a['start']<=b['end'] and b['start']<=a['end']
    return max(a['start'],b['start'])<min(a['end'],b['end'])


def _position(offset, edits, end=False):
    shift=0
    for row in edits:
        if row['end']<=offset:shift+=len(row['text'])-(row['end']-row['start'])
        elif row['start']<offset:return row['start']+shift+(len(row['text']) if end else 0)
        else:break
    return offset+shift


def plan(base, editor, disk):
    for text in (base,editor,disk):
        if not isinstance(text,str) or len(text.encode())>LIMIT:
            raise SurfboardError('Draft review supports text files up to 2 MiB',413)
        if len(text.splitlines())>20000:
            raise SurfboardError('Draft review supports at most 20,000 lines',413)
    mine,theirs=_edits(base,editor),_edits(base,disk)
    if len(mine)+len(theirs)>400:
        raise SurfboardError('Too many concurrent changes for inline review; compare the file manually',409)
    groups=[]
    for row in theirs:
        matches=[edit for edit in mine if _overlap(row,edit)]
        if matches and len(matches)==1 and row==matches[0]:
            left=_position(row['start'],mine);right=_position(row['end'],mine,True)
            if row['start']==row['end']:left-=len(row['text'])
            groups.append({'start':row['start'],'end':row['end'],'external':[row],'conflict':False,'already_applied':True})
            continue
        start=min([row['start'],*[edit['start'] for edit in matches]])
        end=max([row['end'],*[edit['end'] for edit in matches]])
        group={'start':start,'end':end,'external':[row],'conflict':bool(matches)}
        if groups and _overlap(group,groups[-1]):
            prior=groups[-1];prior['end']=max(end,prior['end']);prior['external'].append(row);prior['conflict']|=bool(matches)
        else:groups.append(group)
    chunks=[]
    for group in groups:
        start,end=group['start'],group['end'];text=base[start:end]
        for row in reversed(group['external']):text=text[:row['start']-start]+row['text']+text[row['end']-start:]
        left,right=_position(start,mine),_position(end,mine,True)
        if start==end:
            # A conflicting insertion occupies the user's inserted text.
            matching=next((row for row in mine if row['start']==row['end']==start),None)
            if matching:left-=len(matching['text'])
        before=base[start:end] if group.get('already_applied') else editor[left:right]
        chunks.append({'already_applied':bool(group.get('already_applied')),'start':len(editor[:left].encode('utf-16-le'))//2,'end':len(editor[:right].encode('utf-16-le'))//2,'before':before,'after':text,'conflict':group['conflict']})
    return {'chunks':chunks}
