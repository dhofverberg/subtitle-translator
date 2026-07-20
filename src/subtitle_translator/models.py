"""Domain models used by Subtitle Translator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta


@dataclass(slots=True)
class Subtitle:
    """Represents a single subtitle."""

    index: int
    start: timedelta
    end: timedelta
    text: str

    @property
    def duration(self) -> timedelta:
        """Duration of the subtitle."""
        return self.end - self.start

    @property
    def character_count(self) -> int:
        """Number of characters."""
        return len(self.text)

    @property
    def line_count(self) -> int:
        """Number of text lines."""
        return len(self.text.splitlines())


@dataclass(slots=True)
class SubtitleFile:
    """Represents an entire subtitle file."""

    subtitles: list[Subtitle] = field(default_factory=list)

    @property
    def subtitle_count(self) -> int:
        return len(self.subtitles)
    
    @property
    def first_subtitle(self) -> Subtitle | None:
        if not self.subtitles:
            return None

        return self.subtitles[0]


    @property
    def last_subtitle(self) -> Subtitle | None:
        if not self.subtitles:
            return None

        return self.subtitles[-1]

    @property
    def character_count(self) -> int:
        return sum(s.character_count for s in self.subtitles)

    @property
    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.subtitles)
    
    @property
    def duration(self) -> timedelta:
        if not self.subtitles:
            return timedelta()

        return self.subtitles[-1].end - self.subtitles[0].start