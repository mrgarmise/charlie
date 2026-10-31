"""Small shared host/MicroPython display-only contract. No hardware imports."""
MAX_LABEL = 24
MIN_TTL_MS = 500
MAX_TTL_MS = 10000
MIN_STEP_MS = 100
MAX_STEP_MS = 250


def normalize_label(value):
    if not isinstance(value,str):return 'OBJECT'
    value=value[:128].upper()
    text=''.join(c if ('A'<=c<='Z' or '0'<=c<='9' or c==' ') else ' ' for c in value)
    return (' '.join(text.split())[:MAX_LABEL].strip() or 'OBJECT')


def label_request(text,ttl_ms,step_ms):
    if (not isinstance(text,str) or not text or len(text)>MAX_LABEL or text!=normalize_label(text)
            or type(ttl_ms) is not int or not MIN_TTL_MS<=ttl_ms<=MAX_TTL_MS
            or type(step_ms) is not int or not MIN_STEP_MS<=step_ms<=MAX_STEP_MS):
        raise ValueError('INVALID_OBJECT_LABEL')
    return 'OBJECT_LABEL %d %d %s' % (ttl_ms,step_ms,text)


def capabilities():
    return dict(schema='charlie-display-v1',object_labels=1,width=17,height=7,
                max_label=MAX_LABEL,min_ttl_ms=MIN_TTL_MS,max_ttl_ms=MAX_TTL_MS,
                min_step_ms=MIN_STEP_MS,max_step_ms=MAX_STEP_MS)
