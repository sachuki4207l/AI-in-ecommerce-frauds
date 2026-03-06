import requests
from PIL import Image

BASE = 'http://127.0.0.1:8000'

# helper to create simple colored image
def make_image(path, color):
    img = Image.new('RGB', (224, 224), color)
    img.save(path, 'JPEG')

# 1) create seller
s = requests.post(f'{BASE}/sellers/add', json={'name': 'AI_Seller', 'account_age_days': 50}).json()
seller_id = s['id']
print('seller', s)

# 2) create product image and upload product
make_image('prod.jpg', (200,10,10))
files = {'image': open('prod.jpg','rb')}
data = {'title': 'AIPhone', 'price': 100, 'market_price': 150, 'seller_id': seller_id}
resp = requests.post(f'{BASE}/products/add', data=data, files=files).json()
print('product created', resp)

# helper to create buyer and submit complaint with optional image
def submit_complaint(buyer_name, image_path=None, severity=3):
    b = requests.post(f'{BASE}/buyers/add', json={'name': buyer_name}).json()
    buyer_id = b['id']
    files = None
    data = {'buyer_id': buyer_id, 'seller_id': seller_id, 'complaint_text': 'Test', 'severity_level': severity}
    if image_path:
        files = {'received_image': open(image_path, 'rb')}
    r = requests.post(f'{BASE}/complaints/add', data=data, files=files)
    print('complaint response', r.status_code, r.json())
    return r.json()

print('\n=== Test 1: Identical image ===')
make_image('same.jpg', (200,10,10))
res1 = submit_complaint('BuyerSame', image_path='same.jpg', severity=2)

print('\n=== Test 2: Slightly different image ===')
make_image('slight.jpg', (180,30,30))
res2 = submit_complaint('BuyerSlight', image_path='slight.jpg', severity=2)

print('\n=== Test 3: Very different image ===')
make_image('different.jpg', (10,200,10))
res3 = submit_complaint('BuyerDiff', image_path='different.jpg', severity=2)

# print seller trust after tests
all_sellers = requests.get(f'{BASE}/sellers/all').json()
sel = [x for x in all_sellers if x['id'] == seller_id][0]
print('\nSeller after complaints:', sel)
