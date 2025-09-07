from crewai.tools import BaseTool
from google import genai
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional, Tuple, Type, Dict
from pydantic import BaseModel
from tale_weaver.model.storybook import Storybook
import io
import math
import os
import tempfile
import hashlib

from dotenv import load_dotenv
load_dotenv()

# Initialize Gemini client for image generation
try:
    gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Error initializing Gemini client: {e}. Please ensure GEMINI_API_KEY is valid.")
    gemini_client = None

def _ensure_dir(path: Optional[str]):
    if path:
        os.makedirs(path, exist_ok=True)

class IllustrationTool(BaseTool):
    name: str = "Illustration_tool"
    description: str = (
        "Create illustration for the given storybook."
    )
    args_schema: Type[BaseModel] = Storybook
    _merge_cache: Dict[str, str] = {}

    def _run(self, **data) -> Storybook:
        try:
            _ensure_dir(os.getenv("OUTPUT_DIR", None))
            storybook = Storybook(**data) if not isinstance(data, Storybook) else data
            # Iterate over characters to create single image of each one
            all_char_img_paths = []

            for name, character in storybook.characters.items():
                character.character_image_path = self._generate_image_from_prompt(prompt=character.character_prompt, 
                                                                                  image_suffix=f"_character_{name}.png")
                all_char_img_paths.append(character.character_image_path)
            
            # Iterate over pages to create image of each scene
            for page_number, page in enumerate(storybook.pages, 1):
                char_image_paths = [ storybook.characters[character].character_image_path for character in page.characters ]
                page.scene_image_path = self._generate_image_from_prompt(page.scene_prompt, 
                                                                         f'_scene_{page_number}.png', 
                                                                         char_image_paths)

            # Create cover image
            storybook.storybook_image_path = self._generate_image_from_prompt(
                prompt=storybook.storybook_prompt,
                image_suffix=f"_cover_{storybook.storybook_title}.png",
                image_paths=all_char_img_paths
            )

        except Exception as e:
            error_msg = f"An error occurs during image generation: {str(e)}"
            print(error_msg)
        return storybook
    

    def _merge_cache_key(self, image_paths: List[str]) -> str:
        # Key based on sorted names
        parts = [os.path.splitext(os.path.basename(p))[0] for p in image_paths]
        key_str = "|".join(sorted(parts))
        return hashlib.sha1(key_str.encode("utf-8")).hexdigest()

    def _generate_image_from_prompt(self, prompt: str, image_suffix: str, image_paths: Optional[List[str]] = None) -> str:
        """
        Generate an image from a text prompt using Gemini.
        
        Args:
            prompt: Text prompt for image generation
            scene_number: Scene number for naming
            
        Returns:
            str: Path to the generated image file
        """
        if not gemini_client:
            raise ValueError("Gemini client not initialized")
        
        print(f"Generating image {image_suffix}: {prompt[:50]}...")

        contents = [prompt]
        if image_paths:
            merge_path = self._get_or_create_merge(image_paths)
            contents.append(Image.open(merge_path))
        
        response = gemini_client.models.generate_content(
            model=os.getenv("GEMINI_IMAGE_MODEL"),
            contents=contents,
            config=GenerateContentConfig(
                    response_modalities=[Modality.IMAGE]#, Modality.TEXT]
                )
        )
        
        # Extract image from response
        image_part = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_part = part
                break
            
        if not image_part:
            raise ValueError("No image generated in response")
        
        # Process and save image
        img_data = image_part.inline_data.data
        image = Image.open(io.BytesIO(img_data))
        
        # Convert image format if needed
        if image.mode in ('P', 'PA'):
            image = image.convert('RGB')
        elif image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
            
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=image_suffix, dir=os.getenv("OUTPUT_DIR", None))
        image.save(temp_file.name, 'PNG')
        temp_file.close()
        
        print(f"Image {image_suffix} saved to: {temp_file.name}")
        return temp_file.name    

    def _get_or_create_merge(self, image_paths: List[str]) -> str:
        """
        Returns the character merge path if exists otherwise creates it and updates cache.
        """
        cache_key = self._merge_cache_key(image_paths)

        # Reuse if exist
        cached_path = self._merge_cache.get(cache_key)
        if cached_path and os.path.exists(cached_path):
            return cached_path

        # Create otherwise
        self._merge_cache[cache_key] = self._build_labeled_merge(
            image_paths=image_paths,
            image_suffix=f"merge_{cache_key}.png"
        )
        return self._merge_cache.get(cache_key)

    def _build_labeled_merge(
        self,
        image_paths: List[str],
        image_suffix: str,
        thumb_size: Tuple[int, int] = (420, 420),
        font_size: int = 80,                
        cols: Optional[int] = None,
        bg_color=(255, 255, 255),
        text_color=(0, 0, 0),
        padding: int = 30,
        cell_padding: int = 15,
    ):
        """
        Create a single labeled montage from a variable number of images.

        Each input image is placed in a grid cell with an uppercase label (the filename
        without extension) drawn ABOVE the image. The label uses a fixed `font_size`
        (no auto-shrinking). To ensure the label fits, the cell width is expanded to the
        longest label; images are letterboxed to `thumb_size` while preserving aspect ratio.

        Args:
            image_paths: Paths to input images (must be non-empty).
            image_suffix: Suffix of the image to save.
            thumb_size: Max (width, height) of the image area inside each cell.
            font_size: Fixed label font size (pixels) used for ALL labels.
            cols: Number of grid columns; if None, uses ceil(sqrt(n_images)).
            bg_color: Canvas background color as (R, G, B).
            text_color: Label text color as (R, G, B).
            padding: Outer padding around the entire montage (pixels).
            cell_padding: Inner padding within each cell (around label and image).

        Returns:
            str: The path of the composed image.

        Raises:
            ValueError: If `image_paths` is empty.
        """
        if not image_paths:
            raise ValueError("image_paths must contain at least one path")

        # Load a fixed font
        def load_font(size: int):
            for name in ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf",
                         "Arial.ttf", "Helvetica.ttf", "LiberationSans-Bold.ttf"]:
                try:
                    return ImageFont.truetype(name, size=size)
                except Exception:
                    pass
            return ImageFont.load_default()

        font = load_font(font_size)
        titles = [os.path.splitext(os.path.basename(p).split("_")[-1])[0].upper() for p in image_paths]

        tmp = Image.new("RGB", (10, 10))
        dtmp = ImageDraw.Draw(tmp)
        max_label_w = max(dtmp.textbbox((0, 0), t, font=font)[2] for t in titles)
        label_h = dtmp.textbbox((0, 0), "Hg", font=font)[3]
        label_height = label_h + 10

        cell_w = max(thumb_size[0] + 2 * cell_padding, max_label_w + 2 * cell_padding)
        cell_h = label_height + thumb_size[1] + 2 * cell_padding

        n = len(image_paths)
        cols = cols or max(1, math.ceil(math.sqrt(n)))
        rows = math.ceil(n / cols)

        out_w = padding * 2 + cell_w * cols
        out_h = padding * 2 + cell_h * rows

        canvas = Image.new("RGB", (out_w, out_h), bg_color)
        draw = ImageDraw.Draw(canvas)

        for i, (p, title) in enumerate(zip(image_paths, titles)):
            img = Image.open(p).convert("RGB")

            iw, ih = img.size
            scale = min(thumb_size[0] / iw, thumb_size[1] / ih)
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)

            r, c = divmod(i, cols)
            x0 = padding + c * cell_w
            y0 = padding + r * cell_h

            tw, th = draw.textbbox((0, 0), title, font=font)[2:]
            tx = x0 + (cell_w - tw) // 2
            ty = y0 + cell_padding + (label_height - th) // 2
            draw.text((tx, ty), title, fill=text_color, font=font)

            ix = x0 + (cell_w - nw) // 2
            iy = y0 + label_height + (cell_h - label_height - nh) // 2
            canvas.paste(img, (ix, iy))

        # Output 724x1024 letterboxed
        target_w, target_h = 724, 1024
        scale = min(target_w / out_w, target_h / out_h)
        new_w = max(1, int(round(out_w * scale)))
        new_h = max(1, int(round(out_h * scale)))
        resized = canvas.resize((new_w, new_h), Image.Resampling.LANCZOS)

        final_canvas = Image.new("RGB", (target_w, target_h), bg_color)
        offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
        final_canvas.paste(resized, offset)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=image_suffix, dir=os.getenv("OUTPUT_DIR", None))
        final_canvas.save(temp_file.name, "PNG")
        return temp_file.name