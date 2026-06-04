from pydantic import BaseModel, computed_field
from typing import Optional

class VideoData(BaseModel):
  video_id: str
  platform: str
  title: Optional[str] = "Untitled"
  creator: Optional[str] = "Unknown"
  followers: Optional[int] = 0
  views: Optional[int] = 0
  likes: Optional[int] = 0
  comments: Optional[int] = 0
  duration: Optional[int] = 0
  upload_date: Optional[str] = ""
  transcript: str
  
  @computed_field
  def engagement_rate(self) -> float:
    if self.views and self.views > 0:
      total_engagement = (self.likes or 0) + (self.comments or 0)
      return round((total_engagement/self.views)*100,2)
    return 0.0
