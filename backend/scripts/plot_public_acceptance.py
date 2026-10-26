"""Render descriptive charts from frozen public results; no providers or inferred human scores."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(directory: Path):
    modes=['bm25','vector','hybrid','rrf']
    metrics={mode:json.loads((directory/f'{mode}.metrics.json').read_text(encoding='utf-8')) for mode in modes}
    figure,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
    colors=['#809b9c','#37696a','#b3a080','#b15b78']
    values=[metrics[mode]['retrieval']['evidence_recall_at_5']*100 for mode in modes]
    bars=axes[0].bar(modes,values,color=colors,width=.6)
    axes[0].bar_label(bars,fmt='%.1f%%',padding=4)
    axes[0].set(ylim=(0,100),ylabel='Evidence Recall@5 (%)',title='16 answerable public questions')
    values=[metrics[mode]['latency_ms']['mean'] for mode in modes]
    bars=axes[1].bar(modes,values,color=colors,width=.6)
    axes[1].bar_label(bars,fmt='%.0f',padding=4)
    axes[1].set(ylim=(0,max(values)*1.2),ylabel='Online answer latency (ms)',title='20 questions per mode; one run')
    for axis in axes:
        axis.spines[['top','right']].set_visible(False)
        axis.set_axisbelow(True);axis.grid(axis='y',alpha=.2)
    figure.suptitle('Public-v2 · fixed commits · agent-authored gold · human grading pending',fontsize=12)
    for suffix in ('svg','png'):
        destination=directory/f'public-comparison.{suffix}'
        if destination.exists():
            raise FileExistsError('Do not overwrite experiment artifacts')
        figure.savefig(destination,dpi=180)
        if suffix=='svg':
            destination.write_text('\n'.join(line.rstrip() for line in destination.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    plt.close(figure)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    render(parser.parse_args().directory)
