from langchain_core.documents import Document
import csv,re
from backend.Config.config import settings
from functools import lru_cache

UNK=settings.UNK

def _clean(s):
    bad=re.compile(r'[\ufffc\u200b\u200e\u200f]')
    return bad.sub('',(s or '').strip())


@lru_cache(maxsize=1)
def load_document():
    with open(str(settings.knowledge_path),encoding='utf-8-sig',newline='') as f:
        docs=[]
        dict_header=csv.DictReader(f)
        for idx,row in enumerate(dict_header):
            row={k:_clean(v) for k,v in row.items()}
            part=[]
            if not row['诗歌篇名'] and not row['诗文正文']:
                continue
            for col in settings.TEXT_FIELDS:
                c=(row.get(col) or '').strip()
                if c and c not in UNK:
                    part.append(f'【{col}】 {c}')
            metadata={
                "poem_id":row['诗歌ID'] or f'BSDS{idx:04d}',
                'row': idx,
                'title': row['诗歌篇名'] or '(未题)',
                'genre': row['体裁'] or UNK[3],
                'time': row['创作时间'] or UNK[3],
                'place': row['创作地点'] or UNK[3],
                'persons': row['相关人物'] or UNK[3],
                'places': row['相关地点'] or UNK[3],
                'imagery': row['意象'] or UNK[3],
                'events': row['历史事件'] or UNK[3],
                'variant': row['异文记录'] or UNK[3],
                'edition': row['版本信息'] or UNK[3],
                'source': row['原文出处'] or UNK[3],
                'annotator': row['负责人'] or UNK[3],
            }
            docs.append(Document(page_content='\n'.join(part), metadata=metadata))
        return docs