import os
import json
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///tarot_bot.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    plan_type = Column(String)
    activated_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime)
    payment_status = Column(String, default='pending')

class UserMessageCount(Base):
    __tablename__ = "user_message_counts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    message_count = Column(Integer, default=0)

class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)

class TarotReading(Base):
    __tablename__ = "tarot_readings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    spread_type = Column(String)
    question = Column(Text)
    cards_drawn = Column(Text)
    interpretation = Column(Text)
    reading_date = Column(DateTime, default=datetime.now)

Base.metadata.create_all(bind=engine)

class DatabaseManager:
    def __init__(self):
        self.db = SessionLocal()
    
    def get_subscription(self, user_id):
        try:
            return self.db.query(UserSubscription).filter(
                UserSubscription.user_id == str(user_id)
            ).first()
        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            return None
    
    def update_subscription(self, user_id, plan_type, days):
        try:
            old_sub = self.get_subscription(user_id)
            if old_sub:
                self.db.delete(old_sub)
                self.db.commit()
            
            new_sub = UserSubscription(
                user_id=str(user_id),
                plan_type=plan_type,
                expires_at=datetime.now() + timedelta(days=days),
                payment_status='paid'
            )
            self.db.add(new_sub)
            self.db.commit()
            return new_sub
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            self.db.rollback()
            return None
    
    def get_message_count(self, user_id):
        try:
            count_obj = self.db.query(UserMessageCount).filter(
                UserMessageCount.user_id == str(user_id)
            ).first()
            return count_obj.message_count if count_obj else 0
        except Exception as e:
            logger.error(f"Error getting message count: {e}")
            return 0
    
    def update_message_count(self, user_id, count):
        try:
            count_obj = self.db.query(UserMessageCount).filter(
                UserMessageCount.user_id == str(user_id)
            ).first()
            
            if count_obj:
                count_obj.message_count = count
            else:
                count_obj = UserMessageCount(
                    user_id=str(user_id),
                    message_count=count
                )
                self.db.add(count_obj)
            
            self.db.commit()
            return count_obj
        except Exception as e:
            logger.error(f"Error updating message count: {e}")
            self.db.rollback()
            return None
    
    def save_conversation(self, user_id, role, content):
        try:
            history_count = self.db.query(ConversationHistory).filter(
                ConversationHistory.user_id == str(user_id)
            ).count()
            
            if history_count >= 20:
                oldest = self.db.query(ConversationHistory).filter(
                    ConversationHistory.user_id == str(user_id)
                ).order_by(ConversationHistory.timestamp.asc()).limit(history_count - 19).all()
                for msg in oldest:
                    self.db.delete(msg)
            
            conversation = ConversationHistory(
                user_id=str(user_id),
                role=role,
                content=content
            )
            self.db.add(conversation)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            self.db.rollback()
            return False
    
    def get_conversation_history(self, user_id, limit=20):
        try:
            messages = self.db.query(ConversationHistory).filter(
                ConversationHistory.user_id == str(user_id)
            ).order_by(ConversationHistory.timestamp.asc()).limit(limit).all()
            
            return [
                {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp}
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    def save_tarot_reading(self, user_id, spread_type, question, cards, interpretation):
        try:
            reading = TarotReading(
                user_id=str(user_id),
                spread_type=spread_type,
                question=question,
                cards_drawn=json.dumps(cards),
                interpretation=interpretation
            )
            self.db.add(reading)
            self.db.commit()
            return reading.id
        except Exception as e:
            logger.error(f"Error saving tarot reading: {e}")
            self.db.rollback()
            return None

db_manager = DatabaseManager()
