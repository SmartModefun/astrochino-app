from PIL import Image, ImageDraw, ImageFont
import os

SIZE = 1024
OUT = "resources/icon.png"

os.makedirs("resources/ios", exist_ok=True)
os.makedirs("resources/android", exist_ok=True)

img = Image.new("RGBA", (SIZE, SIZE), (13, 3, 3, 255))
draw = ImageDraw.Draw(img)

# Red circle background
draw.ellipse([100, 100, 924, 924], fill=(198, 40, 40, 255))

# Gold border
for r in range(412, 462):
    draw.ellipse([SIZE//2-r, SIZE//2-r, SIZE//2+r, SIZE//2+r], outline=(212, 160, 23, 255), width=2)

# Inner gold circle
draw.ellipse([250, 250, 774, 774], fill=(13, 3, 3, 255))
draw.ellipse([250, 250, 774, 774], outline=(212, 160, 23, 180), width=4)

# Chinese character 马 (horse) in center
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 280)
except:
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", 280)
    except:
        font = ImageFont.load_default()

# Draw 马
bbox = draw.textbbox((0, 0), "马", font=font)
tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
tx = (SIZE - tw) // 2 - bbox[0]
ty = (SIZE - th) // 2 - bbox[1] - 20
draw.text((tx, ty), "马", fill=(212, 160, 23, 255), font=font)

# Save main icon
img.save(OUT)
print(f"Icon saved: {OUT}")

# iOS sizes
ios_sizes = {
    "icon-20@2x.png": 40, "icon-20@3x.png": 60,
    "icon-29@2x.png": 58, "icon-29@3x.png": 87,
    "icon-40@2x.png": 80, "icon-40@3x.png": 120,
    "icon-60@2x.png": 120, "icon-60@3x.png": 180,
    "icon-76.png": 76, "icon-76@2x.png": 152,
    "icon-83.5@2x.png": 167,
    "icon-1024.png": 1024,
}
for name, sz in ios_sizes.items():
    resized = img.resize((sz, sz), Image.LANCZOS)
    resized.save(f"resources/ios/{name}")

# Android sizes
android_sizes = {
    "mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192,
}
for folder, sz in android_sizes.items():
    os.makedirs(f"resources/android/{folder}", exist_ok=True)
    resized = img.resize((sz, sz), Image.LANCZOS)
    resized.save(f"resources/android/{folder}/icon.png")

# App Store icon copy
img.save("resources/AppStoreIcon.png")
print("All icons generated!")
