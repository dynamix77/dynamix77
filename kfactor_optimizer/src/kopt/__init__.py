"""
K-Factor Optimizer for Ignite Fuel Delivery System

Production-grade tool to propose weekly K-factor updates for automatic-delivery customers.
Optimizes to reduce runouts without over-servicing.
"""

__version__ = "1.0.0"
__author__ = "Fox Fuel"

from .io import load_customer_fuel, load_delivery_tickets, load_degree_days
from .propose import generate_proposals
from .report import generate_html_report

__all__ = [
    "load_customer_fuel",
    "load_delivery_tickets",
    "load_degree_days",
    "generate_proposals",
    "generate_html_report",
]
