# PASSL - Zimbabwe Delivery Marketplace

PASSL is a comprehensive delivery platform connecting Customers, Shops, and Riders in Zimbabwe. It features a Django backend, Flutter mobile app (Android/iOS), and a React-based Shop Portal.

## 🚀 Tech Stack

- **Backend**: Django & Django REST Framework (Python)
- **Mobile App**: Flutter (Dart) - *Customer & Rider Apps in one codebase*
- **Shop Portal**: React + Bootstrap (Vite)
- **Database**: PostgreSQL (Development: SQLite)
- **Payments**: Paynow Zimbabwe (EcoCash, OneMoney, Visa/Mastercard)
- **Maps**: Google Maps Platform

## 📂 Project Structure

- `backend/` - Django API server.
- `mobile/` - Flutter application for Customers and Riders.
- `portal/` - React web dashboard for Shop Owners.

## 🛠️ Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Flutter SDK 3.9+
- Postgres (Optional, uses SQLite by default)

### 1. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # You may need to generate this first
python manage.py migrate
python manage.py runserver
# API available at http://localhost:8000
```

### 2. Shop Portal Setup
```bash
cd portal
npm install
npm run dev
# Dashboard at http://localhost:5173
```

### 3. Mobile App Setup
```bash
cd mobile
flutter pub get
# Edit android/app/src/main/AndroidManifest.xml to add your Google Maps Key
flutter run
```

## 📖 Documentation

For detailed architecture and API endpoints, see [APP_DOCUMENTATION.md](./APP_DOCUMENTATION.md) included in this repo.

## 🇿🇼 Local Context

Designed for the Zimbabwean market:
- **Phone Auth**: Primary identity (Zim +263 numbers).
- **Landmark Addressing**: Support for descriptive addresses.
- **Paynow Integration**: Seamless local payments.

---
*Created by [Your Name/Team]*
