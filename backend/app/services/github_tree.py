"""Commit-pinned resumable directory traversal when GitHub truncates recursive trees."""
from copy import deepcopy
from urllib.parse import quote

MAX_DIRECTORY_REQUESTS=10
MAX_MANIFEST_FILES=250_000
MAX_DIRECTORY_DEPTH=64


def manifest(client,*,base,tree_sha,previous,get_json,supported):
    state=deepcopy(previous) if previous else None
    if state is None:
        recursive=get_json(client,f'{base}/git/trees/{tree_sha}',params={'recursive':'1'})
        if not recursive.get('truncated'):
            return dict(entries=supported(recursive.get('tree')),frontier=[],complete=True,blocked=False)
        state=dict(entries=[],frontier=[dict(path='',sha=tree_sha)],complete=False,blocked=False)
    if state['complete'] or state.get('blocked'):
        return state
    entries={item['path']:item for item in state['entries']}
    frontier=list(state['frontier'])
    for _ in range(MAX_DIRECTORY_REQUESTS):
        if not frontier:
            break
        directory=frontier.pop(0)
        payload=get_json(client,f"{base}/git/trees/{quote(directory['sha'],safe='')}")
        items=payload.get('tree')
        supported(items) # Validate the provider's list shape even if no supported blobs exist.
        if payload.get('truncated'):
            state['blocked']=True # No REST pagination exists for a single truncated non-recursive tree.
        for item in items:
            if not isinstance(item,dict) or not isinstance(item.get('path'),str):
                continue
            name='/'.join(value for value in (directory['path'],item['path']) if value)
            if item.get('type')=='tree' and isinstance(item.get('sha'),str):
                if name.count('/')>=MAX_DIRECTORY_DEPTH or len(frontier)+len(entries)>=MAX_MANIFEST_FILES:
                    state['blocked']=True
                else:
                    frontier.append(dict(path=name,sha=item['sha']))
            elif item.get('type')=='blob':
                for entry in supported([{**item,'path':name}]):
                    if name not in entries and len(entries)>=MAX_MANIFEST_FILES:
                        state['blocked']=True
                        break
                    entries[name]=entry
            if len(entries)>MAX_MANIFEST_FILES:
                state['blocked']=True
                break
        if state['blocked']:
            break
    return dict(entries=sorted(entries.values(),key=lambda item:item['path']),frontier=frontier,
        complete=not frontier and not state['blocked'],blocked=state['blocked'])
