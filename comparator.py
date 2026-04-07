import io
import base64
from PIL import Image, ImageOps
# --- CHANGE: Import the PIL-specific version ---
from pixelmatch.contrib.PIL import pixelmatch


class ImageComparator:
    @staticmethod
    def compare(figma_stream, app_stream):
        try:
            # 1. Load images and fix orientation
            img_figma = Image.open(figma_stream)
            img_app = Image.open(app_stream)

            # --- ADDED: LIMIT IMAGE SIZE TO SAVE MEMORY ---
            MAX_SIZE = 1500  # Pixels
            if img_figma.width > MAX_SIZE or img_figma.height > MAX_SIZE:
                img_figma.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            if img_app.width > MAX_SIZE or img_app.height > MAX_SIZE:
                img_app.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            # ----------------------------------------------

            img_figma = ImageOps.exif_transpose(img_figma).convert('RGBA')
            img_app = ImageOps.exif_transpose(img_app).convert('RGBA')

            # 2. Get sizes
            f_w, f_h = img_figma.size
            a_w, a_h = img_app.size

            # 3. Categorize error
            if f_w != a_w or f_h != a_h:
                error_category = "Dimension/Scaling Mismatch"
            else:
                error_category = "UI Alignment/Style Issue"

            # 4. Standardize dimensions
            width = max(f_w, a_w)
            height = max(f_h, a_h)

            canvas_figma = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            canvas_app = Image.new('RGBA', (width, height), (0, 0, 0, 0))

            canvas_figma.paste(img_figma, (0, 0))
            canvas_app.paste(img_app, (0, 0))

            # 5. Prepare Diff image
            img_diff = Image.new('RGBA', (width, height))

            # --- CHANGE: This PIL version doesn't need width/height arguments! ---
            mismatch_pixels = pixelmatch(
                canvas_figma,
                canvas_app,
                img_diff,
                threshold=0.1,
                includeAA=True
            )

            # 6. Metrics
            total_pixels = width * height
            error_percentage = round((mismatch_pixels / total_pixels) * 100, 2)

            # 7. Base64 Conversion
            buffered = io.BytesIO()
            img_diff.save(buffered, format="PNG")
            diff_base64 = base64.b64encode(buffered.getvalue()).decode()

            return {
                "figma_size": f"{f_w}x{f_h}px",
                "app_size": f"{a_w}x{a_h}px",
                "mismatch_count": mismatch_pixels,
                "error_percent": f"{error_percentage}%",
                "category": error_category,
                "diff_url": f"data:image/png;base64,{diff_base64}"
            }
        except Exception as e:
            print(f"Internal Logic Error: {e}")
            raise e