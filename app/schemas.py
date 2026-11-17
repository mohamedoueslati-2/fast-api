"""Mod?les des requ?tes de l?API."""

from typing import Literal

from pydantic import BaseModel, Field


class ClipInterval(BaseModel):
    start: str
    end: str


class ClipRequest(BaseModel):
    clips: list[ClipInterval] = Field(min_length=1)


class AudioRequest(BaseModel):
    format: Literal["mp3", "wav"]
