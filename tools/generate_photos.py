"""Generate NANE product photos with Gemini, one per menu item, in one shared style.

Usage:  GEMINI_API_KEY=... python3 tools/generate_photos.py [--only cn1,m1] [--model gemini-2.5-flash-image]
Reads prompts from photo-prompts.md, writes photos/<id>.jpg (900x900), skips files that already exist.
"""
import argparse, base64, io, json, os, re, sys, time, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(ROOT, 'photo-prompts.md')
OUT = os.path.join(ROOT, 'photos')


def load_prompts():
    text = open(PROMPTS, encoding='utf-8').read()
    # "- **name** → `photos/<id>.jpg`" followed by "  `<prompt>`"
    return re.findall(r"`photos/([a-z0-9]+)\.jpg`\s*\n\s*`([^`]+)`", text)


def generate(prompt, model, key):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    body = {'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'responseModalities': ['IMAGE'], 'imageConfig': {'aspectRatio': '1:1'}}}
    req = urllib.request.Request(url, json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    for part in data['candidates'][0]['content']['parts']:
        if 'inlineData' in part:
            return base64.b64decode(part['inlineData']['data'])
    raise RuntimeError('no image in response: ' + json.dumps(data)[:300])


def save_square(raw, path, size=900):
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    im.resize((size, size), Image.LANCZOS).save(path, 'JPEG', quality=86, optimize=True, progressive=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--model', default='gemini-2.5-flash-image')
    a = ap.parse_args()
    key = os.environ.get('GEMINI_API_KEY') or sys.exit('Set GEMINI_API_KEY first.')
    only = set(filter(None, a.only.split(',')))
    os.makedirs(OUT, exist_ok=True)
    for pid, prompt in load_prompts():
        path = os.path.join(OUT, pid + '.jpg')
        if (only and pid not in only) or (not only and os.path.exists(path)):
            continue
        for attempt in range(3):
            try:
                save_square(generate(prompt, a.model, key), path)
                print('ok', pid)
                break
            except Exception as e:  # rate limits and transient errors: back off and retry
                print('retry', pid, e)
                time.sleep(10 * (attempt + 1))
        time.sleep(2)


if __name__ == '__main__':
    main()
