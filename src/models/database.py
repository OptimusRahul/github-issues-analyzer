"""SQLAlchemy database models"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class Repo(Base):
    """Repository model"""
    __tablename__ = "repos"

    id = Column(String, primary_key=True)  # format: owner/repo
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    issues = relationship("Issue", back_populates="repo", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Repo(id='{self.id}', name='{self.name}')>"


class Issue(Base):
    """Issue model"""
    __tablename__ = "issues"

    id = Column(String, primary_key=True)  # format: owner/repo#number
    repo_id = Column(String, ForeignKey("repos.id"), nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    html_url = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relationship
    repo = relationship("Repo", back_populates="issues")

    def __repr__(self):
        return f"<Issue(id='{self.id}', title='{self.title}')>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id.split('#')[-1] if '#' in self.id else self.id,
            'title': self.title,
            'body': self.body,
            'html_url': self.html_url,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
        }
