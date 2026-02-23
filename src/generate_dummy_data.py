import os
from PIL import Image
import numpy as np

# Config
base_dir = "../data"
categories = ["Healthy", "Rust", "Blight", "Spot", "Rot"] # 5 Classes to match model config
splits = ["train", "val"]
img_size = (128, 128)
num_images_per_class = 20 # Increased count for better training stability

from PIL import ImageDraw

def create_pattern_image(category, index):
    # Create valid RGB image
    img = Image.new('RGB', img_size, color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    if category == "Healthy":
        # Green background/fill
        img = Image.new('RGB', img_size, color=(34, 139, 34))
    
    elif category == "Rust":
        # Yellow/Orange/Red dots
        img = Image.new('RGB', img_size, color=(34, 139, 34))
        draw = ImageDraw.Draw(img)
        for _ in range(20):
            x = np.random.randint(0, img_size[0])
            y = np.random.randint(0, img_size[1])
            r = np.random.randint(2, 6)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(165, 42, 42))

    elif category == "Blight":
        # Large brown patches
        img = Image.new('RGB', img_size, color=(34, 139, 34))
        draw = ImageDraw.Draw(img)
        for _ in range(3):
            x = np.random.randint(0, img_size[0])
            y = np.random.randint(0, img_size[1])
            r = np.random.randint(10, 30)
            draw.rectangle((x-r, y-r, x+r, y+r), fill=(139, 69, 19))

    elif category == "Spot":
        # Small black spots with yellow halos
        img = Image.new('RGB', img_size, color=(50, 205, 50))
        draw = ImageDraw.Draw(img)
        for _ in range(15):
            x = np.random.randint(0, img_size[0])
            y = np.random.randint(0, img_size[1])
            r = np.random.randint(3, 8)
            draw.ellipse((x-r-1, y-r-1, x+r+1, y+r+1), fill=(255, 255, 0)) # Halo
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(0, 0, 0)) # Spot

    elif category == "Rot":
        # Grayscale/Dark mess
        img = Image.new('RGB', img_size, color=(100, 100, 100))
        draw = ImageDraw.Draw(img)
        for _ in range(10):
            x = np.random.randint(0, img_size[0])
            y = np.random.randint(0, img_size[1])
            draw.line((x, y, x+20, y+20), fill=(0,0,0), width=3)

    return img

print(f"Generating data for classes: {categories}")

for split in splits:
    for category in categories:
        folder = os.path.join(base_dir, split, category)
        os.makedirs(folder, exist_ok=True)
        
        # Clean existing files to avoid mixing
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))

        for i in range(num_images_per_class):
            img = create_pattern_image(category, i)
            img.save(os.path.join(folder, f"{category}_{i}.jpg"))

print("✅ Enhanced dummy dataset created at '../data'")
