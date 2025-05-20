import os

class Config:
    SECRET_KEY = 'dev-secret-key'  # Change this in production
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:123456@localhost/leave_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
