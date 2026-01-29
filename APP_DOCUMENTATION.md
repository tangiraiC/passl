# PASSL Application Documentation

## Overview
PASSL is a Zimbabwe-focused delivery marketplace connecting Shops, Riders, and Customers.

## Architecture
- **Backend**: Django REST Framework (Python)
- **Mobile App**: Flutter (Android/iOS)
- **Shop Portal**: React + Bootstrap (Web)
- **Database**: PostgreSQL (Development: SQLite)
- **Payments**: Paynow Zimbabwe

## Backend API
Base URL: `http://localhost:8000/api/v1/`

### Auth
- `POST /auth/register/`: Register a new user (Customer by default).
- `GET /auth/me/`: Get current user profile.

### Logistics
- `GET /shops/`: List all shops.
- `GET /orders/`: List orders (filtered by role).
- `POST /orders/`: Create an order.

## Mobile App
- Location 10.0.2.2 is used to access localhost from Android Emulator.
- Google Maps API Key required in `AndroidManifest.xml`.

## Shop Portal (React)
- Located in `portal/` directory.
- Uses `axios` for API requests.
- Bootstrap 5 for styling.
