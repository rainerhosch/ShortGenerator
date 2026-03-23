import os, httpx
from dotenv import load_dotenv
load_dotenv()
key = os.environ.get('FREEPIK_API_KEY')
t = '6cb3065f-749b-43f3-bdc3-d554b954f834'
eps = [
    f'https://api.freepik.com/v1/tasks/{t}',
    f'https://api.freepik.com/v1/ai/tasks/{t}',
    f'https://api.freepik.com/v1/ai/mystic/{t}',
    f'https://api.freepik.com/v1/ai/mystic/tasks/{t}'
]
for ep in eps:
    try:
        res = httpx.get(ep, headers={'x-freepik-api-key': key, 'Accept': 'application/json'})
        print(ep, res.status_code, res.text[:200])
    except Exception as e:
        print(ep, e)
