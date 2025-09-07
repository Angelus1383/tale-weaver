from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class Character(BaseModel):
    character_name: str = Field(..., description="the name of the character.")
    character_prompt: str = Field("", description="a very detailed and very effective prompt describing the character to generate as image.")
    character_image_path: Optional[str] = Field("", description="the file path to the image of the characater.")


class Page(BaseModel):
    scene_text: str = Field(..., description="the text of the page")
    page_number: int = Field(..., description="the number of the page")
    characters: List[str] = Field(..., description="list of character names in the scene.")
    scene_prompt: str = Field (..., description="A very detailed, vivid and very effective prompt describing the scene to generate as image.")
    scene_image_path: Optional[str] = Field("", description="The file path to the image of the scene of this page.")


class Storybook(BaseModel):
    storybook_title: str = Field(..., description="the title of the storybook")
    storybook_image_path: Optional[str] = Field("", description="The file path to the image of the storybook cover")
    storybook_prompt: str = Field (..., description="A very detailed and very effective prompt describing the book cover to generate as image.")
    characters: Dict[str, Character] = Field(..., description="Map of characters in the story represented as: character_name -> Character")
    pages: List[Page] = Field(..., description="list of pages indexed by their number")
