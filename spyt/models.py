"""Domain models for Spotify tracks, playlists, artists, and match results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Track:
    """A single song from Spotify (title, artists, album, duration)."""

    title: str
    artists: list[str]
    album: str = ""
    duration_ms: int = 0
    spotify_id: str = ""

    @property
    def artist_str(self) -> str:
        """Comma-separated primary artist string for search queries."""
        return ", ".join(self.artists)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict for ``backup.json``."""
        return asdict(self)


@dataclass
class Artist:
    """A Spotify artist the user follows."""

    name: str
    spotify_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Playlist:
    """A Spotify playlist with embedded track list."""

    name: str
    description: str = ""
    tracks: list[Track] = field(default_factory=list)
    spotify_id: str = ""
    is_liked_songs: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "spotify_id": self.spotify_id,
            "is_liked_songs": self.is_liked_songs,
            "tracks": [t.to_dict() for t in self.tracks],
        }


@dataclass
class MatchResult:
    """Outcome of matching one Spotify track to YouTube Music."""

    track: Track
    video_id: str | None
    matched_title: str = ""
    score: int = 0

    def to_dict(self) -> dict:
        return {
            "track": self.track.to_dict(),
            "video_id": self.video_id,
            "matched_title": self.matched_title,
            "score": self.score,
        }


@dataclass
class ArtistMatchResult:
    """Outcome of matching one Spotify artist to a YouTube channel."""

    artist: Artist
    channel_id: str | None
    matched_name: str = ""
    score: int = 0

    def to_dict(self) -> dict:
        return {
            "artist": self.artist.to_dict(),
            "channel_id": self.channel_id,
            "matched_name": self.matched_name,
            "score": self.score,
        }
