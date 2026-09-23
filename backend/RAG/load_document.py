from langchain_core.documents import Document
import csv,re
from backend.Config.config import _base_dir
from functools import lru_cache

UNK='暂时未录入'

def _clean(s):
    bad=re.compile(r'[\ufffc\u200b\u200e\u200f]')
    return bad.sub('',(s or '').strip())


@lru_cache(maxsize=1)
def load_document():
    with open(_base_dir/'RAG'/'knowledge'/'杜诗.csv',encoding='utf-8-sig',newline='') as f:
        docs=[]
        dict_header=csv.DictReader(f)
        for idx,row in enumerate(dict_header):
            row={k:_clean(v) for k,v in row.items()}
            part=[]
            title=row['诗歌篇名']
            poem_text=row['诗文正文']
            allusion=row['典故']
            note=row['注释']
            comment=row['评点']
            if not row['诗歌篇名'] and not row['诗文正文']:
                continue
            part.append(f'【篇名】{title}')
            part.append(f'【诗正文】{poem_text}')
            if allusion:part.append(f'【典故】{allusion}')
            if note:part.append(f'【注释】{note}')
            if comment:part.append(f'【评点】{comment}')

            metadata={
                "poem_id":row['诗歌ID'] or f'BSDS{idx:04d}',
                'row': idx,
                'title': title or '(未题)',
                'genre': row['体裁'] or UNK,
                'time': row['创作时间'] or UNK,
                'place': row['创作地点'] or UNK,
                'persons': row['相关人物'] or UNK,
                'places': row['相关地点'] or UNK,
                'imagery': row['意象'] or UNK,
                'events': row['历史事件'] or UNK,
                'variant': row['异文记录'] or UNK,
                'source': row['原文出处'] or UNK,
                'annotator': row['负责人'] or UNK,
            }
            docs.append(Document(page_content='\n'.join(part), metadata=metadata))
        return docs