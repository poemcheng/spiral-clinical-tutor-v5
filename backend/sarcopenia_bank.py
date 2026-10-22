"""肌少症階段一題庫：5 職種 × 5 Level × 50 題（30 自評＋20 客觀題）。

題庫內容在 data/item_banks/sarcopenia_item_bank_v1.json，屬平台依中山附醫教材與
AWGS 等指引編寫的草稿，尚待職類教師審題核定。每次登入依現行題本題數分層抽題：
自評依 DRAW_COUNTS 的 self、客觀題依 objective；同一構面內優先抽上一輪未出現的題目。
"""
import json
import random
from functools import lru_cache
from pathlib import Path

BANK_PATH = Path(__file__).resolve().parent.parent / 'data' / 'item_banks' / 'sarcopenia_item_bank_uploaded.json'
DIMS = ['CJ', 'PC', 'COM', 'TC', 'SAFE', 'HC']
SAMPLING_VERSION = 'stratified-unseen-first-v1'
MAX_OPEN_ITEMS = 1  # 每次最多 1 題需教師評閱的簡答，控制作答與評閱負擔


@lru_cache(maxsize=1)
def load_bank():
    return json.loads(BANK_PATH.read_text(encoding='utf-8'))


def has_bank(profession):
    return profession in load_bank()['professions']


def bank_version():
    return load_bank()['version']


def cell(profession, level):
    return load_bank()['professions'][profession]['levels'][str(level)]


def draw_counts(profession):
    return load_bank()['draw_counts'][profession]


def self_scale():
    return dict(load_bank()['self_scale'])


def level_meta(level):
    return load_bank()['levels'][str(level)]


def stratified_draw(pool, n, rng, avoid=(), max_open=None):
    """Spread n picks evenly across the six dimensions.

    Unseen items (not in `avoid`) come first inside each dimension, and dimensions with
    more unseen items receive the extra picks, so consecutive logins overlap as little
    as the bank size allows.
    """
    avoid = set(avoid)
    by_dim = {}
    for d in DIMS:
        items = [dict(q) for q in pool if q['dimension'] == d]
        fresh = [q for q in items if q['item_id'] not in avoid]
        stale = [q for q in items if q['item_id'] in avoid]
        rng.shuffle(fresh)
        rng.shuffle(stale)
        if fresh or stale:
            by_dim[d] = {'fresh': fresh, 'stale': stale}
    picked, open_count = [], 0
    while len(picked) < n:
        order = list(by_dim)
        rng.shuffle(order)
        order.sort(key=lambda d: -len(by_dim[d]['fresh']))
        progressed = False
        for d in order:
            if len(picked) >= n:
                break
            for bucket in ('fresh', 'stale'):
                queue = by_dim[d][bucket]
                while queue:
                    q = queue.pop(0)
                    if max_open is not None and q.get('item_type') == 'short_answer' and open_count >= max_open:
                        continue
                    picked.append(q)
                    open_count += q.get('item_type') == 'short_answer'
                    progressed = True
                    break
                else:
                    continue
                break
        if not progressed:
            break
    return picked


def draw_form(profession, level, previous=None, rng=None):
    """Return (self_items, objective_items) for one login."""
    rng = rng or random.Random()
    previous = previous or {}
    counts = draw_counts(profession)
    c = {kind:[q for q in pool if q.get('review_status') not in ('刪除','需人工確認修改')] for kind,pool in cell(profession, level).items() if isinstance(pool,list)}
    seen_self = {q['item_id'] for q in previous.get('items', [])}
    seen_obj = {q['item_id'] for q in previous.get('objectives', [])}
    items = stratified_draw(c['self'], counts['self'], rng, seen_self)
    objectives = stratified_draw(c['objective'], counts['objective'], rng, seen_obj, MAX_OPEN_ITEMS)
    for q in objectives:
        if q.get('options'):
            q['options'] = list(q['options'])
            rng.shuffle(q['options'])
    rng.shuffle(items)
    rng.shuffle(objectives)
    return items, objectives
