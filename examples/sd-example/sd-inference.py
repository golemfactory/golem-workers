import requests, time, io, base64
from PIL import Image

url = 'http://localhost:8080'
headers = {
	'Content-Type': 'application/json'
}

data = {
	"prompt": "portrait of a young women, blue eyes, cinematic",
	"steps": 10,
	"width": 512,
	"height": 512
}
for i in range(1, 11):
  start_time = time.time()
  response = requests.post(url=f'{url}/sdapi/v1/txt2img', json=data)
  try:
  	r = response.json()
  except Exception:
  	print(f"Status code: {response.status_code}, Data: {response.content}")
  	continue
  end_time = time.time()

  inference_time = (end_time - start_time)
  print(f'Inference time #{i}:', inference_time, "seconds")

  image = Image.open(io.BytesIO(base64.b64decode(r['images'][0])))
  image.save(f'output-{i}.png')
