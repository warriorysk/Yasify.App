
import asyncio
from random import randint
from PIL import Image
import requests
from dotenv import get_key
import os
from time import sleep
import base64
import json

API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": f"Bearer {get_key('.env', 'HuggingFaceAPIKey')}"}

if not os.path.exists("Data"):
    os.makedirs("Data")

async def query(payload):
    try:
        response = await asyncio.to_thread(requests.post, API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error querying API: {e}")
        return None

async def generate_image_single(prompt: str, idx: int):
    seed = randint(0, 1000000)
    payload = {
        "inputs": f"{prompt}, quality=4k, sharpness=maximum, Ultra High details, high resolution, seed={seed}"
    }
    response_content = await query(payload)
    print(type(response_content), response_content[:50])
    if response_content:
        try:
            response_json = json.loads(response_content)
            if "images" in response_json:
                image_base64 = response_json["images"][0]
                image_bytes = base64.b64decode(image_base64)
                file_name = f"Data/{prompt.replace(' ', '_')}{idx}.jpg"
                with open(file_name, "wb") as f:
                    f.write(image_bytes)
                return file_name
                
            else:
                print(f"Unexpected API response format: {response_json}")
        except Exception as e:
            print(f"Error saving image {idx}: {e}")
    return None

async def generate_images_and_return_paths(prompt: str):
    tasks = [generate_image_single(prompt, i + 1) for i in range(4)]
    paths = await asyncio.gather(*tasks)
    return [p for p in paths if p]

def image_to_base64(path):
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")