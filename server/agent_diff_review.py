"""Reverse only the recorded text hunks; never apply paths from patch headers."""
import re
from .surfboards import SurfboardError

_HEADER = re.compile(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')

def hunks(change):
    if change.get('truncated') or change.get('move_path'):
        raise SurfboardError('This edit is partial or renamed; compare and edit it manually before accepting.', 409)
    answer=[];current=None;previous=None
    for line in change.get('diff','').splitlines(keepends=True):
        match=_HEADER.match(line)
        if match:
            current={'old_start':int(match[1]),'old_count':int(match[2] or 1),'new_start':int(match[3]),'new_count':int(match[4] or 1),'old':[],'new':[]};answer.append(current);previous=None
            if len(answer)>200:raise SurfboardError('Too many hunks to reject automatically',413)
        elif current and line[:1] in {' ','+','-'}:
            tag=line[0];text=line[1:]
            if tag in {' ','-'}:current['old'].append(text)
            if tag in {' ','+'}:current['new'].append(text)
            previous=tag
        elif current and line.startswith('\\ No newline at end of file') and previous:
            for side in (('old','new') if previous==' ' else ('old',) if previous=='-' else ('new',)):
                current[side][-1]=current[side][-1].rstrip('\r\n')
        elif current:
            raise SurfboardError('The recorded patch is incomplete or contains multiple files; reject it manually.',409)
        elif not line.startswith(('diff --git ','index ','--- ','+++ ','new file mode ','deleted file mode ','old mode ','new mode ')):
            raise SurfboardError('This recorded edit has no complete unified patch to undo.',409)
    if not answer or any(len(row['old'])!=row['old_count'] or len(row['new'])!=row['new_count'] for row in answer):
        raise SurfboardError('The recorded patch is incomplete; it cannot safely restore the file.',409)
    return answer

def undo(change, content):
    rows=hunks(change);kind=change.get('kind','update').lower()
    if kind in {'add','create'}:
        if len(rows)!=1 or rows[0]['old_count'] or rows[0]['old_start']!=0 or content!=''.join(rows[0]['new']):
            raise SurfboardError('The added file has newer content. Rejecting it would remove another edit.',409)
        return 'delete',None
    if kind in {'delete','remove'}:
        if content is not None or len(rows)!=1 or rows[0]['new_count'] or rows[0]['old_start']!=1:
            raise SurfboardError('The deleted file was recreated or its full contents were not recorded.',409)
        return 'save',''.join(rows[0]['old'])
    if content is None:raise SurfboardError('The edited file is missing. Restore or compare it before rejecting this edit.',409)
    result=content;locations=[]
    for row in rows:
        after=''.join(row['new']);before=''.join(row['old'])
        if not after:raise SurfboardError('This deletion has no unchanged context to locate safely. Review it manually.',409)
        positions=[];start=0
        while True:
            found=result.find(after,start)
            if found<0:break
            end=found+len(after)
            if (found==0 or result[found-1]=='\n') and (after.endswith('\n') or end==len(result)):
                positions.append((found,end))
                if len(positions)>1:break
            start=found+1
        if len(positions)!=1:raise SurfboardError('The edited lines changed or are ambiguous. Compare the current file; newer work was preserved.',409)
        begin,end=positions[0];locations.append((begin,end,before))
    locations.sort(reverse=True)
    for index,(begin,end,before) in enumerate(locations):
        if index and end>locations[index-1][0]:raise SurfboardError('Recorded hunks overlap; review this edit manually.',409)
        result=result[:begin]+before+result[end:]
    return 'save',result
