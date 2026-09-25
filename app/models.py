from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="runner")  # admin, runner, judge
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    runner = relationship("Runner", back_populates="user", uselist=False)

class Runner(Base):
    __tablename__ = "runners"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    dni = Column(String, unique=True, index=True, nullable=False)
    birth_date = Column(Date, nullable=True)
    gender = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    emergency_contact = Column(String, nullable=True)

    user = relationship("User", back_populates="runner")
    registrations = relationship("Registration", back_populates="runner")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # Ej: "10K Juvenil", "21K Elite"
    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)
    gender_filter = Column(String, nullable=True)  # M, F, Mixto

    registrations = relationship("Registration", back_populates="category")

class Race(Base):
    __tablename__ = "races"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)  # Ej: "Maratón Mijovi 2026"
    date = Column(DateTime, nullable=False)
    location = Column(String, nullable=True)
    status = Column(String, default="upcoming")  # upcoming, ongoing, finished

    registrations = relationship("Registration", back_populates="race")

class Registration(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    runner_id = Column(Integer, ForeignKey("runners.id"), nullable=False)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    bib_number = Column(Integer, unique=True, nullable=True)  # Número de dorsal
    payment_status = Column(String, default="pending")  # pending, paid, free
    registration_date = Column(DateTime, default=datetime.utcnow)

    runner = relationship("Runner", back_populates="registrations")
    race = relationship("Race", back_populates="registrations")
    category = relationship("Category", back_populates="registrations")
    result = relationship("Result", back_populates="registration", uselist=False)

class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    registration_id = Column(Integer, ForeignKey("registrations.id"), nullable=False)
    chip_time = Column(String, nullable=True)  # Formato de tiempo o intervalo
    gun_time = Column(String, nullable=True)
    position_overall = Column(Integer, nullable=True)
    position_category = Column(Integer, nullable=True)
    status = Column(String, default="finished")  # finished, dns, dnf

    registration = relationship("Registration", back_populates="result")